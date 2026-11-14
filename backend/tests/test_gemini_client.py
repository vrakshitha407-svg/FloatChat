"""
Unit Tests for Gemini Client and LLM Query Interpretation with Mocking (Step 4.2).
All network requests are mocked; tests run fast, deterministically, and offline.
"""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.api.schemas import ArgoQueryParameters, InterpretationResult
from app.llm.gemini_client import (
    GeminiAPIError,
    GeminiClient,
    GeminiNotConfiguredError,
    GeminiResponseError,
    GeminiTimeoutError,
)
from app.llm.interpreter import QueryInterpreter


class TestGeminiClientDirect:
    """Tests for GeminiClient behavior, configuration checks, and security."""

    def test_unconfigured_client_raises_error(self):
        """Verifies that an unconfigured client reports is_configured()=False and errors on call."""
        client = GeminiClient(api_key="")
        assert client.is_configured() is False

        with pytest.raises(GeminiNotConfiguredError) as exc:
            client.generate_json("Show float 1900121")
        assert "not configured" in str(exc.value)

    def test_configured_client_state(self):
        """Verifies client configuration status when key is supplied."""
        client = GeminiClient(api_key="AIzaSyTestMockKey1234567890")
        assert client.is_configured() is True
        assert client.model_name == "gemini-2.5-flash"
        assert client.timeout == 10.0

    def test_repr_masks_api_key(self):
        """Verifies that API keys are strictly masked and never leaked in repr or str."""
        secret_key = "AIzaSyTestSecretKeyMustNeverBeExposed"
        client = GeminiClient(api_key=secret_key)
        repr_str = repr(client)
        assert secret_key not in repr_str
        assert "AIza...osed" in repr_str

    @patch("httpx.Client.post")
    def test_successful_mocked_gemini_call(self, mock_post):
        """Verifies standard 200 OK JSON parsing from Gemini REST API response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {
                                "text": '{"is_valid_query": true, "intent": "query_profiles", "parameters": {"platform_id": "1900121", "variables": ["TEMP"]}, "confidence": 0.95, "explanation": "Extracted float 1900121"}'
                            }
                        ]
                    },
                }
            ]
        }
        mock_post.return_value = mock_response

        client = GeminiClient(api_key="fake-test-key")
        result = client.generate_json("Show temperature for float 1900121")

        assert result["is_valid_query"] is True
        assert result["intent"] == "query_profiles"
        assert result["parameters"]["platform_id"] == "1900121"
        assert result["parameters"]["variables"] == ["TEMP"]

    @patch("httpx.Client.post")
    def test_timeout_raises_geminitimeouterror(self, mock_post):
        """Verifies that httpx.TimeoutException maps to GeminiTimeoutError."""
        mock_post.side_effect = httpx.TimeoutException("Connection timed out")

        client = GeminiClient(api_key="fake-test-key")
        with pytest.raises(GeminiTimeoutError) as exc:
            client.generate_json("Show salinity")
        assert "timed out" in str(exc.value)

    @patch("httpx.Client.post")
    def test_http_status_error_raises_geminiapierror(self, mock_post):
        """Verifies that non-200 HTTP statuses map to GeminiAPIError with masked keys."""
        fake_key = "super-secret-key-12345"
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.text = f'{{"error": "Forbidden for key {fake_key}"}}'
        mock_post.return_value = mock_response

        client = GeminiClient(api_key=fake_key)
        with pytest.raises(GeminiAPIError) as exc:
            client.generate_json("Show salinity")
        err_msg = str(exc.value)
        assert fake_key not in err_msg
        assert "[REDACTED_API_KEY]" in err_msg
        assert "403" in err_msg

    @patch("httpx.Client.post")
    def test_malformed_json_response_raises_geminiresponseerror(self, mock_post):
        """Verifies that invalid JSON in candidate parts raises GeminiResponseError."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "This is plain prose, not valid JSON output"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        client = GeminiClient(api_key="fake-test-key")
        with pytest.raises(GeminiResponseError) as exc:
            client.generate_json("What is the ocean depth?")
        assert "could not be decoded as JSON" in str(exc.value)


class TestQueryInterpreterWithGemini:
    """Tests for QueryInterpreter using mocked GeminiClient with fallback verification."""

    def test_interpreter_uses_gemini_when_configured(self):
        """Verifies that valid Gemini responses populate InterpretationResult and validate schema."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.generate_json.return_value = {
            "is_valid_query": True,
            "intent": "query_profiles",
            "parameters": {
                "platform_id": "1900121",
                "start_date": "2002-11-01",
                "end_date": "2002-11-30",
                "variables": ["TEMP", "PSAL"],
            },
            "confidence": 0.98,
            "explanation": "Extracted float 1900121 profiles for November 2002.",
        }

        interpreter = QueryInterpreter(gemini_client=mock_client)
        result = interpreter.interpret("Show float 1900121 profiles in November 2002")

        assert result.is_valid_query is True
        assert result.intent == "query_profiles"
        assert result.parameters.platform_id == "1900121"
        assert result.parameters.start_date == "2002-11-01"
        assert result.parameters.end_date == "2002-11-30"
        assert result.parameters.variables == ["TEMP", "PSAL"]
        assert result.confidence == 0.98
        mock_client.generate_json.assert_called_once()

    def test_interpreter_gemini_out_of_domain(self):
        """Verifies that Gemini out_of_domain responses are mapped cleanly."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.generate_json.return_value = {
            "is_valid_query": False,
            "intent": "out_of_domain",
            "parameters": {},
            "confidence": 0.0,
            "explanation": "Query is about baking cookies.",
        }

        interpreter = QueryInterpreter(gemini_client=mock_client)
        result = interpreter.interpret("How do I bake chocolate chip cookies?")

        assert result.is_valid_query is False
        assert result.intent == "out_of_domain"
        assert result.confidence == 0.0

    def test_interpreter_fallback_on_gemini_timeout(self):
        """Verifies graceful fallback to rule-based interpreter on API timeout."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.generate_json.side_effect = GeminiTimeoutError("Request timed out after 10.0s")

        interpreter = QueryInterpreter(gemini_client=mock_client)
        result = interpreter.interpret("Show profiles for float 1900121 in November 2002")

        # Fallback to rule-based parser succeeds
        assert result.is_valid_query is True
        assert result.parameters.platform_id == "1900121"
        assert result.parameters.start_date == "2002-11-01"
        assert result.parameters.end_date == "2002-11-30"
        assert "Fallback from LLM: GeminiTimeoutError" in result.explanation

    def test_interpreter_fallback_on_gemini_http_error(self):
        """Verifies graceful fallback to rule-based interpreter on API 500 error."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.generate_json.side_effect = GeminiAPIError("500 Internal Server Error")

        interpreter = QueryInterpreter(gemini_client=mock_client)
        result = interpreter.interpret("Surface temperature for float 1900121")

        # Fallback to rule-based parser succeeds
        assert result.is_valid_query is True
        assert result.parameters.platform_id == "1900121"
        assert result.parameters.min_depth == 0.0
        assert result.parameters.max_depth == 10.0
        assert "TEMP" in result.parameters.variables
        assert "Fallback from LLM: GeminiAPIError" in result.explanation

    def test_interpreter_fallback_on_invalid_pydantic_schema(self):
        """Verifies that invalid bounds from LLM trigger fallback to rule-based parser."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        # Provide invalid latitude bounds (min_lat > max_lat)
        mock_client.generate_json.return_value = {
            "is_valid_query": True,
            "intent": "query_profiles",
            "parameters": {
                "min_lat": 25.0,
                "max_lat": 10.0,
            },
            "confidence": 0.90,
            "explanation": "Extracted Arabian Sea with inverted coordinates",
        }

        interpreter = QueryInterpreter(gemini_client=mock_client)
        result = interpreter.interpret("Find argo float profiles in the Arabian Sea")

        # Fallback to rule-based parser succeeds with valid Arabian Sea bounds
        assert result.is_valid_query is True
        assert result.parameters.min_lat == 10.0
        assert result.parameters.max_lat == 25.0
        assert result.parameters.min_lon == 50.0
        assert result.parameters.max_lon == 75.0
        assert "Fallback from LLM: ValidationError" in result.explanation
