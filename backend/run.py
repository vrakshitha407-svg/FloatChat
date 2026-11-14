"""Convenience script to run the FloatChat FastAPI backend server."""

import uvicorn

if __name__ == "__main__":
    print("Starting FloatChat backend on http://127.0.0.1:8000...")
    print("Swagger UI docs available at: http://127.0.0.1:8000/docs")
    print("Health check endpoint: http://127.0.0.1:8000/api/health")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
