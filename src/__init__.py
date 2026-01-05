"""
Proto Semantic Reviewer.

An AI-powered agent that reviews Protocol Buffer definitions for semantic
correctness against Google AIP standards and event messaging best practices.

Supports multiple LLM providers: Gemini, OpenAI, and Anthropic.
"""

__version__ = "0.2.0"

from .agent import review_proto, review_proto_structured

__all__ = ["review_proto", "review_proto_structured", "__version__"]
