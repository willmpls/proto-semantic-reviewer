"""
Gemini model adapter.

Handles the specifics of Google's Gemini API including:
- Converting JSON Schema tools to Gemini's FunctionDeclaration format
- Message format conversion (Content/Parts)
- Response parsing for tool calls
"""

from typing import Any, Optional

from .base import ModelAdapter, ToolDeclaration, Message, ToolCall, Role


class GeminiAdapter(ModelAdapter):
    """Adapter for Google Gemini API."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        from google import genai
        from google.genai import types

        self.client = genai.Client(api_key=api_key)
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
    ) -> tuple[str | None, list[ToolCall]]:
        """Generate a response using Gemini."""
        gemini_messages = self._convert_messages(messages)
        gemini_tools = self._convert_tools(tools)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=gemini_messages,
            config=self._types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[gemini_tools],
                temperature=temperature,
            ),
        )

        # Parse response
        if not response.candidates:
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
