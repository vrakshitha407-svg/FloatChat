"""
FastAPI route definitions for conversational AI chat interaction with ARGO ocean data.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_service
from app.api.schemas import ChatQueryRequest, ChatQueryResponse
from app.llm.service import ConversationalQueryService

router = APIRouter()


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    summary="Process conversational query on ARGO data",
    description="Interprets natural language queries, filters ARGO datasets via ArgoQueryEngine, and returns a scientifically grounded summary.",
)
def chat_query(
    request: ChatQueryRequest,
    service: ConversationalQueryService = Depends(get_chat_service),
) -> ChatQueryResponse:
    """Executes natural language query interpretation, data retrieval, and grounded summarization."""
    return service.process_query(prompt=request.prompt)


@router.post(
    "",
    response_model=ChatQueryResponse,
    include_in_schema=False,
)
def chat_query_alias(
    request: ChatQueryRequest,
    service: ConversationalQueryService = Depends(get_chat_service),
) -> ChatQueryResponse:
    """Alias for POST /query."""
    return service.process_query(prompt=request.prompt)
