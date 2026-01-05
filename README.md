# Proto Semantic Reviewer

An AI-powered agent that reviews Protocol Buffer definitions for **semantic correctness** against [Google AIP (API Improvement Proposals)](https://google.aip.dev/) standards and event messaging best practices.

## What It Does

Traditional linters like `buf lint` and `api-linter` check syntactic rules—naming conventions, missing annotations, field numbers. This tool goes deeper, checking **semantic** issues that require understanding the *meaning* of your messages:

- **Organizational standards**: Custom semantic rules (e.g., event_id for idempotency) that extend AIPs
- **Type appropriateness**: Is `string created_at` really the right choice, or should it be `google.protobuf.Timestamp`?
- **Well-known type usage**: Is `double price` correct, or should it be `google.type.Money`?
- **Enum safety**: Does your enum have an `UNSPECIFIED = 0` value for forward compatibility?
- **Schema evolution**: Are your messages designed for safe evolution over time?

## How It Works

The reviewer uses an LLM agent with access to a bundled knowledge base of AIP and organizational standards. The agent autonomously decides which standards to look up based on patterns it detects in your proto.

```mermaid
flowchart TB
    subgraph Input
        Proto[".proto file"]
    end

    subgraph Agent["LLM Agent"]
        Analyze["1. Analyze proto"]
        Check["2. Check all standards"]
        Generate["3. Generate issues"]
    end

    subgraph Tools["Knowledge Base Tools"]
        ListAIP["list_available_aips()"]
        LookupAIP["lookup_aip(number)"]
        ListORG["list_org_standards()"]
        LookupORG["lookup_org_standard(id)"]
    end

    subgraph Standards["YAML Standards"]
        AIPs["standards/aips/*.yaml<br/>AIP-141, 142, 143..."]
        ORGs["standards/org/*.yaml<br/>ORG-001, 002..."]
    end

    subgraph Output
        Response["Issues with references:<br/>AIP-142, ORG-001, etc."]
    end

    Proto --> Analyze
    Analyze --> Check
    Check --> ListAIP & ListORG
    ListAIP --> LookupAIP --> AIPs
    ListORG --> LookupORG --> ORGs
    AIPs --> Generate
    ORGs --> Generate
    Generate --> Response
```

**Both AIPs and ORGs are just "standards":**
- **AIPs** = Google's universal best practices
- **ORGs** = Your organization's custom rules

Each ORG standard has an `applies_to` field (e.g., "messages ending in Event") that the agent checks to determine relevance.

**Example: Multiple standards apply to one message**

```protobuf
message OrderCreatedEvent {
  string order_id = 1;      // ORG-001: Missing event_id (if applies_to matches)
  string created_at = 2;    // AIP-142: Should be Timestamp
  double price = 3;         // AIP-143: Should be Money
}
```

**Key points:**
- **Standards are equal**: AIPs and ORGs are both just standards from different sources
- **ORG applicability**: Each ORG defines its own `applies_to` pattern
- **Multiple violations**: One message can violate any combination of standards
- **Local YAML files**: All standards loaded from `standards/` directory

## Features

- **Multi-Provider LLM Support**: Works with Gemini, OpenAI, or Anthropic
- **AIP Standards**: Universal Google AIP compliance (timestamps, enums, field behavior)
- **Organizational Standards**: Extensible ORG-XXX rules for your organization's requirements
- **HTTP API**: FastAPI server with OpenAPI documentation
- **MCP Server**: IDE integration for IntelliJ, VS Code, and other MCP-compatible tools
- **Optional Authorization**: AD group-based access control via header
- **Docker Ready**: Run anywhere with Docker Compose
- **CLI & Programmatic**: Use from command line or integrate into your Python code
- **Structured Output**: Get JSON results for easy CI integration

## Quick Start (Docker - Recommended)

No local Python installation required. Just Docker.

```bash
# Clone the repository
git clone https://github.com/your-org/proto-semantic-reviewer.git
cd proto-semantic-reviewer

# Set your API key (at least one required)
export GOOGLE_API_KEY=your-gemini-key
# or: export OPENAI_API_KEY=your-openai-key
# or: export ANTHROPIC_API_KEY=your-anthropic-key

# Start the HTTP server
docker-compose up proto-reviewer

# The server is now running at http://localhost:8000
# Open http://localhost:8000/docs for interactive API documentation
```

### Review via HTTP API

```bash
# Review a proto file from disk (simplest approach)
jq -Rs '{proto_content: .}' path/to/your.proto | \
  curl -X POST http://localhost:8000/review \
    -H "Content-Type: application/json" \
    -d @-

# Review inline proto content
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "proto_content": "syntax = \"proto3\";\n\nmessage OrderCreated {\n  string order_id = 1;\n  string created_at = 2;\n}"
  }'

# Review with a specific provider and model
curl -X POST "http://localhost:8000/review?provider=openai&model=gpt-4-turbo" \
  -H "Content-Type: application/json" \
  -d '{"proto_content": "..."}'

# Check server health
curl http://localhost:8000/health
```

### Review via CLI (Docker)

```bash
# Review a proto file
docker-compose run --rm proto-reviewer review /examples/events/bad_event.proto

# Get JSON output
docker-compose run --rm proto-reviewer review /examples/events/bad_event.proto --format json

# Use a specific provider
docker-compose run --rm proto-reviewer review /examples/events/bad_event.proto --provider openai

# List organizational standards
docker-compose run --rm proto-reviewer list-org-standards

# List AIPs
docker-compose run --rm proto-reviewer list-aips
```

See [examples/curl_examples.md](examples/curl_examples.md) for more detailed examples.

---

## Local Installation (Optional)

### macOS (python3 + virtualenv)

macOS doesn't have a `python` command by default. Use `python3`:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with your preferred provider(s)
pip install -e ".[gemini,server]"      # Gemini + HTTP server
# or: pip install -e ".[openai,server]"   # OpenAI + HTTP server
# or: pip install -e ".[full]"            # All providers + server

# Set your API key
export GOOGLE_API_KEY=your-key

# Start the HTTP server
python3 -m src server --port 8000

# Or review a file directly
python3 -m src review path/to/your.proto
```

### Linux (with python symlink)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install and run
pip install -e ".[gemini,server]"
export GOOGLE_API_KEY=your-key
python -m src server --port 8000
```

---

## Supported Providers

| Provider | Environment Variable | Default Model |
|----------|---------------------|---------------|
| Gemini | `GOOGLE_API_KEY` | gemini-2.0-flash |
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |

The agent auto-detects which provider to use based on available API keys. Override with `MODEL_PROVIDER` environment variable or `--provider` CLI flag.

---

## Example Output

```
Found 5 issue(s): 2 error(s), 2 warning(s), 1 suggestion(s)

✗ [ERROR] OrderCreated.created_at
  Issue: Timestamp field uses string type instead of google.protobuf.Timestamp
  Recommendation: Change to google.protobuf.Timestamp for type safety and precision
  Reference: AIP-142

✗ [ERROR] OrderCreated.total
  Issue: Monetary amount uses double type which can cause precision errors
  Recommendation: Use google.type.Money or a custom Money message with units and nanos
  Reference: None

⚠ [WARNING] OrderCreated
  Issue: Event message missing event_id field for idempotency
  Recommendation: Add string event_id field for deduplication
  Reference: ORG-001

Summary: Found 3 issues: 2 errors related to type usage (AIP-142), 1 warning about missing event_id (ORG-001)
```

---

## Standards

### AIP Standards (Universal)

Google AIPs define universal best practices for all Protocol Buffers:

| AIP | Title | Key Checks |
|-----|-------|------------|
| AIP-140 | Field Names | Standard naming (create_time vs created_at) |
| AIP-141 | Quantities | Integer types for counts, avoid float |
| AIP-142 | Time and Duration | Timestamp/Duration types |
| AIP-143 | Standardized Codes | google.type.Money, LatLng, Date |
| AIP-148 | Standard Fields | create_time, update_time, etag, uid |
| AIP-151 | Long-Running Operations | Operation patterns |
| AIP-154 | Resource Freshness | etag usage |
| AIP-155 | Request Identification | request_id patterns |
| AIP-180 | Backwards Compatibility | Enum UNSPECIFIED values |
| AIP-191 | File Layout | Proto file organization |
| AIP-203 | Field Behavior | OUTPUT_ONLY, REQUIRED, IMMUTABLE |

Use `--focus rest` to include additional REST/resource-oriented AIPs (4, 121-123, 131-135, 158).

### Organizational Standards (ORG-XXX)

Extensible organization-specific rules that extend AIPs:

| Standard | Title | Key Checks |
|----------|-------|------------|
| ORG-001 | Event Identification | event_id for idempotency in event messages |

Add your own organizational standards in `src/knowledge/org_standards.py`.

---

## HTTP API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/review` | POST | Review proto content (structured JSON response) |
| `/review/raw` | POST | Review proto content (raw text response) |
| `/health` | GET | Health check with available providers |
| `/providers` | GET | List supported and available providers |
| `/docs` | GET | Swagger UI documentation |
| `/redoc` | GET | ReDoc documentation |

### Query Parameters for /review

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | string | auto | LLM provider (gemini, openai, anthropic) |
| `model` | string | provider default | Specific model name |
| `focus` | string | event | Review focus (event or rest) |

---

## MCP Server (IDE Integration)

The reviewer can run as an MCP (Model Context Protocol) server for integration with IDEs like IntelliJ, VS Code, and other MCP-compatible tools.

### Running the MCP Server

```bash
# STDIO mode (default) - for local IDE plugins
python3 -m src mcp

# HTTP mode - for network access
python3 -m src mcp --http --port 3000

# Via Docker
docker-compose --profile mcp up proto-reviewer-mcp
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `review_proto` | Review proto content for semantic issues |
| `list_aips` | List available AIP standards |
| `list_org_standards` | List available organizational standards |
| `lookup_aip` | Get details for a specific AIP |
| `lookup_org_standard` | Get details for a specific ORG standard |

### IDE Configuration

**VS Code** (`.vscode/mcp.json`):
```json
{
  "servers": {
    "proto-reviewer": {
      "command": "python3",
      "args": ["-m", "src", "mcp"]
    }
  }
}
```

**IntelliJ** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "proto-reviewer": {
      "command": "python3",
      "args": ["-m", "src", "mcp"]
    }
  }
}
```

---

## Programmatic Usage

```python
from src import review_proto, review_proto_structured

# Simple review (returns text)
result = review_proto(proto_content)
print(result)

# With specific provider
result = review_proto(proto_content, provider="openai")

# Structured review (returns dict)
result = review_proto_structured(proto_content, focus="event")
for issue in result["issues"]:
    print(f"[{issue['severity']}] {issue['location']}: {issue['issue']}")
```

---

## CI Integration

### GitHub Actions

```yaml
name: Proto Semantic Review

on:
  pull_request:
    paths:
      - '**/*.proto'

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Review protos
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
        run: |
          docker-compose run --rm proto-reviewer review /protos --format json
```

### GitLab CI

```yaml
proto-review:
  image: docker/compose:latest
  services:
    - docker:dind
  script:
    - docker-compose run --rm proto-reviewer review /protos --format json
  rules:
    - changes:
        - "**/*.proto"
```

---

## Architecture

```
proto-semantic-reviewer/
├── src/
│   ├── __init__.py              # Package exports
│   ├── __main__.py              # CLI entry point
│   ├── agent.py                 # Core agent logic
│   ├── tools.py                 # Agent tools
│   ├── prompts.py               # System prompts (event/REST focused)
│   ├── tool_definitions.py      # Provider-agnostic tool declarations
│   ├── server.py                # FastAPI HTTP server
│   ├── mcp_server.py            # MCP server for IDE integration
│   ├── auth.py                  # AD group authorization middleware
│   ├── adapters/
│   │   ├── base.py              # Abstract adapter interface
│   │   ├── factory.py           # Adapter factory with auto-detection
│   │   ├── gemini_adapter.py    # Gemini implementation
│   │   ├── openai_adapter.py    # OpenAI implementation
│   │   └── anthropic_adapter.py # Anthropic implementation
│   └── knowledge/
│       ├── loader.py            # YAML standards loader
│       └── wellknown_types.py   # Type recommendations
├── standards/                   # YAML-based standards (editable!)
│   ├── aips/                    # AIP standards
│   │   ├── aip-141.yaml
│   │   ├── aip-142.yaml
│   │   ├── aip-143.yaml
│   │   └── ...
│   └── org/                     # Organizational standards
│       └── org-001.yaml
├── examples/
│   ├── events/                  # Example proto files
│   └── curl_examples.md         # HTTP API examples
├── docker-compose.yml           # Local dev setup
├── Dockerfile                   # Container build
└── pyproject.toml               # Package config with optional deps
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | One of three | - | Google AI API key for Gemini |
| `OPENAI_API_KEY` | One of three | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | One of three | - | Anthropic API key |
| `MODEL_PROVIDER` | No | auto-detect | Force a specific provider |
| `ALLOWED_AD_GROUPS` | No | - | Comma-separated list of AD groups for authorization |
| `STANDARDS_DIR` | No | `./standards` | Path to custom standards directory |

### Custom Standards

Standards are loaded from YAML files, making them easy to customize without code changes.

**Directory structure:**
```
standards/
├── aips/           # AIP standards (universal)
│   ├── aip-141.yaml
│   ├── aip-142.yaml
│   └── ...
└── org/            # Organizational standards (your rules)
    └── org-001.yaml
```

**Adding a custom organizational standard:**

```yaml
# standards/org/org-002.yaml
id: ORG-002
title: Correlation Required
summary: |
  All event messages must include correlation_id for distributed tracing.

applies_to: "messages ending in Event"

related_aips:
  - AIP-155

rules:
  - id: ORG-002-CORRELATION-ID
    description: Event messages must have correlation_id field
    check_guidance: Check for correlation_id or trace_id in event messages
    violations:
      - "Missing correlation_id entirely"
      - "Using request_id instead of correlation_id"
```

**Using custom standards with Docker:**

```bash
# Mount your standards directory
docker-compose run --rm \
  -v ./my-standards:/app/standards:ro \
  proto-reviewer review /protos/my.proto

# Or set STANDARDS_DIR
export STANDARDS_DIR=/path/to/my-standards
docker-compose up proto-reviewer
```

### Authorization

The server supports optional AD group-based authorization. When `ALLOWED_AD_GROUPS` is set, requests must include an `X-AD-Memberships` header with at least one matching group.

```bash
# Enable authorization
export ALLOWED_AD_GROUPS=platform-team,backend-team

# Start server
docker-compose up proto-reviewer

# Request with authorization header
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -H "X-AD-Memberships: platform-team,other-team" \
  -d '{"proto_content": "..."}'
```

**Trust Model**: The server trusts the `X-AD-Memberships` header. This assumes an upstream gateway/proxy validates the user's identity and sets the header based on validated AD group membership.

### Installation Extras

```bash
pip install -e ".[gemini]"     # Gemini only
pip install -e ".[openai]"     # OpenAI only
pip install -e ".[anthropic]"  # Anthropic only
pip install -e ".[server]"     # FastAPI server
pip install -e ".[mcp]"        # MCP server for IDE integration
pip install -e ".[full]"       # All providers + server + MCP
pip install -e ".[dev]"        # Development dependencies
```

---

## Development

```bash
# Using Docker (recommended)
docker-compose --profile dev up proto-reviewer-dev

# Or locally with virtualenv (macOS)
python3 -m venv venv
source venv/bin/activate
pip install -e ".[full,dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html
```

---

## Limitations

- **Requires API access**: The agent needs access to at least one LLM provider
- **Not a replacement for syntactic linters**: Use alongside `buf lint` and `api-linter`
- **AI limitations**: May occasionally miss issues or flag false positives
- **Proto3 focused**: Primarily designed for proto3 syntax

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Google AIPs](https://google.aip.dev/) for the API design standards
- [Buf](https://buf.build/) for inspiration on proto tooling
- [Google AI](https://ai.google.dev/), [OpenAI](https://openai.com/), and [Anthropic](https://anthropic.com/) for the LLM APIs
