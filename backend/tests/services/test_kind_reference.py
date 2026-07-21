# SPDX-FileCopyrightText: 2026 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

from app.models.kind import Kind
from app.services import kind_reference
from app.services.kind_reference import resolve_kind_reference
from app.services.kind_reference_migration import migrate_legacy_kind_references


def _kind(
    *,
    user_id: int,
    kind: str,
    name: str,
    namespace: str = "default",
    spec: dict | None = None,
    active: bool = True,
) -> Kind:
    return Kind(
        user_id=user_id,
        kind=kind,
        name=name,
        namespace=namespace,
        is_active=active,
        json={
            "apiVersion": "agent.wecode.io/v1",
            "kind": kind,
            "metadata": {"name": name, "namespace": namespace},
            "spec": spec or {},
        },
    )


def test_id_reference_never_falls_back_to_same_name(test_db) -> None:
    intended = _kind(user_id=1, kind="Bot", name="duplicate")
    wrong_owner = _kind(user_id=2, kind="Bot", name="duplicate")
    test_db.add_all([intended, wrong_owner])
    test_db.commit()

    resolution = resolve_kind_reference(
        test_db,
        kind="Bot",
        ref={
            "id": wrong_owner.id,
            "name": "duplicate",
            "namespace": "default",
        },
        actor_user_id=1,
    )

    assert resolution.resource is None
    assert resolution.reason == "permission_denied"
    legacy = resolve_kind_reference(
        test_db,
        kind="Bot",
        ref={"name": "duplicate", "namespace": "default"},
        actor_user_id=1,
    )
    assert legacy.resource.id == intended.id
    assert legacy.used_legacy_lookup is True


def test_id_reference_validates_kind_active_and_snapshot(test_db) -> None:
    ghost = _kind(user_id=1, kind="Ghost", name="ghost")
    inactive = _kind(user_id=1, kind="Bot", name="inactive", active=False)
    test_db.add_all([ghost, inactive])
    test_db.commit()

    assert (
        resolve_kind_reference(
            test_db,
            kind="Bot",
            ref={"id": ghost.id, "name": "ghost", "namespace": "default"},
            actor_user_id=1,
        ).reason
        == "kind_mismatch"
    )
    assert (
        resolve_kind_reference(
            test_db,
            kind="Bot",
            ref={"id": inactive.id, "name": "inactive", "namespace": "default"},
            actor_user_id=1,
        ).reason
        == "inactive"
    )
    assert (
        resolve_kind_reference(
            test_db,
            kind="Ghost",
            ref={"id": ghost.id, "name": "renamed", "namespace": "default"},
            actor_user_id=1,
        ).reason
        == "name_mismatch"
    )


def test_group_reference_supports_different_team_and_bot_owners(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        kind_reference,
        "check_group_permission",
        lambda db, user_id, namespace, role: user_id == 10 and namespace == "group-a",
    )
    bot = _kind(user_id=20, kind="Bot", name="shared", namespace="group-a")
    same_name = _kind(user_id=30, kind="Bot", name="shared", namespace="group-a")
    test_db.add_all([bot, same_name])
    test_db.commit()

    resolution = resolve_kind_reference(
        test_db,
        kind="Bot",
        ref={"id": bot.id, "name": "shared", "namespace": "group-a"},
        actor_user_id=10,
    )

    assert resolution.resource.id == bot.id


def test_group_owner_can_resolve_owned_reference_without_membership(test_db) -> None:
    bot = _kind(user_id=10, kind="Bot", name="owned", namespace="group-a")
    test_db.add(bot)
    test_db.commit()

    resolution = resolve_kind_reference(
        test_db,
        kind="Bot",
        ref={"name": "owned", "namespace": "group-a"},
        actor_user_id=10,
    )

    assert resolution.resource.id == bot.id
    assert resolution.used_legacy_lookup is True


def test_safe_migration_backfills_unique_refs_and_records_conflicts(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        kind_reference,
        "check_group_permission",
        lambda db, user_id, namespace, role: True,
    )
    unique_ghost = _kind(user_id=1, kind="Ghost", name="unique-ghost")
    legacy_bot = _kind(
        user_id=1,
        kind="Bot",
        name="legacy-bot",
        spec={
            "ghostRef": {"name": "unique-ghost", "namespace": "default"},
            "shellRef": {"name": "Chat", "namespace": "default"},
        },
    )
    duplicate_one = _kind(
        user_id=2,
        kind="Bot",
        name="duplicate-bot",
        namespace="group-a",
    )
    duplicate_two = _kind(
        user_id=3,
        kind="Bot",
        name="duplicate-bot",
        namespace="group-a",
    )
    legacy_team = _kind(
        user_id=1,
        kind="Team",
        name="legacy-team",
        namespace="group-a",
        spec={
            "members": [
                {
                    "botRef": {
                        "name": "duplicate-bot",
                        "namespace": "group-a",
                    }
                }
            ],
            "collaborationModel": "solo",
        },
    )
    test_db.add_all(
        [unique_ghost, legacy_bot, duplicate_one, duplicate_two, legacy_team]
    )
    test_db.commit()

    report = migrate_legacy_kind_references(test_db, apply_changes=True)

    test_db.refresh(legacy_bot)
    test_db.refresh(legacy_team)
    assert legacy_bot.json["spec"]["ghostRef"]["id"] == unique_ghost.id
    assert "id" not in legacy_team.json["spec"]["members"][0]["botRef"]
    assert report.migrated == 1
    assert len(report.conflicts) == 1
    assert report.failures == []
