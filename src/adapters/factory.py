"""
Adapter factory for creating model adapters.

This module handles provider detection and adapter instantiation.
"""

from __future__ import annotations

import os
from typing import Optional, List

from .base import ModelAdapter


def get_available_providers() -> list[str]:
    """
    Return list of providers with available API keys.

    Checks environment variables for each supported provider.
    OpenAI is listed first (preferred default).
    """
    providers = []
    # OpenAI first (preferred default)
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    if os.environ.get("GOOGLE_API_KEY"):
        providers.append("gemini")
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    return providers


def create_adapter(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> ModelAdapter:
    """
    Create a model adapter based on provider or auto-detection.

    Provider selection order:
    1. Explicit `provider` argument
    2. MODEL_PROVIDER environment variable
    3. Auto-detect from available API keys (first found)

    Args:
        provider: One of "gemini", "openai", "anthropic", or None for auto-detect
        model_name: Optional specific model name to use (uses provider default if None)

    Returns:
        Configured ModelAdapter instance

    Raises:
        ValueError: If no API key is available for the requested provider
        ImportError: If the required SDK is not installed
    """
    # Determine provider
    if not provider:
        provider = os.environ.get("MODEL_PROVIDER")

    if not provider:
        # Auto-detect from API keys
        available = get_available_providers()
        if not available:
            raise ValueError(
                "No API key found. Set one of: GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY"
            )
        provider = available[0]  # Use first available

    provider = provider.lower()

    if provider == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable required for Gemini")
        try:
            from .gemini_adapter import GeminiAdapter
            return GeminiAdapter(api_key=api_key, model_name=model_name)
        except ImportError:
            raise ImportError(
                "google-genai not installed. Install with: pip install proto-semantic-reviewer[gemini]"
            )

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required for OpenAI")
        try:
            from .openai_adapter import OpenAIAdapter
            return OpenAIAdapter(api_key=api_key, model_name=model_name)
        except ImportError:
            raise ImportError(
                "openai not installed. Install with: pip install proto-semantic-reviewer[openai]"
            )

    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required for Anthropic")
        try:
            from .anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter(api_key=api_key, model_name=model_name)
        except ImportError:
            raise ImportError(
                "anthropic not installed. Install with: pip install proto-semantic-reviewer[anthropic]"
            )

    else:
        raise ValueError(
            f"Unknown provider: {provider}. Use 'gemini', 'openai', or 'anthropic'"
        )
