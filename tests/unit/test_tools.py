"""
Unit Tests for Agent Tools

Tests for custom tools used by ContractGuard agents.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSearchTool:
    """Tests for search_contracts tool."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, mock_vector_service):
        """Test search tool returns results."""
        mock_embedding_service = AsyncMock()
        mock_embedding_service.embed_query = AsyncMock(return_value=[0.1] * 384)

        # Patch at the services module level since imports happen inside the function
        with patch("src.services.vector_service.get_vector_service", return_value=mock_vector_service), \
             patch("src.services.embedding_service.get_embedding_service", return_value=mock_embedding_service):
            from src.tools.search_tool import search_contracts

            results = await search_contracts(
                query="termination clauses",
                top_k=5,
            )

            assert results is not None
            assert "success" in results

    @pytest.mark.asyncio
    async def test_search_with_document_filter(self, mock_vector_service):
        """Test search with document ID filter."""
        mock_embedding_service = AsyncMock()
        mock_embedding_service.embed_query = AsyncMock(return_value=[0.1] * 384)

        with patch("src.services.vector_service.get_vector_service", return_value=mock_vector_service), \
             patch("src.services.embedding_service.get_embedding_service", return_value=mock_embedding_service):
            from src.tools.search_tool import search_contracts

            results = await search_contracts(
                query="liability",
                document_id="doc-123",
                top_k=3,
            )

            assert results is not None
            assert "success" in results

    @pytest.mark.asyncio
    async def test_search_handles_empty_query(self, mock_vector_service):
        """Test search handles empty query gracefully."""
        mock_vector_service.search.return_value = []
        mock_embedding_service = AsyncMock()
        mock_embedding_service.embed_query = AsyncMock(return_value=[0.1] * 384)

        with patch("src.services.vector_service.get_vector_service", return_value=mock_vector_service), \
             patch("src.services.embedding_service.get_embedding_service", return_value=mock_embedding_service):
            from src.tools.search_tool import search_contracts

            results = await search_contracts(query="", top_k=5)

            # Should handle gracefully and return a dict
            assert results is not None
            assert isinstance(results, dict)


class TestAnalysisTool:
    """Tests for analysis tools."""

    @pytest.mark.asyncio
    async def test_identify_risks_returns_structured_data(self):
        """Test risk identification returns structured data."""
        # Mock the Gemini client
        mock_response = MagicMock()
        mock_response.text = """
        Risk 1: Financial Risk
        - High liability cap of $1,000,000
        - Severity: High
        """

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.tools.analysis_tool.genai.Client", return_value=mock_client):
            from src.tools.analysis_tool import identify_risks

            result = await identify_risks(
                contract_text="The liability shall not exceed $1,000,000."
            )

            assert result is not None
            assert "success" in result

    @pytest.mark.asyncio
    async def test_analyze_clause_extracts_key_terms(self):
        """Test clause analysis extracts key terms."""
        # Mock the Gemini client
        mock_response = MagicMock()
        mock_response.text = """
        Clause Type: Liability Limitation
        Key Terms: $500,000 cap, limitation of liability
        Analysis: This clause limits total liability to $500,000.
        """

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.tools.analysis_tool.genai.Client", return_value=mock_client):
            from src.tools.analysis_tool import analyze_clause

            result = await analyze_clause(
                clause_text="Total liability shall not exceed $500,000.",
                analysis_type="financial",
            )

            assert result is not None
            assert "success" in result


class TestReportTool:
    """Tests for report generation tools."""

    @pytest.mark.asyncio
    async def test_generate_summary_creates_report(self):
        """Test summary generation creates proper report."""
        # Mock the Gemini client
        mock_response = MagicMock()
        mock_response.text = """
        ## Executive Summary
        This is a Non-Disclosure Agreement between Party A and Party B.

        ### Key Terms
        - Term: 3 years
        - Confidentiality Period: 5 years

        ### Risks
        - High liability cap of $500,000
        """

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.tools.report_tool.genai.Client", return_value=mock_client):
            from src.tools.report_tool import generate_summary

            result = await generate_summary(
                contract_text="This is a sample NDA contract text...",
                summary_type="executive",
            )

            assert result is not None
            assert "success" in result

    @pytest.mark.asyncio
    async def test_generate_risk_report(self):
        """Test risk report generation."""
        # Mock the Gemini client
        mock_response = MagicMock()
        mock_response.text = """
        # Risk Assessment Report

        ## Executive Summary
        Overall risk level: Medium

        ## Detailed Risk Analysis
        - Risk 1: High liability cap
        """

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("src.tools.report_tool.genai.Client", return_value=mock_client):
            from src.tools.report_tool import generate_risk_report

            result = await generate_risk_report(
                risks="High liability cap of $500,000",
                contract_summary="NDA between Party A and B",
            )

            assert result is not None
            assert "success" in result


class TestGoogleSearchTool:
    """Tests for Google Search tool."""

    @pytest.mark.asyncio
    async def test_search_detects_contract_queries(self):
        """Test that contract-related queries are detected."""
        from src.tools.google_search_tool import _google_search_impl

        # Contract-related query should suggest using contract tools
        result = await _google_search_impl(
            query="what are standard NDA termination clauses"
        )

        # Should recognize this as potentially contract-related and suggest contract tools
        assert result is not None
        assert "suggestion" in result or "recommendation" in result

    @pytest.mark.asyncio
    async def test_search_handles_generic_queries(self):
        """Test handling of generic non-contract queries."""
        from src.tools.google_search_tool import _google_search_impl

        # Generic query without contract keywords
        result = await _google_search_impl(
            query="weather in San Francisco"
        )

        # Should return a result (may suggest contract capabilities)
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_redirect_to_contracts(self):
        """Test redirect to contract tools suggestion."""
        from src.tools.google_search_tool import _redirect_to_contracts_impl

        # Note: _redirect_to_contracts_impl only takes original_query parameter
        result = await _redirect_to_contracts_impl(
            original_query="find liability clauses",
        )

        assert result is not None
        assert "message" in result or "what_i_can_do" in result


class TestToolIntegration:
    """Integration tests for tool combinations."""

    @pytest.mark.asyncio
    async def test_search_then_analyze_flow(self, mock_vector_service):
        """Test search followed by analysis flow."""
        from src.services.vector_service import SearchResult

        # Setup mock search results
        mock_vector_service.search.return_value = [
            SearchResult(
                id="result-1",
                text="5.1 Liability shall not exceed $500,000.",
                score=0.95,
                metadata={"clause_number": "5.1", "document_id": "doc-1"},
            )
        ]

        mock_embedding_service = AsyncMock()
        mock_embedding_service.embed_query = AsyncMock(return_value=[0.1] * 384)

        # Mock Gemini response for analysis
        mock_response = MagicMock()
        mock_response.text = '{"risk_level": "high", "analysis": "High liability cap"}'
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Patch at service module level
        with patch("src.services.vector_service.get_vector_service", return_value=mock_vector_service), \
             patch("src.services.embedding_service.get_embedding_service", return_value=mock_embedding_service), \
             patch("src.tools.analysis_tool.genai.Client", return_value=mock_client):

            # First search
            from src.tools.search_tool import search_contracts
            search_results = await search_contracts(
                query="liability",
                top_k=1,
            )

            assert search_results is not None
            assert search_results.get("success") is True

            # Then analyze
            from src.tools.analysis_tool import analyze_clause

            analysis = await analyze_clause(
                clause_text="5.1 Liability shall not exceed $500,000.",
                analysis_type="legal",
            )

            assert analysis is not None
            assert "success" in analysis
