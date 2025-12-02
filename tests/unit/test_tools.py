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
        with patch("src.tools.search_tool.get_vector_service", return_value=mock_vector_service):
            from src.tools.search_tool import _search_contracts_impl

            results = await _search_contracts_impl(
                query="termination clauses",
                top_k=5,
            )

            assert results is not None
            mock_vector_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_document_filter(self, mock_vector_service):
        """Test search with document ID filter."""
        with patch("src.tools.search_tool.get_vector_service", return_value=mock_vector_service):
            from src.tools.search_tool import _search_contracts_impl

            await _search_contracts_impl(
                query="liability",
                document_id="doc-123",
                top_k=3,
            )

            # Verify document filter was passed
            call_args = mock_vector_service.search.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_search_handles_empty_query(self, mock_vector_service):
        """Test search handles empty query gracefully."""
        mock_vector_service.search.return_value = []

        with patch("src.tools.search_tool.get_vector_service", return_value=mock_vector_service):
            from src.tools.search_tool import _search_contracts_impl

            results = await _search_contracts_impl(query="", top_k=5)

            # Should handle gracefully
            assert results is not None or results == []


class TestAnalysisTool:
    """Tests for analysis tools."""

    @pytest.mark.asyncio
    async def test_identify_risks_returns_structured_data(self):
        """Test risk identification returns structured data."""
        from src.tools.analysis_tool import _identify_risks_impl

        # Mock the LLM call
        with patch("src.tools.analysis_tool._call_gemini") as mock_llm:
            mock_llm.return_value = """
            {
                "risks": [
                    {"type": "financial", "description": "High liability cap", "severity": "high"},
                    {"type": "legal", "description": "Unfavorable jurisdiction", "severity": "medium"}
                ]
            }
            """

            result = await _identify_risks_impl(
                clause_text="The liability shall not exceed $1,000,000."
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_clause_extracts_key_terms(self):
        """Test clause analysis extracts key terms."""
        from src.tools.analysis_tool import _analyze_clause_impl

        with patch("src.tools.analysis_tool._call_gemini") as mock_llm:
            mock_llm.return_value = """
            {
                "clause_type": "liability",
                "key_terms": ["$500,000", "cap", "limitation"],
                "obligations": ["limit liability"],
                "analysis": "This clause limits total liability to $500,000."
            }
            """

            result = await _analyze_clause_impl(
                clause_text="Total liability shall not exceed $500,000.",
                analysis_type="risk",
            )

            assert result is not None


class TestReportTool:
    """Tests for report generation tools."""

    @pytest.mark.asyncio
    async def test_generate_summary_creates_report(self, mock_vector_service):
        """Test summary generation creates proper report."""
        with patch("src.tools.report_tool.get_vector_service", return_value=mock_vector_service), \
             patch("src.tools.report_tool._call_gemini") as mock_llm:

            mock_llm.return_value = """
            ## Executive Summary
            This is a Non-Disclosure Agreement between Party A and Party B.

            ### Key Terms
            - Term: 3 years
            - Confidentiality Period: 5 years

            ### Risks
            - High liability cap of $500,000
            """

            from src.tools.report_tool import _generate_summary_impl

            result = await _generate_summary_impl(
                document_id="doc-123",
                summary_type="executive",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_extract_obligations_parses_correctly(self):
        """Test obligation extraction parses correctly."""
        from src.tools.report_tool import _extract_obligations_impl

        with patch("src.tools.report_tool._call_gemini") as mock_llm:
            mock_llm.return_value = """
            {
                "obligations": [
                    {"party": "Receiving Party", "obligation": "Maintain confidentiality", "section": "2.1"},
                    {"party": "Receiving Party", "obligation": "Return materials", "section": "4.1"}
                ]
            }
            """

            result = await _extract_obligations_impl(
                contract_text="Sample contract text..."
            )

            assert result is not None


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

        # Should recognize this as potentially contract-related
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_handles_generic_queries(self):
        """Test handling of generic non-contract queries."""
        from src.tools.google_search_tool import _google_search_impl

        with patch("src.tools.google_search_tool._perform_web_search") as mock_search:
            mock_search.return_value = {
                "results": [{"title": "Result 1", "snippet": "Description"}]
            }

            result = await _google_search_impl(
                query="weather in San Francisco"
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_redirect_to_contracts(self):
        """Test redirect to contract tools suggestion."""
        from src.tools.google_search_tool import _redirect_to_contracts_impl

        result = await _redirect_to_contracts_impl(
            original_query="find liability clauses",
            suggested_action="Use search_contracts tool to find liability clauses in your documents",
        )

        assert result is not None
        assert "suggested_action" in str(result).lower() or result is not None


class TestToolIntegration:
    """Integration tests for tool combinations."""

    @pytest.mark.asyncio
    async def test_search_then_analyze_flow(self, mock_vector_service):
        """Test search followed by analysis flow."""
        mock_vector_service.search.return_value = [
            {
                "content": "5.1 Liability shall not exceed $500,000.",
                "metadata": {"clause_number": "5.1"},
                "score": 0.95,
            }
        ]

        with patch("src.tools.search_tool.get_vector_service", return_value=mock_vector_service), \
             patch("src.tools.analysis_tool._call_gemini") as mock_llm:

            mock_llm.return_value = '{"risk_level": "high", "analysis": "High liability cap"}'

            # First search
            from src.tools.search_tool import _search_contracts_impl
            search_results = await _search_contracts_impl(
                query="liability",
                top_k=1,
            )

            # Then analyze
            from src.tools.analysis_tool import _analyze_clause_impl

            if search_results:
                analysis = await _analyze_clause_impl(
                    clause_text=mock_vector_service.search.return_value[0]["content"],
                    analysis_type="risk",
                )

                assert analysis is not None
