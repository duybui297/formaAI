#!/usr/bin/env python3
"""
Wave 0 empirical probe: does qwen-mt-turbo preserve HTML tags?

M4: Probes BOTH the pipeline path (translate_batch, with masking) AND the raw
model path (direct client.chat.completions.create) to separate pipeline masking
artifacts from raw model HTML fidelity.

Sends '<b>hello</b> world' en->vi. Writes BOTH verdicts to wave-0-html-probe.txt.
Usage: cd backend && uv run scripts/wave0_html_probe.py

Plan 03-04 chooses implementation based on PIPELINE_VERDICT (not RAW_VERDICT),
because translate_batch is what the actual pipeline calls.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

OUT_PATH = (
    Path(__file__).parent.parent.parent
    / ".planning/phases/03-pptx-native-pdf/wave-0-html-probe.txt"
)


def _has_html_tags(text: str) -> bool:
    return "<b>" in text and "</b>" in text


def _write(
    pipeline_verdict: str,
    raw_verdict: str,
    pipeline_sample: str = "",
    raw_sample: str = "",
) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        f"pipeline_verdict: {pipeline_verdict}\n"
        f"raw_verdict: {raw_verdict}\n"
        f"pipeline_sample: {pipeline_sample!r}\n"
        f"raw_sample: {raw_sample!r}\n"
        "input: '<b>hello</b> world'\n"
        "source_lang: en\n"
        "target_lang: vi\n"
        "\n"
        "# NOTE: Plan 03-04 implementation choice is based on pipeline_verdict.\n"
        "# PIPELINE path runs placeholder/token masking (translate_batch internals).\n"
        "# RAW path calls model directly with no masking — pure HTML fidelity test.\n"
        "# PIPELINE_PRESERVED  → use HTML directly in translate_batch calls.\n"
        "# PIPELINE_CORRUPTED  → wrap HTML tags in placeholder tokens before translate_batch.\n"
    )
    print(f"Written: {OUT_PATH}")


async def probe() -> None:
    from openai import AsyncOpenAI
    from app.llm.translator import translate_batch

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"')
                    break

    if not api_key:
        print("ERROR: DASHSCOPE_API_KEY not set")
        _write("ERROR: DASHSCOPE_API_KEY missing", "ERROR: DASHSCOPE_API_KEY missing")
        sys.exit(0)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

    payload = "<b>hello</b> world"
    print(f"Input: {payload!r}")

    # ---- PATH 1: Pipeline (translate_batch with masking) ----
    print("\n=== PATH 1: Pipeline (translate_batch) ===")
    pipeline_verdict = "PIPELINE_ERROR"
    pipeline_sample = ""
    try:
        results = await translate_batch(
            client=client,
            segments=[payload],
            source_lang="en",
            target_lang="vi",
        )
        pipeline_sample = results[0] if results else ""
        pipeline_verdict = (
            "PIPELINE_PRESERVED" if _has_html_tags(pipeline_sample)
            else "PIPELINE_CORRUPTED"
        )
        print(f"Output:  {pipeline_sample!r}")
        print(f"Verdict: {pipeline_verdict}")
    except Exception as exc:
        pipeline_verdict = f"PIPELINE_ERROR: {exc}"
        pipeline_sample = str(exc)
        print(f"Error: {exc}")

    # ---- PATH 2: Raw model (direct API call, no masking) ----
    print("\n=== PATH 2: Raw model (direct client.chat.completions) ===")
    raw_verdict = "RAW_ERROR"
    raw_sample = ""
    try:
        response = await client.chat.completions.create(
            model="qwen-mt-turbo",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Translate to Vietnamese, preserve HTML tags exactly: "
                        f"{payload}"
                    ),
                }
            ],
        )
        raw_sample = response.choices[0].message.content or ""
        raw_verdict = (
            "RAW_PRESERVED" if _has_html_tags(raw_sample) else "RAW_CORRUPTED"
        )
        print(f"Output:  {raw_sample!r}")
        print(f"Verdict: {raw_verdict}")
    except Exception as exc:
        raw_verdict = f"RAW_ERROR: {exc}"
        raw_sample = str(exc)
        print(f"Error: {exc}")

    print(f"\nFinal: pipeline={pipeline_verdict} | raw={raw_verdict}")
    _write(pipeline_verdict, raw_verdict, pipeline_sample, raw_sample)


if __name__ == "__main__":
    asyncio.run(probe())
