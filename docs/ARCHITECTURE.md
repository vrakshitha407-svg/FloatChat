# FloatChat – System Architecture

## 1. Project Purpose
FloatChat is an AI-powered conversational interface designed to enable oceanographers, researchers, and students to query, explore, and visualize real ARGO float oceanographic datasets using natural language.

Instead of writing complex code to parse NetCDF files, filter coordinates, and extract oceanographic profiles (e.g., temperature, salinity, pressure across depths), users can ask questions in plain English.

---

## 2. Planned Multi-Stage Architecture

The complete system will follow a clean 4-tier pipeline:

```
[ User Query (Natural Language) ]
               │
               ▼
┌────────────────────────────────────────────────────────┐
│ 1. Frontend Layer (React + Vite)                       │
│    - Chat interface for query input                    │
│    - Interactive Map (Leaflet / Mapbox) for float paths│
│    - Profile Charts (Plotly / Recharts) for T/S curves │
│    - Scientific summary & explanation views            │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP / JSON
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Backend API Layer (FastAPI)                         │
│    - Request routing & validation                      │
│    - Health & status monitoring                        │
│    - Orchestrates LLM parsing and data retrieval       │
└──────────────┬───────────────────────────┬─────────────┘
               │                           │
               ▼                           ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│ 3. LLM Query Interpreter  │ │ 4. ARGO Data Engine      │
│    - Natural language to  │ │    (Pandas & Xarray)     │
│      structured JSON query│ │    - NetCDF file reading │
│    - Parameters: bounding │ │    - Spatial & temporal  │
│      box, time range,     │ │      filtering           │
│      depth, variable      │ │    - QC flags validation │
└───────────────────────────┘ └────────────┬─────────────┘
                                           │
                                           ▼
                              ┌──────────────────────────┐
                              │ 5. Scientific Storage    │
                              │    - data/raw (NetCDF)   │
                              │    - data/processed      │
                              └──────────────────────────┘
```

---

## 3. Data Flow Overview (Future Stages)

1. **User asks a question**: e.g., *"Show salinity profiles in the Arabian Sea between 0 and 500m depth for July 2023."*
2. **Intent Parsing**: LLM receives the prompt with domain schema and outputs structured query parameters:
   - Latitude/Longitude range (bounding box)
   - Date range
   - Depth (pressure) range
   - Variables requested (`PSAL`, `TEMP`, `PRES`)
3. **Data Retrieval & Processing**:
   - The ARGO data engine checks available NetCDF files or index tables.
   - Extracts valid float cycles, coordinates, and observation arrays using Xarray/Pandas.
   - Applies standard ARGO Quality Control (QC) flag filtering.
4. **Response Formatting**:
   - JSON response containing coordinates (for map markers/trajectories) and depth/measurement pairs (for charts).
5. **Visualization**:
   - Frontend renders the float trajectory on an interactive map and plots salinity vs. depth on a profile graph.

---

## 4. Current Status: Stage 1 Foundation
- Project directory structure established.
- FastAPI backend configured with CORS and health-check endpoint (`GET /api/health`).
- React frontend initialized with live backend connectivity check.
- Modular placeholders created for data processing and automated testing.
- No dummy data or LLM calls are implemented yet.
