# SPDX-FileCopyrightText: 2026 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for KnowledgeOrchestrator.search_documents and
RagRuntimeResolver.build_public_query_runtime_spec_from_kb (Bug 4 fix)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kb(
    kb_id: int = 1,
    user_id: int = 99,
    retriever_name: str = "r1",
    embedding_model_name: str = "emb1",
) -> MagicMock:
    """Return a minimal Kind-like mock that represents a KnowledgeBase."""
    kb = MagicMock()
    kb.id = kb_id
    kb.user_id = user_id
    kb.json = {
        "spec": {
            "retrievalConfig": {
                "retriever_name": retriever_name,
                "retriever_namespace": "default",
                "embedding_config": {
                    "model_name": embedding_model_name,
                    "model_namespace": "default",
                },
            }
        }
    }
    return kb


# ---------------------------------------------------------------------------
# KnowledgeOrchestrator.search_documents
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSearchDocumentsOrchestrator:
    """Unit tests for KnowledgeOrchestrator.search_documents."""

    @pytest.fixture
    def orchestrator(self):
        from app.services.knowledge.orchestrator import KnowledgeOrchestrator

        return KnowledgeOrchestrator()

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        return SimpleNamespace(id=1, user_name="testuser")

    @pytest.mark.asyncio
    async def test_raises_value_error_when_kb_not_found(
        self, orchestrator, mock_db, mock_user
    ):
        with patch(
            "app.services.knowledge.orchestrator.KnowledgeService.get_knowledge_base",
            return_value=(None, False),
        ):
            with pytest.raises(ValueError, match="not found"):
                await orchestrator.search_documents(
                    db=mock_db,
                    user=mock_user,
                    knowledge_base_id=999,
                    query="test",
                    top_k=5,
                    score_threshold=0.7,
                )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_access_denied(
        self, orchestrator, mock_db, mock_user
    ):
        kb = _make_kb()
        with patch(
            "app.services.knowledge.orchestrator.KnowledgeService.get_knowledge_base",
            return_value=(kb, False),
        ):
            with pytest.raises(ValueError, match="[Aa]ccess denied"):
                await orchestrator.search_documents(
                    db=mock_db,
                    user=mock_user,
                    knowledge_base_id=1,
                    query="test",
                    top_k=5,
                    score_threshold=0.7,
                )

    @pytest.mark.asyncio
    async def test_raises_when_retriever_name_missing(
        self, orchestrator, mock_db, mock_user
    ):
        kb = MagicMock()
        kb.json = {
            "spec": {"retrievalConfig": {"embedding_config": {"model_name": "emb1"}}}
        }
        with patch(
            "app.services.knowledge.orchestrator.KnowledgeService.get_knowledge_base",
            return_value=(kb, True),
        ):
            with pytest.raises(ValueError, match="retriever_name"):
                await orchestrator.search_documents(
                    db=mock_db,
                    user=mock_user,
                    knowledge_base_id=1,
                    query="test",
                    top_k=5,
                    score_threshold=0.7,
                )

    @pytest.mark.asyncio
    async def test_raises_when_embedding_model_missing(
        self, orchestrator, mock_db, mock_user
    ):
        kb = MagicMock()
        kb.json = {
            "spec": {
                "retrievalConfig": {
                    "retriever_name": "r1",
                    "embedding_config": {},
                }
            }
        }
        with patch(
            "app.services.knowledge.orchestrator.KnowledgeService.get_knowledge_base",
            return_value=(kb, True),
        ):
            with pytest.raises(ValueError, match="embedding model"):
                await orchestrator.search_documents(
                    db=mock_db,
                    user=mock_user,
                    knowledge_base_id=1,
                    query="test",
                    top_k=5,
                    score_threshold=0.7,
                )

    @pytest.mark.asyncio
    async def test_calls_from_kb_overload_not_standard_method(
        self, orchestrator, mock_db, mock_user
    ):
        """Bug 4 regression: search_documents must call build_public_query_runtime_spec_from_kb
        (the overload that accepts an already-resolved kb) instead of the standard method
        that issues a second DB query."""
        kb = _make_kb()
        mock_spec = MagicMock()
        mock_gateway = AsyncMock()
        mock_gateway.query = AsyncMock(return_value={"records": []})

        with (
            patch(
                "app.services.knowledge.orchestrator.KnowledgeService.get_knowledge_base",
                return_value=(kb, True),
            ),
            patch(
                "app.services.rag.runtime_resolver.RagRuntimeResolver"
                ".build_public_query_runtime_spec_from_kb",
                return_value=mock_spec,
            ) as mock_from_kb,
            patch(
                "app.services.rag.runtime_resolver.RagRuntimeResolver"
                ".build_public_query_runtime_spec",
            ) as mock_standard,
            patch(
                "app.services.rag.gateway_factory.get_query_gateway",
                return_value=mock_gateway,
            ),
        ):
            await orchestrator.search_documents(
                db=mock_db,
                user=mock_user,
                knowledge_base_id=1,
                query="hello",
                top_k=5,
                score_threshold=0.7,
            )

        # Must use the overload that skips the extra DB lookup
        mock_from_kb.assert_called_once()
        # The already-resolved kb object must be passed in
        assert mock_from_kb.call_args.kwargs["kb"] is kb
        # The original method (with duplicate DB query) must NOT be called
        mock_standard.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_records_from_gateway(self, orchestrator, mock_db, mock_user):
        kb = _make_kb()
        expected_records = [{"content": "chunk", "score": 0.9, "title": "doc"}]
        mock_gateway = AsyncMock()
        mock_gateway.query = AsyncMock(return_value={"records": expected_records})

        with (
            patch(
                "app.services.knowledge.orchestrator.KnowledgeService.get_knowledge_base",
                return_value=(kb, True),
            ),
            patch(
                "app.services.rag.runtime_resolver.RagRuntimeResolver"
                ".build_public_query_runtime_spec_from_kb",
                return_value=MagicMock(),
            ),
            patch(
                "app.services.rag.gateway_factory.get_query_gateway",
                return_value=mock_gateway,
            ),
        ):
            result = await orchestrator.search_documents(
                db=mock_db,
                user=mock_user,
                knowledge_base_id=1,
                query="test query",
                top_k=3,
                score_threshold=0.6,
            )

        assert result == {"records": expected_records}


# ---------------------------------------------------------------------------
# RagRuntimeResolver.build_public_query_runtime_spec_from_kb
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildPublicQueryRuntimeSpecFromKb:
    """Unit tests for the new RagRuntimeResolver overload introduced in Bug 4 fix."""

    @pytest.fixture
    def resolver(self):
        from app.services.rag.runtime_resolver import RagRuntimeResolver

        return RagRuntimeResolver()

    def test_builds_spec_with_correct_kb_id(self, resolver):
        db = MagicMock()
        kb = _make_kb(kb_id=7, user_id=42)
        mock_retriever_cfg = MagicMock()
        mock_embedding_cfg = MagicMock()

        with (
            patch.object(
                resolver,
                "_build_resolved_retriever_config",
                return_value=mock_retriever_cfg,
            ),
            patch.object(
                resolver,
                "_build_resolved_embedding_model_config",
                return_value=mock_embedding_cfg,
            ),
        ):
            spec = resolver.build_public_query_runtime_spec_from_kb(
                kb=kb,
                db=db,
                query="search query",
                max_results=5,
                retriever_name="r1",
                retriever_namespace="default",
                embedding_model_name="emb1",
                embedding_model_namespace="default",
                user_id=1,
                user_name="user",
                score_threshold=0.7,
                retrieval_mode="vector",
            )

        assert spec.knowledge_base_ids == [7]
        assert spec.query == "search query"
        assert spec.max_results == 5

    def test_does_not_query_database_for_kb(self, resolver):
        """Core assertion for Bug 4: no DB lookup should be issued."""
        db = MagicMock()
        kb = _make_kb()

        with (
            patch.object(
                resolver, "_build_resolved_retriever_config", return_value=MagicMock()
            ),
            patch.object(
                resolver,
                "_build_resolved_embedding_model_config",
                return_value=MagicMock(),
            ),
        ):
            resolver.build_public_query_runtime_spec_from_kb(
                kb=kb,
                db=db,
                query="test",
                max_results=5,
                retriever_name="r1",
                retriever_namespace="default",
                embedding_model_name="emb1",
                embedding_model_namespace="default",
                user_id=1,
                user_name="user",
                score_threshold=0.7,
                retrieval_mode="vector",
            )

        # If a DB query were issued the mock would record a call — must be zero
        db.query.assert_not_called()

    def test_passes_retrieval_config_to_kb_config(self, resolver):
        db = MagicMock()
        kb = _make_kb(kb_id=3, user_id=10)
        mock_retriever_cfg = MagicMock()
        mock_embedding_cfg = MagicMock()

        with (
            patch.object(
                resolver,
                "_build_resolved_retriever_config",
                return_value=mock_retriever_cfg,
            ) as mock_ret,
            patch.object(
                resolver,
                "_build_resolved_embedding_model_config",
                return_value=mock_embedding_cfg,
            ) as mock_emb,
        ):
            spec = resolver.build_public_query_runtime_spec_from_kb(
                kb=kb,
                db=db,
                query="q",
                max_results=10,
                retriever_name="my-retriever",
                retriever_namespace="ns1",
                embedding_model_name="my-emb",
                embedding_model_namespace="ns2",
                user_id=1,
                user_name="u",
                score_threshold=0.8,
                retrieval_mode="hybrid",
                vector_weight=0.6,
                keyword_weight=0.4,
            )

        # Retriever config built with kb owner's user_id (10), not caller's (1)
        mock_ret.assert_called_once_with(
            db=db, user_id=10, name="my-retriever", namespace="ns1"
        )
        mock_emb.assert_called_once_with(
            db=db,
            user_id=10,
            model_name="my-emb",
            model_namespace="ns2",
            user_name="u",
        )
        # Retrieval config embedded in the first KB config entry
        kb_cfg = spec.knowledge_base_configs[0]
        assert kb_cfg.retrieval_config.score_threshold == 0.8
        assert kb_cfg.retrieval_config.retrieval_mode == "hybrid"
        assert kb_cfg.retrieval_config.vector_weight == 0.6
        assert kb_cfg.retrieval_config.keyword_weight == 0.4
