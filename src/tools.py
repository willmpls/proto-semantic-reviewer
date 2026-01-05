"""
Tools for the proto semantic review agent.

These tools provide access to the bundled AIP knowledge base
and organizational standards without requiring any external API calls.
"""

from typing import Optional
from .knowledge import (
    get_aip_summary,
    get_all_aips_summary,
    get_type_info,
    get_all_type_recommendations,
    analyze_field_for_type_recommendation,
    get_semantic_rules_for_concept,
)
from .knowledge.org_standards import (
    get_org_standard_summary,
    get_all_org_standards_summary,
)


def lookup_aip(aip_number: int) -> str:
    """
    Look up guidance for a specific AIP standard.
    
    Args:
        aip_number: The AIP number (e.g., 132 for pagination, 142 for timestamps)
    
    Returns:
        Detailed guidance for the specified AIP including semantic rules,
        common violations, and examples.
    """
    return get_aip_summary(aip_number)


def list_available_aips() -> str:
    """
    List all AIP standards available in the knowledge base.
    
    Returns:
        A summary of all available AIPs with their numbers and titles.
    """
    return get_all_aips_summary()


def lookup_type_recommendation(semantic_concept: str) -> str:
    """
    Look up the recommended protobuf type for a semantic concept.
    
    Args:
        semantic_concept: The concept to look up (e.g., "timestamp", "money", 
                         "duration", "location")
    
    Returns:
        Information about the recommended well-known type, when to use it,
        what to avoid, and examples.
    """
    type_info = get_type_info(semantic_concept)
    
    if type_info:
        lines = [
            f"# {type_info.full_name}",
            "",
            f"**Description:** {type_info.description}",
            "",
            f"**When to use:** {type_info.when_to_use}",
            "",
        ]
        
        if type_info.common_field_patterns:
            lines.append("**Common field name patterns:**")
            for pattern in type_info.common_field_patterns:
                readable = pattern.replace(".*", "*").replace("$", "").replace("^", "")
                lines.append(f"  - {readable}")
            lines.append("")
        
        if type_info.bad_alternatives:
            lines.append("**Avoid these alternatives:**")
            for alt in type_info.bad_alternatives:
                lines.append(f"  - {alt}")
            lines.append("")
        
        lines.append("**Example:**")
        lines.append(f"```protobuf{type_info.example}```")
        
        return "\n".join(lines)
    
    # If not found by name, try to find related rules
    related = get_semantic_rules_for_concept(semantic_concept)
    if related:
        lines = [f"# Related guidance for '{semantic_concept}'", ""]
        for aip_num, rule in related:
            lines.append(f"## AIP-{aip_num}: {rule.id}")
            lines.append(f"{rule.description}")
            lines.append(f"**Check:** {rule.check_guidance}")
            lines.append("")
        return "\n".join(lines)
    
    return f"No specific type recommendation found for '{semantic_concept}'. Consider checking related AIPs with list_available_aips()."


def analyze_field_semantics(field_name: str, field_type: str) -> str:
    """
    Analyze whether a field's type matches its semantic intent based on naming.
    
    Args:
        field_name: The name of the field (e.g., "create_time", "price")
        field_type: The current type of the field (e.g., "string", "int64")
    
    Returns:
        Analysis of whether the type is appropriate, with recommendations
        if a better type exists.
    """
    recommendation = analyze_field_for_type_recommendation(field_name, field_type)
    
    if recommendation:
        wkt, reason = recommendation
        lines = [
            f"# Type Recommendation for '{field_name}'",
            "",
            f"**Current type:** {field_type}",
            f"**Recommended type:** {wkt.full_name}",
            "",
            f"**Reason:** {reason}",
            "",
            f"**Why {wkt.short_name}:** {wkt.when_to_use}",
            "",
        ]
        
        if wkt.bad_alternatives:
            lines.append("**Problems with current approach:**")
            for alt in wkt.bad_alternatives:
                if field_type.lower() in alt.lower():
                    lines.append(f"  - {alt}")
            lines.append("")
        
        lines.append("**Example:**")
        lines.append(f"```protobuf{wkt.example}```")
        
        return "\n".join(lines)
    
    return f"The type '{field_type}' appears appropriate for field '{field_name}'. No semantic mismatch detected."


def get_standard_fields_guidance() -> str:
    """
    Get guidance on standard fields that resources should include.
    
    Returns:
        Information about standard resource fields per AIP-148 and related AIPs.
    """
    return """# Standard Resource Fields (AIP-148)

Resources should typically include these standard fields:

## Required for most resources

### name (string)
- The resource's unique identifier
- Format: `{collection}/{resource_id}` or full path
- Should be field number 1
- Annotate with `[(google.api.field_behavior) = IDENTIFIER]`

### create_time (google.protobuf.Timestamp)
- When the resource was created
- Should be OUTPUT_ONLY
- Use `create_time`, not `created_at` or `creation_time`

### update_time (google.protobuf.Timestamp)
- When the resource was last modified
- Should be OUTPUT_ONLY
- Use `update_time`, not `updated_at` or `modification_time`

## Often needed

### delete_time (google.protobuf.Timestamp)
- When the resource was soft-deleted
- Only present if the resource supports soft delete
- Use instead of boolean `is_deleted`

### etag (string)
- For optimistic concurrency control
- Include if resource supports concurrent updates
- Clients use this with If-Match for safe updates

### uid (string)
- System-generated unique identifier
- Immutable, never reused
- Use instead of separate `uuid` field

## For specific patterns

### display_name (string)
- Human-readable name
- Distinct from `name` (the resource identifier)

### description (string)
- Longer description of the resource

### labels (map<string, string>)
- User-defined key-value metadata

### annotations (map<string, string>)
- Larger, less structured metadata
"""


def get_method_pattern_guidance(method_type: str) -> str:
    """
    Get guidance on request/response patterns for standard methods.
    
    Args:
        method_type: The method type (Get, List, Create, Update, Delete)
    
    Returns:
        Detailed guidance on the expected request and response structure.
    """
    method_type_lower = method_type.lower()
    
    if method_type_lower == "get":
        return get_aip_summary(131)
    elif method_type_lower == "list":
        return get_aip_summary(132)
    elif method_type_lower == "create":
        return get_aip_summary(133)
    elif method_type_lower == "update":
        return get_aip_summary(134)
    elif method_type_lower == "delete":
        return get_aip_summary(135)
    else:
        return f"Unknown method type: {method_type}. Standard methods are: Get, List, Create, Update, Delete."


# =============================================================================
# Event-Focused Tools
# =============================================================================

def get_event_field_guidance() -> str:
    """
    Get guidance on standard event message fields.

    Returns:
        Information about standard event fields like event_id, event_time,
        correlation_id, etc.
    """
    return """# Standard Event Message Fields

## Required Fields

### event_id (string)
- Unique identifier for this event instance
- Should be UUID or similar globally unique ID
- Immutable - assigned at creation time
- Used for idempotency and deduplication
- Different from entity IDs (e.g., order_id)

### event_time (google.protobuf.Timestamp)
- When the event occurred (business time)
- Should be REQUIRED or have OUTPUT_ONLY behavior
- Use event_time or occurred_at, not just "timestamp"
- Distinct from published_at (when sent to message bus)

### event_type (string)
- Fully qualified type name
- Example: "com.example.orders.v1.OrderCreated"
- Enables routing and polymorphic handling
- Consider including in all events for clarity

## Recommended Fields

### correlation_id (string)
- Links related events across a transaction/saga
- Propagated from initial request through all derived events
- Essential for debugging distributed systems

### causation_id (string)
- ID of the event that directly caused this event
- Enables event chain reconstruction
- Different from correlation_id (which spans entire saga)

### trace_id / span_id (string)
- OpenTelemetry/distributed tracing identifiers
- Enables end-to-end request tracing
- Format: W3C Trace Context or similar

### source (string)
- Service or system that produced the event
- Examples: "order-service", "payment-gateway"
- Helps identify event origin in multi-service systems

### schema_version (int32)
- Version of the event schema
- Helps consumers handle schema evolution
- Increment for breaking changes

## Example Event Message

```protobuf
message OrderCreatedEvent {
  // Identity
  string event_id = 1;
  string event_type = 2;  // "com.example.orders.v1.OrderCreated"

  // Timing
  google.protobuf.Timestamp event_time = 3;
  google.protobuf.Timestamp published_at = 4;

  // Correlation
  string correlation_id = 5;
  string causation_id = 6;
  string trace_id = 7;
  string span_id = 8;

  // Metadata
  string source = 9;
  int32 schema_version = 10;

  // Payload
  Order order = 11;
}
```

## Common Anti-Patterns

- Missing event_id (can't deduplicate)
- Using entity ID as event ID (confuses identity)
- String timestamps instead of google.protobuf.Timestamp
- No correlation/causation tracking
- Enum without UNSPECIFIED = 0
"""


def analyze_event_semantics(message_name: str, field_list: str) -> str:
    """
    Analyze an event message for semantic correctness.

    Args:
        message_name: The name of the event message
        field_list: Comma-separated list of field names in the message

    Returns:
        Analysis of the event message structure with recommendations.
    """
    fields = [f.strip().lower() for f in field_list.split(",")]
    issues = []
    suggestions = []
    good = []

    # Check for event_id
    has_event_id = any(f in ["event_id", "eventid", "id", "message_id"] for f in fields)
    if not has_event_id:
        issues.append("Missing event_id - events need unique identifiers for idempotency")
    else:
        good.append("Has event identifier field")

    # Check for event_time
    has_time = any("time" in f or "timestamp" in f or "_at" in f for f in fields)
    if not has_time:
        issues.append("Missing event timestamp (event_time, occurred_at, etc.)")
    else:
        good.append("Has timestamp field")

    # Check for correlation
    has_correlation = any(f in ["correlation_id", "correlationid", "trace_id", "request_id"] for f in fields)
    if not has_correlation:
        suggestions.append("Consider adding correlation_id for distributed tracing")

    # Check for source/origin
    has_source = any(f in ["source", "origin", "producer", "service"] for f in fields)
    if not has_source:
        suggestions.append("Consider adding source field to identify event origin")

    # Check naming convention
    if not message_name.endswith(("Event", "Notification", "Message", "Command")):
        suggestions.append(f"Consider naming convention: {message_name}Event or similar")

    # Check for version
    has_version = any("version" in f for f in fields)
    if not has_version:
        suggestions.append("Consider schema_version for future evolution")

    # Build result
    result = f"# Analysis of {message_name}\n\n"
    result += f"Fields analyzed: {', '.join(fields)}\n\n"

    if good:
        result += "## Good Patterns\n"
        for g in good:
            result += f"- {g}\n"
        result += "\n"

    if issues:
        result += "## Issues\n"
        for issue in issues:
            result += f"- {issue}\n"
        result += "\n"

    if suggestions:
        result += "## Suggestions\n"
        for sug in suggestions:
            result += f"- {sug}\n"
        result += "\n"

    if not issues and not suggestions:
        result += "No significant issues detected. Event structure looks good.\n"

    return result


def lookup_org_standard(standard_id: str) -> str:
    """
    Look up guidance for a specific organizational standard.

    Args:
        standard_id: The org standard ID (e.g., 'ORG-001' for event identification)

    Returns:
        Detailed guidance for the specified organizational standard.
    """
    return get_org_standard_summary(standard_id)


def list_org_standards() -> str:
    """
    List all organizational standards available.

    Returns:
        A summary of all available organizational standards.
    """
    return get_all_org_standards_summary()


# =============================================================================
# Tool Functions Registry
# =============================================================================

TOOL_FUNCTIONS = {
    # AIP-based tools (universal standards)
    "lookup_aip": lookup_aip,
    "list_available_aips": list_available_aips,
    "lookup_type_recommendation": lookup_type_recommendation,
    "analyze_field_semantics": analyze_field_semantics,
    "get_standard_fields_guidance": get_standard_fields_guidance,
    "get_method_pattern_guidance": get_method_pattern_guidance,
    # Event analysis tools
    "get_event_field_guidance": get_event_field_guidance,
    "analyze_event_semantics": analyze_event_semantics,
    # Organizational standards (custom rules)
    "lookup_org_standard": lookup_org_standard,
    "list_org_standards": list_org_standards,
}
