#!/usr/bin/env python3
"""Task-state machine for the License Management WBS.

Single source of truth for task STATUS. Agents must NOT hand-edit status in
PROGRESS.md or the checkboxes in FEATURELIST.md — this script owns them.

Commands:
    next                      print next eligible task (deps DONE, none active)
    start  TASK-x.y           claim a task -> IN_PROGRESS (enforces single-active + deps)
    verify <feature-id>       run one behavior's verification (e.g. 2.2-a) in featurelist.json
    verify TASK-x.y           run all behaviors of a task, then re-project PROGRESS
    verify all                run every behavior, then re-project all tasks
    reconcile                 re-derive PROGRESS task states from featurelist.json (no re-run)
    block  TASK-x.y "reason"  -> BLOCKED (frees the single-active slot)
    status                    print board + roll-up

featurelist.json (behavior-level: id/behavior/verification/state/evidence) is the source of
truth. PROGRESS task state is PROJECTED from it (Rule 9): a task is DONE only when ALL its
behaviors are PASSING. Rules enforced: 1 active task max; dependency gate; verification-gated.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_JSON = os.path.join(ROOT, "scripts", "tasks.json")
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
FEATURELIST = os.path.join(ROOT, "FEATURELIST.md")
FEATURES_JSON = os.path.join(ROOT, "featurelist.json")

VALID = {"TODO", "IN_PROGRESS", "BLOCKED", "DONE"}


def today() -> str:
    return datetime.date.today().isoformat()


def load_tasks() -> dict:
    with open(TASKS_JSON) as f:
        data = json.load(f)
    return {t["id"]: t for t in data["tasks"]}


def short(task_id: str) -> str:
    """TASK-1.1 -> 1.1 (the key used in the PROGRESS.md board)."""
    return task_id.replace("TASK-", "")


def read(path: str) -> str:
    with open(path) as f:
        return f.read()


def write(path: str, text: str) -> None:
    with open(path, "w") as f:
        f.write(text)


# --- PROGRESS.md board parsing -------------------------------------------------
# Row shape: | 1.1 | Name | Layer | Priority | Depends on | Status | Started | Completed | Notes |
ROW_RE = re.compile(r"^\|\s*([0-9]+\.[0-9]+)\s*\|")


def split_cells(line: str) -> list[str]:
    parts = line.split("|")
    return parts  # parts[0] and parts[-1] are the outer empties


def board_status(text: str) -> dict[str, str]:
    """Map short-id -> current Status from the board."""
    out = {}
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if m:
            cells = split_cells(line)
            out[m.group(1).strip()] = cells[6].strip()
    return out


def set_row(text: str, sid: str, *, status=None, started=None, completed=None, note=None) -> str:
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = ROW_RE.match(line)
        if not m or m.group(1).strip() != sid:
            continue
        nl = "\n" if line.endswith("\n") else ""
        cells = line.rstrip("\n").split("|")
        # cells: [ '', ' 1.1 ', name, layer, prio, depends, status, started, completed, notes, '' ]
        if status is not None:
            cells[6] = f" {status} "
        if started is not None:
            cells[7] = f" {started} "
        if completed is not None:
            cells[8] = f" {completed} "
        if note is not None:
            cells[9] = f" {note} "
        lines[i] = "|".join(cells) + nl
        return "".join(lines)
    raise SystemExit(f"Row for {sid} not found in PROGRESS.md")


def update_rollup(text: str) -> str:
    tasks = load_tasks()
    st = board_status(text)
    done = [k for k, v in st.items() if v == "DONE"]
    inprog = sum(1 for v in st.values() if v == "IN_PROGRESS")
    blocked = sum(1 for v in st.values() if v == "BLOCKED")
    total = len(tasks)
    days_total = sum(t["days"] for t in tasks.values())
    days_done = sum(tasks[f"TASK-{k}"]["days"] for k in done if f"TASK-{k}" in tasks)
    days_left = days_total - days_done

    def repl(label, value):
        # Anchor to line start so a roll-up metric label (e.g. "IN_PROGRESS")
        # never matches a board row's Status cell of the same name.
        nonlocal text
        text = re.sub(
            rf"^(\|\s*{re.escape(label)}\s*\|)[^|]*(\|)",
            rf"\1 {value} \2",
            text,
            flags=re.MULTILINE,
        )

    repl("DONE", f"{len(done)} / {total}")
    repl("IN_PROGRESS", str(inprog))
    repl("BLOCKED", str(blocked))
    repl("Est. days remaining", str(days_left))
    return text


def append_changelog(text: str, line: str) -> str:
    placeholder = "- _(empty — no tasks started yet)_"
    entry = f"- {line}"
    if placeholder in text:
        return text.replace(placeholder, entry)
    # append after the "## Changelog" comment block, at end of file
    return text.rstrip() + "\n" + entry + "\n"


# --- FEATURELIST.md checkbox ticking ------------------------------------------
def tick_boxes(task_id: str, check: bool = True) -> None:
    text = read(FEATURELIST)
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"### {task_id} "):
            start = i
            break
    if start is None:
        return
    frm, to = ("- [ ]", "- [x]") if check else ("- [x]", "- [ ]")
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("### ") or lines[j].startswith("## "):
            break
        lines[j] = lines[j].replace(frm, to)
    write(FEATURELIST, "".join(lines))


# --- featurelist.json (behavior-level source of truth) ------------------------
def load_features() -> dict:
    with open(FEATURES_JSON) as f:
        return json.load(f)


def save_features(doc: dict) -> None:
    with open(FEATURES_JSON, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")


def run_feature_verification(feat: dict) -> bool:
    """Run a feature's `verification` shell command. exit 0 => PASSING."""
    cmd = feat["verification"]
    print(f"  [{feat['id']}] {cmd}")
    proc = subprocess.run(cmd, shell=True, cwd=ROOT,
                          capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip().splitlines()
    excerpt = "\n".join(out[-8:]) if out else ""
    if proc.returncode == 0:
        feat["state"] = "PASSING"
        feat["evidence"] = {
            "date": today(),
            "command": cmd,
            "output_excerpt": excerpt,
            "artifact": None,
        }
        print(f"    -> PASSING")
        return True
    feat["state"] = "FAILED"
    feat["evidence"] = None
    print(f"    -> FAILED (exit {proc.returncode})")
    if excerpt:
        print("    " + excerpt.replace("\n", "\n    "))
    return False


def derive_task_state(states: list[str], current: str) -> str:
    """Project a task's PROGRESS state from its features' states (Rule 9)."""
    s = set(states)
    if states and s == {"PASSING"}:
        return "DONE"
    if "FAILED" in s:
        return "IN_PROGRESS"
    if "PASSING" in s:               # partial progress
        return "IN_PROGRESS"
    if "BLOCKED" in s and "IN_PROGRESS" not in s:
        return "BLOCKED"
    # all TODO -> keep whatever start/block set (don't downgrade)
    return current if current in ("IN_PROGRESS", "BLOCKED") else "TODO"


def reconcile(task_ids: list[str] | None = None, *, verbose: bool = True) -> None:
    """Re-derive PROGRESS task states from featurelist.json."""
    doc = load_features()
    by_task: dict[str, list[str]] = {}
    for feat in doc["features"]:
        by_task.setdefault(feat["task"], []).append(feat["state"])

    text = read(PROGRESS)
    cur = board_status(text)
    targets = task_ids or list(by_task)
    changed = []
    for tid in targets:
        sid = short(tid)
        new = derive_task_state(by_task.get(tid, []), cur.get(sid, "TODO"))
        if new == cur.get(sid):
            continue
        kw = {"status": new}
        if new == "DONE":
            kw.update(completed=today(), note="all behaviors PASSING")
        text = set_row(text, sid, **kw)
        text = append_changelog(text, f"{today()}  {tid}  {cur.get(sid)}→{new}  reconciled from featurelist.json")
        changed.append((tid, cur.get(sid), new))
        if new == "DONE":
            tick_boxes(tid, check=True)

    text = update_rollup(text)
    write(PROGRESS, text)
    if verbose:
        if changed:
            for tid, old, new in changed:
                print(f"  PROGRESS: {tid} {old} -> {new}")
        else:
            print("  PROGRESS already in sync.")


# --- state transitions --------------------------------------------------------
def active_task(st: dict[str, str]) -> str | None:
    for sid, status in st.items():
        if status == "IN_PROGRESS":
            return sid
    return None


def require_known(task_id: str, tasks: dict) -> None:
    if task_id not in tasks:
        raise SystemExit(f"Unknown task '{task_id}'. Known: {', '.join(tasks)}")


def cmd_next() -> None:
    tasks = load_tasks()
    st = board_status(read(PROGRESS))
    if active_task(st):
        print(f"A task is already IN_PROGRESS (TASK-{active_task(st)}). Finish or block it first (Rule 1).")
        return
    for tid, t in tasks.items():
        sid = short(tid)
        if st.get(sid) != "TODO":
            continue
        if all(st.get(short(d)) == "DONE" for d in t["deps"]):
            deps = ", ".join(t["deps"]) or "—"
            print(f"NEXT: {tid} — {t['name']}  (deps: {deps})")
            return
    print("No eligible TODO task (all done, blocked, or deps unmet).")


def cmd_start(task_id: str) -> None:
    tasks = load_tasks()
    require_known(task_id, tasks)
    text = read(PROGRESS)
    st = board_status(text)
    sid = short(task_id)

    cur = st.get(sid)
    if cur == "DONE":
        raise SystemExit(f"{task_id} is already DONE.")
    busy = active_task(st)
    if busy and busy != sid:
        raise SystemExit(f"Rule 1 violation: TASK-{busy} is IN_PROGRESS. Only one active task allowed.")
    unmet = [d for d in tasks[task_id]["deps"] if st.get(short(d)) != "DONE"]
    if unmet:
        raise SystemExit(f"Rule 2 violation: unmet deps {unmet}. Finish them first.")

    text = set_row(text, sid, status="IN_PROGRESS", started=today())
    text = update_rollup(text)
    text = append_changelog(text, f"{today()}  {task_id}  {cur}→IN_PROGRESS  started")
    write(PROGRESS, text)
    n = sum(1 for f in load_features()["features"] if f["task"] == task_id)
    print(f"{task_id} → IN_PROGRESS (started {today()}). {n} behaviors to verify in featurelist.json.")


def cmd_verify(arg: str) -> None:
    """Verify a single feature (e.g. 2.2-a), all features of a task (TASK-2.2),
    or everything ('all'). Updates featurelist.json then re-projects PROGRESS."""
    doc = load_features()
    feats = doc["features"]

    if arg == "all":
        targets = feats
    elif arg.startswith("TASK-"):
        targets = [f for f in feats if f["task"] == arg]
        if not targets:
            raise SystemExit(f"No features for {arg} in featurelist.json")
    else:
        targets = [f for f in feats if f["id"] == arg]
        if not targets:
            raise SystemExit(f"Unknown feature id '{arg}'. Use a feature id (2.2-a), TASK-x.y, or 'all'.")

    affected = sorted({f["task"] for f in targets})
    print(f"Verifying {len(targets)} behavior(s) across {len(affected)} task(s)\n" + "-" * 60)
    passed = sum(run_feature_verification(f) for f in targets)
    print("-" * 60)
    save_features(doc)
    print(f"featurelist.json: {passed}/{len(targets)} PASSING, {len(targets) - passed} FAILED.")

    print("Re-projecting PROGRESS (Rule 9):")
    reconcile(affected)

    if passed != len(targets):
        sys.exit(1)


def cmd_reconcile() -> None:
    print("Re-projecting PROGRESS task states from featurelist.json (Rule 9):")
    reconcile()


def cmd_block(task_id: str, reason: str) -> None:
    tasks = load_tasks()
    require_known(task_id, tasks)
    text = read(PROGRESS)
    sid = short(task_id)
    text = set_row(text, sid, status="BLOCKED", note=reason.replace("|", "/"))
    text = update_rollup(text)
    text = append_changelog(text, f"{today()}  {task_id}  →BLOCKED  {reason}")
    write(PROGRESS, text)
    print(f"{task_id} → BLOCKED: {reason}")


def cmd_status() -> None:
    tasks = load_tasks()
    st = board_status(read(PROGRESS))
    width = max(len(t["name"]) for t in tasks.values())
    for tid, t in tasks.items():
        sid = short(tid)
        print(f"  {tid:<9} {t['name']:<{width}}  {st.get(sid, '?')}")
    done = sum(1 for v in st.values() if v == "DONE")
    print(f"\n  DONE {done}/{len(tasks)} | IN_PROGRESS {sum(v=='IN_PROGRESS' for v in st.values())}"
          f" | BLOCKED {sum(v=='BLOCKED' for v in st.values())}")
    busy = active_task(st)
    if busy:
        print(f"  active: TASK-{busy}")


def main(argv: list[str]) -> None:
    if not argv:
        print(__doc__)
        return
    cmd, *rest = argv
    if cmd == "next":
        cmd_next()
    elif cmd == "start":
        cmd_start(rest[0])
    elif cmd == "verify":
        cmd_verify(rest[0])
    elif cmd == "reconcile":
        cmd_reconcile()
    elif cmd == "block":
        cmd_block(rest[0], rest[1] if len(rest) > 1 else "blocked")
    elif cmd == "status":
        cmd_status()
    else:
        raise SystemExit(f"Unknown command '{cmd}'. See: next | start | verify | reconcile | block | status")


if __name__ == "__main__":
    main(sys.argv[1:])
