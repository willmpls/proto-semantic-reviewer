"""
YAML-based standards loader.

Loads AIP and organizational standards from YAML files, enabling:
- Easy editing without code changes
- Organization-specific customization via volume mounts
- Separation of standards data from code

Thread-safe: Uses locks for lazy initialization of cached standards.
"""

from __future__ import annotations

import os
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import yaml

logger = logging.getLogger(__name__)

# Thread locks for safe lazy initialization
_aip_lock = threading.Lock()
_org_lock = threading.Lock()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SemanticRule:
    """A single semantic rule that can be checked."""
    id: str
    description: str
    check_guidance: str
    common_violations: list[str] = field(default_factory=list)
    good_example: Optional[str] = None
    bad_example: Optional[str] = None


@dataclass
class AIPStandard:
    """A complete AIP standard with its semantic rules."""
    number: int
    title: str
    summary: str
    semantic_rules: list[SemanticRule] = field(default_factory=list)


@dataclass
class OrgStandard:
    """An organizational standard with semantic rules."""
    id: str
    title: str
    summary: str
    applies_to: str = ""
    semantic_rules: list[SemanticRule] = field(default_factory=list)
    related_aips: list[str] = field(default_factory=list)


# =============================================================================
# Configuration
# =============================================================================

def get_standards_dir() -> Path:
    """Get the standards directory from environment or default."""
    env_dir = os.environ.get("STANDARDS_DIR")
    if env_dir:
        return Path(env_dir)

    # Default: look for standards/ relative to this file's package
    # This handles both installed package and development scenarios
    package_dir = Path(__file__).parent.parent.parent
    return package_dir / "standards"


# =============================================================================
# YAML Parsing
# =============================================================================

def _parse_rule(rule_data: dict) -> SemanticRule:
    """Parse a rule dictionary into a SemanticRule."""
    return SemanticRule(
        id=rule_data.get("id", ""),
        description=rule_data.get("description", ""),
        check_guidance=rule_data.get("check_guidance", ""),
        common_violations=rule_data.get("violations", []),
        good_example=rule_data.get("good_example"),
        bad_example=rule_data.get("bad_example"),
    )


def _load_aip_from_yaml(file_path: Path) -> Optional[AIPStandard]:
    """Load a single AIP standard from a YAML file."""
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        rules = [_parse_rule(r) for r in data.get("rules", [])]

        return AIPStandard(
            number=data.get("id", 0),
            title=data.get("title", ""),
            summary=data.get("summary", "").strip(),
            semantic_rules=rules,
        )
    except Exception as e:
        logger.warning(f"Failed to load AIP from {file_path}: {e}")
        return None


def _load_org_from_yaml(file_path: Path) -> Optional[OrgStandard]:
    """Load a single organizational standard from a YAML file."""
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        rules = [_parse_rule(r) for r in data.get("rules", [])]

        return OrgStandard(
            id=data.get("id", ""),
            title=data.get("title", ""),
            summary=data.get("summary", "").strip(),
            applies_to=data.get("applies_to", ""),
            semantic_rules=rules,
            related_aips=data.get("related_aips", []),
        )
    except Exception as e:
        logger.warning(f"Failed to load ORG standard from {file_path}: {e}")
        return None


# =============================================================================
# Standards Loading
# =============================================================================

# Cached standards (loaded once at startup)
_aip_standards: Optional[dict[int, AIPStandard]] = None
_org_standards: Optional[dict[str, OrgStandard]] = None


def load_aip_standards(force_reload: bool = False) -> dict[int, AIPStandard]:
    """
    Load all AIP standards from YAML files.

    Standards are cached after first load. Use force_reload=True to refresh.
    Thread-safe: Uses double-checked locking pattern.
    """
    global _aip_standards

    # Fast path: return cached value if available
    if _aip_standards is not None and not force_reload:
        return _aip_standards

    # Slow path: acquire lock and load
    with _aip_lock:
        # Double-check after acquiring lock
        if _aip_standards is not None and not force_reload:
            return _aip_standards

        new_standards: dict[int, AIPStandard] = {}
        standards_dir = get_standards_dir() / "aips"

        if not standards_dir.exists():
            logger.info(f"AIP standards directory not found: {standards_dir}")
            _aip_standards = new_standards
            return _aip_standards

        for yaml_file in standards_dir.glob("*.yaml"):
            aip = _load_aip_from_yaml(yaml_file)
            if aip:
                new_standards[aip.number] = aip
                logger.debug(f"Loaded AIP-{aip.number}: {aip.title}")

        _aip_standards = new_standards
        logger.info(f"Loaded {len(_aip_standards)} AIP standards from {standards_dir}")
        return _aip_standards


def load_org_standards(force_reload: bool = False) -> dict[str, OrgStandard]:
    """
    Load all organizational standards from YAML files.

    Standards are cached after first load. Use force_reload=True to refresh.
    Thread-safe: Uses double-checked locking pattern.
    """
    global _org_standards

    # Fast path: return cached value if available
    if _org_standards is not None and not force_reload:
        return _org_standards

    # Slow path: acquire lock and load
    with _org_lock:
        # Double-check after acquiring lock
        if _org_standards is not None and not force_reload:
            return _org_standards

        new_standards: dict[str, OrgStandard] = {}
        standards_dir = get_standards_dir() / "org"

        if not standards_dir.exists():
            logger.info(f"ORG standards directory not found: {standards_dir}")
            _org_standards = new_standards
            return _org_standards

        for yaml_file in standards_dir.glob("*.yaml"):
            org = _load_org_from_yaml(yaml_file)
            if org:
                new_standards[org.id.upper()] = org
                logger.debug(f"Loaded {org.id}: {org.title}")

        _org_standards = new_standards
        logger.info(f"Loaded {len(_org_standards)} ORG standards from {standards_dir}")
        return _org_standards


# =============================================================================
# Public API (mirrors existing knowledge module interface)
# =============================================================================

def get_aip(number: int) -> Optional[AIPStandard]:
    """Get an AIP standard by number."""
    standards = load_aip_standards()
    return standards.get(number)


def get_all_aips() -> list[AIPStandard]:
    """Get all AIP standards."""
    standards = load_aip_standards()
    return list(standards.values())


def get_aip_summary(number: int) -> str:
    """Get a formatted summary of an AIP for the agent."""
    aip = get_aip(number)
    if not aip:
        return f"AIP-{number} not found in knowledge base."

    lines = [
        f"# AIP-{aip.number}: {aip.title}",
        "",
        aip.summary,
        "",
        "## Semantic Rules",
        "",
    ]

    for rule in aip.semantic_rules:
        lines.append(f"### {rule.id}")
        lines.append(f"**Description:** {rule.description}")
        lines.append(f"**What to check:** {rule.check_guidance}")

        if rule.common_violations:
            lines.append("**Common violations:**")
            for v in rule.common_violations:
                lines.append(f"  - {v}")

        if rule.good_example:
            lines.append(f"**Good example:**\n```protobuf\n{rule.good_example.strip()}\n```")

        if rule.bad_example:
            lines.append(f"**Bad example:**\n```protobuf\n{rule.bad_example.strip()}\n```")

        lines.append("")

    return "\n".join(lines)


def get_all_aips_summary() -> str:
    """Get a brief listing of all available AIPs."""
    standards = load_aip_standards()
    lines = ["# Available AIP Standards", ""]
    for aip in sorted(standards.values(), key=lambda x: x.number):
        lines.append(f"- **AIP-{aip.number}**: {aip.title}")
    return "\n".join(lines)


def get_org_standard(standard_id: str) -> Optional[OrgStandard]:
    """Get an organizational standard by ID."""
    standards = load_org_standards()
    return standards.get(standard_id.upper())


def get_all_org_standards() -> list[OrgStandard]:
    """Get all organizational standards."""
    standards = load_org_standards()
    return list(standards.values())


def get_org_standard_summary(standard_id: str) -> str:
    """Get a formatted summary of an organizational standard."""
    std = get_org_standard(standard_id)
    if not std:
        return f"Organizational standard '{standard_id}' not found."

    lines = [
        f"# {std.id}: {std.title}",
        "",
        std.summary,
        "",
        f"**Applies to:** {std.applies_to}",
        "",
    ]

    if std.related_aips:
        lines.append(f"**Related AIPs:** {', '.join(std.related_aips)}")
        lines.append("(Use lookup_aip() for detailed AIP guidance)")
        lines.append("")

    lines.append("## Semantic Rules")
    lines.append("")

    for rule in std.semantic_rules:
        lines.append(f"### {rule.id}")
        lines.append(f"**Description:** {rule.description}")
        lines.append(f"**What to check:** {rule.check_guidance}")

        if rule.common_violations:
            lines.append("**Common violations:**")
            for v in rule.common_violations:
                lines.append(f"  - {v}")

        if rule.good_example:
            lines.append(f"**Good example:**\n```protobuf\n{rule.good_example.strip()}\n```")

        if rule.bad_example:
            lines.append(f"**Bad example:**\n```protobuf\n{rule.bad_example.strip()}\n```")

        lines.append("")

    return "\n".join(lines)


def get_all_org_standards_summary() -> str:
    """Get a brief listing of all available organizational standards."""
    standards = load_org_standards()

    if not standards:
        return "No organizational standards defined."

    lines = ["# Organizational Standards", ""]
    lines.append("These are organization-specific rules that extend the universal AIP standards.")
    lines.append("")
    for std in standards.values():
        lines.append(f"- **{std.id}**: {std.title}")
        lines.append(f"  Applies to: {std.applies_to}")
    lines.append("")
    lines.append("Use lookup_org_standard(standard_id) for detailed guidance.")
    return "\n".join(lines)


def get_semantic_rules_for_concept(concept: str) -> list[tuple[int, SemanticRule]]:
    """Find semantic rules related to a concept (e.g., 'timestamp', 'pagination')."""
    concept_lower = concept.lower()
    results = []

    for aip in get_all_aips():
        for rule in aip.semantic_rules:
            if (concept_lower in rule.description.lower() or
                concept_lower in rule.check_guidance.lower() or
                concept_lower in rule.id.lower()):
                results.append((aip.number, rule))

    return results
