"""
Proto syntax validation using grpcio-tools.

Validates proto file syntax before semantic review to ensure
the LLM receives well-formed input.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of proto syntax validation."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]

    @property
    def error_message(self) -> str:
        """Get a formatted error message."""
        if self.is_valid:
            return ""
        return "\n".join(self.errors)


class ProtoValidationError(Exception):
    """Raised when proto syntax validation fails."""

    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


def validate_proto_syntax(
    proto_content: str,
    filename: str = "input.proto",
) -> ValidationResult:
    """
    Validate proto file syntax using protoc.

    Args:
        proto_content: The proto file content to validate
        filename: Virtual filename for error messages

    Returns:
        ValidationResult with validation status and any errors

    Note:
        Requires protoc to be installed (via grpcio-tools or system protoc).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Quick pre-validation checks
    content_stripped = proto_content.strip()
    if not content_stripped:
        return ValidationResult(
            is_valid=False,
            errors=["Proto content is empty"],
            warnings=[],
        )

    # Check for syntax declaration
    if 'syntax = "proto3"' not in content_stripped and "syntax = 'proto3'" not in content_stripped:
        if 'syntax = "proto2"' not in content_stripped and "syntax = 'proto2'" not in content_stripped:
            warnings.append("Missing syntax declaration. Assuming proto2 (consider adding 'syntax = \"proto3\";')")

    # Try to run protoc for full validation
    try:
        result = _run_protoc_validation(proto_content, filename)
        if result.errors:
            errors.extend(result.errors)
        if result.warnings:
            warnings.extend(result.warnings)
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    except FileNotFoundError:
        # protoc not available, fall back to basic validation
        logger.warning("protoc not found, using basic validation only")
        return _basic_validation(proto_content, filename)
    except Exception as e:
        logger.error(f"Proto validation error: {e}")
        # If protoc fails unexpectedly, allow the review to proceed
        # with a warning rather than blocking
        warnings.append(f"Could not run full syntax validation: {e}")
        basic_result = _basic_validation(proto_content, filename)
        basic_result.warnings.extend(warnings)
        return basic_result


def _run_protoc_validation(proto_content: str, filename: str) -> ValidationResult:
    """
    Run protoc to validate proto syntax.

    Creates a temporary file and runs protoc with --encode flag
    to trigger syntax parsing without generating output.
    """
    errors: list[str] = []
    warnings: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        proto_path = Path(tmpdir) / filename
        proto_path.write_text(proto_content)

        # Run protoc to check syntax
        # We use -o /dev/null to discard output, we only want error messages
        try:
            result = subprocess.run(
                [
                    "protoc",
                    f"--proto_path={tmpdir}",
                    f"--descriptor_set_out=/dev/null",
                    str(proto_path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                # Parse error output
                stderr = result.stderr.strip()
                if stderr:
                    # Clean up error messages
                    for line in stderr.split("\n"):
                        line = line.strip()
                        if line:
                            # Replace temp path with virtual filename
                            cleaned = line.replace(str(proto_path), filename)
                            cleaned = cleaned.replace(tmpdir + "/", "")
                            if "warning:" in cleaned.lower():
                                warnings.append(cleaned)
                            else:
                                errors.append(cleaned)
                else:
                    errors.append("Proto syntax validation failed")

        except subprocess.TimeoutExpired:
            errors.append("Proto validation timed out")
        except FileNotFoundError:
            raise  # Re-raise to trigger fallback

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _basic_validation(proto_content: str, filename: str) -> ValidationResult:
    """
    Basic proto validation without protoc.

    Checks for common syntax errors that can be detected without
    full parsing:
    - Balanced braces
    - Required keywords
    - Basic structure
    """
    errors: list[str] = []
    warnings: list[str] = []

    lines = proto_content.split("\n")

    # Check brace balance
    brace_count = 0
    for i, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.split("//")[0]
        brace_count += stripped.count("{")
        brace_count -= stripped.count("}")

        if brace_count < 0:
            errors.append(f"{filename}:{i}: Unexpected closing brace")
            break

    if brace_count > 0:
        errors.append(f"{filename}: Unclosed brace (missing {brace_count} closing brace(s))")
    elif brace_count < 0:
        errors.append(f"{filename}: Extra closing brace(s)")

    # Check for at least one message or enum or service
    has_definition = any(
        keyword in proto_content
        for keyword in ["message ", "enum ", "service "]
    )
    if not has_definition:
        warnings.append(f"{filename}: No message, enum, or service definitions found")

    # Check for common typos
    if "messge " in proto_content or "mesage " in proto_content:
        errors.append(f"{filename}: Possible typo - 'message' misspelled")

    if "servce " in proto_content or "servcie " in proto_content:
        errors.append(f"{filename}: Possible typo - 'service' misspelled")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_proto_or_raise(
    proto_content: str,
    filename: str = "input.proto",
) -> None:
    """
    Validate proto syntax and raise if invalid.

    Args:
        proto_content: The proto file content to validate
        filename: Virtual filename for error messages

    Raises:
        ProtoValidationError: If validation fails
    """
    result = validate_proto_syntax(proto_content, filename)
    if not result.is_valid:
        raise ProtoValidationError(
            f"Proto syntax validation failed: {result.error_message}",
            result.errors,
        )
