"""
Gemini model adapter.

Handles the specifics of Google's Gemini API including:
- Converting JSON Schema tools to Gemini's FunctionDeclaration format
- Message format conversion (Content/Parts)
- Response parsing for tool calls
"""

from __future__ import annotations

import logging
import ssl
from typing import Any, Optional, Tuple, List

from .base import (
    ModelAdapter, ToolDeclaration, Message, ToolCall, Role, DEFAULT_TIMEOUT,
    get_provider_headers, get_ca_bundle, get_base_url
)

logger = logging.getLogger(__name__)


class GeminiAdapter(ModelAdapter):
    """Adapter for Google Gemini API."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        from google import genai
        from google.genai import types

        base_url = get_base_url("GEMINI")
        headers = get_provider_headers("GEMINI")
        ca_bundle = get_ca_bundle("GEMINI")

        # Build http_options for custom headers and SSL
        http_options = {}
        if headers:
            http_options["headers"] = headers
            logger.debug(f"Gemini using custom headers: {list(headers.keys())}")
        if ca_bundle:
            http_options["ssl_context"] = ssl.create_default_context(cafile=ca_bundle)
            logger.debug(f"Gemini using custom CA bundle: {ca_bundle}")

        # Build client kwargs
        client_kwargs = {"api_key": api_key}
        if http_options:
            client_kwargs["http_options"] = http_options

        self.client = genai.Client(**client_kwargs)

        # Note: Gemini SDK base URL override may require vertexai=True or
        # specific endpoint configuration. Log if custom URL requested.
        if base_url:
            logger.warning(
                f"GEMINI_BASE_URL={base_url} is set but Gemini SDK may not support "
                "direct base URL override. Consider using Vertex AI configuration instead."
            )

        self.model_name = model_name or self.default_model
        self._types = types

    @property
    def default_model(self) -> str:
        return "gemini-2.0-flash"

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration],
        system_prompt: str,
        temperature: float = 0.2,
        timeout: float | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        """Generate a response using Gemini."""
        timeout = timeout or DEFAULT_TIMEOUT
        gemini_messages = self._convert_messages(messages)
        gemini_tools = self._convert_tools(tools)

        logger.debug(f"Calling Gemini API with model={self.model_name}, timeout={timeout}s")

        try:
            # Gemini SDK uses httpx under the hood which respects timeout settings
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=gemini_messages,
                config=self._types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[gemini_tools],
                    temperature=temperature,
                    http_options={"timeout": timeout},
                ),
            )
        except Exception as e:
            # Check for timeout-related errors
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                logger.error(f"Gemini API timeout after {timeout}s: {e}")
                raise TimeoutError(f"Gemini API request timed out after {timeout}s") from e
            logger.error(f"Gemini API error: {e}")
            raise

        # Parse response
        if not response.candidates:
            logger.warning("Gemini returned no candidates")
            return None, []

        candidate = response.candidates[0]
        text_parts = []
        tool_calls = []

        for part in candidate.content.parts:
            if part.function_call:
                tool_calls.append(ToolCall(
                    id=part.function_call.name,  # Gemini uses name as ID
                    name=part.function_call.name,
                    arguments=dict(part.function_call.args) if part.function_call.args else {},
                ))
            elif part.text:
                text_parts.append(part.text)

        logger.debug(f"Gemini response: {len(text_parts)} text parts, {len(tool_calls)} tool calls")
        return "\n".join(text_parts) if text_parts else None, tool_calls

    def _convert_tools(self, tools: list[ToolDeclaration]) -> Any:
        """Convert JSON Schema tools to Gemini FunctionDeclaration format."""
        declarations = []

        for tool in tools:
            properties = {}
            required = tool.parameters.get("required", [])

            for name, schema in tool.parameters.get("properties", {}).items():
                gemini_type = self._json_type_to_gemini(schema.get("type", "string"))
                properties[name] = self._types.Schema(
                    type=gemini_type,
                    description=schema.get("description", ""),
                )

            declarations.append(
                self._types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=self._types.Schema(
                        type=self._types.Type.OBJECT,
                        properties=properties,
                        required=required,
                    ),
                )
            )

        return self._types.Tool(function_declarations=declarations)

    def _json_type_to_gemini(self, json_type: str) -> Any:
        """Map JSON Schema type to Gemini Type enum."""
        mapping = {
            "string": self._types.Type.STRING,
            "integer": self._types.Type.INTEGER,
            "number": self._types.Type.NUMBER,
            "boolean": self._types.Type.BOOLEAN,
            "array": self._types.Type.ARRAY,
            "object": self._types.Type.OBJECT,
        }
        return mapping.get(json_type, self._types.Type.STRING)

    def _convert_messages(self, messages: list[Message]) -> list[Any]:
        """Convert generic messages to Gemini Content format."""
        gemini_messages = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue  # System handled via system_instruction

            if msg.tool_call_id:
                # Tool response - Gemini uses FunctionResponse in a user message
                gemini_messages.append(
                    self._types.Content(
                        role="user",
                        parts=[self._types.Part(
                            function_response=self._types.FunctionResponse(
                                name=msg.tool_call_id,
                                response={"result": msg.content},
                            )
                        )],
                    )
                )
            elif msg.role == Role.ASSISTANT and msg.tool_calls:
                # Assistant message with tool calls
                parts = []
                if msg.content:
                    parts.append(self._types.Part(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(self._types.Part(
                        function_call=self._types.FunctionCall(
                            name=tc.name,
                            args=tc.arguments,
                        )
                    ))
                gemini_messages.append(
                    self._types.Content(role="model", parts=parts)
                )
            else:
                role = "user" if msg.role == Role.USER else "model"
                gemini_messages.append(
                    self._types.Content(
                        role=role,
                        parts=[self._types.Part(text=msg.content)],
                    )
                )

        return gemini_messages
