# SPDX-FileCopyrightText: 2026 Weibo, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for v1 knowledge API endpoints (/api/knowledge/...)."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /api/knowledge/documents — list_documents_v1
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListDocumentsV1:
    """Tests for list_documents_v1 endpoint."""

    def test_returns_document_list_when_kb_exists(
        self, test_client: TestClient, test_token: str
    ):
        mock_response = MagicMock()
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.list_documents",
            return_value=mock_response,
        ):
            resp = test_client.get(
                "/api/knowledge/documents",
                params={"knowledge_base_id": 1},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 200

    def test_missing_knowledge_base_id_returns_422(
        self, test_client: TestClient, test_token: str
    ):
        resp = test_client.get(
            "/api/knowledge/documents",
            headers=_auth_header(test_token),
        )
        assert resp.status_code == 422

    def test_kb_not_found_returns_404(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.list_documents",
            side_effect=ValueError("Knowledge base 999 not found"),
        ):
            resp = test_client.get(
                "/api/knowledge/documents",
                params={"knowledge_base_id": 999},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_access_denied_returns_403(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.list_documents",
            side_effect=ValueError("Access denied to knowledge base 1"),
        ):
            resp = test_client.get(
                "/api/knowledge/documents",
                params={"knowledge_base_id": 1},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 403

    def test_unauthenticated_request_returns_401_or_403(self, test_client: TestClient):
        resp = test_client.get(
            "/api/knowledge/documents",
            params={"knowledge_base_id": 1},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/knowledge/documents/{id}/content — get_document_content_v1
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetDocumentContentV1:
    """Tests for get_document_content_v1 endpoint."""

    def test_returns_content_for_accessible_document(
        self, test_client: TestClient, test_token: str
    ):
        mock_response = MagicMock()
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.read_document_content",
            return_value=mock_response,
        ):
            resp = test_client.get(
                "/api/knowledge/documents/1/content",
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 200

    def test_document_not_found_returns_404(
        self, test_client: TestClient, test_token: str
    ):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.read_document_content",
            side_effect=ValueError("Document not found"),
        ):
            resp = test_client.get(
                "/api/knowledge/documents/999/content",
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 404

    def test_access_denied_returns_403(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.read_document_content",
            side_effect=ValueError("Access denied to document 1"),
        ):
            resp = test_client.get(
                "/api/knowledge/documents/1/content",
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 403

    def test_pagination_params_forwarded_to_orchestrator(
        self, test_client: TestClient, test_token: str
    ):
        mock_response = MagicMock()
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.read_document_content",
            return_value=mock_response,
        ) as mock_read:
            test_client.get(
                "/api/knowledge/documents/1/content",
                params={"offset": 100, "limit": 500},
                headers=_auth_header(test_token),
            )
        call_kwargs = mock_read.call_args.kwargs
        assert call_kwargs["offset"] == 100
        assert call_kwargs["limit"] == 500


# ---------------------------------------------------------------------------
# POST /api/knowledge/documents — create_document_v1
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateDocumentV1:
    """Tests for create_document_v1 endpoint — all source types and error paths."""

    def test_creates_text_document_returns_201(
        self, test_client: TestClient, test_token: str
    ):
        mock_doc = MagicMock()
        mock_doc.model_fields = {}
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_document_with_content",
            return_value=mock_doc,
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 1,
                    "name": "my-note",
                    "source_type": "text",
                    "content": "Hello, world!",
                },
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 201

    def test_creates_file_document_returns_201(
        self, test_client: TestClient, test_token: str
    ):
        file_b64 = base64.b64encode(b"PDF content bytes").decode()
        mock_doc = MagicMock()
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_document_with_content",
            return_value=mock_doc,
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 1,
                    "name": "report.pdf",
                    "source_type": "file",
                    "file_base64": file_b64,
                    "file_extension": "pdf",
                },
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 201

    def test_creates_web_document_returns_201(
        self, test_client: TestClient, test_token: str
    ):
        mock_doc = MagicMock()
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_web_document",
            new_callable=AsyncMock,
            return_value={"success": True, "document": mock_doc},
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 1,
                    "name": "scraped-page",
                    "source_type": "web",
                    "url": "https://example.com/article",
                },
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 201

    def test_creates_attachment_document_returns_201(
        self, test_client: TestClient, test_token: str
    ):
        mock_doc = MagicMock()
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_document_with_content",
            return_value=mock_doc,
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 1,
                    "name": "from-attachment",
                    "source_type": "attachment",
                    "attachment_id": 42,
                },
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 201

    def test_table_source_type_rejected_with_4xx(
        self, test_client: TestClient, test_token: str
    ):
        # 'table' is reserved for external integrations and must be rejected
        resp = test_client.post(
            "/api/knowledge/documents",
            json={
                "knowledge_base_id": 1,
                "name": "sheet",
                "source_type": "table",
            },
            headers=_auth_header(test_token),
        )
        assert resp.status_code in (400, 422)

    def test_web_scraping_success_but_document_none_returns_502(
        self, test_client: TestClient, test_token: str
    ):
        """Regression test for Bug 3: document=None after scraping must not raise
        AttributeError (500) — endpoint should return 502 instead."""
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_web_document",
            new_callable=AsyncMock,
            return_value={"success": True, "document": None},
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 1,
                    "name": "scraped",
                    "source_type": "web",
                    "url": "https://example.com",
                },
                headers=_auth_header(test_token),
            )
        # Must be 502, not 500 (AttributeError crash)
        assert resp.status_code == 502

    def test_web_url_missing_returns_422(
        self, test_client: TestClient, test_token: str
    ):
        resp = test_client.post(
            "/api/knowledge/documents",
            json={
                "knowledge_base_id": 1,
                "name": "bad",
                "source_type": "web",
            },
            headers=_auth_header(test_token),
        )
        assert resp.status_code == 422

    def test_kb_not_found_returns_404(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_document_with_content",
            side_effect=ValueError("Knowledge base 999 not found"),
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 999,
                    "name": "doc",
                    "source_type": "text",
                    "content": "x",
                },
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 404

    def test_access_denied_returns_403(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_document_with_content",
            side_effect=ValueError("Access denied to knowledge base 1"),
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 1,
                    "name": "doc",
                    "source_type": "text",
                    "content": "x",
                },
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 403

    def test_validation_error_returns_400(
        self, test_client: TestClient, test_token: str
    ):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.create_document_with_content",
            side_effect=ValueError("Unsupported file extension 'exe'"),
        ):
            resp = test_client.post(
                "/api/knowledge/documents",
                json={
                    "knowledge_base_id": 1,
                    "name": "bad.exe",
                    "source_type": "file",
                    "file_base64": base64.b64encode(b"x").decode(),
                    "file_extension": "exe",
                },
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/knowledge/search — search_documents_v1
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSearchDocumentsV1:
    """Tests for search_documents_v1 endpoint."""

    def test_returns_records_on_success(self, test_client: TestClient, test_token: str):
        mock_result = {
            "records": [{"content": "chunk text", "score": 0.92, "title": "doc"}]
        }
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.search_documents",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = test_client.post(
                "/api/knowledge/search",
                json={"knowledge_base_id": 1, "query": "what is RAG?"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert data["records"][0]["score"] == 0.92

    def test_empty_records_returned_when_no_matches(
        self, test_client: TestClient, test_token: str
    ):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.search_documents",
            new_callable=AsyncMock,
            return_value={"records": []},
        ):
            resp = test_client.post(
                "/api/knowledge/search",
                json={"knowledge_base_id": 1, "query": "obscure query"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 200
        assert resp.json()["records"] == []

    def test_kb_not_found_returns_404(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.search_documents",
            new_callable=AsyncMock,
            side_effect=ValueError("Knowledge base 999 not found"),
        ):
            resp = test_client.post(
                "/api/knowledge/search",
                json={"knowledge_base_id": 999, "query": "test"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 404

    def test_access_denied_returns_403(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.search_documents",
            new_callable=AsyncMock,
            side_effect=ValueError("Access denied to knowledge base 1"),
        ):
            resp = test_client.post(
                "/api/knowledge/search",
                json={"knowledge_base_id": 1, "query": "test"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 403

    def test_incomplete_retrieval_config_returns_400(
        self, test_client: TestClient, test_token: str
    ):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.search_documents",
            new_callable=AsyncMock,
            side_effect=ValueError(
                "has incomplete retrieval config (missing retriever_name)"
            ),
        ):
            resp = test_client.post(
                "/api/knowledge/search",
                json={"knowledge_base_id": 1, "query": "test"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 400

    def test_empty_query_rejected_by_schema(
        self, test_client: TestClient, test_token: str
    ):
        resp = test_client.post(
            "/api/knowledge/search",
            json={"knowledge_base_id": 1, "query": ""},
            headers=_auth_header(test_token),
        )
        assert resp.status_code == 422

    def test_custom_top_k_and_score_threshold_forwarded(
        self, test_client: TestClient, test_token: str
    ):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.search_documents",
            new_callable=AsyncMock,
            return_value={"records": []},
        ) as mock_search:
            test_client.post(
                "/api/knowledge/search",
                json={
                    "knowledge_base_id": 1,
                    "query": "test",
                    "top_k": 10,
                    "score_threshold": 0.5,
                },
                headers=_auth_header(test_token),
            )
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["top_k"] == 10
        assert call_kwargs["score_threshold"] == 0.5


# ---------------------------------------------------------------------------
# PUT /api/knowledge/documents/{id} — update_document_v1
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUpdateDocumentV1:
    """Tests for update_document_v1 endpoint.

    Bug 1 regression: only "access denied" errors should return 403;
    all other ValueError (validation failures) must return 400.
    """

    def test_successful_update_returns_200(
        self, test_client: TestClient, test_token: str
    ):
        mock_doc = MagicMock()
        with patch(
            "app.api.endpoints.knowledge.KnowledgeService.update_document",
            return_value=mock_doc,
        ):
            resp = test_client.put(
                "/api/knowledge/documents/1",
                json={"name": "updated-name"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 200

    def test_document_not_found_returns_404(
        self, test_client: TestClient, test_token: str
    ):
        with patch(
            "app.api.endpoints.knowledge.KnowledgeService.update_document",
            side_effect=ValueError("Document not found"),
        ):
            resp = test_client.put(
                "/api/knowledge/documents/999",
                json={"name": "x"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 404

    def test_access_denied_returns_403(self, test_client: TestClient, test_token: str):
        with patch(
            "app.api.endpoints.knowledge.KnowledgeService.update_document",
            side_effect=ValueError("Access denied to document 1"),
        ):
            resp = test_client.put(
                "/api/knowledge/documents/1",
                json={"name": "x"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 403

    def test_validation_error_returns_400_not_403(
        self, test_client: TestClient, test_token: str
    ):
        """Bug 1 regression: a validation ValueError must not fall through to 403."""
        with patch(
            "app.api.endpoints.knowledge.KnowledgeService.update_document",
            side_effect=ValueError("Invalid status value 'unknown'"),
        ):
            resp = test_client.put(
                "/api/knowledge/documents/1",
                json={"name": "x"},
                headers=_auth_header(test_token),
            )
        # Before the bug fix this returned 403
        assert resp.status_code == 400

    def test_none_document_returns_404(self, test_client: TestClient, test_token: str):
        # Service returning None means document does not exist for this user
        with patch(
            "app.api.endpoints.knowledge.KnowledgeService.update_document",
            return_value=None,
        ):
            resp = test_client.put(
                "/api/knowledge/documents/1",
                json={"name": "x"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/knowledge/documents/{id}/content — update_document_content_v1
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUpdateDocumentContentV1:
    """Tests for update_document_content_v1 endpoint.

    Bug 1 regression: access denied must return 403 (not 404).
    Bug 2 regression: response must conform to DocumentContentUpdateResponse schema.
    """

    def test_successful_update_returns_correct_schema(
        self, test_client: TestClient, test_token: str
    ):
        """Bug 2 regression: response_model enforced — all three fields present."""
        mock_result = {
            "success": True,
            "document_id": 1,
            "message": "Document content updated successfully",
        }
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.update_document_content",
            return_value=mock_result,
        ):
            resp = test_client.put(
                "/api/knowledge/documents/1/content",
                json={"content": "# Updated heading\n\nNew content."},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["document_id"] == 1
        assert "message" in data

    def test_document_not_found_returns_404(
        self, test_client: TestClient, test_token: str
    ):
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.update_document_content",
            side_effect=ValueError("Document not found or access denied"),
        ):
            resp = test_client.put(
                "/api/knowledge/documents/999/content",
                json={"content": "x"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 404

    def test_access_denied_returns_403_not_404(
        self, test_client: TestClient, test_token: str
    ):
        """Bug 1 regression: access denied must NOT be swallowed into 404."""
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.update_document_content",
            side_effect=ValueError("Access denied to document 1"),
        ):
            resp = test_client.put(
                "/api/knowledge/documents/1/content",
                json={"content": "x"},
                headers=_auth_header(test_token),
            )
        # Before the bug fix both "not found" and "access denied" returned 404
        assert resp.status_code == 403

    def test_unsupported_document_type_returns_400(
        self, test_client: TestClient, test_token: str
    ):
        """Content update is only allowed for TEXT-type / plain-text file documents."""
        with patch(
            "app.api.endpoints.knowledge.knowledge_orchestrator.update_document_content",
            side_effect=ValueError(
                "Only TEXT type documents or plain text files can be edited"
            ),
        ):
            resp = test_client.put(
                "/api/knowledge/documents/1/content",
                json={"content": "x"},
                headers=_auth_header(test_token),
            )
        assert resp.status_code == 400

    def test_empty_content_rejected_by_schema(
        self, test_client: TestClient, test_token: str
    ):
        resp = test_client.put(
            "/api/knowledge/documents/1/content",
            json={},
            headers=_auth_header(test_token),
        )
        assert resp.status_code == 422
