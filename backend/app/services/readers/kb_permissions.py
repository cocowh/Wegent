# SPDX-FileCopyrightText: 2025 Wegent, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""
Knowledge base external permission resolver extension point.

Loaded via Python entry points mechanism.

Usage (in extension package, e.g. myext/kb_permissions.py):

    from app.services.readers.kb_permissions import IKbPermissionResolver

    class MyResolver(IKbPermissionResolver):
        def __init__(self, base: IKbPermissionResolver):
            self._base = base

        def resolve(self, db, kb_id, user_id, kb):
            # return a role string or None
            ...

        def get_accessible_kb_ids(self, db, user_id):
            # return list of kb_ids the user can access
            ...

Register in pyproject.toml:

    [project.entry-points."wegent.kb_permissions"]
    my_resolver = "myext.kb_permissions:MyResolver"
"""

import importlib.metadata
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Entry point group for KB permission resolvers
ENTRY_POINT_GROUP = "wegent.kb_permissions"


# =============================================================================
# Interface
# =============================================================================


class IKbPermissionResolver(ABC):
    """
    Abstract interface for external knowledge base permission resolution.

    Implementations return a role string when the external system grants
    access, or None to fall through to the built-in permission logic.
    """

    @abstractmethod
    def resolve(
        self,
        db: Session,
        kb_id: int,
        user_id: int,
        kb: object,
    ) -> Optional[str]:
        """
        Resolve permission for a single knowledge base access check.

        Called after all built-in checks have returned False.

        Args:
            db:      Database session
            kb_id:   Knowledge base ID
            user_id: Requesting user ID
            kb:      Kind object (knowledge base record)

        Returns:
            Role string ("Owner"/"Maintainer"/"Developer"/"Reporter") if the
            external system grants access, None to continue with built-in
            denial.
        """
        pass

    @abstractmethod
    def get_accessible_kb_ids(self, db: Session, user_id: int) -> list[int]:
        """
        Return knowledge base IDs accessible to the user via external rules.

        Called during list queries to extend the OR conditions. Return an
        empty list when there are no additional IDs to include.

        Args:
            db:      Database session
            user_id: Requesting user ID

        Returns:
            List of knowledge base IDs (may be empty).
        """
        pass


# =============================================================================
# Default Implementation
# =============================================================================


class DefaultKbPermissionResolver(IKbPermissionResolver):
    """
    No-op resolver used when no extension is configured.

    Always returns None / [] so no extra permissions are granted.
    """

    def resolve(
        self,
        db: Session,
        kb_id: int,
        user_id: int,
        kb: object,
    ) -> Optional[str]:
        return None

    def get_accessible_kb_ids(self, db: Session, user_id: int) -> list[int]:
        return []


# =============================================================================
# Loader
# =============================================================================


def _load_from_entry_points(
    base: IKbPermissionResolver,
) -> Optional[IKbPermissionResolver]:
    """
    Load resolver from entry points.

    Args:
        base: The base resolver to pass to the loaded resolver's constructor.

    Returns:
        The loaded resolver instance, or None if no valid entry point found.
    """
    try:
        entry_points = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:
        # Python < 3.10 compatibility
        all_eps = importlib.metadata.entry_points()
        entry_points = all_eps.get(ENTRY_POINT_GROUP, [])

    if not entry_points:
        return None

    # Use the first entry point
    ep = next(iter(entry_points))

    try:
        resolver_class = ep.load()

        if not issubclass(resolver_class, IKbPermissionResolver):
            logger.error(
                f"Entry point {ep.name} ({resolver_class}) does not implement IKbPermissionResolver"
            )
            return None

        result = resolver_class(base)
        logger.info(f"KB permission resolver loaded from entry point: {ep.name}")
        return result

    except Exception as e:
        logger.warning(f"Failed to load entry point {ep.name}: {e}", exc_info=True)
        return None


def _create_resolver() -> IKbPermissionResolver:
    """Create resolver, loading from entry points if available."""
    base: IKbPermissionResolver = DefaultKbPermissionResolver()

    # Try to load from entry points
    loaded = _load_from_entry_points(base)
    if loaded is not None:
        return loaded

    return base


# =============================================================================
# Lazy Singleton
# =============================================================================


class _LazyReader:
    """Lazy-loaded resolver proxy that delegates to the actual resolver instance."""

    _instance: IKbPermissionResolver | None = None
    _init_lock: threading.Lock = threading.Lock()

    def _get(self) -> IKbPermissionResolver:
        if self._instance is None:
            with self._init_lock:
                # Double-checked locking to ensure only one resolver is created
                # under concurrent access.
                if self._instance is None:
                    self._instance = _create_resolver()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


# =============================================================================
# Export
# =============================================================================

kb_permission_resolver: IKbPermissionResolver = _LazyReader()  # type: ignore
