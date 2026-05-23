<!--
Fill Summary + Linked Issue + Test plan tối thiểu.
Các section conditional (Eval / Security) chỉ bắt buộc khi PR touch model
code hoặc security surface — bỏ qua nếu không áp dụng.
Tham khảo: docs/onboarding/workflow.md
-->

## Summary

<!-- 1-3 câu mô tả WHAT + WHY. Đừng mô tả HOW (đã ở trong diff). -->

## Linked Issue / Spec

<!-- Closes #...  hoặc  Spec: specs/NNN-<slug>/spec.md  hoặc  N/A (1-line fix) -->

## Type

- [ ] 1-line fix / chore (skip phần lớn checklist dưới)
- [ ] Bug fix / small feature
- [ ] Spec-driven feature (full `/speckit.*` flow)

## Constitution compliance

Tick các principle PR này có touch (xem `.specify/memory/constitution.md`):

- [ ] **I — Format Fidelity**: touch `pipeline/` → no layout regression trên hero formats
- [ ] **II — Eval-Driven**: touch prompt/batching/OCR → eval delta dưới đây
- [ ] **III — Native Tool**: thay tech choice locked-in → ADR mới/superseding
- [ ] **IV — Security**: input → LLM, secrets, paths, shell → security note dưới đây
- [ ] PR title theo Conventional Commits

<!-- Nếu không tick gì (vd. chore/docs) → ghi "N/A" và bỏ qua 2 section dưới. -->

## Eval delta — *only if Principle II ticked*

<!--
Metric:    e.g. glossary_adherence | bleu | overflow_flag_rate
Baseline:  e.g. 0.873
After:     e.g. 0.891  (+0.018)
Eval cmd:  make eval  hoặc  pytest backend/tests/eval/<file>::<test>
-->

## Security note — *only if Principle IV ticked*

<!--
(a) Input source       — vd. "user-uploaded DOCX content"
(b) Sanitization       — vd. "ext + magic bytes; content escaped before prompt"
(c) Trust boundary     — vd. "nginx → FastAPI → LLM"
(d) Failure mode       — vd. "if injection succeeds, max impact = leak glossary"

Hoặc paste output của /security-review skill.
-->

## Test plan

- [ ] Tests / lint / typecheck pass (`make test-unit && make lint && make typecheck`)
- [ ] Frontend tests pass nếu touch FE (`cd frontend && npm test`)
- [ ] Manual smoke: <mô tả bước reproduce + expected>

## Docs updated (tick nếu áp dụng)

- [ ] `docs/decisions/00NN-*.md` (ADR mới hoặc updated)
- [ ] `CLAUDE.md`
- [ ] `docs/STATE.md`
- [ ] `.specify/memory/constitution.md` (chỉ amendment hiếm)

## Notes for reviewer

<!-- Optional: gotchas, follow-ups, things reviewer cần biết. -->
