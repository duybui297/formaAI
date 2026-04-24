"""
LLM client factory.

Create ONCE at arq worker startup; store in ctx["llm_client"].
max_retries=0: CORE-06 retry lives in translate_worker, not the SDK.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import Settings


def make_llm_client(settings: Settings) -> AsyncOpenAI:
    """
    Factory for the shared AsyncOpenAI client pointed at DashScope international.

    Key constraints (AI-SPEC §4):
    - base_url: intl endpoint — NOT the China endpoint (dashscope.aliyuncs.com)
    - max_retries=0: SDK-level retry is disabled; CORE-06 in worker owns retry logic
    - timeout=60.0: generous for long translation batches
    """
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=str(settings.dashscope_base_url),
        max_retries=0,
        timeout=60.0,
    )
