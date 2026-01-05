"""
Model adapters for different LLM providers.

This package provides a unified interface for interacting with different
LLM providers (Gemini, OpenAI, Anthropic) through the adapter pattern.
"""

from .base import (
    ModelAdapter,
    ToolDeclaration,
    Message,
    ToolCall,
    Role,
    DEFAULT_TIMEOUT,
)
from .factory import create_adapter, get_available_providers

__all__ = [
    "ModelAdapter",
    "ToolDeclaration",
    "Message",
    "ToolCall",
    "Role",
    "DEFAULT_TIMEOUT",
    "create_adapter",
    "get_available_providers",
]
