"""
Pydantic schemas for ARGO API requests and responses.
Provides structured data validation and documentation for OpenAPI/Swagger UI.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator



class DatasetSummaryResponse(BaseModel):
    """Overall statistics and spatial-temporal bounds of the processed ARGO dataset."""
    status: str = Field(..., description="Status of the dataset, e.g. 'ready' or 'empty'")
    total_profiles: int = Field(..., description="Total count of unique float profiles indexed")
    total_observations: int = Field(..., description="Total count of vertical observation levels across all profiles")
    platforms: List[str] = Field(default_factory=list, description="List of unique float WMO platform IDs")
    date_min: Optional[str] = Field(None, description="Earliest observation timestamp (ISO 8601)")
    date_max: Optional[str] = Field(None, description="Latest observation timestamp (ISO 8601)")
    lat_min: Optional[float] = Field(None, description="Minimum latitude (southernmost bound)")
    lat_max: Optional[float] = Field(None, description="Maximum latitude (northernmost bound)")
    lon_min: Optional[float] = Field(None, description="Minimum longitude (westernmost bound)")
    lon_max: Optional[float] = Field(None, description="Maximum longitude (easternmost bound)")


class ProfileItemSchema(BaseModel):
    """Metadata summary for a single float profile cycle."""
    platform_id: str = Field(..., description="ARGO WMO Platform Identifier (e.g. '1900121')")
    cycle_number: int = Field(..., description="Float dive cycle number")
    datetime: Optional[str] = Field(None, description="Profile surfacing datetime (UTC ISO 8601)")
    latitude: float = Field(..., description="Float surfacing latitude in decimal degrees")
    longitude: float = Field(..., description="Float surfacing longitude in decimal degrees")
    position_qc: str = Field(..., description="Position Quality Control flag (e.g. '1' for Good)")
    juld_qc: str = Field(..., description="Date Quality Control flag (e.g. '1' for Good)")
    data_mode: str = Field(..., description="Data mode: 'D' (delayed), 'A' (adjusted), or 'R' (real-time)")
    pres_source: str = Field(..., description="Parameter resolution mode: 'adjusted' or 'raw'")
    temp_source: str = Field(..., description="Parameter resolution mode: 'adjusted' or 'raw'")
    psal_source: str = Field(..., description="Parameter resolution mode: 'adjusted' or 'raw'")
    min_pressure_dbar: Optional[float] = Field(None, description="Minimum depth/pressure level sampled (dbar)")
    max_pressure_dbar: Optional[float] = Field(None, description="Maximum depth/pressure level sampled (dbar)")
    num_levels: int = Field(..., description="Number of vertical depth levels sampled")
    source_file: str = Field(..., description="Original NetCDF source file name")


class ProfilesListResponse(BaseModel):
    """List of profile metadata records matching query filters."""
    count: int = Field(..., description="Number of profiles returned")
    profiles: List[ProfileItemSchema] = Field(default_factory=list, description="Array of profile items")


class ObservationItemSchema(BaseModel):
    """Single vertical measurement level within a float profile."""
    platform_id: str = Field(..., description="ARGO WMO Platform Identifier")
    cycle_number: int = Field(..., description="Float dive cycle number")
    datetime: Optional[str] = Field(None, description="Observation datetime (UTC ISO 8601)")
    latitude: float = Field(..., description="Observation latitude in decimal degrees")
    longitude: float = Field(..., description="Observation longitude in decimal degrees")
    level_index: int = Field(..., description="Vertical depth level index (0 = near-surface)")
    pressure_dbar: Optional[float] = Field(None, description="Sea water pressure/depth in decibars (dbar)")
    temperature_c: Optional[float] = Field(None, description="Sea water temperature in degrees Celsius (°C)")
    salinity_psu: Optional[float] = Field(None, description="Practical salinity in Practical Salinity Units (PSU)")
    pres_qc: str = Field(..., description="Original Pressure QC flag ('1'=Good, '2'=Probably Good, etc.)")
    temp_qc: str = Field(..., description="Original Temperature QC flag ('1'=Good, '2'=Probably Good, etc.)")
    psal_qc: str = Field(..., description="Original Salinity QC flag ('1'=Good, '2'=Probably Good, etc.)")
    position_qc: str = Field(..., description="Original Position QC flag")
    juld_qc: str = Field(..., description="Original Date QC flag")
    pres_source: str = Field(..., description="Source of pressure data: 'adjusted' or 'raw'")
    temp_source: str = Field(..., description="Source of temperature data: 'adjusted' or 'raw'")
    psal_source: str = Field(..., description="Source of salinity data: 'adjusted' or 'raw'")


class ObservationsListResponse(BaseModel):
    """List of discrete vertical observations matching depth, cycle, and parameter filters."""
    count: int = Field(..., description="Number of observation levels returned")
    observations: List[ObservationItemSchema] = Field(default_factory=list, description="Array of observation items")


class ProfileDetailResponse(BaseModel):
    """Comprehensive single-profile payload for map popups and vertical depth charts."""
    profile: ProfileItemSchema = Field(..., description="Profile metadata")
    observations: List[ObservationItemSchema] = Field(default_factory=list, description="Ordered vertical observation levels")


class ArgoQueryParameters(BaseModel):
    """Structured query parameters extracted from natural language user input."""
    platform_id: Optional[str] = Field(None, description="ARGO Platform WMO ID, e.g. '1900121'")
    cycle_number: Optional[int] = Field(None, ge=0, description="Float cycle number")
    start_date: Optional[str] = Field(None, description="Start date (ISO format YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (ISO format YYYY-MM-DD)")
    min_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Minimum latitude (-90 to 90)")
    max_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Maximum latitude (-90 to 90)")
    min_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Minimum longitude (-180 to 180)")
    max_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Maximum longitude (-180 to 180)")
    min_depth: Optional[float] = Field(None, ge=0.0, description="Minimum pressure/depth in dbar")
    max_depth: Optional[float] = Field(None, ge=0.0, description="Maximum pressure/depth in dbar")
    variables: List[str] = Field(default_factory=list, description="Requested variables (e.g. ['TEMP', 'PSAL'])")

    @model_validator(mode="after")
    def validate_bounds(self) -> "ArgoQueryParameters":
        if self.min_lat is not None and self.max_lat is not None and self.min_lat > self.max_lat:
            raise ValueError("min_lat cannot be greater than max_lat")
        if self.min_lon is not None and self.max_lon is not None and self.min_lon > self.max_lon:
            raise ValueError("min_lon cannot be greater than max_lon")
        if self.min_depth is not None and self.max_depth is not None and self.min_depth > self.max_depth:
            raise ValueError("min_depth cannot be greater than max_depth")
        return self


class InterpretationResult(BaseModel):
    """Result of interpreting a natural language query."""
    is_valid_query: bool = Field(..., description="Whether the input is a valid ARGO/oceanographic query")
    intent: str = Field(..., description="Detected intent: 'query_profiles', 'query_observations', 'summary', or 'out_of_domain'")
    parameters: ArgoQueryParameters = Field(default_factory=ArgoQueryParameters, description="Extracted structured parameters")
    original_prompt: str = Field(..., description="The user's original query text")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score of interpretation (0.0 to 1.0)")
    explanation: Optional[str] = Field(None, description="Explanation or reasoning for interpretation")


class ChatQueryRequest(BaseModel):
    """Natural language user chat query request."""
    prompt: str = Field(..., min_length=1, description="Natural language query string")


class ChatQueryResponse(BaseModel):
    """Structured response containing interpreted query, retrieved data, and grounded summary."""
    prompt: str = Field(..., description="Original user prompt")
    intent: str = Field(..., description="Detected intent: 'query_profiles', 'query_observations', 'summary', or 'out_of_domain'")
    parameters: ArgoQueryParameters = Field(..., description="Validated structured query parameters")
    data: Optional[Dict[str, Any]] = Field(None, description="Retrieved dataset payload (profiles, observations, or summary)")
    data_count: int = Field(0, description="Total count of records returned")
    summary: str = Field(..., description="Grounded natural language answer synthesized from retrieved data")
    interpretation_explanation: Optional[str] = Field(None, description="Reasoning behind query parameter extraction")
    source: str = Field(..., description="Generation source: 'gemini' or 'rule_based'")

