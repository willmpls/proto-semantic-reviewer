"""
Anthropic model adapter.

Handles the specifics of Anthropic's Claude API including:
- JSON Schema tools with input_schema key
- Message format conversion with content blocks
- Response parsing for tool_use blocks
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple, List

import httpx

from .base import ModelAdapter, ToolDeclaration, Message, ToolCall, Role, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


class AnthropicAdapter(ModelAdapter):
    """Adapter for Anthropic Claude API."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = model_name or self.default_model

    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-20250514"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def generate(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration],
        system_prompt: str,
        temperature: float = 0.2,
        timeout: float | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Generate a response using Anthropic Claude."""
        timeout = timeout or DEFAULT_TIMEOUT
        anthropic_messages = self._convert_messages(messages)

        logger.debug(f"Calling Anthropic API with model={self.model_name}, timeout={timeout}s")

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=system_prompt,
                messages=anthropic_messages,
                tools=self._convert_tools(tools),
                temperature=temperature,
                timeout=timeout,
            )
        except httpx.TimeoutException as e:
            logger.error(f"Anthropic API timeout after {timeout}s: {e}")
            raise TimeoutError(f"Anthropic API request timed out after {timeout}s") from e
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        logger.debug(f"Anthropic response: {len(text_parts)} text parts, {len(tool_calls)} tool calls")
        return "\n".join(text_parts) if text_parts else None, tool_calls

    def _convert_tools(self, tools: list[ToolDeclaration]) -> list[dict]:
        """Convert to Anthropic tool format (JSON Schema with input_schema)."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """Convert generic messages to Anthropic format."""
        anthropic_messages = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue  # Handled via system parameter

            if msg.role == Role.TOOL:
                # Tool result - goes in a user message with tool_result content
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }],
                })
            elif msg.role == Role.ASSISTANT:
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                if content:
                    anthropic_messages.append({"role": "assistant", "content": content})
            else:
                anthropic_messages.append({
                    "role": "user",
                    "content": msg.content,
                })

        return anthropic_messages
