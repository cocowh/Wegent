# SPDX-FileCopyrightText: 2025 Wegent, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""
Knowledge base external permission resolver extension point.

Loaded via SERVICE_EXTENSION mechanism, consistent with the
groups/group_members reader pattern.

Usage (in extension package, e.g. myext/kb_permissions.py):

    from app.services.readers.kb_permissions import IKbPermissionResolver

    class MyResolver(IKbPermissionResolver):
        def resolve(self, db, kb_id, user_id, kb):
            # return a role string or None
            ...

        def get_accessible_kb_ids(self, db, user_id):
            # return list of kb_ids the user can access
            ...

    def wrap(base: IKbPermissionResolver) -> MyResolver:
        return MyResolver()
"""

import importlib
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


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

        Called during list queries to extend the OR conditions.  Return an
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


def _create_resolver() -> IKbPermissionResolver:
    """Create resolver, wrapping with extension if SERVICE_EXTENSION is set."""
    from app.core.config import settings

    base: IKbPermissionResolver = DefaultKbPermissionResolver()

    if not settings.SERVICE_EXTENSION:
        return base

    try:
        ext = importlib.import_module(f"{settings.SERVICE_EXTENSION}.kb_permissions")
        result = ext.wrap(base)
        if result is None:
            logger.warning(
                "kb_permissions extension wrap() returned None; "
                f"using default resolver ({settings.SERVICE_EXTENSION})"
            )
        else:
            logger.info("KB permission resolver extension loaded")
            return result
    except ImportError:
        logger.warning(
            "KB permission resolver extension module not found: "
            f"{settings.SERVICE_EXTENSION}.kb_permissions"
        )
    except Exception as e:
        logger.warning(f"Failed to load kb_permissions extension: {e}")

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
