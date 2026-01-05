"""
Organizational semantic standards for proto review.

These are organization-specific rules that extend the universal AIP standards.
Standards are loaded from YAML files in the standards/org/ directory.

Standard naming: ORG-XXX (e.g., ORG-001, ORG-002)

Configuration:
    STANDARDS_DIR: Path to standards directory (default: ./standards/)
"""

from .loader import (
    OrgStandard,
    SemanticRule,
    get_org_standard,
    get_all_org_standards,
    get_org_standard_summary,
    get_all_org_standards_summary,
    load_org_standards,
)

# Backwards compatibility: provide ORG_STANDARDS dict
ORG_STANDARDS = load_org_standards()

__all__ = [
    "OrgStandard",
    "SemanticRule",
    "ORG_STANDARDS",
    "get_org_standard",
    "get_all_org_standards",
    "get_org_standard_summary",
    "get_all_org_standards_summary",
]
