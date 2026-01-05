"""
Provider-agnostic tool declarations for the proto semantic reviewer.

Tools are defined using JSON Schema format for portability across providers.
"""

from .adapters.base import ToolDeclaration


TOOL_DECLARATIONS: list[ToolDeclaration] = [
    ToolDeclaration(
        name="lookup_aip",
        description="Look up guidance for a specific AIP (API Improvement Proposal) standard",
        parameters={
            "type": "object",
            "properties": {
                "aip_number": {
                    "type": "integer",
                    "description": "The AIP number (e.g., 132 for pagination, 142 for timestamps)",
                },
            },
            "required": ["aip_number"],
        },
    ),
    ToolDeclaration(
        name="list_available_aips",
        description="List all AIP standards available in the knowledge base",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    ToolDeclaration(
        name="lookup_type_recommendation",
        description="Look up the recommended protobuf type for a semantic concept",
        parameters={
            "type": "object",
            "properties": {
                "semantic_concept": {
                    "type": "string",
                    "description": "The concept to look up (e.g., 'timestamp', 'money', 'duration', 'location')",
                },
            },
            "required": ["semantic_concept"],
        },
    ),
    ToolDeclaration(
        name="analyze_field_semantics",
        description="Analyze whether a field's type matches its semantic intent based on naming",
        parameters={
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "description": "The name of the field (e.g., 'create_time', 'price')",
                },
                "field_type": {
                    "type": "string",
                    "description": "The current type of the field (e.g., 'string', 'int64')",
                },
            },
            "required": ["field_name", "field_type"],
        },
    ),
    ToolDeclaration(
        name="get_standard_fields_guidance",
        description="Get guidance on standard fields that resources should include (per AIP-148)",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    ToolDeclaration(
        name="get_method_pattern_guidance",
        description="Get guidance on request/response patterns for standard methods",
        parameters={
            "type": "object",
            "properties": {
                "method_type": {
                    "type": "string",
                    "description": "The method type: Get, List, Create, Update, or Delete",
                },
            },
            "required": ["method_type"],
        },
    ),
    # Event analysis tools
    ToolDeclaration(
        name="get_event_field_guidance",
        description="Get guidance on standard event message fields (event_id, event_time, correlation_id, etc.)",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    ToolDeclaration(
        name="analyze_event_semantics",
        description="Analyze an event message for semantic correctness",
        parameters={
            "type": "object",
            "properties": {
                "message_name": {
                    "type": "string",
                    "description": "The name of the event message",
                },
                "field_list": {
                    "type": "string",
                    "description": "Comma-separated list of field names in the message",
                },
            },
            "required": ["message_name", "field_list"],
        },
    ),
    # Organizational standards tools
    ToolDeclaration(
        name="lookup_org_standard",
        description="Look up guidance for a specific organizational standard",
        parameters={
            "type": "object",
            "properties": {
                "standard_id": {
                    "type": "string",
                    "description": "The organizational standard ID (e.g., 'ORG-001' for event identification)",
                },
            },
            "required": ["standard_id"],
        },
    ),
    ToolDeclaration(
        name="list_org_standards",
        description="List all organizational standards available",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
]
