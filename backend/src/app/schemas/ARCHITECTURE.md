# Module: schemas

## Purpose
Pydantic v2 request/response models for the API layer, kept separate from SQLAlchemy ORM models in `app.db.models`. Also holds ORM→dict serializers used to shape API responses.

## Files
| File | Schemas | Used by |
|------|---------|---------|
| auth.py | RegisterRequest, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest, TokenResponse, RefreshTokenResponse, UserResponse, MessageResponse | auth routes |
| glossary.py | CreateGlossaryRequest, RenameGlossaryRequest, CreateTermRequest, UpdateTermRequest | glossary routes |
| segment.py | SegmentPatchRequest (+ `flag_to_dict`, `segment_to_dict` serializers) | segment routes |

## Notes
- `auth.py`: uses `EmailStr` for email fields. `password`/`new_password` constrained `min_length=8, max_length=128`. `full_name` optional. `TokenResponse`/`RefreshTokenResponse` default `token_type="bearer"`.
- `glossary.py`: all requests `frozen=True` (immutable). Create: `name` 1–255, `source_lang`/`target_lang` 2–64. Term create: `source_term`/`target_term` 2–500, `notes` optional ≤1000. `UpdateTermRequest` all fields optional for partial update.
- `segment.py`: `SegmentPatchRequest` `frozen=True`; `edited_text` uses `Field(default=...)` — required field that accepts explicit `None` to clear the edit (≤10_000). `edited_source_text` optional (Phase 4 OCR correction, ≤10_000).
- `flag_to_dict` / `segment_to_dict` convert ORM objects to plain dicts; defensively read enum `.value`, isoformat timestamps, and use `getattr(..., None)` for Phase 4 OCR fields (confidence, region_bbox, region_label, edited_source_text). `Segment`/`SegmentFlag` imported under `TYPE_CHECKING` only.

## Dependencies
pydantic v2 (BaseModel, EmailStr, Field).
