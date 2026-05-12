"""
Spike 002 — Sentinel `|||` edge cases.

Builds on Spike 001 (`|||` chosen, 100% on baseline 5-cell rows). Now validate
four open risks before phase commitment:

  A. Content collision — what happens if a cell's text contains `|||`?
  B. Large-row stress — does `|||` count survive on 20-cell rows?
  C. Whitespace fidelity — leading/trailing spaces per cell preserved?
  D. Glossary interaction — does `terminology` API param coexist with `|||`?

Outputs:
- results.json (raw)
- console summary with per-experiment verdicts
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from openai import OpenAI

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
for line in ENV_PATH.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url=os.environ.get(
        "DASHSCOPE_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ),
)
MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen-mt-turbo")
SEP = "|||"


def translate(text: str, src: str, tgt: str, terms: list[dict] | None = None) -> str:
    opts = {"source_lang": src, "target_lang": tgt}
    if terms:
        opts["terms"] = terms
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": text}],
        extra_body={"translation_options": opts},
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


def exp_a_collision() -> dict:
    """A — cell content literally contains '|||'. Send raw, no escape."""
    cells = ["Year", "Range |||x|||", "Total"]  # middle cell has literal SEP
    text_in = SEP.join(cells)  # produces "Year|||Range |||x||||||Total"
    out = translate(text_in, "en", "vi")
    time.sleep(1.3)
    # Naive split: expect either 3 (good) or many (broken)
    parts = out.split(SEP)
    return {
        "exp": "A_collision_no_escape",
        "in": text_in,
        "out": out,
        "expected_parts": 3,
        "actual_parts": len(parts),
        "verdict": "CONFIRMED_COLLISION_HAZARD" if len(parts) != 3 else "TOLERATED",
    }


def exp_a_collision_escaped() -> dict:
    """A' — pre-escape literal '|||' in cell content to a numeric placeholder,
    then join with SEP. Restore after split."""
    cells = ["Year", "Range |||x|||", "Total"]
    PLACE = "⟦P0⟧"  # numeric-suffixed per Spike 001 rule
    # Escape literal SEP in each cell
    escaped = [c.replace(SEP, PLACE) for c in cells]
    text_in = SEP.join(escaped)
    out = translate(text_in, "en", "vi")
    time.sleep(1.3)
    parts = out.split(SEP)
    # Restore placeholders per cell
    restored = [p.replace(PLACE, SEP) for p in parts]
    return {
        "exp": "A_collision_with_escape",
        "in": text_in,
        "out": out,
        "expected_parts": 3,
        "actual_parts": len(parts),
        "restored_cells": restored,
        "placeholder_survived": all(PLACE in escaped_in == PLACE in p for escaped_in, p in zip(escaped, parts)),
        "verdict": "OK" if len(parts) == 3 else "FAIL",
    }


def exp_b_20_cells() -> dict:
    """B — 20-cell row, mixed short + long content, en->ja (most aggressive)."""
    cells = [f"Item{i}" for i in range(20)]
    text_in = SEP.join(cells)
    out = translate(text_in, "en", "ja")
    time.sleep(1.3)
    actual = out.count(SEP)
    return {
        "exp": "B_20_cells",
        "in_preview": text_in[:80] + "...",
        "out_preview": out[:80] + "...",
        "expected_count": 19,
        "actual_count": actual,
        "verdict": "OK" if actual == 19 else "FAIL",
    }


def exp_c_whitespace() -> dict:
    """C — leading/trailing/internal whitespace fidelity per cell."""
    cells = ["  Apple", "Orange ", "  Banana  ", "Grape"]
    text_in = SEP.join(cells)
    out = translate(text_in, "en", "vi")
    time.sleep(1.3)
    parts = out.split(SEP)
    # Capture per-cell whitespace
    ws_table = []
    for i, (orig, tr) in enumerate(zip(cells, parts)):
        ws_table.append({
            "i": i,
            "orig_repr": repr(orig),
            "trans_repr": repr(tr),
            "orig_leading": len(orig) - len(orig.lstrip()),
            "trans_leading": len(tr) - len(tr.lstrip()),
            "orig_trailing": len(orig) - len(orig.rstrip()),
            "trans_trailing": len(tr) - len(tr.rstrip()),
        })
    leading_preserved = sum(1 for r in ws_table if r["orig_leading"] == r["trans_leading"])
    trailing_preserved = sum(1 for r in ws_table if r["orig_trailing"] == r["trans_trailing"])
    return {
        "exp": "C_whitespace",
        "in": text_in,
        "out": out,
        "parts": parts,
        "table": ws_table,
        "leading_preserved": f"{leading_preserved}/{len(cells)}",
        "trailing_preserved": f"{trailing_preserved}/{len(cells)}",
        "verdict": "OK" if (leading_preserved == len(cells) and trailing_preserved == len(cells)) else "FRAGILE",
    }


def exp_d_glossary() -> dict:
    """D — glossary terminology + sentinel coexistence."""
    cells = ["Apple", "Orange", "Mango"]
    text_in = SEP.join(cells)
    # Force "Apple" -> "Táo Đỏ" via terminology
    terms = [{"source": "Apple", "target": "Táo Đỏ"}]
    out = translate(text_in, "en", "vi", terms=terms)
    time.sleep(1.3)
    parts = out.split(SEP)
    glossary_hit = "Táo Đỏ" in (parts[0] if parts else "")
    return {
        "exp": "D_glossary",
        "in": text_in,
        "out": out,
        "parts": parts,
        "expected_count": 2,
        "actual_count": out.count(SEP),
        "glossary_term_present": glossary_hit,
        "verdict": "OK" if (out.count(SEP) == 2 and glossary_hit) else "INVESTIGATE",
    }


def main() -> None:
    print(f"Model: {MODEL}\nSentinel: {SEP!r}\n")
    results = [
        exp_a_collision(),
        exp_a_collision_escaped(),
        exp_b_20_cells(),
        exp_c_whitespace(),
        exp_d_glossary(),
    ]
    Path(__file__).with_name("results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2)
    )
    print("=== Summary ===")
    for r in results:
        print(f"  [{r['verdict']:25s}] {r['exp']}")
    print("\nResults written to results.json")


if __name__ == "__main__":
    main()
