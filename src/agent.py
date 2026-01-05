"""
Proto Semantic Review Agent.

An agent that reviews Protocol Buffer definitions for semantic
correctness against Google AIP standards and event messaging best practices.

Supports multiple LLM providers: Gemini, OpenAI, and Anthropic.
"""

import json
from typing import Optional

from .adapters import create_adapter, ToolDeclaration
from .adapters.base import Message, Role, ToolCall
from .tool_definitions import TOOL_DECLARATIONS
from .tools import TOOL_FUNCTIONS
from .prompts import SYSTEM_PROMPT, EVENT_SYSTEM_PROMPT


def _execute_tool(tool_call: ToolCall) -> str:
    """Execute a tool and return the result."""
    func = TOOL_FUNCTIONS.get(tool_call.name)
    if func:
        try:
            return str(func(**tool_call.arguments))
        except Exception as e:
            return f"Error executing {tool_call.name}: {e}"
    return f"Unknown tool: {tool_call.name}"


def _create_review_prompt(proto_content: str, focus: str) -> str:
    """Create the review prompt based on focus area."""
    if focus == "event":
        return f"""Please review the following Protocol Buffer definition for semantic issues.

This proto defines EVENT MESSAGES (not REST resources). Focus on:
1. Event identification (event_id, idempotency patterns)
2. Timestamp fields (event_time, created_at patterns) - should use google.protobuf.Timestamp
3. Correlation/tracing (correlation_id, trace_id, span_id)
4. Event versioning (event_version, schema_version)
5. Enum safety for schema evolution (UNSPECIFIED = 0)
6. Nullable fields with wrapper types or optional keyword
7. Type appropriateness for event payloads

Here is the proto file:

```protobuf
{proto_content}
```

Analyze this proto and provide your findings. Use your tools to look up specific guidance as needed."""
    else:
        # REST-focused prompt
        return f"""Please review the following Protocol Buffer definition for semantic issues.

Focus on:
1. Type appropriateness (should string be Timestamp? should double be Money?)
2. Well-known type usage
3. Standard method patterns (Get, List, Create, Update, Delete)
4. Resource design patterns
5. Consistency issues
6. Common anti-patterns

Here is the proto file:

```protobuf
{proto_content}
```

Please analyze this proto and provide your findings. Use your tools to look up specific AIP guidance as needed."""


def review_proto(
    proto_content: str,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    focus: str = "event",
) -> str:
    """
    Review a proto file for semantic issues.

    Args:
        proto_content: The content of the .proto file to review
        provider: Model provider (gemini, openai, anthropic) or None for auto-detect
        model_name: Specific model name to use (uses provider default if None)
        focus: Review focus - "event" for event messages, "rest" for REST APIs

    Returns:
        The review results as a string
    """
    adapter = create_adapter(provider=provider, model_name=model_name)
    system_prompt = EVENT_SYSTEM_PROMPT if focus == "event" else SYSTEM_PROMPT

    user_message = _create_review_prompt(proto_content, focus)
    messages: list[Message] = [Message(role=Role.USER, content=user_message)]

    max_iterations = 10
    for _ in range(max_iterations):
        text, tool_calls = adapter.generate(
            messages=messages,
            tools=TOOL_DECLARATIONS,
            system_prompt=system_prompt,
        )

        if not tool_calls:
            return text or "No issues found."

        # Add assistant's response with tool calls
        messages.append(Message(
            role=Role.ASSISTANT,
            content=text or "",
            tool_calls=tool_calls,
        ))

        # Execute tools and add results
        for tc in tool_calls:
            result = _execute_tool(tc)
            messages.append(Message(
                role=Role.TOOL,
                content=result,
                tool_call_id=tc.id,
            ))

    return "Error: Maximum iterations reached without completing review"


def review_proto_structured(
    proto_content: str,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    focus: str = "event",
) -> dict:
    """
    Review a proto file and return structured results.

    Args:
        proto_content: The content of the .proto file to review
        provider: Model provider (gemini, openai, anthropic) or None for auto-detect
        model_name: Specific model name to use
        focus: Review focus - "event" for event messages, "rest" for REST APIs

    Returns:
        Dictionary with structured review results:
        {
            "issues": [...],
            "summary": "...",
            "error": "..." (optional)
        }
    """
    adapter = create_adapter(provider=provider, model_name=model_name)
    system_prompt = EVENT_SYSTEM_PROMPT if focus == "event" else SYSTEM_PROMPT

    # Modified prompt for structured output
    base_prompt = _create_review_prompt(proto_content, focus)
    structured_prompt = f"""{base_prompt}

After your analysis, provide your final response as a JSON object with this exact structure:
{{
  "issues": [
    {{
      "severity": "error|warning|suggestion",
      "location": "MessageName.field_name or MethodName",
      "issue": "Description of the problem",
      "recommendation": "How to fix it",
      "reference": "AIP-XXX or ORG-XXX or null"
    }}
  ],
  "summary": "Brief summary of findings"
}}

Use your tools to look up specific guidance as needed, then provide the structured JSON response."""

    messages: list[Message] = [Message(role=Role.USER, content=structured_prompt)]

    max_iterations = 10
    for _ in range(max_iterations):
        text, tool_calls = adapter.generate(
            messages=messages,
            tools=TOOL_DECLARATIONS,
            system_prompt=system_prompt,
        )

        if not tool_calls:
            # Try to parse JSON from response
            return _parse_structured_response(text or "")

        # Add assistant's response with tool calls
        messages.append(Message(
            role=Role.ASSISTANT,
            content=text or "",
            tool_calls=tool_calls,
        ))

        # Execute tools and add results
        for tc in tool_calls:
            result = _execute_tool(tc)
            messages.append(Message(
                role=Role.TOOL,
                content=result,
                tool_call_id=tc.id,
            ))

    return {"error": "Maximum iterations reached", "issues": [], "summary": ""}


def _parse_structured_response(full_text: str) -> dict:
    """Parse JSON from the model's text response."""
    try:
        # Look for JSON block in markdown
        if "```json" in full_text:
            json_start = full_text.index("```json") + 7
            json_end = full_text.index("```", json_start)
            json_str = full_text[json_start:json_end].strip()
        elif "```" in full_text and "{" in full_text:
            # Try to find JSON in any code block
            start = full_text.index("```") + 3
            # Skip language identifier if present
            newline = full_text.index("\n", start)
            end = full_text.index("```", newline)
            json_str = full_text[newline:end].strip()
        elif "{" in full_text:
            # Find the JSON object directly
            start = full_text.index("{")
            # Find matching closing brace
            depth = 0
            end = start
            for i, c in enumerate(full_text[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            json_str = full_text[start:end]
        else:
            return {
                "error": "Could not find JSON in response",
                "raw_response": full_text,
                "issues": [],
                "summary": "",
            }

        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "error": f"Could not parse JSON: {e}",
            "raw_response": full_text,
            "issues": [],
            "summary": "",
        }
