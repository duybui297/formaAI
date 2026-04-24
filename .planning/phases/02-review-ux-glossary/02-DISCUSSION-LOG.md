# Phase 2: Review UX + Glossary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 02-review-ux-glossary
**Areas discussed:** UI design skill, Glossary model & matching, Review editor + navigation, Edit persist + regenerate, Flag schema + LAYOUT scope, UPLD-04 glossary picker

---

## Gray area selection

**Question:** Which gray areas do you want to discuss for Phase 2 (Review UX + Glossary)?

| Option | Description | Selected |
|--------|-------------|----------|
| Glossary model & matching | DB schema, per-pair scoping, GLOS-04 match algorithm | ✓ |
| Review editor + navigation | Monaco DiffEditor vs alternatives, virtualization, navigation UX | ✓ |
| Edit persist + regenerate | Debounce, optimistic update, regenerate history | ✓ |
| Flag schema + LAYOUT scope | Flag storage, LAYOUT-02/03 Phase 2 vs Phase 3 boundary, threshold | ✓ |

**User's additional note:** "New UI that get from https://www.typeui.sh/design-skills (together with me to choose first)" — added a 5th area: UI design skill selection.

---

## UI design skill selection

### Initial shortlist (pre-filtered 4 of 12 featured typeui.sh skills)

| Option | Description | Selected |
|--------|-------------|----------|
| Clean (Recommended) | Stripped-down minimalism — best for dense review editor | |
| Refined | Polished, sophisticated — stronger demo wow factor | |
| Bento | Grid / modular sections — fits CRUD lists | |
| Neobrutalism | Bold structural design — memorable but possibly wrong for precision work | |

**User's response:** "anything else? How about shadcn or ant?"

### Expanded comparison — layering clarification

Clarified that typeui.sh skills are design-voice guides layered on top of component libraries (shadcn/Radix/Tailwind already installed in Phase 1), not replacements. Ant Design would mean rewriting every Phase 1 UI component.

| Option | Description | Selected |
|--------|-------------|----------|
| shadcn + typeui.sh skill (Recommended) | Keep Phase 1 shadcn components; layer a skill for design voice | |
| shadcn only, no skill | Stay with shadcn defaults; bespoke Tailwind per-component | |
| Swap to Ant Design | Rip out Radix+shadcn, install antd; 2-3 days rework | |
| Browse more typeui.sh skills | Show all 12 featured skills | |

**User's response:** "no i saw them on typeui.sh, check"

### Full registry enumeration

Confirmed via `bergside/awesome-design-skills` GitHub registry: 58 skills available including `ant` and `shadcn` as skill variants. Narrowed to 4 best-fit for Phase 2.

| Option | Description | Selected |
|--------|-------------|----------|
| shadcn (Recommended) | Codifies shadcn-idiomatic design tokens + patterns | |
| refined | Elegant, upscale aesthetic | |
| editorial | Type-driven, publication-inspired | |
| professional | Dense-data, enterprise-friendly | |

**User's response:** "how about paper? check"

### Paper skill deep-dive

Fetched `paper` SKILL.md: print/document-inspired minimalism, Roboto/Montserrat/PT Mono, semantic tokens, tight spacing rhythm, WCAG 2.2 AA.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — pull paper | Run `npx typeui.sh pull paper`, full font stack | |
| Yes — paper, swap fonts to Geist | Keep Phase 1 Geist | |
| Compare one more — show clean vs paper | Fetch clean SKILL.md for side-by-side | ✓ |
| Different skill | Paper doesn't fit | |

### Paper vs clean comparison

Side-by-side table compared: paper (black #111111 primary, Montserrat display, 4/8/12/16/24/32 spacing, print-feel) vs clean (blue #3B82F6 primary, Poppins display, 8pt grid, universal SaaS).

| Option | Description | Selected |
|--------|-------------|----------|
| paper (Recommended) | Distinctive 'document translation' identity + tighter review-editor density | ✓ |
| clean | Safer, familiar SaaS vibe | |
| paper, fonts swapped to Geist | Paper tokens but Geist fonts | |

**User's choice:** paper with full font stack.
**Notes:** Paper wins on narrative fit ("we translate documents") + review-editor density.

---

## Area 1: Glossary model & matching

### Round 1

**Q1: How to store glossary terms in Postgres?**

| Option | Description | Selected |
|--------|-------------|----------|
| Relational table (Recommended) | Separate `glossary_terms` table with FKs | |
| JSONB blob on glossary | Single JSONB column | |
| Hybrid — JSONB + materialized view | Hybrid pattern | ✓ (overridden below) |

**Q2: How to scope language pairs on glossaries?**

| Option | Description | Selected |
|--------|-------------|----------|
| Glossary = one lang pair (Recommended) | Each glossary scoped to one (source, target) pair | ✓ |
| Term-level lang pair | Glossary container; terms tag their own pair | |
| Pair-agnostic terms | Terms without lang tags | |

**Q3: GLOS-04 post-translation violation matching — which algorithm?**

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive substring (Recommended) | `target.lower() in translated.lower()` | |
| Unicode word-boundary regex | `\b{term}\b` with Unicode flag | |
| Exact substring (case-sensitive) | Literal match | |
| Token-aware with per-lang tokenizer | jieba / fugashi / underthesea | ✓ (overridden below) |

**User's notes:** On Q3 — "Can this defer to qwen-mt-turbo handle natively?"

### Round 2 — clarification + push-back

Claude pushed back on Q1 (hybrid = overkill for PoC) and clarified on Q3 (qwen-mt-turbo's `terminology` param injects terms at inference but doesn't guarantee presence; GLOS-04 is explicitly a post-check per REQUIREMENTS.md).

**Q1-v2: Downgrade to plain relational `glossary_terms` table?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — relational only (Recommended) | Standard two-table schema | |
| Keep hybrid JSONB + MV | Accept Alembic + refresh complexity | |

**User's notes:** "what does glossary_terms mean? in the future i want to replace qwen-mt-turbo to LLM like claude sonnet or gpt-5.5, etc."

**Q3-v2: GLOS-04 post-check algorithm (required — spec can't defer to LLM)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive substring (Recommended) | Substring check with min length 2 | |
| Unicode word-boundary regex | `\b{term}\b` with Unicode flag | |
| Exact case-sensitive substring | Literal match | |
| Token-aware per-lang | jieba + fugashi + underthesea | ✓ (overridden again) |

### Round 3 — final

Explained relational `glossary_terms` schema in plain English + LLM-swap portability narrative (what stays the same, what needs an adapter). Pushed back on token-aware (tokenization isn't what post-check needs — substring presence is).

**Q1-v3: Go with plain relational `glossaries` + `glossary_terms` tables?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — relational (Recommended) | Two-table schema as diagrammed | ✓ |
| Single table with JSONB terms column | One row holds JSONB terms | |

**Q3-v3: Post-check match algorithm (given LLM-swap intent)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive substring (Recommended) | Substring + min length 2 | ✓ |
| Case-insensitive substring + word-boundary for EN/VN | Hybrid per-lang | |
| Token-aware per-lang tokenizers | jieba / fugashi / underthesea | |

**Final Area 1 decisions:** relational tables; pair-scoped glossaries; case-insensitive substring with min length 2.

---

## Area 2: Review editor + navigation

**Q1: Review UI layout — which pattern?**

| Option | Description | Selected |
|--------|-------------|----------|
| Segment table / CAT-tool list (Recommended) | Each segment = one row in shadcn Table | ✓ |
| Two-pane Monaco (synced scroll) | Two Monaco instances side by side | |
| Monaco DiffEditor (as originally sketched) | Single DiffEditor — semantically wrong for translation | |
| Textarea grid with optional Monaco per-row | Table by default, expand to Monaco on click | |

**Q2: How to handle long documents (500+ segments)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Virtualize with react-virtuoso (Recommended) | Variable-height row virtualization | ✓ |
| Paginate — 50 segments per page | Server or client paging | |
| Render all, no virtualization | Map over segments | |

**Q3: Primary navigation mode for finding flagged segments?**

| Option | Description | Selected |
|--------|-------------|----------|
| Filter bar + keyboard shortcuts (Recommended) | Top filter chips + j/k/n/e/r shortcuts | ✓ |
| Left sidebar segment list | Fixed-width column with flag dots | |
| Flag panel floating over content | Collapsible VS Code Problems-style panel | |

**Final Area 2 decisions:** CAT-tool segment table + react-virtuoso + filter chips + keyboard shortcuts.

---

## Area 3: Edit persist + regenerate

**Q1: REV-02 debounce interval for edit persistence?**

| Option | Description | Selected |
|--------|-------------|----------|
| 500ms (Recommended) | Instant feel, safe window | ✓ |
| 1000ms | Half the traffic, small data-loss risk | |
| 2000ms | Fewer writes, higher data-loss window | |
| onBlur only (no debounce) | Persist on focus-leave | |

**Q2: Optimistic vs pessimistic update on segment edit?**

| Option | Description | Selected |
|--------|-------------|----------|
| Optimistic via TanStack Query (Recommended) | Update cache immediately, rollback on error | ✓ |
| Pessimistic — wait for server | Textarea shows saving indicator | |
| Hybrid: optimistic text, pessimistic flag re-compute | Text optimistic; flags wait for server | |

**Q3: REV-04 single-segment regenerate — keep history or overwrite?**

| Option | Description | Selected |
|--------|-------------|----------|
| Overwrite `translated_text`, keep `edited_text` untouched (Recommended) | Export: `edited_text ?? translated_text` | ✓ |
| Overwrite both | Regenerate wipes user edits | |
| Full history of regenerations | `segment_translations` table with N versions | |
| Keep one prior version for undo | `translated_text_prev` column + undo button | |

**Final Area 3 decisions:** 500ms debounce; optimistic TanStack updates; regenerate preserves `edited_text`.

---

## Area 4: Flag schema + LAYOUT scope

**Q1: How to persist REV-03 segment flags?**

| Option | Description | Selected |
|--------|-------------|----------|
| Denormalized boolean columns (Recommended) | `has_overflow`, `has_glossary_violation`, etc. + `flag_details JSONB` | |
| JSONB flags column only | Single `flags JSONB` | |
| Separate `segment_flags` table | One row per flag per segment | ✓ |

**Q2: LAYOUT-02/03 format-specific detectors — Phase 2 or Phase 3?**

| Option | Description | Selected |
|--------|-------------|----------|
| Defer LAYOUT-02/03 to Phase 3 (Recommended) | Move to Phase 3 with format parsers | ✓ |
| Phase 2 wires the interface, Phase 3 implements detectors | Protocol + DOCX trivial-case | |
| Keep per spec — Phase 2 does everything | Implement PPTX + PDF detectors now | |

**Q3: LAYOUT-01 expansion-ratio threshold config?**

| Option | Description | Selected |
|--------|-------------|----------|
| Global env constant (Recommended) | Single `EXPANSION_RATIO_THRESHOLD` env var | |
| Per-language-pair map in settings | `{"en->vi": 1.3, "vi->ja": 0.9, ...}` JSON env | ✓ |
| Per-job user-settable | User picks threshold at job submit time | |

**Final Area 4 decisions:** separate `segment_flags` table (user overrode recommendation for extensibility); LAYOUT-02/03 deferred to Phase 3; per-language-pair threshold map.

---

## Area 5: UPLD-04 glossary picker

**Q1: Single glossary per job or multi-select?**

| Option | Description | Selected |
|--------|-------------|----------|
| Single-select (Recommended) | Dropdown: None + matching glossaries | ✓ |
| Multi-select | Union with last-write-wins conflicts | |

**Q2: How to filter picker by job's language pair?**

| Option | Description | Selected |
|--------|-------------|----------|
| Filter picker to matching-pair glossaries only (Recommended) | Only show matching-pair glossaries; empty state if none | ✓ |
| Show all, grey-out mismatched | All visible, non-matching disabled | |
| Show all, backend rejects on submit | 422 on pair mismatch | |

**Q3: Can glossary change after job submit?**

| Option | Description | Selected |
|--------|-------------|----------|
| Lock at submit (Recommended) | `Job.glossary_id` immutable; new job for new glossary | ✓ |
| Mutable — changes affect pending batches | Swap glossary mid-job | |
| Mutable with full-rerun | Glossary change triggers full retranslate | |

**Final Area 5 decisions:** single-select; filter to matching pair only; lock at submit.

---

## Claude's Discretion

- CSV column order + header variants accepted for GLOS-02 import
- TBX support depth (full TBX-Core subset vs minimal term-pair extraction)
- `segment_flags.severity` default (likely `warn` for all Phase 2 flag types)
- Keyboard shortcut help panel style
- Filter bar chip layout + counts rendering
- Advisory-lock implementation for export (pg advisory lock vs in-memory per-worker)
- Optimistic rollback toast copy
- Glossary table row density + bulk-delete UX
- Paper skill font loading strategy (next/font self-host vs Google Fonts CDN)
- Whether to rework Phase 1 screens to paper tokens in Phase 2 or defer to a polish pass

## Deferred Ideas

- Phase 3: LAYOUT-02 (PPTX/PDF overflow detectors), LAYOUT-03 (PPTX auto-fit, PDF font scaling)
- v2: Multi-select glossaries, translation memory, segment-version history, per-job expansion threshold, token-aware tokenizers, collaborative review, full TBX-v3, soft-delete audit trail
- Out-of-scope (PROJECT.md): per-segment LLM streaming, multi-tenant auth, rate-limit tiers / billing
- Follow-ups: REQUIREMENTS.md + ROADMAP.md edit moving LAYOUT-02/03 traceability Phase 2 → Phase 3; CLAUDE.md §Frontend note about CAT-table choice over Monaco
