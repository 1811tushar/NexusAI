"""Typed settings for every variable in contract section 11 (AI-FD-02). Fails fast on missing secrets."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- internal auth (required: no default on purpose) ---
    internal_api_key: str = Field(min_length=16)

    # --- LLM ---
    llm_provider: Literal["gemini", "ollama", "groq"] = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str | None = None          # MUST be confirmed in Google AI Studio on the day you build
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str | None = None          # pick one that supports tool calling
    groq_api_key: str | None = None
    groq_model: str | None = None
    llm_max_retries: int = Field(4, ge=0, le=10)
    llm_timeout_s: float = 60.0

    # --- embeddings / reranker ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"   # "hashing" = deterministic test embedder (no download)
    embedding_dim: int = 384
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- web search (used by AI B) ---
    tavily_api_key: str | None = None
    web_search_enabled: bool = True

    # --- database (two roles, AI-FD-05) ---
    ai_db_host: str = "postgres"
    ai_db_port: int = 5432
    ai_db_name: str = "nexusai"
    ai_db_rw_user: str = "ai_rw"
    ai_db_rw_password: str = Field(min_length=1)
    ai_db_ro_user: str = "ai_readonly"
    ai_db_ro_password: str = Field(min_length=1)
    db_pool_min: int = 1
    db_pool_max: int = 8

    # --- agent knobs (AI B) ---
    max_loops: int = Field(3, ge=1, le=5)
    confidence_min: float = Field(0.7, ge=0, le=1)
    top_k: int = Field(8, ge=1, le=50)
    sql_row_limit: int = Field(200, ge=1)
    sql_timeout_ms: int = Field(5000, ge=100)
    max_tool_attempts: int = Field(3, ge=1, le=10)
    guardrails_enabled: bool = True
    pii_redaction_enabled: bool = True

    # --- chunking / ingestion ---
    chunking_mode: Literal["fixed", "semantic"] = "semantic"
    chunk_tokens: int = Field(500, ge=100, le=1000)
    chunk_overlap_tokens: int = Field(90, ge=0, le=300)
    max_upload_mb: int = 20
    max_pages: int = 500
    max_chars: int = 3_000_000
    max_chunks_per_doc: int = 2000
    ingest_timeout_s: float = 100.0          # Spring waits 120 s
    retrieval_per_doc_cap: int = Field(4, ge=1)

    # --- observability ---
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None
    log_level: str = "INFO"

    @field_validator("internal_api_key")
    @classmethod
    def _no_placeholder_key(cls, v: str) -> str:
        if v.lower() in {"changeme", "change-me", "secret", "password"}:
            raise ValueError("INTERNAL_API_KEY must not be a placeholder")
        return v

    @model_validator(mode="after")
    def _overlap_smaller_than_chunk(self) -> Settings:
        if self.chunk_overlap_tokens >= self.chunk_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_TOKENS")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
