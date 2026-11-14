# FloatChat – AI-Powered Conversational Interface for ARGO Ocean Data Discovery and Visualization

**5th-Semester Engineering Mini Project**

---

## 1. Project Purpose

**FloatChat** enables researchers, educators, and oceanography enthusiasts to explore and visualize real-world ARGO float oceanographic data using natural language queries.

ARGO is a global array of nearly 4,000 autonomous profiling floats that measure temperature, salinity, and pressure across the global oceans down to 2,000 meters. Extracting and analyzing these scientific datasets typically requires specialized domain knowledge and scripting in scientific formats like NetCDF.

FloatChat bridges this gap by:
1. Translating natural language questions into structured query parameters (location, time window, depth level, oceanographic variables).
2. Querying and processing actual ARGO datasets using Python scientific libraries (**Pandas** and **Xarray**).
3. Displaying interactive visualizations (maps of float trajectories and depth-profile charts) alongside clear explanations.

---

## 2. Planned Architecture

The system is structured in three decoupled tiers:

1. **Frontend (`frontend/`)**: Modern React interface featuring a chat panel, interactive map view, and scientific profile charts.
2. **Backend (`backend/`)**: FastAPI application providing REST endpoints, query orchestration, and data serialization.
3. **Data & AI Layer (`backend/app/argo/`)**:
   - Query parser translating questions to structured filters.
   - ARGO data processing engine utilizing Xarray and Pandas on authentic NetCDF files.

---

## 3. Current Implementation Status (Stage 1)

This project is being developed incrementally. In **Stage 1**:
- [x] Clean modular repository structure established.
- [x] Backend initialized with FastAPI, CORS middleware, and configuration management.
- [x] Health-check endpoint operational: `GET /api/health`.
- [x] Automated backend tests for health-check endpoint.
- [x] Frontend initialized with React and Vite.
- [x] Frontend health-check dashboard verifying backend connectivity in real time.
- [ ] *Pending Stage 2+: ARGO NetCDF data ingestion and query engine.*
- [ ] *Pending Stage 3+: LLM query interpretation and parameter extraction.*
- [ ] *Pending Stage 4+: Interactive map and depth profile chart visualizations.*

> **Scientific Integrity Notice**: No fake ARGO observations or simulated data are used. Actual ARGO data ingestion begins in subsequent stages with genuine datasets.

---

## 4. Getting Started

### Prerequisites
- **Python 3.10+** (Tested on Python 3.14)
- **Node.js 18+** and **npm**

---

### Backend Setup

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the FastAPI development server:
   ```bash
   python run.py
   # Or directly with uvicorn:
   uvicorn app.main:app --reload --port 8000
   ```

5. Verify backend health endpoint:
   - Visit: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
   - Interactive API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

6. Run automated tests:
   ```bash
   pytest tests/
   ```

---

### Frontend Setup

1. Open a second terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```

4. Open your browser and visit:
   [http://localhost:5173](http://localhost:5173)

The page will immediately ping the FastAPI backend and display a live status badge indicating successful communication.
