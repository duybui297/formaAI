"""
Admin user management routes — TASK-3.6.

GET    /admin/users              — paginated list (excludes soft-deleted), admin-only
POST   /admin/users              — create user, admin-only
PATCH  /admin/users/{id}         — update full_name / is_active / is_superuser, admin-only
DELETE /admin/users/{id}         — soft-delete (sets deleted_at + is_active=False), admin-only

Guards:
  - Admin cannot deactivate or demote their own account.
  - Admin cannot delete their own account.
  - Last remaining active admin cannot be demoted, deactivated, or deleted.

Soft-deleted email reuse policy:
  A soft-deleted email is still considered taken → POST with that email returns 409.
  Rationale: avoids ghost-data collisions on UUIDs held by other tables (jobs, glossaries).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.models import User
from app.db.session import get_session

log = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin-users"])


# ---------------------------------------------------------------------------
# Pydantic schemas (kept local — no shared schema file for user admin yet)
# ---------------------------------------------------------------------------

class UserItem(BaseModel):
    """User representation in list + detail responses (no password)."""
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserItem]
    total: int
    page: int
    page_size: int


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    password: str = Field(..., min_length=8)
    is_superuser: bool = False
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            raise ValueError("full_name cannot be blank")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _count_active_admins(session: AsyncSession) -> int:
    """Return number of active, non-deleted superusers."""
    result = await session.execute(
        select(func.count()).where(
            User.is_superuser.is_(True),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one()


async def _get_user_or_404(session: AsyncSession, user_id: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id!r} not found",
        )
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List users with pagination and filters (admin only)",
)
async def list_users(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        default=None,
        description="Substring search on email OR full_name",
    ),
    role: Optional[str] = Query(
        default=None,
        description="Filter by role: admin (is_superuser=True) or user (is_superuser=False)",
    ),
    active: Optional[bool] = Query(
        default=None,
        description="Filter by is_active: true or false",
    ),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserListResponse:
    """Paginated list of users, excluding soft-deleted rows.

    Filters: search (email OR full_name substring), role (admin/user), active (bool).
    """
    if role is not None and role not in ("admin", "user"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role must be 'admin' or 'user'",
        )

    base_q = select(User).where(User.deleted_at.is_(None))

    if search:
        pattern = f"%{search}%"
        base_q = base_q.where(
            or_(
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
            )
        )

    if role == "admin":
        base_q = base_q.where(User.is_superuser.is_(True))
    elif role == "user":
        base_q = base_q.where(User.is_superuser.is_(False))

    if active is not None:
        base_q = base_q.where(User.is_active.is_(active))

    # Count
    count_q = select(func.count()).select_from(base_q.subquery())
    total: int = (await session.execute(count_q)).scalar_one()

    # Page
    offset = (page - 1) * page_size
    rows_result = await session.execute(
        base_q.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    users = rows_result.scalars().all()

    return UserListResponse(
        users=[UserItem.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/users",
    response_model=UserItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin only)",
)
async def create_user(
    body: CreateUserRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserItem:
    """Create a user account.

    Soft-deleted email reuse: a soft-deleted email is still considered taken → 409.
    This prevents orphaned FK rows (jobs, glossaries) from colliding with a new user.
    """
    # Check for existing email (including soft-deleted rows)
    existing = await session.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        is_superuser=body.is_superuser,
        is_active=body.is_active,
        email_verified=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    log.info("admin_user_created", actor_id=current_user.id, new_user_id=user.id, email=user.email)

    return UserItem.model_validate(user)


@router.patch(
    "/users/{user_id}",
    response_model=UserItem,
    status_code=status.HTTP_200_OK,
    summary="Update a user's full_name, is_active, or is_superuser (admin only)",
)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserItem:
    """Partial update for full_name / is_active / is_superuser.

    Guards:
    - Cannot deactivate own account.
    - Cannot demote own account (is_superuser → False).
    - Cannot deactivate or demote the last remaining active admin.
    """
    user = await _get_user_or_404(session, user_id)

    # --- Self-guard ---
    is_self = user_id == current_user.id
    if is_self:
        if body.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account",
            )
        if body.is_superuser is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot demote your own admin account",
            )

    # --- Last-admin guard ---
    # Check if this operation would remove the last active admin.
    # We only need to guard if the target user IS currently an active admin.
    if user.is_superuser and user.is_active and user.deleted_at is None:
        active_admin_count = await _count_active_admins(session)
        if active_admin_count <= 1:
            if body.is_superuser is False:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot demote the last remaining admin account",
                )
            if body.is_active is False:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot deactivate the last remaining admin account",
                )

    # Apply updates
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_superuser is not None:
        user.is_superuser = body.is_superuser

    await session.commit()
    await session.refresh(user)

    log.info(
        "admin_user_updated",
        actor_id=current_user.id,
        target_user_id=user.id,
        changes=body.model_dump(exclude_none=True),
    )

    return UserItem.model_validate(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Soft-delete a user (admin only)",
)
async def soft_delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft-delete: sets deleted_at=now() and is_active=False.

    The user disappears from GET /admin/users and can no longer authenticate.

    Guards:
    - Cannot delete own account.
    - Cannot delete the last remaining active admin.
    """
    user = await _get_user_or_404(session, user_id)

    # Already soft-deleted — idempotent, return 204
    if user.deleted_at is not None:
        return

    # --- Self-guard ---
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    # --- Last-admin guard ---
    if user.is_superuser and user.is_active:
        active_admin_count = await _count_active_admins(session)
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete the last remaining admin account",
            )

    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False

    await session.commit()

    log.info("admin_user_soft_deleted", actor_id=current_user.id, target_user_id=user.id)
