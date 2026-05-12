"""
Spike 001 — Table row sentinel-delimiter survival across qwen-mt-turbo.

Question: Can a row of N table cells be packed into ONE translation call by
joining cells with a sentinel string, and have qwen-mt-turbo preserve the
sentinel count + position in the output?

If YES → Option A (row-level segments) is feasible. ~10x fewer segments for
table-heavy PDFs (1381 cells → ~150 rows on job 7f958166).

If NO → fall back to Option B (HTML table) or Option C (header-row + per-row
with smarter detection).

Sentinel candidates (priority order — most-likely-safe first):
  ⟦CELL⟧   — uses the same ⟦⟧ bracket family as CORE-05 placeholder masking
            (already proven qwen-safe in production)
  |||      — ASCII triple-pipe, common table delimiter, but model may
            normalize to single | or remove
  <CELL>   — XML-ish tag, may be stripped by model
  \\t       — literal tab character; risk of whitespace collapse

Run: uv run python run_spike.py
Output: results.json + console summary
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

# Load .env
ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
for line in ENV_PATH.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ["DASHSCOPE_API_KEY"]
BASE_URL = os.environ.get(
    "DASHSCOPE_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)
MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen-mt-turbo")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def translate(text: str, src: str, tgt: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": text}],
        extra_body={"translation_options": {"source_lang": src, "target_lang": tgt}},
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


# Test rows mimic real PDF table content
CASES = [
    # (lang_pair, label, cells)
    (("en", "vi"), "header_row", ["Year", "Revenue", "Growth"]),
    (("en", "vi"), "data_row_numeric", ["2023", "100M", "15%"]),
    (("en", "vi"), "data_row_short", ["N/A", "Pending", "—"]),
    (("ja", "vi"), "ja_header", ["商品名", "価格", "在庫数"]),
    (("ja", "vi"), "ja_data", ["りんご", "150円", "20個"]),
    (("vi", "en"), "vi_header", ["Sản phẩm", "Giá", "Số lượng"]),
    (("en", "ja"), "en_to_ja_5cell", ["Apple", "Orange", "Banana", "Grape", "Mango"]),
    (("zh", "vi"), "zh_short", ["年份", "金额"]),
]

SENTINELS = ["⟦CELL⟧", "|||", "<CELL>", "\t"]


def run_one(sentinel: str) -> dict:
    rows = []
    survived = 0
    for (src, tgt), label, cells in CASES:
        text_in = sentinel.join(cells)
        expected = len(cells) - 1  # N cells → N-1 sentinels
        try:
            text_out = translate(text_in, src, tgt)
        except Exception as exc:  # noqa: BLE001
            rows.append({
                "label": label, "src": src, "tgt": tgt,
                "in": text_in, "out": None, "err": str(exc),
                "expected_count": expected, "actual_count": -1,
                "survived": False,
            })
            continue
        actual = text_out.count(sentinel)
        ok = actual == expected
        if ok:
            survived += 1
        rows.append({
            "label": label, "src": src, "tgt": tgt,
            "in": text_in, "out": text_out,
            "expected_count": expected, "actual_count": actual,
            "survived": ok,
        })
        time.sleep(1.3)  # respect free-tier RPM
    return {
        "sentinel": sentinel,
        "survived_rows": survived,
        "total_rows": len(CASES),
        "survival_rate": survived / len(CASES),
        "rows": rows,
    }


def main() -> int:
    print(f"Model: {MODEL}")
    print(f"Cases: {len(CASES)} rows × {len(SENTINELS)} sentinels = {len(CASES) * len(SENTINELS)} calls")
    print(f"Est duration: ~{len(CASES) * len(SENTINELS) * 1.5}s\n")

    all_results = []
    for sentinel in SENTINELS:
        print(f"=== Testing sentinel: {sentinel!r} ===")
        result = run_one(sentinel)
        all_results.append(result)
        print(f"  survival: {result['survived_rows']}/{result['total_rows']} "
              f"({result['survival_rate']:.0%})\n")

    out_path = Path(__file__).parent / "results.json"
    out_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")

    # Verdict
    print("\n=== VERDICT ===")
    best = max(all_results, key=lambda r: r["survival_rate"])
    print(f"Best sentinel: {best['sentinel']!r} — {best['survival_rate']:.0%} survival")
    if best["survival_rate"] >= 0.95:
        print("GREEN — Option A feasible with this sentinel.")
    elif best["survival_rate"] >= 0.7:
        print("YELLOW — feasible with guard rails (fallback per-cell on parse failure).")
    else:
        print("RED — sentinel approach not viable; recommend Option B (HTML table) or C.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
