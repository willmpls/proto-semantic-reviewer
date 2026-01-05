"""
Proto Semantic Reviewer - CLI Entry Point.

Usage:
    python -m src review path/to/file.proto
    python -m src review - < file.proto
    python -m src review path/to/file.proto --format json
    python -m src server --port 8000
    python -m src mcp                # MCP server (stdio mode)
    python -m src mcp --http         # MCP server (http mode)
"""

import argparse
import json
import sys
from pathlib import Path

from .agent import review_proto, review_proto_structured


def read_proto_content(path_or_stdin: str) -> str:
    """Read proto content from file or stdin."""
    if path_or_stdin == "-":
        return sys.stdin.read()

    path = Path(path_or_stdin)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return path.read_text()


def format_structured_output(result: dict, output_format: str) -> str:
    """Format the structured result for output."""
    if output_format == "json":
        return json.dumps(result, indent=2)

    # Text format
    lines = []

    if "error" in result and result["error"]:
        lines.append(f"Error: {result['error']}")
        if "raw_response" in result:
            lines.append("\nRaw response:")
            lines.append(result["raw_response"])
        return "\n".join(lines)

    issues = result.get("issues", [])
    summary = result.get("summary", "")

    if not issues:
        lines.append("No semantic issues found.")
    else:
        # Group by severity
        errors = [i for i in issues if i.get("severity") == "error"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        suggestions = [i for i in issues if i.get("severity") == "suggestion"]

        lines.append(f"Found {len(issues)} issue(s): {len(errors)} error(s), {len(warnings)} warning(s), {len(suggestions)} suggestion(s)")
        lines.append("")

        for severity, items in [("error", errors), ("warning", warnings), ("suggestion", suggestions)]:
            if items:
                icon = {"error": "[ERROR]", "warning": "[WARNING]", "suggestion": "[SUGGESTION]"}[severity]
                for item in items:
                    lines.append(f"{icon} {item.get('location', 'unknown')}")
                    lines.append(f"  Issue: {item.get('issue', 'No description')}")
                    lines.append(f"  Recommendation: {item.get('recommendation', 'None')}")
                    ref = item.get("reference") or item.get("aip")
                    if ref:
                        lines.append(f"  Reference: {ref}")
                    lines.append("")

    if summary:
        lines.append(f"Summary: {summary}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Review Protocol Buffer definitions for semantic correctness",
        prog="proto-semantic-reviewer",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Review command
    review_parser = subparsers.add_parser("review", help="Review a proto file")
    review_parser.add_argument(
        "proto_file",
        help="Path to the .proto file to review, or '-' for stdin",
    )
    review_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    review_parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "anthropic"],
        default=None,
        help="Model provider. Auto-detected from API keys if not specified.",
    )
    review_parser.add_argument(
        "--model",
        default=None,
        help="Specific model name. Uses provider's default if not specified.",
    )
    review_parser.add_argument(
        "--focus",
        choices=["event", "rest"],
        default="event",
        help="Review focus: 'event' for event messages, 'rest' for REST APIs (default: event)",
    )
    review_parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw model response instead of structured format",
    )

    # Server command
    server_parser = subparsers.add_parser("server", help="Run the HTTP review server")
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )

    # MCP server command
    mcp_parser = subparsers.add_parser("mcp", help="Run the MCP server for IDE integration")
    mcp_parser.add_argument(
        "--http",
        action="store_true",
        help="Use HTTP transport instead of stdio (default: stdio)",
    )
    mcp_parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port for HTTP transport (default: 3000, ignored for stdio)",
    )

    # List AIPs command
    subparsers.add_parser("list-aips", help="List available AIP standards")

    # Lookup AIP command
    lookup_parser = subparsers.add_parser("lookup-aip", help="Look up a specific AIP")
    lookup_parser.add_argument("aip_number", type=int, help="AIP number to look up")

    # List organizational standards command
    subparsers.add_parser("list-org-standards", help="List available organizational standards")

    # Lookup organizational standard command
    lookup_org_parser = subparsers.add_parser("lookup-org-standard", help="Look up a specific organizational standard")
    lookup_org_parser.add_argument("standard_id", help="Organizational standard ID (e.g., ORG-001)")

    args = parser.parse_args()

    if args.command == "review":
        try:
            proto_content = read_proto_content(args.proto_file)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            if args.raw:
                result = review_proto(
                    proto_content,
                    provider=args.provider,
                    model_name=args.model,
                    focus=args.focus,
                )
                print(result)
            else:
                result = review_proto_structured(
                    proto_content,
                    provider=args.provider,
                    model_name=args.model,
                    focus=args.focus,
                )
                output = format_structured_output(result, args.format)
                print(output)

                # Exit with error code if there are errors
                if result.get("issues"):
                    errors = [i for i in result["issues"] if i.get("severity") == "error"]
                    if errors:
                        sys.exit(1)
        except ValueError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)
        except ImportError as e:
            print(f"Missing dependency: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error during review: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "server":
        try:
            from .server import run_server
            print(f"Starting server on http://{args.host}:{args.port}")
            print(f"API docs available at http://{args.host}:{args.port}/docs")
            run_server(host=args.host, port=args.port)
        except ImportError as e:
            print(f"Server dependencies not installed: {e}", file=sys.stderr)
            print("Install with: pip install proto-semantic-reviewer[server]", file=sys.stderr)
            sys.exit(1)

    elif args.command == "mcp":
        try:
            from .mcp_server import run_mcp_server
            transport = "http" if args.http else "stdio"
            if transport == "http":
                print(f"Starting MCP server on http://localhost:{args.port}", file=sys.stderr)
            run_mcp_server(transport=transport, port=args.port)
        except ImportError as e:
            print(f"MCP dependencies not installed: {e}", file=sys.stderr)
            print("Install with: pip install proto-semantic-reviewer[mcp]", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list-aips":
        from .tools import list_available_aips
        print(list_available_aips())

    elif args.command == "lookup-aip":
        from .tools import lookup_aip
        print(lookup_aip(args.aip_number))

    elif args.command == "list-org-standards":
        from .tools import list_org_standards
        print(list_org_standards())

    elif args.command == "lookup-org-standard":
        from .tools import lookup_org_standard
        print(lookup_org_standard(args.standard_id))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
