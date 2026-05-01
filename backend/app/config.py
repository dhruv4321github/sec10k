"""Centralised settings loaded from env / .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str = "sk-missing"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # SEC
    sec_user_agent: str = "FairPlay Take-Home test@example.com"

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/sec10k"

    # Retrieval / chunking
    chunk_size: int = 800
    chunk_overlap: int = 100
    top_k: int = 5

    embedding_dim: int = 1536
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
