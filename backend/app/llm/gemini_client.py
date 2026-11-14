"""
Google Gemini API Client for FloatChat.
Provides REST-based JSON generation using httpx with timeout controls,
robust error handling, and API key protection.
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Base exception for Gemini client operations."""
    pass


class GeminiNotConfiguredError(GeminiError):
    """Raised when Gemini API key is missing or blank."""
    pass


class GeminiAPIError(GeminiError):
    """Raised when the Gemini REST API returns an HTTP error."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when a request to the Gemini API times out."""
    pass


class GeminiResponseError(GeminiError):
    """Raised when the Gemini response structure is malformed or invalid."""
    pass


class GeminiClient:
    """
    Client for interacting with Google's Gemini LLM REST API.
    Designed for deterministic, structured JSON extraction with fallback support.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key: Optional[str] = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model_name: str = model_name or settings.GEMINI_MODEL
        self.timeout: float = timeout if timeout is not None else settings.LLM_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        """Checks if a valid, non-empty API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def __repr__(self) -> str:
        """Safe representation ensuring API keys are never exposed in logs or strings."""
        masked_key = (
            f"{self.api_key[:4]}...{self.api_key[-4:]}"
            if self.api_key and len(self.api_key) > 8
            else ("***" if self.api_key else "None")
        )
        return (
            f"GeminiClient(model='{self.model_name}', "
            f"configured={self.is_configured()}, api_key='{masked_key}')"
        )

    def generate_json(
        self, prompt: str, system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends a prompt to Gemini with response_mime_type="application/json"
        and returns the parsed JSON dictionary.

        Raises:
            GeminiNotConfiguredError: If API key is missing.
            GeminiTimeoutError: If the request exceeds timeout.
            GeminiAPIError: If HTTP error occurs.
            GeminiResponseError: If the response is malformed or invalid JSON.
        """
        if not self.is_configured():
            raise GeminiNotConfiguredError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in environment or .env."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        if system_instruction:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    params={"key": self.api_key},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise GeminiTimeoutError(
                f"Gemini API request timed out after {self.timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise GeminiAPIError(
                f"Gemini API network connection failure: {exc}"
            ) from exc

        if response.status_code != 200:
            error_msg = response.text
            if self.api_key and self.api_key in error_msg:
                error_msg = error_msg.replace(self.api_key, "[REDACTED_API_KEY]")
            raise GeminiAPIError(
                f"Gemini API error (status {response.status_code}): {error_msg}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise GeminiResponseError("Failed to parse Gemini response as JSON") from exc

        candidates = data.get("candidates", [])
        if not candidates:
            feedback = data.get("promptFeedback", {})
            raise GeminiResponseError(f"Gemini returned no candidates. Feedback: {feedback}")

        first_candidate = candidates[0]
        finish_reason = first_candidate.get("finishReason")
        if finish_reason and finish_reason not in ("STOP", "MAX_TOKENS", None):
            raise GeminiResponseError(
                f"Gemini candidate stopped with unexpected reason: {finish_reason}"
            )

        parts = first_candidate.get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise GeminiResponseError("Gemini candidate did not contain text content")

        raw_text = parts[0]["text"]
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiResponseError(
                f"Candidate text could not be decoded as JSON: {raw_text[:200]}"
            ) from exc

    def generate_text(
        self, prompt: str, system_instruction: Optional[str] = None
    ) -> str:
        """
        Sends a prompt to Gemini and returns the generated text response.

        Raises:
            GeminiNotConfiguredError: If API key is missing.
            GeminiTimeoutError: If the request exceeds timeout.
            GeminiAPIError: If HTTP error occurs.
            GeminiResponseError: If the response is malformed.
        """
        if not self.is_configured():
            raise GeminiNotConfiguredError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in environment or .env."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
            },
        }

        if system_instruction:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    params={"key": self.api_key},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise GeminiTimeoutError(
                f"Gemini API request timed out after {self.timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise GeminiAPIError(
                f"Gemini API network connection failure: {exc}"
            ) from exc

        if response.status_code != 200:
            error_msg = response.text
            if self.api_key and self.api_key in error_msg:
                error_msg = error_msg.replace(self.api_key, "[REDACTED_API_KEY]")
            raise GeminiAPIError(
                f"Gemini API error (status {response.status_code}): {error_msg}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise GeminiResponseError("Failed to parse Gemini response as JSON") from exc

        candidates = data.get("candidates", [])
        if not candidates:
            feedback = data.get("promptFeedback", {})
            raise GeminiResponseError(f"Gemini returned no candidates. Feedback: {feedback}")

        first_candidate = candidates[0]
        finish_reason = first_candidate.get("finishReason")
        if finish_reason and finish_reason not in ("STOP", "MAX_TOKENS", None):
            raise GeminiResponseError(
                f"Gemini candidate stopped with unexpected reason: {finish_reason}"
            )

        parts = first_candidate.get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise GeminiResponseError("Gemini candidate did not contain text content")

        return parts[0]["text"].strip()
