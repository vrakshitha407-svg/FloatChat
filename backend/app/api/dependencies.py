"""
FastAPI dependency injection providers.
"""

from functools import lru_cache
from pathlib import Path

from app.argo.query import ArgoQueryEngine
from app.llm.interpreter import QueryInterpreter
from app.llm.service import ConversationalQueryService
from app.llm.summarizer import DataSummarizer

# Resolve default processed data directory
PROCESSED_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed"


@lru_cache()
def get_query_engine() -> ArgoQueryEngine:
    """
    Provides a cached instance of the ArgoQueryEngine pointing to data/processed/.
    Can be easily overridden in tests using app.dependency_overrides.
    """
    return ArgoQueryEngine(processed_dir=PROCESSED_DATA_DIR)


@lru_cache()
def get_query_interpreter() -> QueryInterpreter:
    """Provides a cached instance of the QueryInterpreter."""
    return QueryInterpreter()


@lru_cache()
def get_data_summarizer() -> DataSummarizer:
    """Provides a cached instance of the DataSummarizer."""
    return DataSummarizer()


@lru_cache()
def get_chat_service() -> ConversationalQueryService:
    """Provides a cached instance of ConversationalQueryService connecting all components."""
    return ConversationalQueryService(
        query_engine=get_query_engine(),
        interpreter=get_query_interpreter(),
        summarizer=get_data_summarizer(),
    )
