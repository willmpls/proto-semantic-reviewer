"""
Tests for the proto semantic reviewer.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.knowledge import (
    get_aip,
    get_aip_summary,
    get_all_aips_summary,
    analyze_field_for_type_recommendation,
    get_type_info,
)
from src.tools import (
    lookup_aip,
    list_available_aips,
    lookup_type_recommendation,
    analyze_field_semantics,
    get_standard_fields_guidance,
    get_method_pattern_guidance,
)
from src.agent import ReviewResult, ReviewContext


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestAIPKnowledge:
    """Tests for the AIP knowledge base."""

    def test_get_aip_exists(self):
        """Test that we can retrieve existing AIPs."""
        aip = get_aip(132)
        assert aip is not None
        assert aip.number == 132
        assert aip.title == "Standard Methods: List"
        assert len(aip.semantic_rules) > 0

    def test_get_aip_not_exists(self):
        """Test that non-existent AIPs return None."""
        aip = get_aip(9999)
        assert aip is None

    def test_get_aip_summary(self):
        """Test AIP summary formatting."""
        summary = get_aip_summary(142)
        assert "AIP-142" in summary
        assert "Timestamp" in summary
        assert "Duration" in summary

    def test_get_all_aips_summary(self):
        """Test listing all AIPs."""
        summary = get_all_aips_summary()
        assert "AIP-132" in summary
        assert "AIP-142" in summary
        assert "AIP-148" in summary

    def test_key_aips_present(self):
        """Test that all key AIPs are in the knowledge base."""
        # Only check AIPs that are actually bundled in the standards/aips/ directory
        key_aips = [126, 132, 140, 141, 142, 143, 144, 145, 146, 148, 155, 158, 180, 202, 203, 213, 216]
        for aip_num in key_aips:
            aip = get_aip(aip_num)
            assert aip is not None, f"AIP-{aip_num} should be in knowledge base"


class TestWellKnownTypes:
    """Tests for well-known type recommendations."""

    def test_get_timestamp_info(self):
        """Test getting Timestamp type info."""
        info = get_type_info("Timestamp")
        assert info is not None
        assert info.full_name == "google.protobuf.Timestamp"

    def test_get_money_info(self):
        """Test getting Money type info."""
        info = get_type_info("Money")
        assert info is not None
        assert info.full_name == "google.type.Money"

    def test_analyze_timestamp_field(self):
        """Test that timestamp fields are detected."""
        result = analyze_field_for_type_recommendation("create_time", "string")
        assert result is not None
        wkt, reason = result
        assert wkt.short_name == "Timestamp"

    def test_analyze_money_field(self):
        """Test that money fields are detected."""
        result = analyze_field_for_type_recommendation("price", "double")
        assert result is not None
        wkt, reason = result
        assert wkt.short_name == "Money"

    def test_analyze_duration_field(self):
        """Test that duration fields are detected."""
        result = analyze_field_for_type_recommendation("timeout_seconds", "int32")
        assert result is not None
        wkt, reason = result
        assert wkt.short_name == "Duration"

    def test_analyze_correct_type(self):
        """Test that correct types don't trigger recommendations."""
        result = analyze_field_for_type_recommendation("create_time", "google.protobuf.Timestamp")
        assert result is None

    def test_analyze_non_matching_field(self):
        """Test that unrelated fields don't trigger recommendations."""
        result = analyze_field_for_type_recommendation("display_name", "string")
        assert result is None


class TestTools:
    """Tests for the agent tools."""

    def test_lookup_aip(self):
        """Test the lookup_aip tool."""
        result = lookup_aip(132)
        assert "AIP-132" in result
        assert "List" in result
        assert "pagination" in result.lower()

    def test_lookup_aip_not_found(self):
        """Test lookup_aip with non-existent AIP."""
        result = lookup_aip(9999)
        assert "not found" in result.lower()

    def test_list_available_aips(self):
        """Test the list_available_aips tool."""
        result = list_available_aips()
        assert "AIP-132" in result
        assert "AIP-142" in result

    def test_lookup_type_recommendation(self):
        """Test the lookup_type_recommendation tool."""
        result = lookup_type_recommendation("timestamp")
        assert "google.protobuf.Timestamp" in result

    def test_analyze_field_semantics_mismatch(self):
        """Test analyze_field_semantics with type mismatch."""
        result = analyze_field_semantics("created_at", "string")
        assert "Timestamp" in result
        assert "Recommend" in result or "recommend" in result

    def test_analyze_field_semantics_ok(self):
        """Test analyze_field_semantics with correct type."""
        result = analyze_field_semantics("display_name", "string")
        assert "appropriate" in result.lower()

    def test_get_standard_fields_guidance(self):
        """Test the standard fields guidance tool."""
        result = get_standard_fields_guidance()
        assert "create_time" in result
        assert "update_time" in result
        assert "name" in result

    def test_get_method_pattern_guidance(self):
        """Test the method pattern guidance tool."""
        result = get_method_pattern_guidance("List")
        assert "page_size" in result or "pagination" in result.lower()


class TestFixtures:
    """Tests using the fixture proto files."""

    def test_good_example_exists(self):
        """Test that the good example fixture exists."""
        path = FIXTURES_DIR / "good_example.proto"
        assert path.exists()
        content = path.read_text()
        assert "google.protobuf.Timestamp" in content
        assert "create_time" in content

    def test_bad_example_exists(self):
        """Test that the bad example fixture exists."""
        path = FIXTURES_DIR / "bad_example.proto"
        assert path.exists()
        content = path.read_text()
        # Should have various issues
        assert "double price" in content  # Money as double
        assert "string created_at" in content  # Timestamp as string

    def test_bad_example_has_timestamp_issues(self):
        """Test that we can detect timestamp issues in the bad example."""
        path = FIXTURES_DIR / "bad_example.proto"
        content = path.read_text()

        # Check that the bad patterns exist
        assert "string created_at" in content

        # Verify our tools would catch the created_at pattern
        result1 = analyze_field_for_type_recommendation("created_at", "string")
        assert result1 is not None

        # Also test create_time pattern which should definitely match
        result2 = analyze_field_for_type_recommendation("create_time", "string")
        assert result2 is not None

    def test_bad_example_has_money_issues(self):
        """Test that we can detect money issues in the bad example."""
        path = FIXTURES_DIR / "bad_example.proto"
        content = path.read_text()
        
        assert "double price" in content
        
        result = analyze_field_for_type_recommendation("price", "double")
        assert result is not None
        wkt, _ = result
        assert wkt.short_name == "Money"


class TestAgentIntegration:
    """Integration tests for the agent (requires mocking the API)."""

    @patch('src.agent.create_adapter')
    def test_review_proto_returns_result(self, mock_create_adapter):
        """Test that review_proto returns a ReviewResult."""
        # Create mock adapter
        mock_adapter = MagicMock()
        mock_adapter.provider_name = "mock"
        mock_adapter.model_name = "mock-model"
        mock_adapter.generate.return_value = ("No issues found.", [])
        mock_create_adapter.return_value = mock_adapter

        from src.agent import review_proto
        result = review_proto('syntax = "proto3"; message Test {}')

        assert isinstance(result, ReviewResult)
        assert result.provider_name == "mock"
        assert result.model_name == "mock-model"
        assert "No issues found" in result.content

    @patch('src.agent.create_adapter')
    def test_review_proto_structured_returns_result(self, mock_create_adapter):
        """Test that review_proto_structured returns a ReviewResult with dict content."""
        # Create mock adapter
        mock_adapter = MagicMock()
        mock_adapter.provider_name = "mock"
        mock_adapter.model_name = "mock-model"
        mock_adapter.generate.return_value = (
            '{"issues": [], "summary": "No issues found"}',
            []
        )
        mock_create_adapter.return_value = mock_adapter

        from src.agent import review_proto_structured
        result = review_proto_structured('syntax = "proto3"; message Test {}')

        assert isinstance(result, ReviewResult)
        assert result.is_structured
        assert isinstance(result.content, dict)
        assert "issues" in result.content

    def test_review_context_defaults(self):
        """Test ReviewContext default values."""
        context = ReviewContext()
        assert context.provider is None
        assert context.model_name is None
        assert context.focus == "event"
        assert context.max_iterations > 0
        assert context.max_input_size > 0

    def test_review_context_custom_values(self):
        """Test ReviewContext with custom values."""
        context = ReviewContext(
            provider="openai",
            model_name="gpt-4",
            focus="rest",
            max_iterations=5,
        )
        assert context.provider == "openai"
        assert context.model_name == "gpt-4"
        assert context.focus == "rest"
        assert context.max_iterations == 5


class TestValidation:
    """Tests for input validation."""

    def test_empty_proto_raises_error(self):
        """Test that empty proto content raises ValueError."""
        from src.agent import _validate_input
        with pytest.raises(ValueError, match="empty"):
            _validate_input("", 100000, validate_syntax=False)

    def test_whitespace_proto_raises_error(self):
        """Test that whitespace-only proto content raises ValueError."""
        from src.agent import _validate_input
        with pytest.raises(ValueError, match="empty"):
            _validate_input("   \n\t  ", 100000, validate_syntax=False)

    def test_large_proto_raises_error(self):
        """Test that oversized proto content raises ValueError."""
        from src.agent import _validate_input
        large_content = "x" * 1000
        with pytest.raises(ValueError, match="exceeds maximum"):
            _validate_input(large_content, 100, validate_syntax=False)


# Run with: pytest tests/ -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
