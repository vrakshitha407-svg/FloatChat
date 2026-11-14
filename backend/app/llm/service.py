"""
Conversational Query Service for FloatChat.
Orchestrates natural language interpretation, ARGO QueryEngine execution,
and grounded data summarization into a unified conversational flow.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from app.api.schemas import ArgoQueryParameters, ChatQueryResponse, InterpretationResult
from app.argo.query import ArgoQueryEngine
from app.llm.interpreter import QueryInterpreter
from app.llm.summarizer import DataSummarizer


class ConversationalQueryService:
    """
    End-to-end service connecting natural language queries to the ARGO query engine
    and producing scientifically grounded natural language summaries.
    """

    def __init__(
        self,
        query_engine: Optional[ArgoQueryEngine] = None,
        interpreter: Optional[QueryInterpreter] = None,
        summarizer: Optional[DataSummarizer] = None,
    ):
        self.query_engine: ArgoQueryEngine = query_engine or ArgoQueryEngine()
        self.interpreter: QueryInterpreter = interpreter or QueryInterpreter()
        self.summarizer: DataSummarizer = summarizer or DataSummarizer()

    def process_query(self, prompt: str) -> ChatQueryResponse:
        """
        Executes the full conversational ARGO pipeline:
        1. Interpret natural language prompt into structured parameters.
        2. Query the ARGO query engine (Parquet datasets).
        3. Synthesize a grounded summary of the results.
        """
        cleaned_prompt = prompt.strip() if prompt else ""

        # Step 1: Query Interpretation
        interpretation = self.interpreter.interpret(cleaned_prompt)

        # Step 2: Handle out-of-domain or invalid queries immediately
        if not interpretation.is_valid_query or interpretation.intent == "out_of_domain":
            summary_text, source = self.summarizer.summarize(
                prompt=cleaned_prompt,
                interpretation=interpretation,
                data=None,
            )
            return ChatQueryResponse(
                prompt=cleaned_prompt,
                intent="out_of_domain",
                parameters=interpretation.parameters,
                data=None,
                data_count=0,
                summary=summary_text,
                interpretation_explanation=interpretation.explanation,
                source=source,
            )

        # Step 3: Query Execution against ArgoQueryEngine
        data_payload: Optional[Dict[str, Any]] = None
        data_count: int = 0

        if interpretation.intent == "summary":
            summary_data = self.query_engine.get_summary()
            data_payload = {"summary": summary_data}
            data_count = int(summary_data.get("total_profiles", 0))

        elif interpretation.intent == "query_profiles":
            p = interpretation.parameters
            df = self.query_engine.filter_profiles(
                min_lat=p.min_lat,
                max_lat=p.max_lat,
                min_lon=p.min_lon,
                max_lon=p.max_lon,
                start_date=p.start_date,
                end_date=p.end_date,
                platform_id=p.platform_id,
            )
            records = self._dataframe_to_records(df)
            data_payload = {"profiles": records, "count": len(records)}
            data_count = len(records)

        elif interpretation.intent == "query_observations":
            p = interpretation.parameters
            df = self.query_engine.filter_observations(
                platform_id=p.platform_id,
                cycle_number=p.cycle_number,
                min_depth=p.min_depth,
                max_depth=p.max_depth,
                min_lat=p.min_lat,
                max_lat=p.max_lat,
                min_lon=p.min_lon,
                max_lon=p.max_lon,
            )
            records = self._dataframe_to_records(df)
            data_payload = {"observations": records, "count": len(records)}
            data_count = len(records)

        else:
            # Fallback to general profiles
            df = self.query_engine.filter_profiles()
            records = self._dataframe_to_records(df)
            data_payload = {"profiles": records, "count": len(records)}
            data_count = len(records)

        # Step 4: Grounded Summarization
        summary_text, source = self.summarizer.summarize(
            prompt=cleaned_prompt,
            interpretation=interpretation,
            data=data_payload,
        )

        return ChatQueryResponse(
            prompt=cleaned_prompt,
            intent=interpretation.intent,
            parameters=interpretation.parameters,
            data=data_payload,
            data_count=data_count,
            summary=summary_text,
            interpretation_explanation=interpretation.explanation,
            source=source,
        )

    @staticmethod
    def _dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Converts DataFrame to clean, JSON-serializable list of dictionaries."""
        if df.empty:
            return []
        df_clean = df.copy()
        if "datetime" in df_clean.columns:
            df_clean["datetime"] = df_clean["datetime"].apply(
                lambda x: x.isoformat() if isinstance(x, pd.Timestamp) and not pd.isna(x) else None
            )
        return df_clean.replace({np.nan: None}).to_dict(orient="records")
