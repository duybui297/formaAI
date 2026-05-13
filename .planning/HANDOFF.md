# Session Handoff — 2026-05-13

## TL;DR for next session

Phase 03.3 done. Stack-merged into `main` (commit `4073150`). Backup tag at
`main-backup-pre-phase-03.3-merge`.

**Next action:** run `/gsd-spec-phase 06` to scope the generic render-strategy
pipeline. Pre-written spec brief lives at
`.planning/phases/06-render-strategy-pipeline/06-SPEC-BRIEF.md` — feed it to
the discuss/spec phase as primer.

## Current state

| Item | Value |
|------|-------|
| Branch | `main` (HEAD `4073150`) |
| Last commit | `docs(phase-03): resolve UAT gaps after 03.1 gap closure` |
| Backup before merge | `main-backup-pre-phase-03.3-merge` (`ff26d87`) |
| Worker / API containers | running; restart needed only when new code lands |
| Web UI | http://localhost:8080 |
| Last UAT job | `b425150a-54b6-46c4-8b7e-190362608138` (ja→vi, accepted-with-defer) |
| Latest test jobs | `e1dcbbf1-...` (ja→en), `b425150a-...` (ja→vi) — both surfaced overflow + caption-near-image issues |

## What landed today (this session)

Stack of fixes culminating in `main`:

```
4073150 docs(phase-03): resolve UAT gaps after 03.1 gap closure (cherry-pick)
06ec4b0 docs(phase-03.3): close phase with deferred items captured
4ad0814 fix(pdf): multi-line scale geometry + pre-check image collision
518637b fix(pdf): reassembler pos_to_block uses same filter as extractor
a76c0e4 fix(pdf): filter non-table blocks by cell rects, not table bbox
7f47f5e fix(pdf): adaptive scale_low for text blocks too (not just table cells)
b68aac3 feat(pdf): identity-skip + adaptive scale_low for table cells
8201305 perf(llm): tune batch size to 10 + log mismatch payloads
44b6139 perf(llm): sentinel-batched translate_batch (50x call reduction)
7954e35 fix(pdf): index table cells by table.rows[r].cells[c]
```

Plus today's stacked merge brought in all phase-02 / phase-03 / phase-03.1 /
phase-03.2 / phase-04 work that had been on feature branches but never on
`main`. Net: `main` went from `ff26d87` (phase-1 only) to `4073150` (full
PoC + 03.3).

## Open issues — surfaced during UAT, NOT yet fixed

| Tag | Symptom | Status | Captured in |
|-----|---------|--------|-------------|
| D-1 | Figure caption adjacent to image not translated (image_collision pre-check preserves source) | Deferred, source-preserved (graceful) | `.planning/phases/03.3-native-pdf-table-cell-fidelity/03.3-DEFERRED.md` |
| D-2 | Text formatting (color, bold, italic, underline, font family) lost in translated PDF | Deferred | Same DEFERRED.md |
| D-3 | CJK→Latin 5–9× expansion overflows narrow table cells (450 cells in job e1dcbbf1) — PyMuPDF draws at scale_low floor, glyphs cramped/clipped | Open | Phase 06 brief below |
| D-4 | `llm_refusal` false-positive on filenames with `×` (U+00D7) | Cosmetic, defer | (no-op for output PDF) |
| D-5 | Image-baked speech bubbles on page 5 — invisible to PyMuPDF native extractor | Out of scope (needs OCR fallback for native PDFs) | (separate phase eventually) |

D-1, D-3 are the strongest drivers for Phase 06 (D-1 = caption strategy,
D-3 = generic shrink-fit strategy).

## What to do next session

**Step 1 (recommended) — run spec phase:**
```
/gsd-spec-phase 06
```
The spec-phase skill will read `06-SPEC-BRIEF.md` as the source-of-truth idea
and produce an ambiguity-scored `06-SPEC.md`. Then continue:

```
/gsd-discuss-phase 06
/gsd-plan-phase 06
/gsd-execute-phase 06
```

**Step 2 (alternative — skip planning, ship dry-run hotfix first):**
If user wants immediate value before the full phase 06 work, the
half-day patch is:
- Replace `_estimate_max_fitting_scale` in
  `backend/src/app/pipeline/pdf/reassembler.py` with a dry-run binary
  search using a scratch page copy + `page.insert_htmlbox(rect, html,
  scale_low=s, scale_high=s)` measurement loop over `[0.7, 0.5, 0.3,
  0.2, 0.15]`. Pick the first scale where `spare_height >= 0`.
- Returns ground-truth scale instead of heuristic; kills the 450
  overflow flags on next run for any doc type, not just this one.
- Cost: ~5 scratch renders × 1409 cells × 10ms ≈ 70s extra wallclock.
- Acceptable on a PoC; revisit if jobs slow noticeably.

Phase 06's full multi-strategy pipeline is the structural answer, but the
hotfix is harmless and could ship alongside.

## Repo state (working tree at handoff time)

```
modified:  .planning/STATE.md             (auto-updated by gsd-tools)
modified:  .planning/ROADMAP.md           (phase 03.3 marked complete)
modified:  .planning/REQUIREMENTS.md      (auto-updated)
untracked: .claude/scheduled_tasks.lock   (ignore)
untracked: .claude/worktrees/             (ignore)
untracked: .playwright-mcp/               (ignore)
untracked: backend/fonts/NotoSans*.ttf    (Docker bake-time files)
untracked: phase3-*.png                   (dev screenshots)
```

Nothing critical untracked. Run `git status` at session start to verify.

## Tooling notes

- `worker` + `api` containers will pick up new code via volume mount on
  `docker compose restart worker api`. Code changes do NOT require a rebuild.
- Web on `http://localhost:8080` (host 3000 was conflicting with a Windows
  process — `docker-compose.yml` remap is permanent now).
- DashScope batch size knob: `DASHSCOPE_BATCH_SIZE=10` in `.env` (default).
  Tune higher if you have a low-CJK source doc; tune lower if mismatch logs
  show >10%.

## Memory files (auto-loaded next session)

`~/.claude/projects/-home-thu-dev-projects-ai-translation/memory/` contains:
- `project_overview.md`
- `feedback_commit_scopes.md`
- `feedback_gsd_v140_commands.md`
- `project_qwen_mt_sentinel_rule.md`
- `project_pymupdf_table_cells_indexing.md`

All loaded automatically.
