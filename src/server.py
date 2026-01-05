"""
FastAPI server for proto semantic review.

Provides HTTP endpoints for reviewing Protocol Buffer definitions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agent import review_proto, review_proto_structured, ReviewContext
from .adapters import get_available_providers
from .auth import ADAuthMiddleware

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Proto Semantic Reviewer",
    description="""
AI-powered semantic review of Protocol Buffer definitions.

Checks event messages and REST APIs for semantic correctness against
Google AIP standards and event messaging best practices.

Supports multiple LLM providers: Gemini, OpenAI, and Anthropic.
    """,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add AD group authorization middleware (optional, enabled via ALLOWED_AD_GROUPS env var)
app.add_middleware(ADAuthMiddleware)


class ReviewRequest(BaseModel):
    """Request body for proto review."""
    proto_content: str = Field(
        ...,
        description="The .proto file content to review",
        examples=['''syntax = "proto3";

message OrderCreatedEvent {
  string order_id = 1;
  string created_at = 2;
  double total = 3;
}''']
    )


class ReviewIssue(BaseModel):
    """A single review issue."""
    severity: str = Field(..., description="error, warning, or suggestion")
    location: str = Field(..., description="Message.field or method location")
    issue: str = Field(..., description="Description of the problem")
    recommendation: str = Field(..., description="How to fix it")
    reference: Optional[str] = Field(None, description="AIP-XXX or ORG-XXX reference")


class ReviewResponse(BaseModel):
    """Response from proto review."""
    issues: list[ReviewIssue] = Field(default_factory=list)
    summary: str = Field("")
    provider: str = Field(..., description="Model provider used")
    model: str = Field(..., description="Model name used")


class RawReviewResponse(BaseModel):
    """Raw text response from proto review."""
    raw_response: str
    provider: str
    model: str


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    available_providers: list[str]


class ProvidersResponse(BaseModel):
    """Available providers response."""
    available: list[str]
    supported: list[str]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns the service status and which model providers have API keys configured.
    """
    providers = get_available_providers()
    return HealthResponse(
        status="healthy",
        available_providers=providers,
    )


@app.get("/providers", response_model=ProvidersResponse)
async def list_providers():
    """
    List available model providers.

    Shows which providers are supported and which have API keys configured.
    """
    return ProvidersResponse(
        available=get_available_providers(),
        supported=["gemini", "openai", "anthropic"],
    )


@app.post(
    "/review",
    response_model=ReviewResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Review failed"},
    },
)
async def review_proto_endpoint(
    request: ReviewRequest,
    provider: Optional[str] = Query(
        None,
        description="Model provider: gemini, openai, or anthropic. Auto-detected if not specified."
    ),
    model: Optional[str] = Query(
        None,
        description="Specific model name. Uses provider's default if not specified."
    ),
    focus: str = Query(
        "event",
        description="Review focus: 'event' for event messages, 'rest' for REST APIs"
    ),
):
    """
    Review a Protocol Buffer definition for semantic issues.

    Analyzes the proto content and returns structured issues with recommendations.

    - **proto_content**: The .proto file content to review
    - **provider**: Model provider (auto-detected from API keys if not specified)
    - **model**: Specific model name (uses provider default if not specified)
    - **focus**: Review focus - 'event' for event messaging, 'rest' for REST APIs
    """
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Structured review request received")

    if not request.proto_content.strip():
        raise HTTPException(status_code=400, detail="proto_content cannot be empty")

    try:
        context = ReviewContext(provider=provider, model_name=model, focus=focus)

        # Run the sync review function in a thread pool to avoid blocking
        result = await asyncio.to_thread(
            review_proto_structured,
            proto_content=request.proto_content,
            context=context,
        )

        # Handle error in result content
        if isinstance(result.content, dict) and result.content.get("error"):
            logger.error(f"[{request_id}] Review error: {result.content.get('error')}")
            raise HTTPException(
                status_code=500,
                detail="Review processing failed"  # Sanitized error message
            )

        logger.info(
            f"[{request_id}] Review completed: provider={result.provider_name}, "
            f"model={result.model_name}, iterations={result.iterations_used}"
        )

        content = result.content if isinstance(result.content, dict) else {}
        return ReviewResponse(
            issues=[ReviewIssue(**issue) for issue in content.get("issues", [])],
            summary=content.get("summary", ""),
            provider=result.provider_name,
            model=result.model_name,
        )

    except ValueError as e:
        logger.warning(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        logger.error(f"[{request_id}] Import error: {e}")
        raise HTTPException(status_code=500, detail="Required provider SDK not installed")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.exception(f"[{request_id}] Unexpected error during review")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@app.post(
    "/review/raw",
    response_model=RawReviewResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Review failed"},
    },
)
async def review_proto_raw_endpoint(
    request: ReviewRequest,
    provider: Optional[str] = Query(None, description="Model provider"),
    model: Optional[str] = Query(None, description="Specific model name"),
    focus: str = Query("event", description="Review focus: 'event' or 'rest'"),
):
    """
    Review a Protocol Buffer definition and return raw text response.

    Returns the model's unstructured text response without JSON parsing.
    """
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Raw review request received")

    if not request.proto_content.strip():
        raise HTTPException(status_code=400, detail="proto_content cannot be empty")

    try:
        context = ReviewContext(provider=provider, model_name=model, focus=focus)

        # Run the sync review function in a thread pool to avoid blocking
        result = await asyncio.to_thread(
            review_proto,
            proto_content=request.proto_content,
            context=context,
        )

        logger.info(
            f"[{request_id}] Raw review completed: provider={result.provider_name}, "
            f"model={result.model_name}, iterations={result.iterations_used}"
        )

        return RawReviewResponse(
            raw_response=result.content if isinstance(result.content, str) else str(result.content),
            provider=result.provider_name,
            model=result.model_name,
        )

    except ValueError as e:
        logger.warning(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        logger.error(f"[{request_id}] Import error: {e}")
        raise HTTPException(status_code=500, detail="Required provider SDK not installed")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.exception(f"[{request_id}] Unexpected error during raw review")
        raise HTTPException(status_code=500, detail="An internal error occurred")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    from .logging_config import configure_logging

    # Configure structured logging before starting server
    configure_logging()

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
