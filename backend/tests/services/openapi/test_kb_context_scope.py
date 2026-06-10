# SPDX-FileCopyrightText: 2026 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

from sqlalchemy.orm import Session

from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeFolderCreate
from app.services.knowledge.folder_service import KnowledgeFolderService
from app.services.knowledge.knowledge_service import KnowledgeService
from app.services.openapi.kb_context import KnowledgeBaseContextCreator


def test_create_contexts_preserves_empty_restricted_scope(
    test_db: Session,
    test_user,
) -> None:
    kb_id = KnowledgeService.create_knowledge_base(
        test_db,
        test_user.id,
        KnowledgeBaseCreate(name="ctx-empty-scope-kb"),
    )
    folder = KnowledgeFolderService.create_folder(
        test_db,
        kb_id,
        test_user.id,
        KnowledgeFolderCreate(name="empty", parent_id=0),
    )

    creator = KnowledgeBaseContextCreator(test_db, test_user.id)
    contexts = creator.create_contexts(
        subtask_id=123,
        kb_refs=[
            {
                "namespace": "default",
                "name": "ctx-empty-scope-kb",
                "folder_ids": [folder.id],
                "document_ids": None,
                "include_subfolders": True,
            }
        ],
    )

    assert len(contexts) == 1
    assert contexts[0].type_data["knowledge_id"] == kb_id
    assert contexts[0].type_data["scope_restricted"] is True
    assert contexts[0].type_data["document_ids"] == []
    assert contexts[0].type_data["folder_ids"] == [folder.id]
    assert contexts[0].type_data["include_subfolders"] is True
