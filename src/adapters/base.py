"""
Base classes for model adapters.

This module defines the abstract interface that all model adapters must implement,
providing a unified way to interact with different LLM providers.
"""

from __future__ import annotations

import os
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple, List, Union

# Default timeout for LLM API calls (in seconds)
DEFAULT_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", 120))


def get_provider_headers(provider_prefix: str) -> dict[str, str]:
    """
    Parse HTTP headers from environment variables.

    Environment variables matching {PROVIDER}_HEADER_{NAME}=value are converted
    to HTTP headers with the following rules:
    - Single underscore `_` becomes a hyphen `-`
    - Double underscore `__` becomes a literal underscore `_`

    Examples:
        OPENAI_HEADER_X_Request_Id=123      -> {"X-Request-Id": "123"}
        OPENAI_HEADER_X__Custom__Name=val   -> {"X_Custom_Name": "val"}
        OPENAI_HEADER_Content_Type=json     -> {"Content-Type": "json"}

    Args:
        provider_prefix: The provider name in uppercase (e.g., "OPENAI", "ANTHROPIC")

    Returns:
        Dictionary of header names to values
    """
    prefix = f"{provider_prefix}_HEADER_"
    headers = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            header_name = key[len(prefix):]
            # Use placeholder to preserve double underscores
            header_name = header_name.replace("__", "\x00")
            header_name = header_name.replace("_", "-")
            header_name = header_name.replace("\x00", "_")
            headers[header_name] = value
    return headers


def get_ca_bundle(provider_prefix: str) -> Optional[str]:
    """
    Get CA certificate bundle path from environment.

    Checks in order of precedence:
    1. {PROVIDER}_CA_BUNDLE (e.g., OPENAI_CA_BUNDLE)
    2. LLM_CA_BUNDLE
    3. SSL_CERT_FILE (standard OpenSSL env var)
    4. REQUESTS_CA_BUNDLE (commonly used by Python HTTP libraries)

    Only returns paths that actually exist on the filesystem.

    Args:
        provider_prefix: The provider name in uppercase (e.g., "OPENAI", "ANTHROPIC")

    Returns:
        Path to CA bundle file, or None if not configured or file doesn't exist
    """
    candidates = [
        (f"{provider_prefix}_CA_BUNDLE", os.environ.get(f"{provider_prefix}_CA_BUNDLE")),
        ("LLM_CA_BUNDLE", os.environ.get("LLM_CA_BUNDLE")),
        ("SSL_CERT_FILE", os.environ.get("SSL_CERT_FILE")),
        ("REQUESTS_CA_BUNDLE", os.environ.get("REQUESTS_CA_BUNDLE")),
    ]

    for env_var, path in candidates:
        if path:
            if os.path.isfile(path):
                return path
            # Log warning for explicitly set but missing CA bundles
            # (skip warning for SSL_CERT_FILE/REQUESTS_CA_BUNDLE as these are often set system-wide)
            if env_var in (f"{provider_prefix}_CA_BUNDLE", "LLM_CA_BUNDLE"):
                import logging
                logging.getLogger(__name__).warning(
                    f"{env_var}={path} specified but file does not exist, ignoring"
                )

    return None


def get_base_url(provider_prefix: str) -> Optional[str]:
    """
    Get custom base URL from environment.

    Args:
        provider_prefix: The provider name in uppercase (e.g., "OPENAI", "ANTHROPIC")

    Returns:
        Custom base URL, or None if not configured
    """
    return os.environ.get(f"{provider_prefix}_BASE_URL")


def create_ssl_context(ca_bundle: Optional[str]) -> Union[ssl.SSLContext, bool]:
    """
    Create an SSL context with custom CA bundle if provided.

    Args:
        ca_bundle: Path to CA certificate bundle file, or None

    Returns:
        ssl.SSLContext if ca_bundle provided, True otherwise (use default verification)
    """
    if ca_bundle:
        ctx = ssl.create_default_context(cafile=ca_bundle)
        return ctx
    return True


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
        timeout: float | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        """
        Generate a response from the model.

        Args:
            messages: Conversation history in provider-agnostic format
            tools: Available tools in JSON Schema format
            system_prompt: System instructions for the model
            temperature: Sampling temperature (0.0-1.0)
            timeout: Request timeout in seconds (uses DEFAULT_TIMEOUT if None)

        Returns:
            Tuple of (text_response, tool_calls)
            - text_response: The model's text output, or None if only tool calls
            - tool_calls: List of tool calls the model wants to make

        Raises:
            TimeoutError: If the request exceeds the timeout
            Exception: Provider-specific errors are logged and re-raised
        """
        pass
