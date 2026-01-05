"""
AD Group Authorization middleware for the Proto Semantic Reviewer.

This module provides optional authorization based on AD group membership.
Authorization is disabled by default and enabled via ALLOWED_AD_GROUPS env var.
"""

from __future__ import annotations

import os
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def get_allowed_groups() -> set[str]:
    """
    Get allowed AD groups from environment.

    Returns:
        Set of allowed group names, or empty set if not configured.
    """
    groups = os.environ.get("ALLOWED_AD_GROUPS", "")
    return set(g.strip() for g in groups.split(",") if g.strip())


def is_auth_enabled() -> bool:
    """Check if AD authorization is enabled."""
    return bool(get_allowed_groups())


def check_authorization(user_groups: set[str], allowed_groups: set[str]) -> bool:
    """
    Check if user is authorized based on group membership.

    Args:
        user_groups: Set of groups the user belongs to
        allowed_groups: Set of groups allowed to access the service

    Returns:
        True if user has at least one matching group, False otherwise.
    """
    return bool(user_groups & allowed_groups)


class ADAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check AD group membership for authorization.

    When ALLOWED_AD_GROUPS is set, requests must include an X-AD-Memberships
    header with at least one group that matches the allow list.

    Trust Model:
        This middleware trusts the X-AD-Memberships header. It assumes an
        upstream gateway/proxy validates the user's identity and sets the
        header based on validated AD group membership.
    """

    async def dispatch(self, request: Request, call_next):
        allowed = get_allowed_groups()

        # If no allowed groups configured, auth is disabled
        if not allowed:
            return await call_next(request)

        # Get user's groups from header
        header = request.headers.get("X-AD-Memberships", "")
        user_groups = set(g.strip() for g in header.split(",") if g.strip())

        # Check if user has at least one allowed group
        if not check_authorization(user_groups, allowed):
            logger.warning(
                f"Authorization denied for {request.method} {request.url.path}. "
                f"User groups: {user_groups}, Allowed: {allowed}"
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: user not in allowed AD groups"}
            )

        logger.debug(
            f"Authorization granted for {request.method} {request.url.path}. "
            f"Matching groups: {user_groups & allowed}"
        )
        return await call_next(request)
