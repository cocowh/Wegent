# SPDX-FileCopyrightText: 2026 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Backfill uniquely resolvable Team/Bot reference IDs."""

import argparse
import json

from app.db.session import SessionLocal
from app.services.kind_reference_migration import migrate_legacy_kind_references


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist unique matches. The default is a read-only audit.",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        report = migrate_legacy_kind_references(db, apply_changes=args.apply)
        print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
