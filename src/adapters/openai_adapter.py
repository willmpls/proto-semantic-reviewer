"""
OpenAI model adapter.

Handles the specifics of OpenAI's API including:
- JSON Schema tools (native format)
- Message format conversion
- Response parsing for tool calls with JSON argument parsing
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Tuple, List

import httpx

from .base import (
    ModelAdapter, ToolDeclaration, Message, ToolCall, Role, DEFAULT_TIMEOUT,
    get_provider_headers, get_ca_bundle, get_base_url, create_ssl_context
)

logger = logging.getLogger(__name__)


class OpenAIAdapter(ModelAdapter):
    """Adapter for OpenAI API."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        from openai import OpenAI

        base_url = get_base_url("OPENAI")
        headers = get_provider_headers("OPENAI")
        ca_bundle = get_ca_bundle("OPENAI")

        # Create custom httpx client if headers or CA bundle are configured
        http_client = None
        if headers or ca_bundle:
            ssl_context = create_ssl_context(ca_bundle)
            http_client = httpx.Client(headers=headers, verify=ssl_context)
            logger.debug(f"OpenAI using custom HTTP client: headers={list(headers.keys())}, ca_bundle={ca_bundle}")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )

        # Log configuration at INFO level for visibility
        if base_url:
            logger.info(f"OpenAI adapter configured with custom base URL: {base_url}")
        else:
            logger.info("OpenAI adapter using default base URL (api.openai.com)")

        self.model_name = model_name or self.default_model

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    @property
    def provider_name(self) -> str:
        return "openai"

    def generate(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration],
        system_prompt: str,
        temperature: float = 0.2,
        timeout: float | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Generate a response using OpenAI."""
        timeout = timeout or DEFAULT_TIMEOUT

        # Build messages with system prompt first
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(self._convert_messages(messages))

        logger.debug(f"Calling OpenAI API with model={self.model_name}, timeout={timeout}s")

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                tools=self._convert_tools(tools),
                temperature=temperature,
                timeout=timeout,
            )
        except Exception as e:
            # OpenAI SDK raises various exceptions for timeouts
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                logger.error(f"OpenAI API timeout after {timeout}s: {e}")
                raise TimeoutError(f"OpenAI API request timed out after {timeout}s") from e
            logger.error(f"OpenAI API error: {e}")
            raise

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

        logger.debug(f"OpenAI response: text={'yes' if text_content else 'no'}, {len(tool_calls)} tool calls")
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
