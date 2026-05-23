---
name: Spike (throwaway research)
about: Time-boxed exploration để answer 1 câu hỏi tech. Code throwaway.
title: "spike(<scope>): <question>"
labels: ["type:spike", "needs-triage"]
assignees: []
---

## Question

<!-- 1 question only. Nếu có 2+, mở 2+ spikes. -->

## Why this question matters

<!-- Decision nào sẽ unblock sau spike. Ai consume kết quả. -->

## Hypothesis

<!-- Bạn dự đoán câu trả lời ra sao trước khi chạy spike. Sai cũng OK. -->

## Time-box

- Estimate: <e.g. 1 ngày, 4h>
- Hard stop: <date / commit count>

## Method

<!-- High-level approach: dataset, baseline, metric. Nếu spike là benchmark giữa 2 lib, list cụ thể. -->

- Setup:
- Inputs:
- Metric:
- Comparison:

## Acceptance criteria (cho spike done)

- [ ] Câu hỏi có answer rõ ràng (yes/no/numbers) ⇒ write verdict
- [ ] Verdict captured trong: Issue comment HOẶC ADR mới HOẶC commit message
- [ ] Spike branch deleted (`git branch -D spike/<slug>`)

## Out of scope

- Không ship spike code vào main
- Không refactor codebase
- Không thêm doc unless verdict needs codification (ADR)

## Related ADR / SPEC sẽ refer kết quả

<!-- Nếu spike inform a future ADR / Phase SPEC, link ở đây. -->
