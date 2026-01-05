#!/usr/bin/env python3
"""
Example usage of the proto semantic reviewer.

This script demonstrates how to use the reviewer programmatically.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import review_proto, review_proto_structured
from src.tools import (
    lookup_aip,
    analyze_field_semantics,
    lookup_type_recommendation,
)


def example_tool_usage():
    """Demonstrate using the tools directly."""
    print("=" * 60)
    print("Example: Using tools directly")
    print("=" * 60)
    
    # Look up an AIP
    print("\n--- Looking up AIP-142 (Timestamps) ---")
    print(lookup_aip(142)[:500] + "...")
    
    # Analyze a field
    print("\n--- Analyzing 'created_at' as string ---")
    print(analyze_field_semantics("created_at", "string"))
    
    # Get type recommendation
    print("\n--- Looking up 'money' type recommendation ---")
    print(lookup_type_recommendation("money"))


def example_review():
    """Demonstrate reviewing a proto file."""
    print("\n" + "=" * 60)
    print("Example: Reviewing a proto file")
    print("=" * 60)
    
    # Check if API key is set
    if not os.environ.get("GOOGLE_API_KEY"):
        print("\nNote: Set GOOGLE_API_KEY environment variable to run the full review.")
        print("Skipping API-based review example.")
        return
    
    sample_proto = '''
syntax = "proto3";

package example.v1;

message User {
  string id = 1;
  string name = 2;
  string email = 3;
  double account_balance = 4;
  string created_at = 5;
  int32 session_timeout_seconds = 6;
}

message GetUserRequest {
  int64 user_id = 1;
}

message ListUsersRequest {
  int32 offset = 1;
  int32 limit = 2;
}

message ListUsersResponse {
  repeated User items = 1;
  bool has_more = 2;
}
'''
    
    print("\nProto to review:")
    print(sample_proto)
    
    print("\nRunning semantic review...")
    result = review_proto_structured(sample_proto)
    
    print("\nReview results:")
    import json
    print(json.dumps(result, indent=2))


def main():
    """Run examples."""
    example_tool_usage()
    example_review()


if __name__ == "__main__":
    main()
