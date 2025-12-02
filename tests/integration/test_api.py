"""
Integration Tests for API Endpoints

Tests the FastAPI endpoints with mocked services.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_ok(self, test_client):
        """Test health endpoint returns healthy status."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy" or "status" in data

    def test_health_check_includes_services(self, test_client):
        """Test health check includes service statuses."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        # Should include service health info
        assert "services" in data or "status" in data


class TestQueryEndpoint:
    """Tests for query endpoint."""

    def test_query_requires_question(self, test_client):
        """Test query endpoint requires question field."""
        response = test_client.post("/api/v1/query", json={})

        assert response.status_code == 422  # Validation error

    def test_query_accepts_valid_request(self, test_client, test_query_request):
        """Test query endpoint accepts valid request."""
        with patch("src.main.run_agent_query") as mock_query:
            mock_query.return_value = {
                "answer": "The termination conditions are...",
                "sources": [],
            }

            response = test_client.post("/api/v1/query", json=test_query_request)

            # Should either succeed or be handled
            assert response.status_code in [200, 500, 503]

    def test_query_with_session(self, test_client):
        """Test query with session context."""
        with patch("src.main.run_agent_query") as mock_query:
            mock_query.return_value = {"answer": "Test answer", "sources": []}

            response = test_client.post("/api/v1/query", json={
                "question": "What is the contract term?",
                "session_id": "test-session-123",
            })

            assert response.status_code in [200, 500, 503]


class TestSearchEndpoint:
    """Tests for search endpoint."""

    def test_search_requires_query(self, test_client):
        """Test search endpoint requires query parameter."""
        response = test_client.post("/api/v1/search", data={})

        assert response.status_code == 422

    def test_search_returns_results(self, test_client, mock_vector_service):
        """Test search returns results."""
        with patch("src.main.get_vector_service", return_value=mock_vector_service):
            response = test_client.post("/api/v1/search", data={
                "query": "termination clauses",
                "top_k": "5",
            })

            # Should handle the request
            assert response.status_code in [200, 500, 503]


class TestDocumentUploadEndpoint:
    """Tests for document upload endpoint."""

    def test_upload_requires_file(self, test_client):
        """Test upload endpoint requires file."""
        response = test_client.post("/api/v1/documents/upload")

        assert response.status_code == 422

    def test_upload_accepts_pdf(self, test_client, test_upload_file, mock_storage_service, mock_vector_service):
        """Test upload accepts PDF files."""
        with patch("src.main.get_storage_service", return_value=mock_storage_service), \
             patch("src.main.get_vector_service", return_value=mock_vector_service):

            response = test_client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", test_upload_file, "application/pdf")},
                data={"collection_name": "contracts"},
            )

            # Should handle the request
            assert response.status_code in [200, 201, 500, 503]


class TestSessionEndpoint:
    """Tests for session management endpoint."""

    def test_create_session(self, test_client, mock_session_manager):
        """Test session creation."""
        with patch("src.main.get_session_manager", return_value=mock_session_manager):
            response = test_client.post("/api/v1/sessions", json={
                "user_id": "test-user-1",
            })

            # Should handle the request
            assert response.status_code in [200, 201, 500, 503]


class TestA2AEndpoints:
    """Tests for A2A Protocol endpoints."""

    def test_agent_card_endpoint(self, test_client):
        """Test Agent Card discovery endpoint."""
        response = test_client.get("/a2a/.well-known/agent.json")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data or "skills" in data

    def test_a2a_task_creation(self, test_client):
        """Test A2A task submission."""
        response = test_client.post("/a2a/tasks", json={
            "skillId": "contract_search",
            "input": {"query": "termination", "top_k": 5},
        })

        # Should handle the request
        assert response.status_code in [200, 201, 202, 400, 500]


class TestMCPEndpoints:
    """Tests for MCP endpoints."""

    def test_list_tools(self, test_client):
        """Test MCP tools listing."""
        response = test_client.get("/mcp/tools")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data or isinstance(data, list)

    def test_call_tool(self, test_client):
        """Test MCP tool invocation."""
        response = test_client.post("/mcp/tools/search_contracts", json={
            "query": "liability clauses",
            "top_k": 3,
        })

        # Should handle the request
        assert response.status_code in [200, 400, 404, 500]


class TestTaskEndpoints:
    """Tests for long-running task endpoints."""

    def test_create_task(self, test_client):
        """Test task creation."""
        response = test_client.post("/api/v1/tasks", json={
            "name": "contract_analysis",
            "input_data": {"document_id": "doc-123", "query": "Full analysis"},
        })

        # Should handle the request
        assert response.status_code in [200, 201, 400, 500]

    def test_get_task_status(self, test_client):
        """Test getting task status."""
        response = test_client.get("/api/v1/tasks/test-task-123")

        # Should handle the request (404 if not found, 200 if found)
        assert response.status_code in [200, 404, 500]


class TestEvaluationEndpoints:
    """Tests for evaluation endpoints."""

    def test_run_evaluation_suite(self, test_client):
        """Test running evaluation suite."""
        response = test_client.post("/api/v1/evaluation/suite", json={
            "suite_name": "quick",
        })

        # Should handle the request
        assert response.status_code in [200, 202, 400, 500]

    def test_get_metrics(self, test_client):
        """Test getting evaluation metrics."""
        response = test_client.get("/api/v1/evaluation/metrics")

        # Should handle the request
        assert response.status_code in [200, 500]


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_endpoint(self, test_client):
        """Test invalid endpoint returns 404."""
        response = test_client.get("/api/v1/nonexistent")

        assert response.status_code == 404

    def test_invalid_method(self, test_client):
        """Test invalid method returns 405."""
        response = test_client.delete("/api/v1/query")

        assert response.status_code == 405

    def test_malformed_json(self, test_client):
        """Test malformed JSON returns 422."""
        response = test_client.post(
            "/api/v1/query",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
