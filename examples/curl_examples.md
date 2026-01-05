# Proto Semantic Reviewer - curl Examples

This document shows how to use the HTTP API to review Protocol Buffer definitions.

## Prerequisites

### Option 1: Docker (Recommended)

No local Python installation required. Just Docker.

```bash
# Set your API key (at least one required)
export GOOGLE_API_KEY=your-gemini-key
# or: export OPENAI_API_KEY=your-openai-key
# or: export ANTHROPIC_API_KEY=your-anthropic-key

# Start the server
docker-compose up proto-reviewer
```

### Option 2: Local Installation (macOS)

macOS uses `python3` and virtual environments:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with your preferred provider + server
pip install -e ".[gemini,server]"  # or [openai] or [anthropic]

# Set your API key
export GOOGLE_API_KEY=your-gemini-key

# Start the server
python3 -m src server --port 8000
```

### Option 3: Local Installation (Linux with python symlink)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install and run
pip install -e ".[gemini,server]"
export GOOGLE_API_KEY=your-gemini-key
python -m src server --port 8000
```

---

## Health Check

Verify the server is running and which providers are available:

```bash
curl http://localhost:8000/health
```

Example response:
```json
{
  "status": "healthy",
  "available_providers": ["gemini", "openai"]
}
```

## List Providers

See which providers are supported and configured:

```bash
curl http://localhost:8000/providers
```

Response:
```json
{
  "available": ["gemini"],
  "supported": ["gemini", "openai", "anthropic"]
}
```

## Review a Proto File

### Basic Review (Event Focus - Default)

```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "proto_content": "syntax = \"proto3\";\n\nmessage OrderCreated {\n  string order_id = 1;\n  string created_at = 2;\n  double total = 3;\n}"
  }'
```

### Review with Specific Provider

```bash
curl -X POST "http://localhost:8000/review?provider=openai" \
  -H "Content-Type: application/json" \
  -d '{
    "proto_content": "syntax = \"proto3\";\n\nmessage UserEvent {\n  string id = 1;\n  int64 timestamp = 2;\n}"
  }'
```

### Review with Specific Model

```bash
curl -X POST "http://localhost:8000/review?provider=anthropic&model=claude-3-5-sonnet-20241022" \
  -H "Content-Type: application/json" \
  -d '{
    "proto_content": "..."
  }'
```

### REST API Focus (Instead of Events)

```bash
curl -X POST "http://localhost:8000/review?focus=rest" \
  -H "Content-Type: application/json" \
  -d '{
    "proto_content": "syntax = \"proto3\";\n\nmessage GetBookRequest {\n  int64 book_id = 1;\n}"
  }'
```

### Get Raw (Unstructured) Response

```bash
curl -X POST http://localhost:8000/review/raw \
  -H "Content-Type: application/json" \
  -d '{
    "proto_content": "..."
  }'
```

## Review from File

### Using jq to Build JSON

```bash
# Read proto file and review
cat examples/events/bad_event.proto | \
  jq -Rs '{proto_content: .}' | \
  curl -X POST http://localhost:8000/review \
    -H "Content-Type: application/json" \
    -d @-
```

### Using a Shell Variable

```bash
PROTO_CONTENT=$(cat examples/events/bad_event.proto)
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d "{\"proto_content\": $(echo "$PROTO_CONTENT" | jq -Rs .)}"
```

## Example Response

```json
{
  "issues": [
    {
      "severity": "error",
      "location": "OrderCreated.created_at",
      "issue": "Timestamp field uses string type instead of google.protobuf.Timestamp",
      "recommendation": "Change to google.protobuf.Timestamp for type safety and precision",
      "reference": "AIP-142"
    },
    {
      "severity": "error",
      "location": "OrderCreated.total",
      "issue": "Monetary amount uses double type which can cause precision errors",
      "recommendation": "Use google.type.Money or a custom Money message with units and nanos",
      "reference": null
    },
    {
      "severity": "warning",
      "location": "OrderCreated",
      "issue": "Event message missing event_id field for idempotency",
      "recommendation": "Add string event_id field for deduplication",
      "reference": "ORG-001"
    }
  ],
  "summary": "Found 3 issues: 2 errors related to type usage (AIP-142), 1 warning about missing event_id (ORG-001)",
  "provider": "gemini",
  "model": "gemini-2.0-flash"
}
```

## API Documentation

The server provides automatic API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Error Handling

### Missing API Key

```bash
curl http://localhost:8000/review -X POST \
  -H "Content-Type: application/json" \
  -d '{"proto_content": "..."}'
```

Response (400):
```json
{
  "detail": "No API key found. Set one of: GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY"
}
```

### Empty Proto Content

```bash
curl http://localhost:8000/review -X POST \
  -H "Content-Type: application/json" \
  -d '{"proto_content": ""}'
```

Response (400):
```json
{
  "detail": "proto_content cannot be empty"
}
```

### Missing SDK

```bash
curl "http://localhost:8000/review?provider=openai" -X POST \
  -H "Content-Type: application/json" \
  -d '{"proto_content": "..."}'
```

Response (500):
```json
{
  "detail": "openai not installed. Install with: pip install proto-semantic-reviewer[openai]"
}
```

## CLI Alternative

### Using Docker

```bash
# Review a file
docker-compose run --rm proto-reviewer review /examples/events/bad_event.proto

# With specific provider
docker-compose run --rm proto-reviewer review /examples/events/bad_event.proto --provider openai

# JSON output
docker-compose run --rm proto-reviewer review /examples/events/bad_event.proto --format json

# List event standards
docker-compose run --rm proto-reviewer list-events
```

### Using Local Installation (macOS)

```bash
# Activate your virtualenv first
source venv/bin/activate

# Review a file
python3 -m src review examples/events/bad_event.proto

# With specific provider
python3 -m src review examples/events/bad_event.proto --provider openai

# JSON output
python3 -m src review examples/events/bad_event.proto --format json

# REST focus instead of events
python3 -m src review examples/events/bad_event.proto --focus rest
```
