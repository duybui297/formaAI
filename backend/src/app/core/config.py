from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
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
    dashscope_model: str = "qwen-mt-turbo"

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

    # Phase 4: OCR configuration (D-04-06, D-04-10, D-04-17)
    ocr_page_dpi: int = Field(default=300, alias="OCR_PAGE_DPI")
    ocr_page_concurrency: int = Field(default=1, alias="OCR_PAGE_CONCURRENCY")
    ocr_text_density_threshold: float = Field(default=50.0, alias="OCR_TEXT_DENSITY_THRESHOLD")

    # D-02-12: per-language-pair expansion ratio thresholds (LAYOUT-01)
    # JSON string env var: EXPANSION_RATIO_THRESHOLDS
    # Format: {"src->tgt": float, ...} e.g. {"en->vi": 1.3, "vi->en": 0.9}
    # Default values tuned empirically; override via env without code change.
    expansion_ratio_thresholds: str = Field(
        default='{"en->vi": 1.3, "vi->en": 0.9, "ja->vi": 1.5, "vi->ja": 0.9, "vi->zh": 0.85, "en->ja": 1.6}',
        description="JSON map of 'src->tgt' to float expansion ratio threshold. Default 1.5 if pair absent.",
    )

    # Auth
    secret_key: SecretStr = Field(
        description="JWT secret key. Generate with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    login_max_attempts: int = 5
    login_attempt_window_minutes: int = 10
    login_lockout_minutes: int = 15
    password_reset_token_expire_minutes: int = 60  # 1 hour
    forgot_password_cooldown_seconds: int = 60  # prevent spam — minimum time between reset emails

    # Email SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "noreply@forma.app"
    smtp_tls: bool = True

    @field_validator("token_budget")
    @classmethod
    def validate_token_budget(cls, v: int) -> int:
        if not (500 <= v <= 7000):
            raise ValueError(f"token_budget must be 500-7000, got {v}")
        return v

    @field_validator("expansion_ratio_thresholds")
    @classmethod
    def validate_expansion_thresholds_json(cls, v: str) -> str:
        """T-02-02-01: Validate JSON at startup — fail fast rather than at property access."""
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"EXPANSION_RATIO_THRESHOLDS must be valid JSON: {e}"
            ) from e
        if not isinstance(parsed, dict):
            raise ValueError("EXPANSION_RATIO_THRESHOLDS must be a JSON object (dict)")
        for k, val in parsed.items():
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"EXPANSION_RATIO_THRESHOLDS: value for '{k}' must be a number, got {type(val).__name__}"
                )
        return v

    @property
    def expansion_thresholds_dict(self) -> dict[str, float]:
        """Return the parsed expansion ratio thresholds as a dict."""
        return json.loads(self.expansion_ratio_thresholds)


@lru_cache
def get_settings() -> Settings:
    return Settings()
