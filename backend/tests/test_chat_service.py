"""
Integration Tests for ConversationalQueryService (Step 4.3).
Verifies the end-to-end integration between QueryInterpreter, ArgoQueryEngine,
and DataSummarizer on real processed ARGO Parquet data.
"""

import pytest

from app.argo.query import ArgoQueryEngine
from app.llm.gemini_client import GeminiClient
from app.llm.interpreter import QueryInterpreter
from app.llm.service import ConversationalQueryService
from app.llm.summarizer import DataSummarizer


@pytest.fixture
def chat_service():
    """Provides a clean ConversationalQueryService instance using real Parquet data and offline LLM."""
    query_engine = ArgoQueryEngine(processed_dir="data/processed")
    interpreter = QueryInterpreter(gemini_client=GeminiClient(api_key=""))
    summarizer = DataSummarizer(gemini_client=GeminiClient(api_key=""))
    return ConversationalQueryService(
        query_engine=query_engine,
        interpreter=interpreter,
        summarizer=summarizer,
    )


class TestConversationalQueryService:
    """Verifies end-to-end natural language queries translated to real ARGO engine queries."""

    def test_service_catalog_summary(self, chat_service):
        """Natural language request for dataset overview."""
        response = chat_service.process_query("What data do you have available?")

        assert response.intent == "summary"
        assert response.data_count == 3
        assert response.data is not None
        assert "summary" in response.data
        assert response.data["summary"]["total_profiles"] == 3
        assert response.data["summary"]["total_observations"] == 135
        assert "1900121" in response.data["summary"]["platforms"]
        assert "3 profile(s)" in response.summary
        assert response.source == "rule_based"

    def test_service_profiles_query(self, chat_service):
        """Natural language request for specific float profiles."""
        # November 2002 contains Cycle 1 (Nov 11) and Cycle 2 (Nov 21)
        response_nov = chat_service.process_query("Show profiles for float 1900121 in November 2002")

        assert response_nov.intent == "query_profiles"
        assert response_nov.parameters.platform_id == "1900121"
        assert response_nov.parameters.start_date == "2002-11-01"
        assert response_nov.parameters.end_date == "2002-11-30"
        assert response_nov.data_count == 2
        assert len(response_nov.data["profiles"]) == 2
        assert "1900121" in response_nov.summary
        assert "2 ARGO profile(s)" in response_nov.summary

        # Without date filter, returns all 3 profiles for float 1900121
        response_all = chat_service.process_query("Show profiles for float 1900121")
        assert response_all.data_count == 3
        assert len(response_all.data["profiles"]) == 3
        assert "3 ARGO profile(s)" in response_all.summary

    def test_service_observations_query(self, chat_service):
        """Natural language request for cycle and depth observations."""
        response = chat_service.process_query(
            "Show measurements for float 1900121 cycle 1 between 0 and 100m"
        )

        assert response.intent == "query_observations"
        assert response.parameters.platform_id == "1900121"
        assert response.parameters.cycle_number == 1
        assert response.parameters.min_depth == 0.0
        assert response.parameters.max_depth == 100.0
        assert response.data_count > 0
        for obs in response.data["observations"]:
            assert obs["platform_id"] == "1900121"
            assert obs["cycle_number"] == 1
            assert 0.0 <= obs["pressure_dbar"] <= 100.0
        assert "vertical observation level(s)" in response.summary

    def test_service_nonexistent_float(self, chat_service):
        """Natural language query for a float ID not in the dataset."""
        response = chat_service.process_query("Find profiles for float 9999999")

        assert response.intent == "query_profiles"
        assert response.parameters.platform_id == "9999999"
        assert response.data_count == 0
        assert response.data["profiles"] == []
        assert "No matching ARGO observations or profiles were found" in response.summary

    def test_service_out_of_domain(self, chat_service):
        """Natural language query outside oceanographic scope."""
        response = chat_service.process_query("Can you write a poem about artificial intelligence?")

        assert response.intent == "out_of_domain"
        assert response.data is None
        assert response.data_count == 0
        assert "FloatChat specializes in ARGO oceanographic float data" in response.summary
