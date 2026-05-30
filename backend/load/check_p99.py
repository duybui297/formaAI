"""
TASK-4.2-d: P99 latency checker for Locust CSV output.

Usage:
    uv run python load/check_p99.py load/out_stats.csv <threshold_ms>

Parses the Locust `_stats.csv` output, finds the aggregated row
(Name == "Aggregated"), reads the 99th-percentile response time column,
and exits 0 if P99 < threshold_ms, or 1 with a clear message if not.

Locust _stats.csv columns (locust >= 2.x):
    Type, Name, Request Count, Failure Count, Median Response Time,
    Average Response Time, Min Response Time, Max Response Time,
    Average Content Size, Requests/s, Failures/s,
    50%, 66%, 75%, 80%, 90%, 95%, 98%, 99%, 99.9%, 99.99%, 100%

The P99 column header is "99%".
"""
from __future__ import annotations

import csv
import sys


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: python check_p99.py <stats_csv_path> <threshold_ms>",
            file=sys.stderr,
        )
        sys.exit(2)

    csv_path = sys.argv[1]
    try:
        threshold_ms = float(sys.argv[2])
    except ValueError:
        print(
            f"ERROR: threshold_ms must be a number, got {sys.argv[2]!r}",
            file=sys.stderr,
        )
        sys.exit(2)

    # -----------------------------------------------------------------------
    # Parse CSV
    # -----------------------------------------------------------------------
    try:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
    except FileNotFoundError:
        print(
            f"ERROR: CSV file not found: {csv_path!r}\n"
            "Make sure locust ran with --csv load/out and the file exists.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not rows:
        print(f"ERROR: CSV file is empty: {csv_path!r}", file=sys.stderr)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Find Aggregated row — locust writes it as Name == "Aggregated"
    # -----------------------------------------------------------------------
    aggregated = next(
        (r for r in rows if r.get("Name", "").strip().lower() == "aggregated"),
        None,
    )
    if aggregated is None:
        # Fall back: use the last row (locust always appends Aggregated last)
        aggregated = rows[-1]
        print(
            f"WARNING: No 'Aggregated' row found by name; using last row: "
            f"Name={aggregated.get('Name')!r}",
            file=sys.stderr,
        )

    # -----------------------------------------------------------------------
    # Extract P99 column
    # -----------------------------------------------------------------------
    # Locust column header is "99%" (with the percent sign)
    p99_raw = aggregated.get("99%") or aggregated.get("99")
    if p99_raw is None:
        # Print available columns to help diagnose
        print(
            f"ERROR: P99 column ('99%') not found in CSV.\n"
            f"Available columns: {list(aggregated.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        p99_ms = float(p99_raw)
    except (ValueError, TypeError):
        print(
            f"ERROR: Could not parse P99 value {p99_raw!r} as a number.",
            file=sys.stderr,
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Compare and exit
    # -----------------------------------------------------------------------
    total_requests = aggregated.get("Request Count", "?")
    failure_count = aggregated.get("Failure Count", "?")
    rps = aggregated.get("Requests/s", "?")

    print(
        f"Load test summary: "
        f"requests={total_requests}, failures={failure_count}, "
        f"rps={rps}, P99={p99_ms}ms, threshold={threshold_ms}ms"
    )

    if p99_ms < threshold_ms:
        print(f"PASS: P99 {p99_ms}ms < {threshold_ms}ms threshold")
        sys.exit(0)
    else:
        print(
            f"FAIL: P99 {p99_ms}ms >= {threshold_ms}ms threshold. "
            f"Response times exceed the SLA — investigate DB/Redis latency or "
            f"concurrency bottlenecks.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
