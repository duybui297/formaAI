---
name: Bug report
about: Report 1 bug có thể reproduce.
title: "fix(<scope>): <short summary>"
labels: ["type:bug", "needs-triage"]
assignees: []
---

## Symptom

<!-- What's wrong, observable from outside. 1-2 sentences. -->

## Reproduce steps

<!-- Tối thiểu các bước để 1 dev khác trigger được bug. -->

1.
2.
3.

## Expected vs Actual

| | Expected | Actual |
|---|---|---|
| Behaviour | | |
| HTTP status / output | | |
| Log message | | |

## Environment

| | Value |
|---|---|
| Branch / commit | |
| Local / staging / prod | |
| Browser (nếu UI bug) | |
| OS | |
| Docker compose file | `docker-compose.yml` / `docker-compose.prod.yml` |

## Logs / Traceback

<!-- Paste relevant logs. Redact secrets. Trim đến đoạn quan trọng. -->

```
<logs here>
```

## Job ID (nếu liên quan 1 translation job)

```
<uuid>
```

Inputs / output / segments trong `.data/jobs/<uuid>/` — share nếu cần (cẩn thận PII).

## Hypothesis (optional)

<!-- Nếu bạn có dự đoán root cause. -->

## Impact

- [ ] Blocker (prod down)
- [ ] High (feature unusable)
- [ ] Medium (workaround tồn tại)
- [ ] Low (cosmetic)

## Related

- Linked Issues / PRs:
- Open-issues table trong `docs/STATE.md` (tag mới? D-N)
