from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"
    api_prefix: str = "/v1"
    data_dir: Path = Path("./data")
    audit_log_path: Path = Path("./var/audit.jsonl")
    ticket_db_path: Path = Path("./var/tickets.db")

    retrieval_backend: Literal["memory", "elasticsearch"] = "memory"
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "resolveai-policies"
    elasticsearch_api_key: str | None = None
    elastic_semantic_enabled: bool = False

    decision_engine: Literal["rules", "openai_compatible"] = "rules"
    openai_compatible_base_url: str = "http://localhost:11434/v1"
    openai_compatible_api_key: str = "local"
    openai_compatible_model: str | None = None

    max_request_chars: int = Field(default=8000, ge=100, le=100_000)
    policy_top_k: int = Field(default=4, ge=1, le=20)
    policy_max_age_days: int = Field(default=730, ge=30, le=3650)

    def ensure_runtime_paths(self) -> None:
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.ticket_db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_paths()
    return settings
