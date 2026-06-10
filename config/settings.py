from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "TonamiIbuki企业 IT 运维智能体系统"
    ENV: str = "dev"
    API_TOKEN: str = ""
    LLM_PROVIDER: Literal["mock", "openai", "deepseek", "ollama", "siliconflow", "bedrock"] = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    TOOL_MODE: Literal["simulate", "real"] = "simulate"
    EMBEDDING_PROVIDER: Literal["mock", "openai", "ollama"] = "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    RERANKER_PROVIDER: Literal["mock", "cross-encoder"] = "mock"
    LLM_CACHE_PATH: Path = Field(default=Path("data/cache/llm_cache.json"))
    KNOWLEDGE_DIR: Path = Field(default=Path("data/knowledge"))
    KB_PATH: Path = Field(default=Path("data/kb/runbooks.json"))
    RAG_EVAL_PATH: Path = Field(default=Path("data/eval/rag_eval.json"))
    RRF_K: int = 60
    TOP_K: int = 5
    RISK_APPROVAL_THRESHOLD: Literal["medium", "high", "critical"] = "high"
    AUDIT_LOG_PATH: Path = Field(default=Path("data/audit/audit.jsonl"))
    CASE_DB_PATH: Path = Field(default=Path("data/cases/cases.json"))
    SQLITE_DB_PATH: Path = Field(default=Path("data/state/tonamiibuki.db"))
    SANDBOX_DIR: Path = Field(default=Path("data/sandbox"))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.CASE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    settings.LLM_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.RAG_EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
