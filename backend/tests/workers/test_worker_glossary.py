"""Worker glossary injection tests — GLOS-03.

Stubs: will pass after Plan 04 wires glossary into translate_worker.py.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 worker extension", strict=False)
async def test_worker_loads_glossary_terms(mock_arq_ctx, db_session, make_glossary, make_glossary_term):
    """Worker calls translate_batch with glossary dict when job has glossary_id — GLOS-03."""
    g = await make_glossary()
    await make_glossary_term(g.id, source_term="AICore", target_term="AICore")
    # Verify translate_batch called with non-None glossary kwarg


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 worker extension", strict=False)
async def test_worker_passes_none_glossary_when_no_glossary(mock_arq_ctx, db_session):
    """Worker passes glossary=None when job has no glossary_id — GLOS-03."""
    # Verify translate_batch called with glossary=None
