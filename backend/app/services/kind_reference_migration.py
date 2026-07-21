# SPDX-FileCopyrightText: 2026 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Safe, best-effort migration of legacy Bot and Ghost references."""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.kind import Kind
from app.services.kind_reference import legacy_reference_candidates

logger = logging.getLogger(__name__)


@dataclass
class KindReferenceMigrationReport:
    """Counts and diagnostics produced by a reference migration run."""

    migrated: int = 0
    conflicts: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def migrate_legacy_kind_references(
    db: Session,
    *,
    apply_changes: bool = False,
) -> KindReferenceMigrationReport:
    """Backfill only uniquely resolvable refs and never fail the full run."""
    report = KindReferenceMigrationReport()
    parents = (
        db.query(Kind)
        .filter(Kind.kind.in_(["Bot", "Team"]), Kind.is_active.is_(True))
        .all()
    )
    for parent in parents:
        try:
            changed = _migrate_parent(parent, db, report)
            if changed and apply_changes:
                db.add(parent)
            elif changed:
                db.expire(parent, ["json"])
        except Exception as exc:
            diagnostic = f"{parent.kind}:{parent.id}:{type(exc).__name__}"
            report.failures.append(diagnostic)
            logger.warning(
                "Kind reference migration failed for %s id=%s",
                parent.kind,
                parent.id,
                exc_info=True,
            )
    if apply_changes:
        db.commit()
    return report


def _migrate_parent(
    parent: Kind,
    db: Session,
    report: KindReferenceMigrationReport,
) -> bool:
    payload = deepcopy(parent.json) if isinstance(parent.json, dict) else {}
    spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else {}
    refs = (
        [spec.get("ghostRef")]
        if parent.kind == "Bot"
        else [member.get("botRef") for member in spec.get("members") or []]
    )
    target_kind = "Ghost" if parent.kind == "Bot" else "Bot"
    changed = False
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict) or ref.get("id") is not None:
            continue
        name = ref.get("name")
        namespace = ref.get("namespace", "default")
        diagnostic = f"{parent.kind}:{parent.id}:{index}:{namespace}/{name}"
        if not name:
            report.invalid.append(diagnostic)
            logger.warning("Invalid legacy Kind reference: %s", diagnostic)
            continue
        candidates = legacy_reference_candidates(
            db,
            kind=target_kind,
            name=name,
            namespace=namespace,
            actor_user_id=parent.user_id,
        )
        if len(candidates) == 1:
            ref["id"] = candidates[0].id
            report.migrated += 1
            changed = True
        elif len(candidates) > 1:
            report.conflicts.append(diagnostic)
            logger.warning("Ambiguous legacy Kind reference: %s", diagnostic)
        else:
            report.invalid.append(diagnostic)
            logger.warning("Unresolved legacy Kind reference: %s", diagnostic)
    if changed:
        parent.json = payload
    return changed
