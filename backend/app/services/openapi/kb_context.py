# SPDX-FileCopyrightText: 2025 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""
Knowledge base context creation for OpenAPI v1/responses endpoint.

This module provides functionality to create SubtaskContext records
for knowledge bases specified in API requests.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.subtask_context import ContextStatus, ContextType, SubtaskContext
from app.services.knowledge.task_knowledge_base_service import (
    task_knowledge_base_service,
)
from app.services.openapi.kb_resolver import (
    KnowledgeBaseNameResolver,
    ResolvedKnowledgeBase,
    ResolvedKnowledgeBaseRef,
)

logger = logging.getLogger(__name__)


class KnowledgeBaseContextCreator:
    """
    Creator for knowledge base SubtaskContext records.

    This class handles the creation of SubtaskContext records for
    knowledge bases specified in OpenAPI requests, enabling RAG
    functionality through the existing context processing pipeline.
    """

    def __init__(self, db: Session, user_id: int):
        """
        Initialize the creator.

        Args:
            db: Database session
            user_id: ID of the user creating the contexts
        """
        self.db = db
        self.user_id = user_id
        self.resolver = KnowledgeBaseNameResolver(db, user_id)

    def create_contexts(
        self,
        subtask_id: int,
        kb_refs: List[dict] | None = None,
        *,
        kb_names: List[dict] | None = None,
        task=None,
        user_name: Optional[str] = None,
    ) -> List[SubtaskContext]:
        """
        Create SubtaskContext records for knowledge bases.

        This method resolves knowledge base names to IDs and creates
        corresponding SubtaskContext records that will be processed
        by the existing RAG pipeline.

        Args:
            subtask_id: ID of the subtask to attach contexts to
            kb_refs: List of dicts with 'namespace', 'name', and optional scope keys
            kb_names: Backward-compatible alias for unscoped knowledge base names
            task: Optional task to sync selected KBs into task-level refs
            user_name: Optional user name used as boundBy during task-level sync

        Returns:
            List of created SubtaskContext records
        """
        refs = kb_refs if kb_refs is not None else kb_names
        if not refs:
            return []

        scope_specified = any(
            ref.get("folder_ids") is not None or ref.get("document_ids") is not None
            for ref in refs
        )
        if scope_specified:
            resolution_result = self.resolver.resolve_refs(refs, raise_on_error=True)
        else:
            resolution_result = self.resolver.resolve(refs, raise_on_error=True)

        if not resolution_result.resolved:
            logger.warning(
                "[KBContextCreator] No knowledge bases resolved for subtask %d",
                subtask_id,
            )
            return []

        # Create SubtaskContext records
        contexts = []
        for kb in resolution_result.resolved:
            context = self._create_kb_context(subtask_id, kb)
            contexts.append(context)

        # Batch insert all contexts
        if contexts:
            self.db.add_all(contexts)
            self.db.commit()

            # Refresh to get IDs
            for ctx in contexts:
                self.db.refresh(ctx)

            logger.info(
                "[KBContextCreator] Created %d KB contexts for subtask %d: %s",
                len(contexts),
                subtask_id,
                [ctx.id for ctx in contexts],
            )

            if task is not None and user_name:
                self._sync_contexts_to_task(task, contexts, user_name)

        return contexts

    def _create_kb_context(
        self,
        subtask_id: int,
        kb: ResolvedKnowledgeBase | ResolvedKnowledgeBaseRef,
    ) -> SubtaskContext:
        """
        Create a single knowledge base SubtaskContext.

        Args:
            subtask_id: ID of the subtask to attach context to
            kb: Resolved knowledge base metadata with optional scope

        Returns:
            SubtaskContext object (not yet committed)
        """
        # Build type_data with knowledge_id for RAG processing
        type_data = {
            "knowledge_id": kb.kb_id,
            "document_count": None,  # Will be populated by RAG service if needed
        }
        scope_restricted = getattr(kb, "scope_restricted", False)
        if scope_restricted:
            type_data["scope_restricted"] = True
            type_data["document_ids"] = getattr(kb, "resolved_document_ids", [])
            folder_ids = getattr(kb, "folder_ids", None)
            if folder_ids is not None:
                type_data["folder_ids"] = folder_ids
                type_data["include_subfolders"] = getattr(
                    kb, "include_subfolders", True
                )

        context = SubtaskContext(
            subtask_id=subtask_id,
            user_id=self.user_id,
            context_type=ContextType.KNOWLEDGE_BASE.value,
            name=kb.display_name,
            status=ContextStatus.READY.value,
            type_data=type_data,
        )

        logger.debug(
            "[KBContextCreator] Creating KB context: subtask_id=%d, kb_id=%d, name=%s",
            subtask_id,
            kb.kb_id,
            kb.display_name,
        )

        return context

    def _sync_contexts_to_task(
        self,
        task,
        contexts: List[SubtaskContext],
        user_name: str,
    ) -> None:
        """Best-effort sync of selected KB contexts to task-level knowledgeBaseRefs."""
        for context in contexts:
            knowledge_id = (
                context.type_data.get("knowledge_id") if context.type_data else None
            )
            if not knowledge_id:
                continue
            if context.type_data.get("scope_restricted") is True:
                logger.info(
                    "[KBContextCreator] Skip task-level sync for scoped KB %s "
                    "from subtask %s",
                    knowledge_id,
                    context.subtask_id,
                )
                continue
            synced = task_knowledge_base_service.sync_subtask_kb_to_task(
                db=self.db,
                task=task,
                knowledge_id=knowledge_id,
                user_id=self.user_id,
                user_name=user_name,
            )
            if synced:
                logger.info(
                    "[KBContextCreator] Synced KB %s to task %s from subtask-level selection",
                    knowledge_id,
                    task.id,
                )
