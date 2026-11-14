"""
Grounded Data Summarizer for ARGO Ocean Data.
Produces scientifically grounded summaries strictly from retrieved ARGO data.
Supports both live Google Gemini LLM synthesis and deterministic offline template generation.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.api.schemas import ArgoQueryParameters, InterpretationResult
from app.llm.gemini_client import GeminiClient
from app.llm.prompts import DATA_SUMMARIZATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class DataSummarizer:
    """
    Synthesizes natural language summaries grounded strictly in queried ARGO observations.
    Never fabricates observations, coordinates, dates, or measurements.
    """

    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini_client: GeminiClient = gemini_client or GeminiClient()

    def summarize(
        self,
        prompt: str,
        interpretation: InterpretationResult,
        data: Optional[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """
        Generates a factual summary of the retrieved data.
        Returns:
            Tuple[str, str]: (summary_text, source) where source is 'gemini' or 'rule_based'.
        """
        # Case 1: Out of domain or invalid query
        if not interpretation.is_valid_query or interpretation.intent == "out_of_domain":
            return (
                "FloatChat specializes in ARGO oceanographic float data discovery and visualization. "
                "You can ask about float profiles, dive cycles, ocean temperatures, salinity measurements, "
                "or depth levels (e.g., 'Show profiles for float 1900121' or 'Check salinity between 0 and 500m in the Arabian Sea').",
                "rule_based",
            )

        # Case 2: No data or empty match
        data_count = self._get_data_count(data)
        if data is None or data_count == 0:
            return self._summarize_empty_results(interpretation.parameters), "rule_based"

        # Case 3: Summary intent or non-empty query results
        computed_stats = self._compute_statistics(interpretation.intent, data)
        rule_summary = self._generate_rule_based_summary(
            interpretation.intent, data, computed_stats
        )

        # Attempt Gemini summarization if configured
        if self.gemini_client.is_configured():
            try:
                llm_summary = self._generate_gemini_summary(
                    prompt=prompt,
                    intent=interpretation.intent,
                    parameters=interpretation.parameters,
                    computed_stats=computed_stats,
                    data=data,
                )
                if llm_summary and len(llm_summary.strip()) > 10:
                    return llm_summary.strip(), "gemini"
            except Exception as exc:
                logger.warning(
                    "Gemini summarization failed (%s: %s); falling back to rule-based summary",
                    type(exc).__name__,
                    exc,
                )

        return rule_summary, "rule_based"

    @staticmethod
    def _get_data_count(data: Optional[Dict[str, Any]]) -> int:
        """Determines total matching records from payload."""
        if not data:
            return 0
        if "summary" in data:
            return int(data["summary"].get("total_profiles", 0))
        if "count" in data:
            return int(data["count"])
        if "profiles" in data:
            return len(data["profiles"])
        if "observations" in data:
            return len(data["observations"])
        return 0

    @staticmethod
    def _summarize_empty_results(params: ArgoQueryParameters) -> str:
        """Generates clear, informative message when 0 records match criteria."""
        filters = []
        if params.platform_id:
            filters.append(f"float ID {params.platform_id}")
        if params.cycle_number is not None:
            filters.append(f"cycle #{params.cycle_number}")
        if params.min_depth is not None or params.max_depth is not None:
            d_min = params.min_depth if params.min_depth is not None else 0.0
            d_max = f"{params.max_depth} dbar" if params.max_depth is not None else "deepest"
            filters.append(f"depth {d_min} to {d_max}")
        if params.start_date or params.end_date:
            dates = f"{params.start_date or 'earliest'} to {params.end_date or 'latest'}"
            filters.append(f"dates {dates}")
        if params.min_lat is not None or params.max_lat is not None:
            filters.append(f"latitudes {params.min_lat}° to {params.max_lat}°")

        criteria_str = f" for {', '.join(filters)}" if filters else ""
        return (
            f"No matching ARGO observations or profiles were found{criteria_str}. "
            "Please check the platform identifier, date range, or depth bounds."
        )

    def _compute_statistics(
        self, intent: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Computes empirical aggregates strictly from the actual returned dataset."""
        stats: Dict[str, Any] = {}

        if intent == "summary" and "summary" in data:
            s = data["summary"]
            stats["total_profiles"] = s.get("total_profiles", 0)
            stats["total_observations"] = s.get("total_observations", 0)
            stats["platforms"] = s.get("platforms", [])
            stats["date_min"] = s.get("date_min")
            stats["date_max"] = s.get("date_max")
            stats["lat_min"] = s.get("lat_min")
            stats["lat_max"] = s.get("lat_max")
            stats["lon_min"] = s.get("lon_min")
            stats["lon_max"] = s.get("lon_max")
            return stats

        if intent == "query_profiles" and "profiles" in data:
            profiles = data["profiles"]
            stats["count"] = len(profiles)
            stats["platforms"] = sorted(
                list({str(p["platform_id"]) for p in profiles if "platform_id" in p})
            )
            stats["cycles"] = sorted(
                list(
                    {
                        p["cycle_number"]
                        for p in profiles
                        if "cycle_number" in p and p["cycle_number"] is not None
                    }
                )
            )
            dates = [p["datetime"].split("T")[0] for p in profiles if p.get("datetime")]
            if dates:
                stats["date_min"] = min(dates)
                stats["date_max"] = max(dates)
            lats = [p["latitude"] for p in profiles if p.get("latitude") is not None]
            lons = [p["longitude"] for p in profiles if p.get("longitude") is not None]
            if lats:
                stats["lat_min"] = min(lats)
                stats["lat_max"] = max(lats)
            if lons:
                stats["lon_min"] = min(lons)
                stats["lon_max"] = max(lons)
            return stats

        if intent == "query_observations" and "observations" in data:
            obs = data["observations"]
            stats["count"] = len(obs)
            stats["platforms"] = sorted(
                list({str(o["platform_id"]) for o in obs if "platform_id" in o})
            )
            stats["cycles"] = sorted(
                list(
                    {
                        o["cycle_number"]
                        for o in obs
                        if "cycle_number" in o and o["cycle_number"] is not None
                    }
                )
            )
            pressures = [
                o["pressure_dbar"] for o in obs if o.get("pressure_dbar") is not None
            ]
            temps = [
                o["temperature_c"] for o in obs if o.get("temperature_c") is not None
            ]
            salinities = [
                o["salinity_psu"] for o in obs if o.get("salinity_psu") is not None
            ]
            if pressures:
                stats["pressure_min"] = min(pressures)
                stats["pressure_max"] = max(pressures)
            if temps:
                stats["temp_min"] = min(temps)
                stats["temp_max"] = max(temps)
            if salinities:
                stats["salinity_min"] = min(salinities)
                stats["salinity_max"] = max(salinities)
            return stats

        return stats

    def _generate_rule_based_summary(
        self, intent: str, data: Dict[str, Any], stats: Dict[str, Any]
    ) -> str:
        """Deterministic, template-driven summarization using computed metrics."""
        if intent == "summary":
            total_p = stats.get("total_profiles", 0)
            total_o = stats.get("total_observations", 0)
            platforms_str = ", ".join(stats.get("platforms", [])) or "N/A"
            d_min = stats.get("date_min", "N/A")
            if d_min and "T" in str(d_min):
                d_min = str(d_min).split("T")[0]
            d_max = stats.get("date_max", "N/A")
            if d_max and "T" in str(d_max):
                d_max = str(d_max).split("T")[0]
            lat_min = stats.get("lat_min")
            lat_max = stats.get("lat_max")
            lon_min = stats.get("lon_min")
            lon_max = stats.get("lon_max")

            geo_str = ""
            if lat_min is not None and lat_max is not None:
                geo_str = f" Geographic coverage spans latitude {lat_min:.2f}° to {lat_max:.2f}° and longitude {lon_min:.2f}° to {lon_max:.2f}°."

            return (
                f"The ARGO dataset currently contains {total_p} profile(s) and {total_o} vertical observation levels "
                f"from platform(s) {platforms_str}, spanning from {d_min} to {d_max}.{geo_str}"
            )

        if intent == "query_profiles":
            count = stats.get("count", 0)
            platforms_str = ", ".join(stats.get("platforms", []))
            cycles_str = ", ".join(map(str, stats.get("cycles", [])))
            d_min = stats.get("date_min")
            d_max = stats.get("date_max")
            date_str = f" from {d_min} to {d_max}" if d_min and d_max else ""
            lat_min = stats.get("lat_min")
            lat_max = stats.get("lat_max")
            lon_min = stats.get("lon_min")
            lon_max = stats.get("lon_max")
            geo_str = ""
            if lat_min is not None and lat_max is not None and lon_min is not None and lon_max is not None:
                geo_str = f" between latitudes {lat_min:.2f}° to {lat_max:.2f}° and longitudes {lon_min:.2f}° to {lon_max:.2f}°"

            return (
                f"Found {count} ARGO profile(s) for platform(s) {platforms_str} (cycle(s): {cycles_str}){date_str}{geo_str}."
            )

        if intent == "query_observations":
            count = stats.get("count", 0)
            platforms_str = ", ".join(stats.get("platforms", []))
            cycles_str = ", ".join(map(str, stats.get("cycles", [])))
            p_min = stats.get("pressure_min")
            p_max = stats.get("pressure_max")
            t_min = stats.get("temp_min")
            t_max = stats.get("temp_max")
            s_min = stats.get("salinity_min")
            s_max = stats.get("salinity_max")

            details = []
            if p_min is not None and p_max is not None:
                details.append(f"pressures from {p_min:.1f} to {p_max:.1f} dbar")
            if t_min is not None and t_max is not None:
                details.append(f"seawater temperatures from {t_min:.2f}°C to {t_max:.2f}°C")
            if s_min is not None and s_max is not None:
                details.append(f"practical salinity from {s_min:.2f} to {s_max:.2f} PSU")

            measurements_str = f" Measured {', and '.join(details)}." if details else ""
            cycle_info = f" (cycle(s): {cycles_str})" if cycles_str else ""

            return (
                f"Retrieved {count} vertical observation level(s) for platform(s) {platforms_str}{cycle_info}.{measurements_str}"
            )

        return f"Successfully retrieved {self._get_data_count(data)} records."

    def _generate_gemini_summary(
        self,
        prompt: str,
        intent: str,
        parameters: ArgoQueryParameters,
        computed_stats: Dict[str, Any],
        data: Dict[str, Any],
    ) -> str:
        """Sends strictly grounded statistical context to Gemini for natural language synthesis."""
        sample_records: List[Dict[str, Any]] = []
        if intent == "query_profiles" and "profiles" in data:
            sample_records = data["profiles"][:3]
        elif intent == "query_observations" and "observations" in data:
            sample_records = data["observations"][:3]

        context_payload = {
            "user_query": prompt,
            "detected_intent": intent,
            "query_parameters": parameters.model_dump(exclude_none=True),
            "factual_dataset_statistics": computed_stats,
            "sample_records": sample_records,
        }

        user_content = (
            f"User Question: '{prompt}'\n\n"
            f"Factual Retrieved ARGO Data Summary:\n"
            f"{json.dumps(context_payload, default=str, indent=2)}\n\n"
            "Provide a concise, scientifically accurate natural language summary (2 to 4 sentences) answering the user's question grounded strictly in the data above."
        )

        return self.gemini_client.generate_text(
            prompt=user_content,
            system_instruction=DATA_SUMMARIZATION_SYSTEM_PROMPT,
        )
