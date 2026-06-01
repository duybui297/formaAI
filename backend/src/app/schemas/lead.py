"""Pydantic schemas for marketing lead capture (TASK-3.5)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    """Body for POST /leads."""

    email: EmailStr = Field(..., description="Contact email address")
    plan: str = Field(..., description="Plan the visitor expressed interest in (free/pro/business or any string)")


class LeadResponse(BaseModel):
    """Response for POST /leads — 201 Created."""

    id: str
    email: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}
