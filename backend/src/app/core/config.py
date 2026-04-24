from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # DashScope (AI-SPEC §4: must be intl key from dashscope-intl.aliyuncs.com)
    dashscope_api_key: SecretStr
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    # Database (D-03: postgresql+asyncpg DSN; SecretStr — DSN contains password)
    database_url: SecretStr

    # Redis (D-03)
    redis_url: str = "redis://redis:6379/0"

    # File storage (D-04: per-job layout under .data/jobs/{job_id}/)
    data_dir: str = "/data"

    # Translation batch token budget (D-07: 2-4K range; tune empirically)
    token_budget: int = 3000

    # Worker batch concurrency (D-17: 4 concurrent DashScope calls per job)
    worker_concurrency: int = 4

    @field_validator("token_budget")
    @classmethod
    def validate_token_budget(cls, v: int) -> int:
        if not (500 <= v <= 7000):
            raise ValueError(f"token_budget must be 500-7000, got {v}")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
