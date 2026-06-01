"""
Marketing lead capture — TASK-3.5.

POST /leads  — open (no auth); stores {email, plan} and returns 201.
Reachable as /api/leads via the Next.js proxy (proxy strips /api prefix).
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.db.models import Lead
from app.schemas.lead import LeadCreate, LeadResponse

log = structlog.get_logger()

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capture a marketing lead from the pricing page",
)
async def create_lead(
    body: LeadCreate,
    session: AsyncSession = Depends(get_session),
) -> LeadResponse:
    """Store a marketing lead and return the created row.

    - Open endpoint — no auth required (a visitor, not a logged-in user).
    - email validated as EmailStr by Pydantic → 422 on invalid format.
    - plan is a free string; no constraint beyond non-empty.
    """
    lead = Lead(
        id=str(uuid.uuid4()),
        email=str(body.email),
        plan=body.plan,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    log.info("lead_captured", lead_id=lead.id, plan=lead.plan)

    return LeadResponse(
        id=lead.id,
        email=lead.email,
        plan=lead.plan,
        created_at=lead.created_at,
    )
