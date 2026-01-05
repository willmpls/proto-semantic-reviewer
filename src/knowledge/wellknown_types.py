"""
Well-known protobuf types reference for semantic proto review.

This module provides guidance on when to use Google's well-known types
and common type mappings based on field semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
import re


@dataclass
class WellKnownType:
    """A well-known protobuf type with usage guidance."""
    full_name: str
    short_name: str
    description: str
    when_to_use: str
    common_field_patterns: list[str]
    bad_alternatives: list[str]
    example: str


# =============================================================================
# Well-Known Types Reference
# =============================================================================

WELL_KNOWN_TYPES: dict[str, WellKnownType] = {}


# -----------------------------------------------------------------------------
# Timestamp
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["Timestamp"] = WellKnownType(
    full_name="google.protobuf.Timestamp",
    short_name="Timestamp",
    description="Represents a point in time independent of any time zone or calendar",
    when_to_use="Any field representing a specific moment in time",
    common_field_patterns=[
        r".*_time$",           # create_time, update_time, expire_time
        r".*_at$",             # created_at, updated_at (though _time is preferred)
        r"^(created|updated|deleted|expires?|start|end|last|first).*",
        r".*timestamp.*",
        r".*date.*time.*",     # datetime fields
        r".*_date$",           # Sometimes dates need time precision
    ],
    bad_alternatives=[
        "string (ISO 8601 format) - loses type safety",
        "int64 (Unix timestamp) - ambiguous precision (seconds vs millis)",
        "int32 (Unix timestamp) - Y2038 problem",
    ],
    example="""
// Good
google.protobuf.Timestamp create_time = 1;
google.protobuf.Timestamp expire_time = 2;

// Bad
string create_time = 1;  // No type safety
int64 created_at_millis = 1;  // Ambiguous, non-standard
""",
)


# -----------------------------------------------------------------------------
# Duration
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["Duration"] = WellKnownType(
    full_name="google.protobuf.Duration",
    short_name="Duration",
    description="Represents a signed, fixed-length span of time",
    when_to_use="Any field representing a length of time or time interval",
    common_field_patterns=[
        r".*duration.*",
        r".*timeout.*",
        r".*ttl.*",            # time-to-live
        r".*_seconds$",        # Indicates duration
        r".*_minutes$",
        r".*_hours$",
        r".*_days$",
        r".*interval.*",
        r".*delay.*",
        r".*period.*",
        r".*wait.*",
        r".*retention.*",
    ],
    bad_alternatives=[
        "int32/int64 with _seconds suffix - loses precision, requires unit convention",
        "float/double - precision issues",
        "string - parsing overhead, no validation",
    ],
    example="""
// Good
google.protobuf.Duration timeout = 1;
google.protobuf.Duration retention_period = 2;

// Bad
int32 timeout_seconds = 1;  // Loses nanosecond precision
int64 ttl_ms = 2;  // Unit ambiguity
""",
)


# -----------------------------------------------------------------------------
# FieldMask
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["FieldMask"] = WellKnownType(
    full_name="google.protobuf.FieldMask",
    short_name="FieldMask",
    description="Represents a set of field paths for partial operations",
    when_to_use="Update operations to specify which fields to modify, or read operations to specify which fields to return",
    common_field_patterns=[
        r".*update_mask.*",
        r".*field_mask.*",
        r".*read_mask.*",
    ],
    bad_alternatives=[
        "repeated string fields - loses validation of field paths",
        "Custom mask message - non-standard, reinventing the wheel",
    ],
    example="""
// Good
message UpdateBookRequest {
  Book book = 1;
  google.protobuf.FieldMask update_mask = 2;
}

// Bad
message UpdateBookRequest {
  Book book = 1;
  repeated string fields_to_update = 2;  // No path validation
}
""",
)


# -----------------------------------------------------------------------------
# Empty
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["Empty"] = WellKnownType(
    full_name="google.protobuf.Empty",
    short_name="Empty",
    description="A message with no fields, used when there's nothing to return",
    when_to_use="Delete operations that don't use soft delete, or any operation with no meaningful response",
    common_field_patterns=[],  # Used as a return type, not a field
    bad_alternatives=[
        "Custom empty message - non-standard, unnecessary duplication",
        "Returning the deleted resource when hard deleting",
    ],
    example="""
// Good
rpc DeleteBook(DeleteBookRequest) returns (google.protobuf.Empty);

// Bad - for hard delete
rpc DeleteBook(DeleteBookRequest) returns (DeleteBookResponse);
message DeleteBookResponse {}  // Just use Empty
""",
)


# -----------------------------------------------------------------------------
# Any
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["Any"] = WellKnownType(
    full_name="google.protobuf.Any",
    short_name="Any",
    description="Contains an arbitrary serialized protocol buffer message along with a type URL",
    when_to_use="When you need to store/transmit arbitrary protobuf messages and the type isn't known at compile time",
    common_field_patterns=[
        r".*payload.*",
        r".*data.*",
        r".*extension.*",
        r".*details.*",        # e.g., error details
    ],
    bad_alternatives=[
        "bytes - loses type information",
        "string (JSON) - loses type safety and efficiency",
    ],
    example="""
// Good - error details pattern
message Status {
  int32 code = 1;
  string message = 2;
  repeated google.protobuf.Any details = 3;
}
""",
)


# -----------------------------------------------------------------------------
# Struct
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["Struct"] = WellKnownType(
    full_name="google.protobuf.Struct",
    short_name="Struct",
    description="Represents a JSON object with dynamic structure",
    when_to_use="When you need to store arbitrary JSON-like data that doesn't have a fixed schema",
    common_field_patterns=[
        r".*metadata.*",
        r".*properties.*",
        r".*attributes.*",
        r".*labels.*",
        r".*config.*",
        r".*settings.*",
        r".*extra.*",
        r".*custom.*",
    ],
    bad_alternatives=[
        "string (JSON) - requires parsing, no partial access",
        "bytes (JSON) - same issues plus encoding ambiguity",
        "map<string, string> - only supports string values",
    ],
    example="""
// Good
message Resource {
  string name = 1;
  google.protobuf.Struct metadata = 2;  // Arbitrary key-value data
}

// Acceptable alternative for simple cases
message Resource {
  string name = 1;
  map<string, string> labels = 2;  // When values are always strings
}
""",
)


# -----------------------------------------------------------------------------
# Wrapper Types (Optional Primitives)
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["StringValue"] = WellKnownType(
    full_name="google.protobuf.StringValue",
    short_name="StringValue",
    description="Wrapper for string to distinguish null from empty string",
    when_to_use="When you need to distinguish between 'not set' and 'set to empty string'",
    common_field_patterns=[],  # Context-dependent
    bad_alternatives=[
        "string with sentinel value like 'NULL' - magic values are error-prone",
        "separate boolean has_field - clutters the message",
    ],
    example="""
// Good - when null vs empty matters
google.protobuf.StringValue middle_name = 1;  // null = unknown, "" = no middle name

// In proto3, often unnecessary - just use string if empty and unset are equivalent
string description = 1;  // Empty and unset both mean "no description"
""",
)

WELL_KNOWN_TYPES["Int32Value"] = WellKnownType(
    full_name="google.protobuf.Int32Value",
    short_name="Int32Value",
    description="Wrapper for int32 to distinguish null from zero",
    when_to_use="When you need to distinguish between 'not set' and 'set to zero'",
    common_field_patterns=[],
    bad_alternatives=[
        "int32 with sentinel value like -1 - magic values are error-prone",
    ],
    example="""
// Good - when null vs zero matters
google.protobuf.Int32Value page_size = 1;  // null = use default, 0 = invalid
""",
)

WELL_KNOWN_TYPES["BoolValue"] = WellKnownType(
    full_name="google.protobuf.BoolValue",
    short_name="BoolValue",
    description="Wrapper for bool to distinguish null from false",
    when_to_use="When you need three states: true, false, and unset/unknown",
    common_field_patterns=[],
    bad_alternatives=[
        "bool - can't distinguish unset from false",
        "enum with UNKNOWN, TRUE, FALSE - non-standard",
    ],
    example="""
// Good - when null vs false matters
google.protobuf.BoolValue is_active = 1;  // null = inherit from parent
""",
)


# -----------------------------------------------------------------------------
# Google Common Types (google.type.*)
# -----------------------------------------------------------------------------
WELL_KNOWN_TYPES["Money"] = WellKnownType(
    full_name="google.type.Money",
    short_name="Money",
    description="Represents an amount of money with currency",
    when_to_use="Any field representing monetary amounts",
    common_field_patterns=[
        r".*price.*",
        r".*cost.*",
        r".*amount.*",         # When monetary
        r".*fee.*",
        r".*balance.*",
        r".*payment.*",
        r".*total.*",          # When monetary
        r".*rate.*",           # Hourly rate, etc.
        r".*salary.*",
        r".*budget.*",
    ],
    bad_alternatives=[
        "double/float - precision loss, floating point issues with money",
        "int64 (cents) - loses currency information, error-prone",
        "string - parsing overhead, no validation",
        "Decimal string - non-standard, requires parsing",
    ],
    example="""
// Good
google.type.Money price = 1;
google.type.Money monthly_budget = 2;

// Bad
double price = 1;  // Floating point errors
int64 price_cents = 1;  // Loses currency, easy to forget to divide
string price = 1;  // Requires parsing, no validation
""",
)

WELL_KNOWN_TYPES["Date"] = WellKnownType(
    full_name="google.type.Date",
    short_name="Date",
    description="Represents a calendar date (year, month, day) without time",
    when_to_use="When you need a date without time component (birthdays, due dates, etc.)",
    common_field_patterns=[
        r".*birth.*date.*",
        r".*due.*date.*",
        r".*start.*date.*",
        r".*end.*date.*",
        r".*effective.*date.*",
        r".*expir.*date.*",    # expiry_date, expiration_date
    ],
    bad_alternatives=[
        "string (YYYY-MM-DD) - no validation",
        "Timestamp - includes unnecessary time component",
        "int32 (YYYYMMDD) - error-prone parsing",
    ],
    example="""
// Good
google.type.Date birth_date = 1;
google.type.Date due_date = 2;

// Bad
string birth_date = 1;  // No validation, format ambiguity
""",
)

WELL_KNOWN_TYPES["TimeOfDay"] = WellKnownType(
    full_name="google.type.TimeOfDay",
    short_name="TimeOfDay",
    description="Represents a time of day without date or time zone",
    when_to_use="Recurring times like business hours, alarm times",
    common_field_patterns=[
        r".*open.*time.*",
        r".*close.*time.*",
        r".*start.*time.*",    # When daily recurring
        r".*alarm.*time.*",
        r".*schedule.*time.*",
    ],
    bad_alternatives=[
        "string (HH:MM) - no validation",
        "int32 (seconds since midnight) - non-intuitive",
    ],
    example="""
// Good
google.type.TimeOfDay opening_time = 1;
google.type.TimeOfDay closing_time = 2;

// Bad
string opening_time = 1;  // Format ambiguity (12h vs 24h)
""",
)

WELL_KNOWN_TYPES["LatLng"] = WellKnownType(
    full_name="google.type.LatLng",
    short_name="LatLng",
    description="Represents a geographic coordinate (latitude and longitude)",
    when_to_use="Any field representing a geographic location",
    common_field_patterns=[
        r".*location.*",
        r".*coordinates?.*",
        r".*position.*",
        r".*geo.*",
        r".*lat.*lng.*",
        r".*latitude.*",
        r".*longitude.*",
    ],
    bad_alternatives=[
        "Two separate double fields - loses semantic grouping",
        "string (lat,lng) - requires parsing",
        "Custom message - non-standard",
    ],
    example="""
// Good
google.type.LatLng location = 1;

// Bad
double latitude = 1;
double longitude = 2;  // Loses grouping, could be assigned independently
""",
)

WELL_KNOWN_TYPES["Color"] = WellKnownType(
    full_name="google.type.Color",
    short_name="Color",
    description="Represents a color in RGBA color space",
    when_to_use="Any field representing a color",
    common_field_patterns=[
        r".*color.*",
        r".*background.*",
        r".*foreground.*",
        r".*tint.*",
    ],
    bad_alternatives=[
        "string (hex) - no validation, multiple formats (#RGB, #RRGGBB, etc.)",
        "int32 (packed RGBA) - non-intuitive, endianness issues",
    ],
    example="""
// Good
google.type.Color background_color = 1;

// Acceptable for simple cases
string color_hex = 1;  // When interop with CSS/web is primary concern
""",
)


# =============================================================================
# Field Pattern Analysis
# =============================================================================

def analyze_field_for_type_recommendation(
    field_name: str,
    current_type: str
) -> Optional[tuple[WellKnownType, str]]:
    """
    Analyze a field name and its current type to recommend a better type.
    
    Returns: (recommended_type, reason) or None if current type seems appropriate
    """
    field_name_lower = field_name.lower()
    current_type_lower = current_type.lower()
    
    # Check each well-known type's patterns
    for wkt_name, wkt in WELL_KNOWN_TYPES.items():
        for pattern in wkt.common_field_patterns:
            if re.match(pattern, field_name_lower):
                # Check if already using the correct type
                if wkt.short_name.lower() in current_type_lower:
                    return None
                if wkt.full_name.lower() in current_type_lower:
                    return None
                
                # Special handling for specific types
                if wkt_name == "Timestamp":
                    if current_type_lower in ["string", "int32", "int64"]:
                        return (wkt, f"Field '{field_name}' appears to represent a point in time")
                
                elif wkt_name == "Duration":
                    if current_type_lower in ["string", "int32", "int64", "float", "double"]:
                        return (wkt, f"Field '{field_name}' appears to represent a time duration")
                
                elif wkt_name == "Money":
                    if current_type_lower in ["float", "double", "int32", "int64", "string"]:
                        return (wkt, f"Field '{field_name}' appears to represent a monetary amount")
                
                elif wkt_name == "Date":
                    if current_type_lower in ["string", "int32"]:
                        return (wkt, f"Field '{field_name}' appears to represent a calendar date")
                
                elif wkt_name == "LatLng":
                    if current_type_lower in ["string"]:
                        return (wkt, f"Field '{field_name}' appears to represent a geographic location")
    
    return None


def get_type_info(type_name: str) -> Optional[WellKnownType]:
    """Get information about a well-known type by name."""
    # Try exact match
    if type_name in WELL_KNOWN_TYPES:
        return WELL_KNOWN_TYPES[type_name]
    
    # Try case-insensitive match
    type_name_lower = type_name.lower()
    for name, wkt in WELL_KNOWN_TYPES.items():
        if name.lower() == type_name_lower:
            return wkt
        if wkt.full_name.lower() == type_name_lower:
            return wkt
    
    return None


def get_all_type_recommendations() -> str:
    """Get a formatted summary of all type recommendations."""
    lines = ["# Well-Known Types Reference", ""]
    
    for name, wkt in WELL_KNOWN_TYPES.items():
        lines.append(f"## {wkt.full_name}")
        lines.append(f"**When to use:** {wkt.when_to_use}")
        
        if wkt.common_field_patterns:
            lines.append("**Common field patterns:** " + ", ".join(
                p.replace(".*", "*").replace("$", "")
                for p in wkt.common_field_patterns[:5]
            ))
        
        if wkt.bad_alternatives:
            lines.append("**Avoid:**")
            for alt in wkt.bad_alternatives[:3]:
                lines.append(f"  - {alt}")
        
        lines.append("")
    
    return "\n".join(lines)
