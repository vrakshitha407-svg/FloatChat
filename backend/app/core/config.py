import os
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables from .env file if present
load_dotenv()


class Settings(BaseModel):
    """Application configuration parameters."""
    PROJECT_NAME: str = "FloatChat API"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api"
    
    # Allowed CORS origins for development (Vite frontend on 5173 / localhost)
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Gemini LLM configuration (reads from environment variables)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "10.0"))


settings = Settings()
