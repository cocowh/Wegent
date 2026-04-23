# SPDX-FileCopyrightText: 2025 Wegent, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the KB permission resolver extension point.

Covers:
- DefaultKbPermissionResolver no-op behaviour
- _create_resolver returns default when SERVICE_EXTENSION is unset
- _create_resolver wraps with extension when SERVICE_EXTENSION is set
- _LazyReader initialises lazily and delegates via __getattr__
- ImportError produces a warning log and falls back to the default resolver
- General exception produces a warning log and falls back to the default resolver
- get_user_kb_permission calls the resolver as the final fallback
"""

import importlib
import sys
from types import ModuleType
from typing import Optional
from unittest.mock import MagicMock, patch

# Use importlib.import_module to get the actual module object, not the
# instance exported by app.services.share.__init__.py under the same name.
_kss_module = importlib.import_module("app.services.share.knowledge_share_service")

import pytest
from sqlalchemy.orm import Session

from app.services.readers.kb_permissions import (
    DefaultKbPermissionResolver,
    IKbPermissionResolver,
    _create_resolver,
    _LazyReader,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> Session:
    return MagicMock(spec=Session)


def _make_kb(kb_id: int = 1) -> MagicMock:
    kb = MagicMock()
    kb.id = kb_id
    return kb


# ---------------------------------------------------------------------------
# DefaultKbPermissionResolver
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_default_resolver_resolve_returns_none() -> None:
    """DefaultKbPermissionResolver.resolve always returns None."""
    resolver = DefaultKbPermissionResolver()
    result = resolver.resolve(_make_db(), kb_id=1, user_id=42, kb=_make_kb())
    assert result is None


@pytest.mark.unit
def test_default_resolver_get_accessible_kb_ids_returns_empty_list() -> None:
    """DefaultKbPermissionResolver.get_accessible_kb_ids always returns []."""
    resolver = DefaultKbPermissionResolver()
    result = resolver.get_accessible_kb_ids(_make_db(), user_id=42)
    assert result == []


# ---------------------------------------------------------------------------
# _create_resolver — no extension configured
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_resolver_returns_default_when_no_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When SERVICE_EXTENSION is empty, _create_resolver returns DefaultKbPermissionResolver."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "SERVICE_EXTENSION", "")
    result = _create_resolver()
    assert isinstance(result, DefaultKbPermissionResolver)


# ---------------------------------------------------------------------------
# _create_resolver — extension loaded via wrap(base)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_resolver_wraps_with_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When SERVICE_EXTENSION is set and wrap() succeeds, the wrapped resolver is used."""

    class _CustomResolver(IKbPermissionResolver):
        def resolve(self, db, kb_id, user_id, kb) -> Optional[str]:
            return "Reporter"

        def get_accessible_kb_ids(self, db, user_id) -> list[int]:
            return [10, 20]

    def _fake_wrap(base: IKbPermissionResolver) -> IKbPermissionResolver:
        return _CustomResolver()

    fake_ext = ModuleType("myext.kb_permissions")
    fake_ext.wrap = _fake_wrap  # type: ignore[attr-defined]

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SERVICE_EXTENSION = "myext"
        with patch("importlib.import_module", return_value=fake_ext):
            from app.services.readers import kb_permissions

            result = kb_permissions._create_resolver()

    assert isinstance(result, _CustomResolver)
    assert result.resolve(_make_db(), kb_id=1, user_id=1, kb=_make_kb()) == "Reporter"
    assert result.get_accessible_kb_ids(_make_db(), user_id=1) == [10, 20]


# ---------------------------------------------------------------------------
# _create_resolver — ImportError falls back to default with warning
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_resolver_falls_back_on_import_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ImportError during extension load logs a warning and returns the default resolver."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SERVICE_EXTENSION = "missing_ext"
        with patch("importlib.import_module", side_effect=ImportError("no module")):
            import logging

            with caplog.at_level(
                logging.WARNING, logger="app.services.readers.kb_permissions"
            ):
                from app.services.readers import kb_permissions

                result = kb_permissions._create_resolver()

    assert isinstance(result, DefaultKbPermissionResolver)
    assert any("not found" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _create_resolver — generic exception falls back to default with warning
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_resolver_falls_back_on_general_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-ImportError exception during extension load logs a warning and returns default."""
    fake_ext = ModuleType("myext.kb_permissions")
    fake_ext.wrap = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[attr-defined]

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SERVICE_EXTENSION = "myext"
        with patch("importlib.import_module", return_value=fake_ext):
            import logging

            with caplog.at_level(
                logging.WARNING, logger="app.services.readers.kb_permissions"
            ):
                from app.services.readers import kb_permissions

                result = kb_permissions._create_resolver()

    assert isinstance(result, DefaultKbPermissionResolver)
    assert any("Failed to load" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _LazyReader — lazy initialisation and __getattr__ delegation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_lazy_reader_initialises_only_once() -> None:
    """_LazyReader calls _create_resolver exactly once across multiple method calls."""
    mock_resolver = MagicMock(spec=IKbPermissionResolver)
    mock_resolver.get_accessible_kb_ids.return_value = [5]
    mock_resolver.resolve.return_value = None

    lazy = _LazyReader()
    lazy._instance = None  # reset state for isolation

    with patch(
        "app.services.readers.kb_permissions._create_resolver",
        return_value=mock_resolver,
    ) as mock_create:
        _ = lazy.get_accessible_kb_ids(_make_db(), user_id=1)
        _ = lazy.get_accessible_kb_ids(_make_db(), user_id=2)
        _ = lazy.resolve(_make_db(), kb_id=1, user_id=1, kb=_make_kb())

    # _create_resolver should be called only once (lazy singleton)
    assert mock_create.call_count == 1


@pytest.mark.unit
def test_lazy_reader_delegates_resolve_via_getattr() -> None:
    """_LazyReader.__getattr__ transparently delegates to the underlying resolver."""
    mock_resolver = MagicMock(spec=IKbPermissionResolver)
    mock_resolver.resolve.return_value = "Developer"

    lazy = _LazyReader()
    lazy._instance = mock_resolver

    result = lazy.resolve(_make_db(), kb_id=7, user_id=3, kb=_make_kb())

    assert result == "Developer"
    mock_resolver.resolve.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: get_user_kb_permission calls resolver as final fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_user_kb_permission_calls_external_resolver_as_last_resort(
    test_db: Session,
) -> None:
    """
    When all built-in checks deny access, kb_permission_resolver.resolve is called
    and its returned role is used.
    """
    from unittest.mock import MagicMock, patch

    from app.services.share.knowledge_share_service import KnowledgeShareService

    service = KnowledgeShareService()
    db = test_db

    # Build a minimal mock KB that has no creator match, no group, no org, no share
    mock_kb = MagicMock()
    mock_kb.id = 99
    mock_kb.user_id = 999  # not the requesting user
    mock_kb.namespace = "default"
    mock_kb.kind = "KnowledgeBase"
    mock_kb.is_active = True

    with (
        patch.object(db, "query") as mock_query,
        patch(
            "app.services.readers.kb_permissions.kb_permission_resolver"
        ) as mock_resolver,
        patch.object(_kss_module, "is_organization_namespace", return_value=False),
        patch.object(_kss_module, "is_restricted_analyst", return_value=False),
    ):
        # KB lookup returns mock_kb, subsequent explicit-permission lookup returns None
        mock_query.return_value.filter.return_value.first.side_effect = [
            mock_kb,  # KB lookup
            None,  # no explicit ResourceMember
        ]
        # External resolver grants Reporter access
        mock_resolver.resolve.return_value = "Reporter"

        has_access, role, is_creator = service.get_user_kb_permission(
            db, knowledge_base_id=99, user_id=1
        )

    assert has_access is True
    assert role == "Reporter"
    assert is_creator is False


@pytest.mark.unit
def test_get_user_kb_permission_external_resolver_not_called_when_creator(
    test_db: Session,
) -> None:
    """
    When the user is the KB creator, kb_permission_resolver.resolve must NOT be called.
    """
    from unittest.mock import MagicMock, patch

    from app.services.share.knowledge_share_service import KnowledgeShareService

    service = KnowledgeShareService()
    db = test_db

    mock_kb = MagicMock()
    mock_kb.id = 55
    mock_kb.user_id = 7  # matches requesting user
    mock_kb.namespace = "default"
    mock_kb.kind = "KnowledgeBase"
    mock_kb.is_active = True

    with (
        patch.object(db, "query") as mock_query,
        patch(
            "app.services.readers.kb_permissions.kb_permission_resolver"
        ) as mock_resolver,
        patch.object(_kss_module, "is_restricted_analyst", return_value=False),
    ):
        mock_query.return_value.filter.return_value.first.return_value = mock_kb

        has_access, _role, is_creator = service.get_user_kb_permission(
            db, knowledge_base_id=55, user_id=7
        )

    assert has_access is True
    assert is_creator is True
    mock_resolver.resolve.assert_not_called()
