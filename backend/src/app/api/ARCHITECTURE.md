# Module: api

## Purpose
HTTP layer for the AI Translation backend: FastAPI routers, dependency injection, CORS, and JWT auth dependencies. Translates HTTP requests into service/pipeline calls; owns no business logic beyond request validation, ownership checks, and serialization.

## Dependency injection (deps.py)
- `get_session` (from `app.db.session`) — async SQLAlchemy `AsyncSession` per request.
- `get_redis(request)` — shared `redis.asyncio.Redis` client read from `request.app.state.redis` (created once in lifespan).
- `get_arq_pool(request)` — shared arq pool from `request.app.state.arq_pool`. W11: never create a per-request pool.
- `get_settings(request)` — cached `Settings` from `request.app.state.settings`.
- `security = HTTPBearer(auto_error=False)` — Bearer token extractor; no auto-401 so dependencies control error shape.
- `get_current_user` — decodes access token via `decode_access_token`, loads `User` by `sub` (user_id); 401 on missing/invalid token, bad payload, or unknown user.
- `get_current_active_user` — wraps `get_current_user`; 403 if `user.is_active` is false. This is the auth dependency used by all protected routes.
- `get_optional_user` — same lookup but returns `None` instead of raising (no protected route currently uses it).
- LLM client also lives on app.state (`request.app.state.llm_client`), consumed directly in segment regenerate.

## Middleware
`middleware/cors.py` — `add_cors_middleware(app)`:
- Origins from `CORS_ALLOWED_ORIGINS` env (comma-separated), default `http://localhost:3000`. Never `["*"]`.
- `allow_credentials=False`.
- Methods: `GET, POST, PATCH, DELETE, OPTIONS`.
- Headers: `Content-Type, Accept`.
- Note: refresh/CSRF flow uses cookies but `allow_credentials=False` here — cross-origin cookie auth relies on same-site deployment / proxy.

## Routers & endpoints

| Router | Endpoints | Notes |
|--------|-----------|-------|
| auth (`/auth`) | POST `/register` (201), POST `/login`, POST `/refresh`, POST `/logout` (204), GET `/me`, POST `/forgot-password`, POST `/reset-password` | JWT access + httpOnly refresh cookie + non-httpOnly CSRF cookie; Redis-backed login lockout; CSRF double-submit check on refresh |
| upload | POST `/upload` (202) | Validate ext/size/lang/glossary, scanned-PDF + tracked-changes probe, save file, create job, enqueue `translate_job` |
| jobs | GET `/jobs`, GET `/jobs/{id}`, GET `/jobs/{id}/artifacts?artifact=`, GET `/jobs/{id}/pages/{n}.png`, GET `/jobs/{id}/download` | Per-user filtering + ownership; FileResponse; paths server-derived from job_id |
| segments | GET `/jobs/{id}/segments`, PATCH `/jobs/{id}/segments/{sid}`, POST `/jobs/{id}/segments/{sid}/regenerate` | Optimistic edit (`edited_text`) + sync LLM regen (overwrites `translated_text`); 409 unless job done/needs_review |
| sse | GET `/jobs/{id}/stream` | `EventSourceResponse`, Redis pub/sub on `job:{id}`, `ping=15`, closes on terminal status |
| export | POST `/jobs/{id}/export` | Idempotent DOCX/PPTX/PDF reassembly; FileResponse or JSONResponse(409/500) |
| glossaries | GET/POST `/glossaries`, GET/PATCH/DELETE `/glossaries/{id}`, GET/POST `/glossaries/{id}/terms`, POST `/glossaries/{id}/terms/import`, PATCH/DELETE `/glossaries/{id}/terms/{term_id}` | Full CRUD + CSV/TBX import; per-user ownership; import route declared before `/{term_id}` |
| languages | GET `/languages` | Static qwen-mt-turbo language list; no auth (TODO phase-2) |
| health | GET `/health` | Liveness `{"status":"ok"}`; no auth; Docker healthcheck (D-18) |

### Endpoint detail notes
- **upload** — 413 fast-path on Content-Length + streaming 64KB-chunk guard (25 MB cap); 415 on disallowed ext, 422 on unsupported format / bad target_lang / glossary pair mismatch. Scanned-PDF detection via PyMuPDF + `detect_scanned_pdf` (override-able). Tracked-changes probe for `.docx`. File stored at `{data_dir}/jobs/{job_id}/source{ext}`; job row created first, `input_path` patched after. Returns `{job_id, has_tracked_changes, is_scanned}`.
- **jobs/{id}/artifacts** — strict allowlist `bilingual_pdf | translated_pdf | translated_docx` → fixed filename + media type; path from `data_dir/jobs/{job_id}/`; 409 unless status in `done|needs_review`; 404 if file missing. T-04-09 (no user path components).
- **jobs/{id}/pages/{n}.png** — serves cached `pages/page-{n}.png`; `page_n` typed int (no traversal).
- **jobs/{id}/download** — streams `job.output_path` (server-stored, T-06b-01); 409 unless done/needs_review; 404 if path missing.
- **segments PATCH** — updates `edited_text` (+ optional `edited_source_text`); compound WHERE `(job_id, id)`; null clears edit.
- **segments regenerate** — sync `translate_batch` using job's locked glossary; prefers `edited_source_text` (corrected OCR) over `source_text`; overwrites only `translated_text`, never `edited_text`.
- **export** — `export_job(session, job_id, data_dir)`; advisory lock + atomic write (D-02-22); does not mutate segment rows; `ValueError`→409, others→500 JSON.

## Auth flow
- **Protected routes:** all of jobs, segments, sse, export, upload, glossaries (except `DELETE /glossaries/{id}/terms/{term_id}`, which currently has no auth dependency), and `GET /auth/me` — via `get_current_active_user`. `GET /languages` and `GET /health` are unauthenticated.
- **Login:** email+password (`verify_password`) → 15-min access token returned in body (`TokenResponse.access_token`); sets `refresh_token` (httpOnly, samesite=strict, 30-day) + `csrf_token` (non-httpOnly) cookies. `secure=False` (dev). Failed attempts tracked in Redis (`login_attempts:{user_id}:{ip}`); lockout key set after `login_max_attempts` for `login_lockout_minutes`; 429 while locked.
- **Access token validation:** `decode_access_token` in `get_current_user`; `sub` claim = user_id; DB lookup confirms user exists + active.
- **Refresh + CSRF:** `POST /auth/refresh` reads refresh cookie, `decode_refresh_token`, re-checks lockout, then double-submit CSRF check — `x-csrf-token` header must equal `csrf_token` cookie (403 mismatch). Verifies user still active, then rotates: new access token + new refresh + new CSRF cookies.
- **Logout:** deletes `refresh_token`, `csrf_token`, `forma_access_token` cookies (204). Client drops local access token.
- **Forgot/reset password:** silent-success response (no user enumeration); `check_only` query flag returns 404 for missing user; Redis cooldown rate-limit; old unused `PasswordResetToken`s invalidated; new token emailed via `aiosmtplib` (skipped if SMTP unconfigured). Reset validates token (unused + unexpired) and updates `hashed_password`.

## Dependencies
- `fastapi`, `sse-starlette` (`EventSourceResponse`), `starlette` responses (`FileResponse`, `JSONResponse`).
- `redis.asyncio` (lockout, cooldown, SSE pub/sub), `sqlalchemy` async (`AsyncSession`, `select/update/func`).
- `app.core.security` (token create/decode, password hash/verify, reset-token gen), `app.core.config` (`Settings`).
- `app.db.models` (`User`, `Job`, `Segment`, `SegmentFlag`, `Glossary`, `GlossaryTerm`, `PasswordResetToken`, enums), `app.db.session`.
- `app.schemas.*` (auth, segment, glossary request/response models).
- `app.services.*` (`job_service`, `glossary_service`, `export_service`), `app.llm.translator` (`translate_batch`), `app.pipeline.*` (scanned-PDF detector, DOCX tracked-changes probe).
- `aiosmtplib` (reset email), `structlog` (logging).
