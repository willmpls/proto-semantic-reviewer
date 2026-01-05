"""
MCP (Model Context Protocol) server for the Proto Semantic Reviewer.

Exposes the proto reviewer as MCP tools for IDE integration (IntelliJ, VS Code, etc.).

Usage:
    python -m src mcp              # STDIO mode (default, for local IDE plugins)
    python -m src mcp --http       # HTTP mode (for remote/network access)
    python -m src mcp --port 3000  # HTTP with custom port
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Dict

# Configure logging (critical for STDIO mode - never use print())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _create_mcp(host: str = "127.0.0.1", port: int = 8000):
    """Create and configure the MCP FastMCP instance."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "mcp package not installed. Install with: pip install proto-semantic-reviewer[mcp]"
        )

    mcp = FastMCP(
        "Proto Semantic Reviewer",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,  # Simpler for testing, no session tracking required
    )
    _register_tools(mcp)
    return mcp


def _register_tools(mcp):
    """Register all MCP tools."""

    @mcp.tool()
    async def review_proto(
        content: str,
        focus: str = "event",
        provider: str | None = None,
    ) -> dict[str, Any]:
        """
        Review a Protocol Buffer definition for semantic issues.

        Analyzes the proto content against Google AIP standards and event messaging
        best practices, returning structured issues with recommendations.

        Args:
            content: The .proto file content to review
            focus: Review focus - 'event' for event messages (default), 'rest' for REST APIs
            provider: LLM provider to use (gemini, openai, anthropic). Auto-detected if not specified.

        Returns:
            Dictionary with 'issues' list, 'summary', 'provider', and 'model' fields.
            Each issue has: severity, location, issue, recommendation, reference.
        """
        logger.info(f"Reviewing proto ({len(content)} bytes, focus={focus})")

        from .agent import review_proto_structured
        from .adapters import create_adapter

        try:
            result = review_proto_structured(
                proto_content=content,
                provider=provider,
                focus=focus,
            )

            # Get adapter info for response
            adapter = create_adapter(provider=provider)

            return {
                "issues": result.get("issues", []),
                "summary": result.get("summary", ""),
                "provider": adapter.provider_name,
                "model": getattr(adapter, "model_name", adapter.default_model),
                "error": result.get("error"),
            }

        except Exception as e:
            logger.error(f"Review failed: {e}")
            return {
                "issues": [],
                "summary": "",
                "provider": "unknown",
                "model": "unknown",
                "error": str(e),
            }

    @mcp.tool()
    def list_org_standards() -> list[dict[str, Any]]:
        """
        List available organizational standards (ORG-001, etc.).

        Returns all organization-specific semantic standards that extend
        the universal AIP standards with additional requirements.

        Returns:
            List of standards with id, title, and summary for each.
        """
        from .knowledge.org_standards import ORG_STANDARDS

        return [
            {
                "id": std.id,
                "title": std.title,
                "summary": std.summary.strip(),
                "applies_to": std.applies_to,
            }
            for std in ORG_STANDARDS.values()
        ]

    @mcp.tool()
    def list_aips() -> list[dict[str, str]]:
        """
        List available AIP (API Improvement Proposal) standards.

        Returns all Google AIP standards that the reviewer can reference,
        covering proto best practices for both events and REST APIs.

        Returns:
            List of AIPs with number, title, and summary for each.
        """
        from .knowledge.aip_standards import AIP_STANDARDS

        return [
            {
                "aip": aip_num,
                "title": aip["title"],
                "summary": aip["summary"],
            }
            for aip_num, aip in AIP_STANDARDS.items()
        ]

    @mcp.tool()
    def lookup_org_standard(standard_id: str) -> dict[str, Any]:
        """
        Look up detailed guidance for a specific organizational standard.

        Args:
            standard_id: The standard ID (e.g., 'ORG-001')

        Returns:
            Full standard details including title, summary, rules, and examples.
        """
        from .knowledge.org_standards import ORG_STANDARDS

        std_id = standard_id.upper()
        if std_id not in ORG_STANDARDS:
            return {"error": f"Unknown standard: {standard_id}"}

        std = ORG_STANDARDS[std_id]
        return {
            "id": std.id,
            "title": std.title,
            "summary": std.summary.strip(),
            "applies_to": std.applies_to,
            "related_aips": std.related_aips,
            "rules": [
                {
                    "id": rule.id,
                    "description": rule.description,
                    "check_guidance": rule.check_guidance,
                    "common_violations": rule.common_violations,
                }
                for rule in std.semantic_rules
            ],
        }

    @mcp.tool()
    def lookup_aip(aip_number: int) -> dict[str, Any]:
        """
        Look up detailed guidance for a specific AIP.

        Args:
            aip_number: The AIP number (e.g., 142 for timestamps, 180 for enums)

        Returns:
            Full AIP details including title, summary, guidance, and examples.
        """
        from .knowledge.aip_standards import AIP_STANDARDS

        aip_key = str(aip_number)
        if aip_key not in AIP_STANDARDS:
            return {"error": f"Unknown AIP: {aip_number}"}

        aip = AIP_STANDARDS[aip_key]
        return {
            "aip": aip_number,
            "title": aip["title"],
            "summary": aip["summary"],
            "guidance": aip.get("guidance", ""),
            "key_points": aip.get("key_points", []),
            "examples": aip.get("examples", {}),
        }


def run_mcp_server(transport: str = "stdio", host: str = "0.0.0.0", port: int = 3000):
    """
    Run the MCP server.

    Args:
        transport: Transport mode - 'stdio' for local IDE plugins, 'http' for network access
        host: Host to bind to for HTTP transport (default: 0.0.0.0)
        port: Port number for HTTP transport (ignored for stdio)
    """
    mcp = _create_mcp(host=host, port=port)
    logger.info(f"Starting MCP server (transport={transport})")

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        logger.info(f"HTTP server starting on http://{host}:{port}/mcp")
        mcp.run(transport="streamable-http")
    else:
        raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'http'.")
