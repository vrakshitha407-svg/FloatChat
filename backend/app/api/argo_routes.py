"""
FastAPI route definitions for ARGO oceanographic data querying.
Queries the processed Parquet datasets exclusively through ArgoQueryEngine.
"""

from typing import List, Optional
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_query_engine
from app.api.schemas import (
    DatasetSummaryResponse,
    ObservationsListResponse,
    ProfileDetailResponse,
    ProfilesListResponse,
)
from app.argo.query import ArgoQueryEngine

router = APIRouter()


@router.get(
    "/summary",
    response_model=DatasetSummaryResponse,
    summary="Get ARGO dataset summary",
    description="Returns high-level statistics and spatial-temporal bounding coordinates for the processed dataset.",
)
def get_dataset_summary(
    engine: ArgoQueryEngine = Depends(get_query_engine),
) -> DatasetSummaryResponse:
    """Returns dataset overview and spatiotemporal limits."""
    summary_data = engine.get_summary()
    return DatasetSummaryResponse(**summary_data)


@router.get(
    "/profiles",
    response_model=ProfilesListResponse,
    summary="Query ARGO profiles",
    description="Filters float profiles by bounding box (lat/lon), date range, and platform identifier.",
)
def query_profiles(
    min_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Minimum latitude (-90 to 90)"),
    max_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Maximum latitude (-90 to 90)"),
    min_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Minimum longitude (-180 to 180)"),
    max_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Maximum longitude (-180 to 180)"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format YYYY-MM-DD)"),
    platform_id: Optional[str] = Query(None, description="ARGO Platform WMO ID (e.g. '1900121')"),
    engine: ArgoQueryEngine = Depends(get_query_engine),
) -> ProfilesListResponse:
    """Filters profile metadata using spatial, temporal, and platform constraints."""
    # Coordinate range validation
    if min_lat is not None and max_lat is not None and min_lat > max_lat:
        raise HTTPException(status_code=400, detail="min_lat cannot be greater than max_lat")

    if min_lon is not None and max_lon is not None and min_lon > max_lon:
        raise HTTPException(status_code=400, detail="min_lon cannot be greater than max_lon")

    # Date range validation
    parsed_start = None
    parsed_end = None
    if start_date is not None:
        try:
            parsed_start = pd.to_datetime(start_date, utc=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format YYYY-MM-DD")

    if end_date is not None:
        try:
            parsed_end = pd.to_datetime(end_date, utc=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format YYYY-MM-DD")

    if parsed_start is not None and parsed_end is not None and parsed_start > parsed_end:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")

    # Query through ArgoQueryEngine
    df = engine.filter_profiles(
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        start_date=parsed_start,
        end_date=parsed_end,
        platform_id=platform_id,
    )

    if df.empty:
        return ProfilesListResponse(count=0, profiles=[])

    # Convert timestamps to ISO string and clean NaNs
    df_clean = df.copy()
    if "datetime" in df_clean.columns:
        df_clean["datetime"] = df_clean["datetime"].apply(
            lambda x: x.isoformat() if isinstance(x, pd.Timestamp) and not pd.isna(x) else None
        )
    records = df_clean.replace({np.nan: None}).to_dict(orient="records")

    return ProfilesListResponse(count=len(records), profiles=records)


@router.get(
    "/observations",
    response_model=ObservationsListResponse,
    summary="Query ARGO observations",
    description="Filters discrete observation levels by platform, cycle number, and depth/pressure range.",
)
def query_observations(
    platform_id: Optional[str] = Query(None, description="ARGO Platform WMO ID (e.g. '1900121')"),
    cycle_number: Optional[int] = Query(None, ge=0, description="Float cycle number"),
    min_depth: Optional[float] = Query(None, ge=0.0, description="Minimum depth/pressure in decibars (dbar)"),
    max_depth: Optional[float] = Query(None, ge=0.0, description="Maximum depth/pressure in decibars (dbar)"),
    min_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Minimum latitude"),
    max_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Maximum latitude"),
    min_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Minimum longitude"),
    max_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Maximum longitude"),
    engine: ArgoQueryEngine = Depends(get_query_engine),
) -> ObservationsListResponse:
    """Filters vertical observation levels by platform, depth interval, and location."""
    if min_depth is not None and max_depth is not None and min_depth > max_depth:
        raise HTTPException(status_code=400, detail="min_depth cannot be greater than max_depth")

    if min_lat is not None and max_lat is not None and min_lat > max_lat:
        raise HTTPException(status_code=400, detail="min_lat cannot be greater than max_lat")

    if min_lon is not None and max_lon is not None and min_lon > max_lon:
        raise HTTPException(status_code=400, detail="min_lon cannot be greater than max_lon")

    df = engine.filter_observations(
        platform_id=platform_id,
        cycle_number=cycle_number,
        min_depth=min_depth,
        max_depth=max_depth,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
    )

    if df.empty:
        return ObservationsListResponse(count=0, observations=[])

    df_clean = df.copy()
    if "datetime" in df_clean.columns:
        df_clean["datetime"] = df_clean["datetime"].apply(
            lambda x: x.isoformat() if isinstance(x, pd.Timestamp) and not pd.isna(x) else None
        )
    records = df_clean.replace({np.nan: None}).to_dict(orient="records")

    return ObservationsListResponse(count=len(records), observations=records)


@router.get(
    "/profiles/{platform_id}/{cycle_number}",
    response_model=ProfileDetailResponse,
    summary="Get single profile detail with observation levels",
    description="Retrieves profile metadata bundled with ordered vertical observation levels for charting.",
)
def get_profile_detail(
    platform_id: str,
    cycle_number: int,
    engine: ArgoQueryEngine = Depends(get_query_engine),
) -> ProfileDetailResponse:
    """Retrieves full profile details including vertical observation curve."""
    detail = engine.get_profile_detail(platform_id=platform_id, cycle_number=cycle_number)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Profile for platform {platform_id} cycle {cycle_number} not found.",
        )

    return ProfileDetailResponse(**detail)
