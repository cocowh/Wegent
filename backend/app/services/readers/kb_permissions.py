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

    def create() -> MyResolver:
        return MyResolver()
"""

import importlib
import logging
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
# Loader
# =============================================================================


def _create_resolver() -> Optional[IKbPermissionResolver]:
    """Load resolver from SERVICE_EXTENSION if configured."""
    from app.core.config import settings

    if not settings.SERVICE_EXTENSION:
        return None
    try:
        ext = importlib.import_module(f"{settings.SERVICE_EXTENSION}.kb_permissions")
        resolver = ext.create()
        logger.info("KB permission resolver extension loaded")
        return resolver
    except ImportError:
        return None
    except Exception as e:
        logger.warning(f"Failed to load kb_permissions extension: {e}")
        return None


# =============================================================================
# Lazy Singleton
# =============================================================================


class _LazyResolver:
    """Lazy-loaded resolver proxy that delegates to the actual resolver."""

    _instance: Optional[IKbPermissionResolver] = None
    _initialized: bool = False

    def _get(self) -> Optional[IKbPermissionResolver]:
        if not self._initialized:
            self._instance = _create_resolver()
            self._initialized = True
        return self._instance

    def resolve(
        self, db: Session, kb_id: int, user_id: int, kb: object
    ) -> Optional[str]:
        resolver = self._get()
        if resolver is None:
            return None
        return resolver.resolve(db, kb_id, user_id, kb)

    def get_accessible_kb_ids(self, db: Session, user_id: int) -> list[int]:
        resolver = self._get()
        if resolver is None:
            return []
        return resolver.get_accessible_kb_ids(db, user_id)


# =============================================================================
# Export
# =============================================================================

kbPermissionResolver: _LazyResolver = _LazyResolver()
