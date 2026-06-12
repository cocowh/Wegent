# SPDX-FileCopyrightText: 2026 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Shared helpers for scoped knowledge-base tool access."""

import json
from typing import Any, Optional

DOCUMENT_SCOPE_OUT_OF_RANGE_MESSAGE = (
    "Requested documents are outside the allowed scoped knowledge range "
    "for this conversation."
)


def dedupe_document_ids(document_ids: Optional[list[int]]) -> list[int]:
    """Deduplicate document IDs while preserving input order."""
    if not document_ids:
        return []
    seen: set[int] = set()
    deduped: list[int] = []
    for document_id in document_ids:
        if document_id in seen:
            continue
        seen.add(document_id)
        deduped.append(document_id)
    return deduped


def get_out_of_scope_document_ids(
    *,
    requested_document_ids: list[int],
    allowed_document_ids: list[int],
) -> list[int]:
    """Return requested document IDs that are not in the scoped allowlist."""
    allowed_set = set(allowed_document_ids)
    return [
        document_id
        for document_id in requested_document_ids
        if document_id not in allowed_set
    ]


def format_document_scope_violation(
    *,
    knowledge_base_ids: list[int],
    accessible_document_count: int,
    message: str = DOCUMENT_SCOPE_OUT_OF_RANGE_MESSAGE,
    requested_document_ids: Optional[list[int]] = None,
) -> str:
    """Build a fail-closed scoped document access rejection payload."""
    payload: dict[str, Any] = {
        "status": "error",
        "error_code": "document_scope_violation",
        "message": message,
        "knowledge_base_ids": knowledge_base_ids,
        "accessible_document_count": accessible_document_count,
    }
    if requested_document_ids is not None:
        payload["requested_document_ids"] = requested_document_ids
    return json.dumps(payload, ensure_ascii=False)
