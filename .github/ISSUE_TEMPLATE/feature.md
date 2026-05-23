---
name: Feature request / Spec request
about: Đề xuất feature hoặc behaviour mới. Có thể seed cho /speckit.specify.
title: "feat(<scope>): <short summary>"
labels: ["type:feature", "needs-triage"]
assignees: []
---

## Problem / Motivation

<!-- WHY: vấn đề người dùng / use case gì cần giải. Tránh prescribe solution ở đây. -->

## Proposed behaviour

<!-- WHAT (high-level): user-visible behaviour sau khi feature ship. Không chi tiết tech. -->

## Acceptance criteria

<!-- Cách verify feature done. Mỗi gạch đầu dòng là 1 observable behaviour. -->

- [ ]
- [ ]
- [ ]

## Constraints / Non-goals

<!-- Cái gì rõ ràng NẰM NGOÀI scope. Tránh re-litigate sau. -->

-
-

## Constitution principles impact

<!-- Tick nếu áp dụng. Block work nếu vi phạm Principle I (Format Fidelity). -->

- [ ] Touch hero formats (DOCX / native PDF / PPTX) → cần layout-regression check
- [ ] Touch model code (prompt / batching / OCR post-proc) → cần eval delta
- [ ] Touch user input → LLM surface → cần /security-review
- [ ] Thay đổi tech choice locked-in → cần ADR mới

## Related

<!-- Link tới ADR, REQ ID (REQUIREMENTS.md), phase, hoặc Issue khác. -->

- REQ: <REQ-ID>
- ADR: docs/decisions/<file>
- Phase: docs/ROADMAP.md (phase #)
