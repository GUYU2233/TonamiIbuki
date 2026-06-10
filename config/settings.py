"""Application settings — configurable via environment variables."""
from __future__ import annotations

import os
from pathlib import Path


class Settings:
    # --- Server ---
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # --- CORS (plan 7.3) ---
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",")

    # --- LLM ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")           # mock | openai | ollama
    LLM_MODEL: str = os.getenv("LLM_MODEL", "mock")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")                  # secret
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # --- Embedding ---
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "mock")  # mock | openai | ollama
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "mock")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))

    # --- Reranker ---
    RERANKER_PROVIDER: str = os.getenv("RERANKER_PROVIDER", "mock")  # mock | cross-encoder

    # --- RAG ---
    RRF_K: int = int(os.getenv("RRF_K", "60"))

    # --- Vector Store ---
    VECTOR_STORE_PATH: str = os.getenv("VECTOR_STORE_PATH", "data/chroma_db")

    # --- SQLite ---
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "data/tonamiibuki.db")

    # --- Knowledge Base ---
    KB_RUNBOOKS_PATH: str = os.getenv("KB_RUNBOOKS_PATH", "data/kb/runbooks.json")
    KB_MARKDOWN_DIR: str = os.getenv("KB_MARKDOWN_DIR", "data/knowledge")

    # --- Security / Rate Limiting (plan 7.2) ---
    RATE_LIMIT_REQUESTS_PER_SEC: float = float(os.getenv("RATE_LIMIT_REQUESTS_PER_SEC", "10.0"))
    RATE_LIMIT_BURST: int = int(os.getenv("RATE_LIMIT_BURST", "20"))

    # --- Secrets Management (plan 7.4) ---
    # Secrets should be set via environment variables, never hard-coded.
    # For local development, use a .env file (loaded via python-dotenv).
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    API_TOKEN_SALT: str = os.getenv("API_TOKEN_SALT", "tonamiibuki")

    # --- Auth ---
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- Tools ---
    SIMULATE_TOOLS: bool = os.getenv("SIMULATE_TOOLS", "true").lower() in ("true", "1", "yes")

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    AUDIT_LOG_PATH: Path = DATA_DIR / "audit.jsonl"


settings = Settings()
