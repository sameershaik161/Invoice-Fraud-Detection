import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "InvoiceFactoringGuard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    # CORS — allow frontend dev server
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # Data paths
    DATA_DIR: Path = Path(__file__).parent.parent / "data"

    # Neo4j graph store
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_ENABLED: bool = False

    # Optional server-side AI providers; deterministic mode works without any keys.
    AI_PROVIDER: str = "none"
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_BASE_URL: str = "https://api.openai.com/v1"
    AI_FALLBACK_PROVIDER: str = "none"
    AI_FALLBACK_API_KEY: str = ""
    AI_FALLBACK_MODEL: str = ""
    AI_FALLBACK_BASE_URL: str = "https://api.openai.com/v1"
    AI_TIMEOUT_SECONDS: int = 8
    GEMINI_API_KEY: str = ""
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta"

    # Risk engine weights (max total = 100)
    WEIGHT_MULTIPLE_LENDERS: int = 30
    WEIGHT_INVOICE_SIMILARITY: int = 20
    WEIGHT_GSTIN_MATCH: int = 15
    WEIGHT_DELIVERY_PROOF: int = 10
    WEIGHT_TIMING_OVERLAP: int = 10
    WEIGHT_HIGH_VALUE: int = 5
    WEIGHT_LINE_ITEM_SIMILARITY: int = 10
    WEIGHT_CIRCULAR_NETWORK: int = 15
    WEIGHT_MODIFIED_INVOICE_ID: int = 15

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[1] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
