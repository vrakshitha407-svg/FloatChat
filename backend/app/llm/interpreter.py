"""
Natural Language Query Interpreter for ARGO Ocean Data.
Combines Google Gemini LLM parameter extraction with a deterministic,
rule-based parser as a guaranteed offline fallback.
"""

import calendar
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.api.schemas import ArgoQueryParameters, InterpretationResult
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import QUERY_INTERPRETATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Known oceanographic geographic regions and bounding boxes (min_lat, max_lat, min_lon, max_lon)
KNOWN_REGIONS = {
    "arabian sea": (10.0, 25.0, 50.0, 75.0),
    "bay of bengal": (5.0, 22.0, 80.0, 95.0),
    "equatorial indian ocean": (-10.0, 10.0, 50.0, 90.0),
    "indian ocean": (-40.0, 25.0, 40.0, 100.0),
    "madagascar": (-26.0, -11.0, 43.0, 51.0),
    "somali basin": (-5.0, 12.0, 45.0, 60.0),
}

# Domain keywords indicating oceanographic relevance
OCEAN_KEYWORDS = {
    "argo", "float", "ocean", "sea", "water", "marine", "salinity",
    "temperature", "temp", "depth", "pressure", "profile", "cycle",
    "observation", "measurements", "thermocline", "psu", "dbar",
    "coordinates", "latitude", "longitude", "wmo", "incois", "coriolis",
    "summary", "dataset", "catalog", "overview"
}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}


class QueryInterpreter:
    """
    Interprets natural language queries into structured ARGO query parameters.
    Supports both Google Gemini LLM extraction (when configured) and
    deterministic offline rule-based extraction as a guaranteed fallback.
    """

    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini_client: GeminiClient = gemini_client or GeminiClient()

    def interpret(self, prompt: str) -> InterpretationResult:
        """
        Parses a natural language query and returns an InterpretationResult.
        Uses Gemini LLM if configured; otherwise seamlessly uses rule-based parsing.
        """
        cleaned_prompt = prompt.strip() if prompt else ""
        if not cleaned_prompt:
            return InterpretationResult(
                is_valid_query=False,
                intent="out_of_domain",
                parameters=ArgoQueryParameters(),
                original_prompt=cleaned_prompt,
                confidence=0.0,
                explanation="Empty query provided.",
            )

        if self.gemini_client.is_configured():
            try:
                return self._interpret_with_gemini(cleaned_prompt)
            except Exception as exc:
                logger.warning(
                    "Gemini LLM interpretation failed (%s: %s); falling back to rule-based interpreter",
                    type(exc).__name__,
                    exc,
                )
                fallback_result = self._interpret_rule_based(cleaned_prompt)
                fallback_result.explanation = (
                    f"{fallback_result.explanation} (Fallback from LLM: {type(exc).__name__})"
                )
                return fallback_result

        return self._interpret_rule_based(cleaned_prompt)

    def _interpret_with_gemini(self, cleaned_prompt: str) -> InterpretationResult:
        """Extracts parameters using Gemini LLM and validates against Pydantic schema."""
        raw = self.gemini_client.generate_json(
            cleaned_prompt,
            system_instruction=QUERY_INTERPRETATION_SYSTEM_PROMPT,
        )

        is_valid = bool(raw.get("is_valid_query", True))
        intent = raw.get("intent", "query_profiles")
        raw_conf = raw.get("confidence", 0.9)
        try:
            confidence = max(0.0, min(1.0, float(raw_conf)))
        except (ValueError, TypeError):
            confidence = 0.85

        explanation = raw.get("explanation", "Extracted via Gemini LLM.")

        if not is_valid or intent == "out_of_domain":
            return InterpretationResult(
                is_valid_query=False,
                intent="out_of_domain",
                parameters=ArgoQueryParameters(),
                original_prompt=cleaned_prompt,
                confidence=confidence,
                explanation=explanation,
            )

        raw_params = raw.get("parameters") or {}
        if not isinstance(raw_params, dict):
            raw_params = {}

        # Coerce types if needed
        if raw_params.get("platform_id") is not None:
            raw_params["platform_id"] = str(raw_params["platform_id"])

        # Validate through Pydantic schema (raises ValidationError if invalid bounds)
        validated_params = ArgoQueryParameters(**raw_params)

        # Ensure valid intent
        if intent not in ("query_profiles", "query_observations", "summary"):
            if validated_params.cycle_number is not None or validated_params.min_depth is not None or validated_params.max_depth is not None:
                intent = "query_observations"
            else:
                intent = "query_profiles"

        return InterpretationResult(
            is_valid_query=True,
            intent=intent,
            parameters=validated_params,
            original_prompt=cleaned_prompt,
            confidence=confidence,
            explanation=explanation,
        )

    def _interpret_rule_based(self, cleaned_prompt: str) -> InterpretationResult:
        """Deterministic rule-based interpretation used offline or as fallback."""
        prompt_lower = cleaned_prompt.lower()

        # Check for dataset summary / catalog intent
        if self._is_summary_intent(prompt_lower):
            return InterpretationResult(
                is_valid_query=True,
                intent="summary",
                parameters=ArgoQueryParameters(),
                original_prompt=cleaned_prompt,
                confidence=0.95,
                explanation="User is requesting an overview or summary of available ARGO datasets.",
            )

        # Check if query is within oceanographic/ARGO domain
        platform_id = self._extract_platform_id(prompt_lower)
        is_domain = self._is_ocean_domain(prompt_lower) or (platform_id is not None)

        if not is_domain:
            return InterpretationResult(
                is_valid_query=False,
                intent="out_of_domain",
                parameters=ArgoQueryParameters(),
                original_prompt=cleaned_prompt,
                confidence=0.0,
                explanation="The query does not appear to be related to ARGO float data, oceanography, or marine observations.",
            )

        # Extract parameters
        cycle_number = self._extract_cycle_number(prompt_lower)
        min_depth, max_depth = self._extract_depth_range(prompt_lower)
        start_date, end_date = self._extract_date_range(prompt_lower)
        min_lat, max_lat, min_lon, max_lon = self._extract_bounding_box(prompt_lower)
        variables = self._extract_variables(prompt_lower)

        # Determine specific intent
        if cycle_number is not None or min_depth is not None or max_depth is not None:
            intent = "query_observations"
        else:
            intent = "query_profiles"

        params = ArgoQueryParameters(
            platform_id=platform_id,
            cycle_number=cycle_number,
            start_date=start_date,
            end_date=end_date,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lon=min_lon,
            max_lon=max_lon,
            min_depth=min_depth,
            max_depth=max_depth,
            variables=variables,
        )

        explanation = f"Interpreted intent as '{intent}' with extracted parameters."

        return InterpretationResult(
            is_valid_query=True,
            intent=intent,
            parameters=params,
            original_prompt=cleaned_prompt,
            confidence=0.90,
            explanation=explanation,
        )

    def _is_ocean_domain(self, text: str) -> bool:
        """Determines if the text contains domain-relevant terminology or regions."""
        for kw in OCEAN_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return True
        for region in KNOWN_REGIONS:
            if region in text:
                return True
        return False

    def _is_summary_intent(self, text: str) -> bool:
        """Detects if query asks for a general dataset overview or catalog."""
        summary_patterns = [
            r"what (data|floats|profiles) (do you have|are available)",
            r"(show|get|display) (the )?summary",
            r"(dataset|data) (summary|overview|catalog)",
            r"list (all )?(the )?(floats|platforms|profiles)",
        ]
        for pattern in summary_patterns:
            if re.search(pattern, text):
                return True
        return False

    def _extract_platform_id(self, text: str) -> Optional[str]:
        """Extracts 7-digit WMO float platform identifier."""
        labeled = re.search(r"\b(float|platform|wmo|id)\s*#?\s*([0-9]{7})\b", text)
        if labeled:
            return labeled.group(2)

        standalone = re.search(r"\b([1-7][0-9]{6})\b", text)
        if standalone:
            return standalone.group(1)

        return None

    def _extract_cycle_number(self, text: str) -> Optional[int]:
        """Extracts float cycle number."""
        match = re.search(r"\b(cycle|dive)\s*#?\s*([0-9]+)\b", text)
        if match:
            try:
                return int(match.group(2))
            except ValueError:
                return None
        return None

    def _extract_depth_range(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """Extracts vertical depth or pressure range in decibars / meters."""
        if "surface" in text:
            return 0.0, 10.0
        if "shallow" in text:
            return 0.0, 200.0
        if "deep" in text and not re.search(r"(deeper than|below)", text):
            return 1000.0, None

        between_match = re.search(
            r"(?:between|from)\s+([0-9]+(?:\.[0-9]+)?)\s+(?:and|to)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:m|meter|meters|dbar)?",
            text,
        )
        if between_match:
            try:
                d1 = float(between_match.group(1))
                d2 = float(between_match.group(2))
                return min(d1, d2), max(d1, d2)
            except ValueError:
                pass

        range_match = re.search(
            r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:-|to)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|meter|meters|dbar)\b",
            text,
        )
        if range_match:
            try:
                d1 = float(range_match.group(1))
                d2 = float(range_match.group(2))
                return min(d1, d2), max(d1, d2)
            except ValueError:
                pass

        below_match = re.search(r"(?:below|deeper than|greater than)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:m|meter|meters|dbar)?", text)
        if below_match:
            try:
                return float(below_match.group(1)), None
            except ValueError:
                pass

        above_match = re.search(r"(?:above|shallower than|up to|down to)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:m|meter|meters|dbar)?", text)
        if above_match:
            try:
                return 0.0, float(above_match.group(1))
            except ValueError:
                pass

        return None, None

    def _extract_date_range(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts date range or month period."""
        iso_range = re.search(r"\b([0-9]{4}-[0-9]{2}-[0-9]{2})\s+(?:to|and|-)\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\b", text)
        if iso_range:
            return iso_range.group(1), iso_range.group(2)

        single_iso = re.search(r"\b([0-9]{4}-[0-9]{2}-[0-9]{2})\b", text)
        if single_iso:
            date_str = single_iso.group(1)
            return date_str, date_str

        month_match = re.search(r"\b(" + "|".join(MONTH_NAMES.keys()) + r")\s+([0-9]{4})\b", text)
        if month_match:
            month_str = month_match.group(1)
            year_int = int(month_match.group(2))
            month_int = MONTH_NAMES[month_str]
            _, last_day = calendar.monthrange(year_int, month_int)
            start_date = f"{year_int:04d}-{month_int:02d}-01"
            end_date = f"{year_int:04d}-{month_int:02d}-{last_day:02d}"
            return start_date, end_date

        year_match = re.search(r"\b(?:in|during|year)\s+([12][0-9]{3})\b", text)
        if year_match:
            year_int = int(year_match.group(1))
            return f"{year_int:04d}-01-01", f"{year_int:04d}-12-31"

        return None, None

    def _extract_bounding_box(self, text: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Extracts spatial bounding box from region names or explicit coordinates."""
        for region, bbox in KNOWN_REGIONS.items():
            if region in text:
                return bbox

        coord_match = re.search(
            r"lat(?:itude)?\s*(?:between|from)?\s*(-?[0-9]+(?:\.[0-9]+)?)\s*(?:and|to|-)\s*(-?[0-9]+(?:\.[0-9]+)?)",
            text,
        )
        if coord_match:
            try:
                l1 = float(coord_match.group(1))
                l2 = float(coord_match.group(2))
                return min(l1, l2), max(l1, l2), None, None
            except ValueError:
                pass

        return None, None, None, None

    def _extract_variables(self, text: str) -> List[str]:
        """Extracts scientific variables requested in the prompt."""
        vars_found = []

        if re.search(r"\b(temp|temperature|thermal|sst)\b", text):
            vars_found.append("TEMP")

        if re.search(r"\b(salinity|salt|psal|psu)\b", text):
            vars_found.append("PSAL")

        if re.search(r"\b(pressure|depth|pres|dbar)\b", text):
            vars_found.append("PRES")

        return vars_found
