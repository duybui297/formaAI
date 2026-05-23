from __future__ import annotations

from pydantic import BaseModel, Field


class CreateGlossaryRequest(BaseModel, frozen=True):
    name: str = Field(..., min_length=1, max_length=255)
    source_lang: str = Field(..., min_length=2, max_length=64)
    target_lang: str = Field(..., min_length=2, max_length=64)


class RenameGlossaryRequest(BaseModel, frozen=True):
    name: str = Field(..., min_length=1, max_length=255)


class CreateTermRequest(BaseModel, frozen=True):
    source_term: str = Field(..., min_length=2, max_length=500)
    target_term: str = Field(..., min_length=2, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class UpdateTermRequest(BaseModel, frozen=True):
    source_term: str | None = Field(default=None, min_length=2, max_length=500)
    target_term: str | None = Field(default=None, min_length=2, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
