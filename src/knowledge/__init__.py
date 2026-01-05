"""
Bundled knowledge base for proto semantic review.

This package contains AIP standards, organizational standards, and well-known
type references needed for semantic analysis. Standards are loaded from YAML
files, enabling easy customization.

Configuration:
    STANDARDS_DIR: Path to standards directory (default: ./standards/)
"""

from .loader import (
    # Data classes
    AIPStandard,
    SemanticRule,
    OrgStandard,
    # AIP functions
    get_aip,
    get_all_aips,
    get_aip_summary,
    get_all_aips_summary,
    get_semantic_rules_for_concept,
    load_aip_standards,
    # ORG functions
    get_org_standard,
    get_all_org_standards,
    get_org_standard_summary,
    get_all_org_standards_summary,
    load_org_standards,
)

from .wellknown_types import (
    WellKnownType,
    WELL_KNOWN_TYPES,
    analyze_field_for_type_recommendation,
    get_type_info,
    get_all_type_recommendations,
)


# Backwards compatibility: provide AIP_STANDARDS dict
def _get_aip_standards_dict():
    """Lazy load AIP standards as a dict for backwards compatibility."""
    return load_aip_standards()

# This will be populated on first access
AIP_STANDARDS = _get_aip_standards_dict()


__all__ = [
    # AIP Standards
    "AIPStandard",
    "SemanticRule",
    "get_aip",
    "get_all_aips",
    "get_aip_summary",
    "get_all_aips_summary",
    "get_semantic_rules_for_concept",
    "load_aip_standards",
    "AIP_STANDARDS",
    # ORG Standards
    "OrgStandard",
    "get_org_standard",
    "get_all_org_standards",
    "get_org_standard_summary",
    "get_all_org_standards_summary",
    "load_org_standards",
    # Well-known types
    "WellKnownType",
    "WELL_KNOWN_TYPES",
    "analyze_field_for_type_recommendation",
    "get_type_info",
    "get_all_type_recommendations",
]
