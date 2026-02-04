"""Tests for the process lookup skill."""

from unittest.mock import MagicMock, patch

import pytest

from src.skills.process_lookup import ProcessLookupOutput, ProcessLookupSkill, ProcessResult


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = MagicMock()
    return client


@pytest.fixture
def skill(mock_supabase_client):
    """Create a ProcessLookupSkill with mock client."""
    return ProcessLookupSkill(client=mock_supabase_client)


class TestProcessLookupSkill:
    """Tests for ProcessLookupSkill."""

    def test_search_returns_results(self, skill, mock_supabase_client):
        """Test that search returns properly formatted results."""
        # Mock the RPC response
        mock_response = MagicMock()
        mock_response.data = [
            {
                "process_key": "billing-dispute",
                "name": "Billing Dispute Resolution",
                "domain": "billing",
                "version": "1.0.0",
                "rank": 0.85,
                "process_text": "Handle customer billing disputes...",
                "steps_json": [{"key": "verify", "label": "Verify Identity"}],
            },
            {
                "process_key": "refund-request",
                "name": "Refund Request",
                "domain": "billing",
                "version": "1.0.0",
                "rank": 0.65,
                "process_text": "Process refund requests...",
                "steps_json": None,
            },
        ]
        mock_supabase_client.rpc.return_value.execute.return_value = mock_response

        # Perform search
        result = skill.search("I was charged twice")

        # Verify RPC was called correctly
        mock_supabase_client.rpc.assert_called_once_with(
            "search_processes",
            {
                "search_query": "I was charged twice",
                "search_locale": "en",
                "search_domain": None,
                "search_queue_tag": None,
                "result_limit": 5,
            },
        )

        # Verify results
        assert isinstance(result, ProcessLookupOutput)
        assert len(result.results) == 2
        assert result.results[0].process_key == "billing-dispute"
        assert result.results[0].score == 0.85
        assert result.results[1].process_key == "refund-request"
        assert result.query_time_ms > 0

    def test_search_with_filters(self, skill, mock_supabase_client):
        """Test search with domain and queue_tag filters."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase_client.rpc.return_value.execute.return_value = mock_response

        skill.search(
            "password reset",
            locale="en",
            domain="account",
            queue_tag="account-support",
            limit=3,
        )

        mock_supabase_client.rpc.assert_called_once_with(
            "search_processes",
            {
                "search_query": "password reset",
                "search_locale": "en",
                "search_domain": "account",
                "search_queue_tag": "account-support",
                "result_limit": 3,
            },
        )

    def test_search_empty_results(self, skill, mock_supabase_client):
        """Test search with no matching results."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase_client.rpc.return_value.execute.return_value = mock_response

        result = skill.search("xyz123 nonsense query")

        assert len(result.results) == 0
        assert result.query_time_ms > 0

    def test_get_tool_definition(self, skill):
        """Test that tool definition has required fields."""
        definition = skill.get_tool_definition()

        assert definition["name"] == "process_lookup"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"
        assert "query" in definition["input_schema"]["properties"]
        assert "query" in definition["input_schema"]["required"]

    def test_format_for_llm_with_results(self, skill):
        """Test formatting results for LLM consumption."""
        output = ProcessLookupOutput(
            results=[
                ProcessResult(
                    process_key="billing-dispute",
                    name="Billing Dispute Resolution",
                    domain="billing",
                    version="1.0.0",
                    score=0.85,
                    process_text="Handle customer billing disputes and charge corrections.",
                    steps_json=[
                        {"key": "verify", "label": "Verify Identity"},
                        {"key": "resolve", "label": "Resolve Issue"},
                    ],
                )
            ],
            query_time_ms=15.5,
        )

        formatted = skill.format_for_llm(output)

        assert "Billing Dispute Resolution" in formatted
        assert "billing-dispute" in formatted
        assert "0.85" in formatted
        assert "Verify Identity" in formatted

    def test_format_for_llm_empty_results(self, skill):
        """Test formatting when no results found."""
        output = ProcessLookupOutput(results=[], query_time_ms=10.0)

        formatted = skill.format_for_llm(output)

        assert formatted == "No matching processes found."


class TestProcessLookupFunction:
    """Tests for the module-level process_lookup function."""

    @patch("src.skills.process_lookup.get_supabase_client")
    def test_process_lookup_function(self, mock_get_client):
        """Test the convenience function."""
        from src.skills.process_lookup import process_lookup

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "process_key": "test",
                "name": "Test Process",
                "domain": "test",
                "version": "1.0.0",
                "rank": 0.9,
                "process_text": "Test description",
                "steps_json": None,
            }
        ]
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = process_lookup("test query")

        assert len(result.results) == 1
        assert result.results[0].process_key == "test"
