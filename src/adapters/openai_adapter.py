"""
OpenAI model adapter.

Handles the specifics of OpenAI's API including:
- JSON Schema tools (native format)
- Message format conversion
- Response parsing for tool calls with JSON argument parsing
"""

import json
from typing import Any, Optional

from .base import ModelAdapter, ToolDeclaration, Message, ToolCall, Role


class OpenAIAdapter(ModelAdapter):
    """Adapter for OpenAI API."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name or self.default_model

    @property
    def default_model(self) -> str:
        return "gpt-5.2"

    @property
    def provider_name(self) -> str:
        return "openai"

    def generate(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration],
        system_prompt: str,
        temperature: float = 0.2,
    ) -> tuple[str | None, list[ToolCall]]:
        """Generate a response using OpenAI."""
        # Build messages with system prompt first
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(self._convert_messages(messages))

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=openai_messages,
            tools=self._convert_tools(tools),
            temperature=temperature,
        )

        message = response.choices[0].message
        text_content = message.content
        tool_calls = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return text_content, tool_calls

    def _convert_tools(self, tools: list[ToolDeclaration]) -> list[dict]:
        """Convert to OpenAI function format (JSON Schema based)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in tools
        ]

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """Convert generic messages to OpenAI format."""
        openai_messages = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue  # Already handled as first message

            if msg.role == Role.TOOL:
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
            elif msg.role == Role.ASSISTANT and msg.tool_calls:
                openai_messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            }
                        }
                        for tc in msg.tool_calls
                    ],
                })
            else:
                role = "user" if msg.role == Role.USER else "assistant"
                openai_messages.append({
                    "role": role,
                    "content": msg.content,
                })

        return openai_messages
