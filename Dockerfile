# Proto Semantic Reviewer
# An AI-powered agent for reviewing Protocol Buffer definitions

FROM python:3.12-slim

# Labels
LABEL org.opencontainers.image.title="Proto Semantic Reviewer"
LABEL org.opencontainers.image.description="AI-powered semantic review of Protocol Buffer definitions"
LABEL org.opencontainers.image.version="0.2.0"
LABEL org.opencontainers.image.vendor="Your Organization"
LABEL org.opencontainers.image.licenses="MIT"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd --gid 1000 reviewer \
    && useradd --uid 1000 --gid reviewer --shell /bin/bash --create-home reviewer

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application code and standards
COPY --chown=reviewer:reviewer src/ ./src/
COPY --chown=reviewer:reviewer standards/ ./standards/
COPY --chown=reviewer:reviewer pyproject.toml .
COPY --chown=reviewer:reviewer README.md .

# Install the package with all providers and server support
# You can customize this to install only what you need:
#   [gemini] - Google Gemini only
#   [openai] - OpenAI only
#   [anthropic] - Anthropic only
#   [server] - FastAPI server
#   [full] - All providers + server
RUN pip install --no-cache-dir -e ".[full]"

# Create directories for mounting files (must be done as root)
# /app/standards is the default; can be overridden with STANDARDS_DIR env var
RUN mkdir -p /protos /examples && chown reviewer:reviewer /protos /examples

# Switch to non-root user
USER reviewer

# Expose the server port
EXPOSE 8000

# Health check for server mode
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set the entrypoint
ENTRYPOINT ["python", "-m", "src"]

# Default command runs the server
CMD ["server", "--host", "0.0.0.0", "--port", "8000"]
