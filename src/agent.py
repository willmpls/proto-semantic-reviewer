"""
Proto Semantic Review Agent.

An agent that reviews Protocol Buffer definitions for semantic
correctness against Google AIP standards and event messaging best practices.

Supports multiple LLM providers: Gemini, OpenAI, and Anthropic.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Any, Union, Dict, List

from .adapters import create_adapter, ToolDeclaration
from .adapters.base import Message, Role, ToolCall
from .tool_definitions import TOOL_DECLARATIONS
from .tools import TOOL_FUNCTIONS
from .prompts import SYSTEM_PROMPT, EVENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_MAX_INPUT_SIZE = 100 * 1024  # 100KB


@dataclass
class ReviewContext:
    """Encapsulates the context for a proto review request."""
    provider: Optional[str] = None
    model_name: Optional[str] = None
    focus: str = "event"
    max_iterations: int = field(default_factory=lambda: int(
        os.environ.get("MAX_ITERATIONS", DEFAULT_MAX_ITERATIONS)
    ))
    max_input_size: int = field(default_factory=lambda: int(
        os.environ.get("MAX_INPUT_SIZE", DEFAULT_MAX_INPUT_SIZE)
    ))


@dataclass
class ReviewResult:
    """Result of a proto review including adapter metadata."""
    content: str | dict
    provider_name: str
    model_name: str
    iterations_used: int = 0

    @property
    def is_structured(self) -> bool:
        return isinstance(self.content, dict)


def _execute_tool(tool_call: ToolCall) -> str:
    """Execute a tool and return the result."""
    func = TOOL_FUNCTIONS.get(tool_call.name)
    if func:
        try:
            logger.debug(f"Executing tool: {tool_call.name} with args: {tool_call.arguments}")
            result = str(func(**tool_call.arguments))
            logger.debug(f"Tool {tool_call.name} returned {len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_call.name}: {e}", exc_info=True)
            return f"Error executing {tool_call.name}: {e}"
    logger.warning(f"Unknown tool requested: {tool_call.name}")
    return f"Unknown tool: {tool_call.name}"


def _validate_input(proto_content: str, max_size: int, validate_syntax: bool = True) -> None:
    """Validate proto content before review.

    Args:
        proto_content: The proto file content
        max_size: Maximum allowed size in bytes
        validate_syntax: Whether to validate proto syntax (default True)

    Raises:
        ValueError: If content is empty, exceeds size limit, or has syntax errors
    """
    if not proto_content or not proto_content.strip():
        raise ValueError("Proto content cannot be empty")

    content_size = len(proto_content.encode('utf-8'))
    if content_size > max_size:
        raise ValueError(
            f"Proto content size ({content_size} bytes) exceeds maximum "
            f"allowed size ({max_size} bytes)"
        )

    # Optionally validate proto syntax
    if validate_syntax:
        try:
            from .validation import validate_proto_syntax
            result = validate_proto_syntax(proto_content)
            if not result.is_valid:
                raise ValueError(f"Proto syntax error: {result.error_message}")
            if result.warnings:
                for warning in result.warnings:
                    logger.warning(f"Proto validation warning: {warning}")
        except ImportError:
            # grpcio-tools not installed, skip validation
            logger.debug("Proto syntax validation skipped (grpcio-tools not installed)")


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
    context: Optional[ReviewContext] = None,
) -> ReviewResult:
    """
    Review a proto file for semantic issues.

    Args:
        proto_content: The content of the .proto file to review
        provider: Model provider (gemini, openai, anthropic) or None for auto-detect
        model_name: Specific model name to use (uses provider default if None)
        focus: Review focus - "event" for event messages, "rest" for REST APIs
        context: Optional ReviewContext with additional configuration

    Returns:
        ReviewResult with the review text and adapter metadata
    """
    # Use context if provided, otherwise create from parameters
    if context is None:
        context = ReviewContext(provider=provider, model_name=model_name, focus=focus)

    # Validate input
    _validate_input(proto_content, context.max_input_size)

    logger.info(f"Starting proto review with provider={context.provider}, focus={context.focus}")

    adapter = create_adapter(provider=context.provider, model_name=context.model_name)
    system_prompt = EVENT_SYSTEM_PROMPT if context.focus == "event" else SYSTEM_PROMPT

    user_message = _create_review_prompt(proto_content, context.focus)
    messages: list[Message] = [Message(role=Role.USER, content=user_message)]

    iterations_used = 0
    for iteration in range(context.max_iterations):
        iterations_used = iteration + 1
        logger.debug(f"Agent iteration {iterations_used}/{context.max_iterations}")

        text, tool_calls = adapter.generate(
            messages=messages,
            tools=TOOL_DECLARATIONS,
            system_prompt=system_prompt,
        )

        if not tool_calls:
            logger.info(f"Review completed in {iterations_used} iterations")
            return ReviewResult(
                content=text or "No issues found.",
                provider_name=adapter.provider_name,
                model_name=adapter.model_name,
                iterations_used=iterations_used,
            )

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

    logger.warning(f"Maximum iterations ({context.max_iterations}) reached")
    return ReviewResult(
        content="Error: Maximum iterations reached without completing review",
        provider_name=adapter.provider_name,
        model_name=adapter.model_name,
        iterations_used=iterations_used,
    )


def review_proto_structured(
    proto_content: str,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    focus: str = "event",
    context: Optional[ReviewContext] = None,
) -> ReviewResult:
    """
    Review a proto file and return structured results.

    Args:
        proto_content: The content of the .proto file to review
        provider: Model provider (gemini, openai, anthropic) or None for auto-detect
        model_name: Specific model name to use
        focus: Review focus - "event" for event messages, "rest" for REST APIs
        context: Optional ReviewContext with additional configuration

    Returns:
        ReviewResult with structured dict content:
        {
            "issues": [...],
            "summary": "...",
            "error": "..." (optional)
        }
    """
    # Use context if provided, otherwise create from parameters
    if context is None:
        context = ReviewContext(provider=provider, model_name=model_name, focus=focus)

    # Validate input
    _validate_input(proto_content, context.max_input_size)

    logger.info(f"Starting structured proto review with provider={context.provider}, focus={context.focus}")

    adapter = create_adapter(provider=context.provider, model_name=context.model_name)
    system_prompt = EVENT_SYSTEM_PROMPT if context.focus == "event" else SYSTEM_PROMPT

    # Modified prompt for structured output
    base_prompt = _create_review_prompt(proto_content, context.focus)
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

    iterations_used = 0
    for iteration in range(context.max_iterations):
        iterations_used = iteration + 1
        logger.debug(f"Structured review iteration {iterations_used}/{context.max_iterations}")

        text, tool_calls = adapter.generate(
            messages=messages,
            tools=TOOL_DECLARATIONS,
            system_prompt=system_prompt,
        )

        if not tool_calls:
            # Try to parse JSON from response
            logger.info(f"Structured review completed in {iterations_used} iterations")
            parsed = _parse_structured_response(text or "")
            return ReviewResult(
                content=parsed,
                provider_name=adapter.provider_name,
                model_name=adapter.model_name,
                iterations_used=iterations_used,
            )

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

    logger.warning(f"Maximum iterations ({context.max_iterations}) reached for structured review")
    return ReviewResult(
        content={"error": "Maximum iterations reached", "issues": [], "summary": ""},
        provider_name=adapter.provider_name,
        model_name=adapter.model_name,
        iterations_used=iterations_used,
    )


def _parse_structured_response(full_text: str) -> dict:
    """Parse JSON from the model's text response.

    Uses multiple strategies to extract JSON:
    1. Look for ```json code blocks
    2. Look for any ``` code blocks containing JSON
    3. Use regex to find JSON object pattern
    4. Fall back to brace matching
    """
    if not full_text:
        logger.warning("Empty response received for structured parsing")
        return {
            "error": "Empty response",
            "issues": [],
            "summary": "",
        }

    json_str = None

    # Strategy 1: Look for ```json code block
    json_block_match = re.search(r'```json\s*\n?(.*?)\n?```', full_text, re.DOTALL)
    if json_block_match:
        json_str = json_block_match.group(1).strip()
        logger.debug("Found JSON in ```json code block")

    # Strategy 2: Look for any code block that starts with {
    if json_str is None:
        code_block_match = re.search(r'```\w*\s*\n?(\{.*?\})\s*\n?```', full_text, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1).strip()
            logger.debug("Found JSON in generic code block")

    # Strategy 3: Use regex to find a JSON object with "issues" key
    if json_str is None:
        # Look for JSON object containing "issues" array
        json_pattern = re.search(
            r'\{[^{}]*"issues"\s*:\s*\[.*?\][^{}]*"summary"\s*:\s*"[^"]*"[^{}]*\}',
            full_text,
            re.DOTALL
        )
        if json_pattern:
            json_str = json_pattern.group(0)
            logger.debug("Found JSON via issues/summary pattern match")

    # Strategy 4: Find outermost JSON object using brace matching
    if json_str is None and "{" in full_text:
        try:
            start = full_text.index("{")
            depth = 0
            in_string = False
            escape_next = False
            end = start

            for i, c in enumerate(full_text[start:], start):
                if escape_next:
                    escape_next = False
                    continue
                if c == '\\' and in_string:
                    escape_next = True
                    continue
                if c == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break

            if depth == 0 and end > start:
                json_str = full_text[start:end]
                logger.debug("Found JSON via brace matching")
        except (ValueError, IndexError) as e:
            logger.debug(f"Brace matching failed: {e}")

    # Try to parse the extracted JSON
    if json_str:
        try:
            result = json.loads(json_str)
            # Ensure required fields exist
            if "issues" not in result:
                result["issues"] = []
            if "summary" not in result:
                result["summary"] = ""
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
            return {
                "error": f"Could not parse JSON: {e}",
                "raw_response": full_text[:500] + "..." if len(full_text) > 500 else full_text,
                "issues": [],
                "summary": "",
            }

    logger.warning("Could not find JSON in response")
    return {
        "error": "Could not find JSON in response",
        "raw_response": full_text[:500] + "..." if len(full_text) > 500 else full_text,
        "issues": [],
        "summary": "",
    }
