# Module: core

## Purpose
Cross-cutting primitives shared across the backend: application settings, structured logging configuration, and authentication/security helpers (password hashing, JWT). No business logic; imported by routes, services, and workers.

## Files
| File | Responsibility |
|------|----------------|
| config.py | Settings (pydantic-settings) — env vars, SecretStr, validators |
| logging.py | structlog configuration |
| security.py | password hashing (bcrypt), JWT encode/decode, token helpers |

## Settings (config.py)
- `Settings(BaseSettings)` loads from `.env` (utf-8, `case_sensitive=False`).
- Required env (no default): `dashscope_api_key` (SecretStr), `database_url` (SecretStr — DSN holds password), `secret_key` (SecretStr, JWT signing).
- DashScope defaults: `dashscope_base_url` = intl compatible-mode endpoint, `dashscope_model` = `qwen-mt-turbo`.
- Infra defaults: `redis_url` = `redis://redis:6379/0`, `data_dir` = `/data`.
- Translation: `token_budget` = 3000, `worker_concurrency` = 4.
- OCR (aliased env): `ocr_page_dpi` (300, `OCR_PAGE_DPI`), `ocr_page_concurrency` (1, `OCR_PAGE_CONCURRENCY`), `ocr_text_density_threshold` (50.0, `OCR_TEXT_DENSITY_THRESHOLD`).
- `expansion_ratio_thresholds`: JSON string env (`EXPANSION_RATIO_THRESHOLDS`) mapping `"src->tgt"` to float; default 1.5 if pair absent. Parsed via `expansion_thresholds_dict` property.
- Auth defaults: `algorithm` = HS256, `access_token_expire_minutes` = 15, `refresh_token_expire_days` = 30, `login_max_attempts` = 5, `login_attempt_window_minutes` = 10, `login_lockout_minutes` = 15, `password_reset_token_expire_minutes` = 60, `forgot_password_cooldown_seconds` = 60.
- SMTP defaults: `smtp_host`, `smtp_port` 587, `smtp_user`, `smtp_password` (SecretStr), `smtp_from`, `smtp_tls` True.
- Validators: `validate_token_budget` enforces 500–7000; `validate_expansion_thresholds_json` fails fast at startup (valid JSON, must be dict, values numeric).
- `get_settings()` wrapped in `@lru_cache` — single cached Settings instance.

## Security (security.py)
- `hash_password` / `verify_password`: bcrypt (`hashpw`/`checkpw` with `gensalt`); verify swallows exceptions → returns False.
- `create_access_token`: encodes payload + `exp` + `type="access"`; default expiry from `access_token_expire_minutes` or supplied `expires_delta`.
- `create_refresh_token`: `exp` from `refresh_token_expire_days`, `type="refresh"`.
- `decode_access_token` / `decode_refresh_token`: decode + verify signature/algorithm; enforce matching `type` claim; return None on `JWTError` or type mismatch.
- `generate_password_reset_token`: opaque `secrets.token_hex(32)` (not a JWT).
- `create_email_verify_token`: JWT with `sub`, `email`, `exp` (from `password_reset_token_expire_minutes`).
- Algorithm HS256; signed with `secret_key` (SecretStr, `.get_secret_value()`). All timestamps timezone-aware UTC.

## Logging (logging.py)
- `configure_logging(level="INFO")`: sets stdlib `basicConfig`, configures structlog; idempotent.
- structlog processors: `merge_contextvars`, `add_log_level`, `TimeStamper(iso)`, `StackInfoRenderer`, `format_exc_info`, `JSONRenderer` → JSON to stdout (D-19, captured by docker logs).
- `make_filtering_bound_logger(INFO)`, `PrintLoggerFactory`, `cache_logger_on_first_use=True`.
- `bind_job_id(job_id)` / `clear_job_id()`: bind/clear `job_id` contextvar per coroutine context.

## Dependencies
pydantic / pydantic-settings (SecretStr, field_validator, BaseSettings), structlog, bcrypt, python-jose (jose.jwt), stdlib (secrets, datetime, json, functools.lru_cache, logging).
