"""
Tests for run_post_check — all 4 flag detectors.

TDD RED: written before implementation.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.db.models import FlagSeverity, FlagType, Segment
from app.services.glossary_service import run_post_check


def _make_segment(seg_id: str, source_text: str, translated_text: str) -> MagicMock:
    """Build a mock Segment-like object for post_check tests."""
    seg = MagicMock(spec=Segment)
    seg.id = seg_id
    seg.source_text = source_text
    return seg


@pytest.mark.asyncio
async def test_run_post_check_overflow_flag(db_session):
    """Expansion ratio > threshold triggers overflow flag with severity=warn."""
    seg = _make_segment("s1", "ab", "a" * 20)  # ratio=10x >> 1.5 threshold
    translated_map = {"s1": "a" * 20}
    flags_added = []

    async def mock_execute(stmt):
        r = MagicMock()
        r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        return r

    # Use real db_session but intercept add_all to capture flags
    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={"vi->en": 1.5},
        job_id="test-job-id",
    )

    overflow_flags = [f for f in flags_added if f.flag_type == FlagType.overflow]
    assert len(overflow_flags) == 1
    assert overflow_flags[0].severity == FlagSeverity.warn
    assert overflow_flags[0].details["ratio"] > 1.5


@pytest.mark.asyncio
async def test_run_post_check_glossary_violation_flag(db_session):
    """Glossary term present in source but absent from translation triggers violation."""
    source = "Please review the mã nguồn carefully."
    translated = "Please review the program carefully."
    seg = _make_segment("s2", source, translated)
    translated_map = {"s2": translated}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    glossary = {"mã nguồn": "source code"}

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=glossary,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={},
        job_id="test-job-id",
    )

    viol_flags = [f for f in flags_added if f.flag_type == FlagType.glossary_violation]
    assert len(viol_flags) == 1
    assert viol_flags[0].severity == FlagSeverity.warn
    assert viol_flags[0].details["expected"] == "source code"


@pytest.mark.asyncio
async def test_run_post_check_glossary_no_violation_when_term_present(db_session):
    """No violation when glossary target term appears in translation."""
    source = "Hãy xem mã nguồn này."
    translated = "Please look at this source code."
    seg = _make_segment("s3", source, translated)
    translated_map = {"s3": translated}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary={"mã nguồn": "source code"},
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={},
        job_id="test-job-id",
    )

    viol_flags = [f for f in flags_added if f.flag_type == FlagType.glossary_violation]
    assert len(viol_flags) == 0


@pytest.mark.asyncio
async def test_run_post_check_glossary_no_violation_when_source_not_in_source(db_session):
    """No violation if source term doesn't appear in source text."""
    source = "This text has nothing relevant."
    translated = "This text has nothing relevant."
    seg = _make_segment("s4", source, translated)
    translated_map = {"s4": translated}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary={"mã nguồn": "source code"},
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={},
        job_id="test-job-id",
    )

    viol_flags = [f for f in flags_added if f.flag_type == FlagType.glossary_violation]
    assert len(viol_flags) == 0


@pytest.mark.asyncio
async def test_run_post_check_placeholder_mismatch_flag(db_session):
    """⟦T1⟧ in source but absent from translation triggers placeholder_mismatch."""
    source = "See ⟦T1⟧ for details."
    translated = "See the document for details."
    seg = _make_segment("s5", source, translated)
    translated_map = {"s5": translated}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={},
        job_id="test-job-id",
    )

    pm_flags = [f for f in flags_added if f.flag_type == FlagType.placeholder_mismatch]
    assert len(pm_flags) == 1
    assert pm_flags[0].severity == FlagSeverity.warn
    assert "⟦T1⟧" in pm_flags[0].details["missing_tokens"]


@pytest.mark.asyncio
async def test_run_post_check_placeholder_no_flag_when_preserved(db_session):
    """No placeholder_mismatch when ⟦T1⟧ present in both source and translation."""
    source = "Click ⟦T1⟧ to continue."
    translated = "Nhấn ⟦T1⟧ để tiếp tục."
    seg = _make_segment("s6", source, translated)
    translated_map = {"s6": translated}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={},
        job_id="test-job-id",
    )

    pm_flags = [f for f in flags_added if f.flag_type == FlagType.placeholder_mismatch]
    assert len(pm_flags) == 0


@pytest.mark.asyncio
async def test_run_post_check_llm_refusal_flag_long_source(db_session):
    """LLM refusal: source > 8 chars AND translated == source → flag."""
    text = "This is a long sentence that was not translated."
    seg = _make_segment("s7", text, text)
    translated_map = {"s7": text}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={},
        job_id="test-job-id",
    )

    refusal_flags = [f for f in flags_added if f.flag_type == FlagType.llm_refusal]
    assert len(refusal_flags) == 1
    assert refusal_flags[0].severity == FlagSeverity.warn


@pytest.mark.asyncio
async def test_run_post_check_llm_refusal_no_flag_short_strings(db_session):
    """LLM refusal: source ≤ 8 chars → NO flag (prevents false positives on 'AI', 'OK', 'v2')."""
    for short_text in ["AI", "OK", "v2", "HTTP"]:
        seg = _make_segment(f"s_{short_text}", short_text, short_text)
        flags_added = []

        original_add_all = db_session.add_all
        def capture_add_all(items):
            flags_added.extend(items)
            return original_add_all(items)
        db_session.add_all = capture_add_all

        await run_post_check(
            db_session,
            batch_segs=[seg],
            translated_map={f"s_{short_text}": short_text},
            glossary=None,
            source_lang="vi",
            target_lang="en",
            expansion_thresholds={},
            job_id="test-job-id",
        )

        refusal_flags = [f for f in flags_added if f.flag_type == FlagType.llm_refusal]
        assert len(refusal_flags) == 0, f"False positive on short text: {short_text!r}"


@pytest.mark.asyncio
async def test_run_post_check_glossary_skips_short_target_terms(db_session):
    """Glossary terms with target shorter than 2 chars are skipped (D-02-07)."""
    source = "The AI system processed it."
    translated = "The system processed it."
    seg = _make_segment("s8", source, translated)
    translated_map = {"s8": translated}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    # "AI" → "KI" — target term is 2 chars so it should still be checked
    # But "AI" → "a" (1 char) should be SKIPPED
    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary={"AI": "a"},  # 1-char target → skip
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
        job_id="test-job-id",
    )

    viol_flags = [f for f in flags_added if f.flag_type == FlagType.glossary_violation]
    assert len(viol_flags) == 0


@pytest.mark.asyncio
async def test_run_post_check_all_flags_severity_warn(db_session):
    """All Phase 2 flag types use FlagSeverity.warn (D-02-09)."""
    source = "⟦T1⟧ mã nguồn"
    # Missing placeholder + glossary violation + refusal impossible simultaneously
    # Test just that overflow flag uses warn
    seg = _make_segment("s9", "ab", "a" * 20)
    translated_map = {"s9": "a" * 20}
    flags_added = []

    original_add_all = db_session.add_all
    def capture_add_all(items):
        flags_added.extend(items)
        return original_add_all(items)
    db_session.add_all = capture_add_all

    await run_post_check(
        db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={"vi->en": 1.5},
        job_id="test-job-id",
    )

    for flag in flags_added:
        assert flag.severity == FlagSeverity.warn, f"Flag {flag.flag_type} has severity {flag.severity}"
