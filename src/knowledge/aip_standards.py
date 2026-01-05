"""
Bundled AIP (API Improvement Proposals) standards for semantic proto review.

Standards are loaded from YAML files in the standards/aips/ directory.
This module provides backwards compatibility imports.

Configuration:
    STANDARDS_DIR: Path to standards directory (default: ./standards/)
"""

from .loader import (
    AIPStandard,
    SemanticRule,
    get_aip,
    get_all_aips,
    get_aip_summary,
    get_all_aips_summary,
    get_semantic_rules_for_concept,
    load_aip_standards,
)

# Backwards compatibility: provide AIP_STANDARDS dict
AIP_STANDARDS = load_aip_standards()

__all__ = [
    "AIPStandard",
    "SemanticRule",
    "AIP_STANDARDS",
    "get_aip",
    "get_all_aips",
    "get_aip_summary",
    "get_all_aips_summary",
    "get_semantic_rules_for_concept",
]
