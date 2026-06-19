"""
Pydantic schemas for auth endpoints.
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # US-1.1: strong password = ≥8 chars + 1 number + 1 uppercase
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool = False
    avatar_url: str | None = None


class UpdateMeRequest(BaseModel):
    full_name: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class AvatarResponse(BaseModel):
    avatar_url: str


class MessageResponse(BaseModel):
    message: str


class NotificationPreferencesResponse(BaseModel):
    email_job_complete: bool = True
    email_job_failed: bool = True
    email_license_expiry: bool = True
    email_license_revoked: bool = False
    email_marketing: bool = False


class UpdateNotificationPreferencesRequest(BaseModel):
    email_job_complete: bool | None = None
    email_job_failed: bool | None = None
    email_license_expiry: bool | None = None
    email_license_revoked: bool | None = None
    email_marketing: bool | None = None


class TranslationDefaultsResponse(BaseModel):
    preferred_source_lang: str | None = None
    preferred_target_lang: str | None = None
    default_glossary_id: str | None = None
    auto_detect: bool = False


class UpdateTranslationDefaultsRequest(BaseModel):
    preferred_source_lang: str | None = None
    preferred_target_lang: str | None = None
    default_glossary_id: str | None = None
    auto_detect: bool | None = None


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime
    raw_key: str  # Only returned ONCE at creation time


# ---------------------------------------------------------------------------
# Team Workspace
# ---------------------------------------------------------------------------


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class MemberResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    joined_at: datetime


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    created_at: datetime
    expires_at: datetime


class WorkspaceResponse(BaseModel):
    members: list[MemberResponse]
    pending_invites: list[InviteResponse]
