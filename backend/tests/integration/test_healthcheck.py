"""Integration tests: INFRA-01 + INFRA-02 — DashScope endpoint + terminology.

Requires DASHSCOPE_API_KEY environment variable. Tests skip automatically when key
is not set — safe to run in CI without the key.

Security note (T-01-11-02): API responses are asserted on shape/content only.
Raw API response text is never printed to avoid accidental information disclosure.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def dashscope_settings():
    """Load settings; skip if DASHSCOPE_API_KEY not set."""
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        pytest.skip("DASHSCOPE_API_KEY not set — skipping DashScope integration tests")
    # W10: import from app.XXX not backend.src.app.XXX
    from app.core.config import Settings

    return Settings(
        dashscope_api_key=key,
        database_url="postgresql+asyncpg://placeholder:placeholder@localhost:5432/placeholder",
    )


@pytest.fixture(scope="function")
def llm_client(dashscope_settings):
    """Function-scoped: AsyncOpenAI's underlying httpx transport binds to the
    event loop it's created in, and pytest-asyncio creates a fresh loop per
    test. A module-scoped client from a stale loop triggers APIConnectionError
    on subsequent tests. One client per test is ~30ms overhead, worth the
    determinism.
    """
    from app.llm.client import make_llm_client

    return make_llm_client(settings=dashscope_settings)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashscope_reachable_and_translates(llm_client) -> None:
    """INFRA-01: qwen-mt-turbo responds to a 1-sentence VN->EN probe."""
    from app.llm.translator import translate_batch

    result = await translate_batch(
        client=llm_client,
        segments=["Xin chào thế giới"],
        source_lang="vi",
        target_lang="en",
    )
    assert len(result) == 1, "CORE-03: must return 1 translation for 1 input"
    assert len(result[0]) > 0, "translation must not be empty"
    assert any(
        word in result[0].lower() for word in ["hello", "hi", "greetings", "world"]
    ), (
        f"Expected VN->EN translation of 'Xin chào thế giới' to contain "
        f"hello/world; got: {result[0]!r}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_terminology_respected_vn_en(llm_client) -> None:
    """INFRA-02: terminology param causes qwen-mt-turbo to use the provided term."""
    from app.llm.translator import translate_batch

    glossary = {"AICore": "AICore"}  # force brand name preservation VN->EN
    result = await translate_batch(
        client=llm_client,
        segments=["Đây là sản phẩm của AICore dành cho thị trường Việt Nam."],
        source_lang="vi",
        target_lang="en",
        glossary=glossary,
    )
    assert len(result) == 1
    assert "AICore" in result[0], (
        f"Expected 'AICore' to be preserved via terminology param; got: {result[0]!r}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_terminology_respected_ja_en(llm_client) -> None:
    """INFRA-02: terminology param works on JA->EN pair too."""
    from app.llm.translator import translate_batch

    glossary = {"AICore": "AICore"}
    result = await translate_batch(
        client=llm_client,
        segments=["AICore はベトナムのAI企業です。"],
        source_lang="ja",
        target_lang="en",
        glossary=glossary,
    )
    assert len(result) == 1
    assert "AICore" in result[0], (
        f"Expected 'AICore' to be preserved in JA->EN translation; got: {result[0]!r}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_detect_source_language(llm_client) -> None:
    """INFRA-01 / D-16: auto source lang detection works."""
    from app.llm.translator import translate_batch

    result = await translate_batch(
        client=llm_client,
        segments=["日本語のテスト文章です。"],
        source_lang="auto",
        target_lang="en",
    )
    assert len(result) == 1
    assert len(result[0]) > 0, "auto-detected translation must not be empty"
