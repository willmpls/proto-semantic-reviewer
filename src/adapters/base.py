"""
Base classes for model adapters.

This module defines the abstract interface that all model adapters must implement,
providing a unified way to interact with different LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(Enum):
    """Message role in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolDeclaration:
    """Provider-agnostic tool declaration using JSON Schema format."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema format


@dataclass
class ToolCall:
    """Represents a tool call from the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool."""
    tool_call_id: str
    content: str


@dataclass
class Message:
    """Provider-agnostic message format."""
    role: Role
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None  # For tool responses


class ModelAdapter(ABC):
    """
    Abstract base class for model adapters.

    Each adapter handles the specifics of a particular LLM provider:
    - Tool declaration format conversion
    - Message format conversion
    - Response parsing
    - System prompt injection
    """

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model name for this provider."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'gemini', 'openai', 'anthropic')."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration],
        system_prompt: str,
        temperature: float = 0.2,
    ) -> tuple[str | None, list[ToolCall]]:
        """
        Generate a response from the model.

        Args:
            messages: Conversation history in provider-agnostic format
            tools: Available tools in JSON Schema format
            system_prompt: System instructions for the model
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Tuple of (text_response, tool_calls)
            - text_response: The model's text output, or None if only tool calls
            - tool_calls: List of tool calls the model wants to make
        """
        pass
