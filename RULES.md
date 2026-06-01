# Agent Execution Rules — License Management WBS

## Rule 0 — Session continuity (read first)
At the start of every session, **read [`SESSIONS.md`](./SESSIONS.md)** to recover prior context
(decisions, infra, demo accounts, open gaps). When meaningful work is done, **append** a new
`## Session N` block to the end of `SESSIONS.md` — never delete past entries. `CLAUDE.md` (auto-loaded)
points here too.

---


Binding rules for any AI agent working the backlog in [`FEATURELIST.md`](./FEATURELIST.md).
Status lives in [`PROGRESS.md`](./PROGRESS.md) and is **owned by `scripts/verify_task.py`** — not by you.

---

## Rule 1 — One feature active at a time
At most **one** task may be `IN_PROGRESS` across the whole backlog. Finish it (→ `DONE`) or park it (→ `BLOCKED`) before starting another. `scripts/verify_task.py start` refuses if another task is already active.

## Rule 2 — Dependency gate
Start a task only when **every** task in its `Depends on` list is `DONE`. The runner enforces this; do not bypass it.

## Rule 3 — Verification gates completion
A task becomes `DONE` **only** when its verification command exits `0`:
```
python3 scripts/verify_task.py verify TASK-<id>
```
This runs `verify/TASK-<id>.sh`, which must assert **every** Acceptance Criterion of the task. Exit `0` = all pass. Any non-zero exit = task stays `IN_PROGRESS`. There is no manual path to `DONE`.

## Rule 4 — Do NOT hand-edit status
Never edit by hand:
- the **Status / Started / Completed** cells in `PROGRESS.md`,
- the roll-up counts or changelog in `PROGRESS.md`,
- the `- [ ]` Acceptance Criteria checkboxes in `FEATURELIST.md`.

Only `scripts/verify_task.py` writes those. Editing them manually is a rule violation — the script is the single source of truth. You may freely edit task *descriptions/steps* (the spec), just not *state*.

## Rule 5 — Your loop
```
python3 scripts/verify_task.py next            # show next eligible task
python3 scripts/verify_task.py start TASK-x.y  # claim it (sets IN_PROGRESS + Started)
# ... implement the task's Implementation Steps ...
# ... write/extend verify/TASK-x.y.sh to assert each Acceptance Criterion ...
python3 scripts/verify_task.py verify TASK-x.y # gate: pass → DONE, fail → stays IN_PROGRESS
python3 scripts/verify_task.py status          # board + roll-up
```

## Rule 6 — Writing the verification script
- One file per task: `verify/TASK-<id>.sh`. The runner creates a failing stub on first `start` if absent.
- It must be **deterministic** and **self-checking**: run the real commands (migrations, unit/integration tests, lint, load test thresholds) and `exit 1` on any failure, `exit 0` only when all criteria hold.
- No `exit 0` shortcuts, no `|| true` masking, no commenting-out a failing check. A green verify must mean the feature genuinely works.
- Tests must be real (no stubbed assertions, no deleted cases to force green).

## Rule 7 — Blocked tasks
If you cannot proceed (missing secret, upstream bug, ambiguous spec): `python3 scripts/verify_task.py block TASK-x.y "<reason>"`. This frees the single-active slot. Resolve, then `start` again.

## Rule 8 — Honesty
Report failures with the real output. Never mark or describe a task as passing when its verify command did not exit `0`. If verify fails, the task is not done — say so.

## Rule 9 — `featurelist.json` is the behavior source; PROGRESS is a projection
`featurelist.json` holds one entry per **behavior** (`id, behavior, verification, state, evidence`). It is the granular source of truth.

When a feature's `verification` command finishes:
- exit `0` → that feature's `state` = `PASSING`, and its `evidence` is filled (date + command + output excerpt);
- non-zero → `state` = `FAILED`, `evidence` cleared.

Then the runner **re-derives** each affected task's `PROGRESS.md` state automatically (no hand edits):

| Task's features in `featurelist.json` | Task state in `PROGRESS.md` |
|----------------------------------------|------------------------------|
| **all** `PASSING` | `DONE` (Completed date set, FEATURELIST boxes ticked) |
| any `FAILED`, or some `PASSING` + some `TODO` (partial) | `IN_PROGRESS` |
| any `BLOCKED` (none in progress) | `BLOCKED` |
| all `TODO` | unchanged (`TODO`, or whatever `start`/`block` set) |

A task therefore reaches `DONE` only when **every** one of its behaviors is `PASSING`. Run `verify` (per feature or per task) — never edit `state`/`evidence` in either file by hand. `reconcile` re-projects without re-running.

---

### Quick reference
| Command | Effect |
|---------|--------|
| `verify_task.py next` | print next eligible task (deps DONE, none active) |
| `verify_task.py start TASK-x.y` | claim (enforces single-active + deps) → `IN_PROGRESS` |
| `verify_task.py verify <feature-id>` | run one behavior's `verification` (e.g. `2.2-a`) → PASSING/FAILED + evidence, then re-project task |
| `verify_task.py verify TASK-x.y` | run all behaviors of the task, then re-project: all PASSING → `DONE` |
| `verify_task.py verify all` | run every behavior, then re-project all tasks |
| `verify_task.py reconcile` | re-derive PROGRESS task states from `featurelist.json` (no re-run) |
| `verify_task.py block TASK-x.y "reason"` | → `BLOCKED`, frees the active slot |
| `verify_task.py status` | status board + roll-up |
