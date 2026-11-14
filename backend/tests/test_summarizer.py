"""
Unit Tests for DataSummarizer (Step 4.3).
Tests factual grounding, statistical bounds calculations, and fallback mechanisms.
"""

from unittest.mock import MagicMock
import pytest

from app.api.schemas import ArgoQueryParameters, InterpretationResult
from app.llm.gemini_client import GeminiAPIError, GeminiClient, GeminiTimeoutError
from app.llm.summarizer import DataSummarizer


@pytest.fixture
def offline_summarizer():
    """Provides a DataSummarizer with an unconfigured Gemini client for deterministic offline testing."""
    return DataSummarizer(gemini_client=GeminiClient(api_key=""))


class TestDataSummarizerUnit:
    """Unit tests for offline template summarization and statistical grounding."""

    def test_summarize_dataset_summary_offline(self, offline_summarizer):
        """Verifies accurate summary formatting for overall dataset overview."""
        interpretation = InterpretationResult(
            is_valid_query=True,
            intent="summary",
            parameters=ArgoQueryParameters(),
            original_prompt="What data is available?",
        )
        data = {
            "summary": {
                "status": "ready",
                "total_profiles": 3,
                "total_observations": 135,
                "platforms": ["1900121"],
                "date_min": "2002-11-01T02:49:00+00:00",
                "date_max": "2002-11-21T02:37:00+00:00",
                "lat_min": -9.92,
                "lat_max": -9.84,
                "lon_min": 58.74,
                "lon_max": 59.50,
            }
        }

        summary_text, source = offline_summarizer.summarize(
            prompt="What data is available?",
            interpretation=interpretation,
            data=data,
        )

        assert source == "rule_based"
        assert "3 profile(s)" in summary_text
        assert "135 vertical observation levels" in summary_text
        assert "1900121" in summary_text
        assert "2002-11-01" in summary_text
        assert "2002-11-21" in summary_text
        assert "-9.92°" in summary_text

    def test_summarize_profiles_offline(self, offline_summarizer):
        """Verifies summary formatting for profile query results."""
        interpretation = InterpretationResult(
            is_valid_query=True,
            intent="query_profiles",
            parameters=ArgoQueryParameters(platform_id="1900121"),
            original_prompt="Show profiles for float 1900121",
        )
        data = {
            "count": 2,
            "profiles": [
                {
                    "platform_id": "1900121",
                    "cycle_number": 1,
                    "datetime": "2002-11-01T02:49:00+00:00",
                    "latitude": -9.84,
                    "longitude": 58.74,
                },
                {
                    "platform_id": "1900121",
                    "cycle_number": 2,
                    "datetime": "2002-11-11T02:51:00+00:00",
                    "latitude": -9.92,
                    "longitude": 59.10,
                },
            ],
        }

        summary_text, source = offline_summarizer.summarize(
            prompt="Show profiles for float 1900121",
            interpretation=interpretation,
            data=data,
        )

        assert source == "rule_based"
        assert "2 ARGO profile(s)" in summary_text
        assert "1900121" in summary_text
        assert "2002-11-01" in summary_text
        assert "2002-11-11" in summary_text

    def test_summarize_observations_offline(self, offline_summarizer):
        """Verifies observation level formatting with temperature, depth, and salinity ranges."""
        interpretation = InterpretationResult(
            is_valid_query=True,
            intent="query_observations",
            parameters=ArgoQueryParameters(platform_id="1900121", cycle_number=1),
            original_prompt="Surface temperature for float 1900121 cycle 1",
        )
        data = {
            "count": 3,
            "observations": [
                {
                    "platform_id": "1900121",
                    "cycle_number": 1,
                    "pressure_dbar": 4.0,
                    "temperature_c": 28.53,
                    "salinity_psu": 35.10,
                },
                {
                    "platform_id": "1900121",
                    "cycle_number": 1,
                    "pressure_dbar": 50.0,
                    "temperature_c": 26.10,
                    "salinity_psu": 35.25,
                },
                {
                    "platform_id": "1900121",
                    "cycle_number": 1,
                    "pressure_dbar": 100.0,
                    "temperature_c": 21.40,
                    "salinity_psu": 35.31,
                },
            ],
        }

        summary_text, source = offline_summarizer.summarize(
            prompt="Surface temperature for float 1900121 cycle 1",
            interpretation=interpretation,
            data=data,
        )

        assert source == "rule_based"
        assert "3 vertical observation level(s)" in summary_text
        assert "4.0 to 100.0 dbar" in summary_text
        assert "21.40°C to 28.53°C" in summary_text
        assert "35.10 to 35.31 PSU" in summary_text

    def test_summarize_zero_results(self, offline_summarizer):
        """Verifies clear message when no matching records exist."""
        interpretation = InterpretationResult(
            is_valid_query=True,
            intent="query_profiles",
            parameters=ArgoQueryParameters(platform_id="9999999"),
            original_prompt="Show profiles for float 9999999",
        )
        data = {"count": 0, "profiles": []}

        summary_text, source = offline_summarizer.summarize(
            prompt="Show profiles for float 9999999",
            interpretation=interpretation,
            data=data,
        )

        assert source == "rule_based"
        assert "No matching ARGO observations or profiles were found" in summary_text
        assert "9999999" in summary_text

    def test_summarize_out_of_domain(self, offline_summarizer):
        """Verifies guidance response for non-oceanographic queries."""
        interpretation = InterpretationResult(
            is_valid_query=False,
            intent="out_of_domain",
            parameters=ArgoQueryParameters(),
            original_prompt="How do I bake sourdough bread?",
        )

        summary_text, source = offline_summarizer.summarize(
            prompt="How do I bake sourdough bread?",
            interpretation=interpretation,
            data=None,
        )

        assert source == "rule_based"
        assert "FloatChat specializes in ARGO oceanographic float data" in summary_text


class TestDataSummarizerWithGemini:
    """Tests for DataSummarizer with mocked Gemini client calls and error fallbacks."""

    def test_summarize_with_mocked_gemini(self):
        """Verifies that configured Gemini client synthesizes LLM summaries when successful."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.generate_text.return_value = (
            "Float 1900121 completed 3 profile cycles in November 2002 across the equatorial Indian Ocean, "
            "sampling surface temperatures up to 28.5°C."
        )

        summarizer = DataSummarizer(gemini_client=mock_client)
        interpretation = InterpretationResult(
            is_valid_query=True,
            intent="query_profiles",
            parameters=ArgoQueryParameters(platform_id="1900121"),
            original_prompt="Summarize float 1900121",
        )
        data = {
            "count": 3,
            "profiles": [
                {
                    "platform_id": "1900121",
                    "cycle_number": 1,
                    "datetime": "2002-11-01T02:49:00+00:00",
                    "latitude": -9.84,
                    "longitude": 58.74,
                }
            ],
        }

        summary_text, source = summarizer.summarize(
            prompt="Summarize float 1900121",
            interpretation=interpretation,
            data=data,
        )

        assert source == "gemini"
        assert "Float 1900121 completed 3 profile cycles" in summary_text
        mock_client.generate_text.assert_called_once()

    def test_summarize_gemini_fallback_on_timeout(self):
        """Verifies fallback to rule-based summary when Gemini API times out."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.generate_text.side_effect = GeminiTimeoutError("Request timed out")

        summarizer = DataSummarizer(gemini_client=mock_client)
        interpretation = InterpretationResult(
            is_valid_query=True,
            intent="query_profiles",
            parameters=ArgoQueryParameters(platform_id="1900121"),
            original_prompt="Show float 1900121 profiles",
        )
        data = {
            "count": 1,
            "profiles": [
                {
                    "platform_id": "1900121",
                    "cycle_number": 1,
                    "datetime": "2002-11-01T02:49:00+00:00",
                    "latitude": -9.84,
                    "longitude": 58.74,
                }
            ],
        }

        summary_text, source = summarizer.summarize(
            prompt="Show float 1900121 profiles",
            interpretation=interpretation,
            data=data,
        )

        # Successfully falls back to rule-based template
        assert source == "rule_based"
        assert "Found 1 ARGO profile(s) for platform(s) 1900121" in summary_text

    def test_summarize_gemini_fallback_on_api_error(self):
        """Verifies fallback to rule-based summary when Gemini API returns HTTP 500."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.generate_text.side_effect = GeminiAPIError("500 Server Error")

        summarizer = DataSummarizer(gemini_client=mock_client)
        interpretation = InterpretationResult(
            is_valid_query=True,
            intent="summary",
            parameters=ArgoQueryParameters(),
            original_prompt="What data do you have?",
        )
        data = {
            "summary": {
                "total_profiles": 3,
                "total_observations": 135,
                "platforms": ["1900121"],
                "date_min": "2002-11-01",
                "date_max": "2002-11-21",
            }
        }

        summary_text, source = summarizer.summarize(
            prompt="What data do you have?",
            interpretation=interpretation,
            data=data,
        )

        assert source == "rule_based"
        assert "The ARGO dataset currently contains 3 profile(s)" in summary_text
