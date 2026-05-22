# Workflow — Spec-Kit + PR + Commit Rules

> Project dùng **Spec-Kit** (GitHub) làm spec-driven development framework.
> Mỗi dev chọn AI agent của mình (Claude / Cursor / Copilot / ...) — workflow
> giống nhau, chỉ khác slash command interface.

## TL;DR — 3 mức task

| Task size | Workflow |
|---|---|
| **1-line fix** (typo, comment, version bump) | Branch + PR. Không cần SPEC. |
| **Small feature / bug fix** (< 1 ngày) | Issue → branch → PR (PR body = mini-SPEC). |
| **Phase / feature lớn** (>1 ngày, nhiều file, model code) | Full Spec-Kit flow (xem dưới). |

## 1. Spec-Kit setup (1 lần per máy)

### Install CLI (global)

```bash
# Latest tag: https://github.com/github/spec-kit/releases
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<TAG>

# Verify
specify --version
```

### Init agent integration (per-repo, per-dev)

```bash
cd ai-translation

# Chọn 1 trong các integration sau:
specify init . --here --integration claude    --ignore-agent-tools
specify init . --here --integration cursor    --ignore-agent-tools
specify init . --here --integration copilot   --ignore-agent-tools
specify init . --here --integration codex     --ignore-agent-tools
specify init . --here --integration gemini    --ignore-agent-tools
# ...
specify integration list                       # xem full list (30+ agents)
```

Init sẽ:
- Tạo `.specify/` (1 lần) với templates + scripts + memory.
- Cài slash commands vào folder của agent bạn chọn (vd. `.claude/skills/speckit-*`, `.cursor/...`).

⚠️ **Mỗi dev chỉ commit init output của 1 agent ưu tiên**. Nếu bạn dùng Cursor mà repo đang ship `.claude/skills/speckit-*`, init cho Cursor và **chỉ commit** `.cursor/...` artifacts; KHÔNG xóa `.claude/skills/speckit-*` của người khác.

### UTF-8 fix cho Windows

Lần đầu chạy `specify init` trên Windows có thể crash `UnicodeEncodeError`. Fix:

```powershell
[Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
# Restart shell, hoặc set inline:
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null
```

## 2. Full Spec-Kit flow (for big features)

```
/speckit.constitution    # chỉ khi muốn amend constitution (rất hiếm)
                         #
/speckit.specify         # WHAT — bạn describe feature, agent ghi spec.md
                         #
/speckit.clarify         # de-risk underspecified areas (recommended)
                         # agent hỏi từng câu, bạn trả lời, spec.md update
                         #
/speckit.plan            # HOW — tech approach, file structure, edge cases
                         # output: plan.md
                         #
/speckit.tasks           # break plan → tasks.md (checklist)
                         #
/speckit.taskstoissues   # optional — push tasks → GitHub Issues
                         #
/speckit.analyze         # cross-artifact consistency check
                         # (constitution ↔ spec ↔ plan ↔ tasks)
                         #
/speckit.implement       # execute tasks one by one
                         #
/speckit.checklist       # (sau implement, trước merge) — quality gates
```

Output sống trong `specs/NNN-<slug>/{spec,plan,tasks,checklist}.md`. Commit tất cả vào branch.

### Khi nào skip step nào?

- **`/speckit.clarify`** — skip nếu spec đã rõ ràng (vd. bug fix với reproduce steps cụ thể).
- **`/speckit.analyze`** — skip cho task < 3 file changes.
- **`/speckit.checklist`** — skip nếu PR template đã cover gate cần thiết.
- **`/speckit.taskstoissues`** — skip nếu team không track granular tasks trên GitHub.

## 3. Branching

```
main                              # protected — chỉ merge qua PR
├── feature/<slug>                # feature/spec-06-render-strategy
├── fix/<slug>                    # fix/cors-env-driven
├── docs/<slug>                   # docs/onboarding-vn
├── chore/<slug>                  # chore/bump-fastapi-016
└── spike/<slug>                  # spike/qwen-mt-plus-quality (throwaway)
```

Spike branches: code throwaway, không merge vào `main`. Verdict + insights vào ADR hoặc commit message rồi `git branch -D`.

## 4. Commit conventions (Conventional Commits)

```
<type>(<scope>): <imperative summary, lowercase, no period>

[optional body explaining why]

[optional footer: BREAKING CHANGE, Closes #123, Refs ADR-0008]
```

**Types** (đã dùng trong repo):

| Type | Khi nào dùng |
|---|---|
| `feat` | Feature mới user-facing |
| `fix` | Bug fix |
| `docs` | Chỉ docs / comments |
| `chore` | Maintenance (deps, config, build) |
| `refactor` | Code change không thay behavior |
| `perf` | Performance improvement |
| `test` | Thêm/sửa test |
| `spec` | Spec / planning artifacts (specs/, .specify/) |

**Scopes** (đã dùng):
`api`, `worker`, `llm`, `pdf`, `docx`, `pptx`, `ocr`, `db`, `infra`, `web`, `review`, `glossary`, `phase-NN`, `state`.

**Ví dụ**:
```
feat(pdf): adaptive scale_low for table cells
fix(api): make CORS allowed origins env-configurable
perf(llm): sentinel-batched translate_batch (50x call reduction)
docs(phase-06): capture phase context
spec(phase-06): add SPEC.md for render-strategy-pipeline
chore(workflow): migrate GSD → Spec-Kit
```

## 5. PR template

`.github/PULL_REQUEST_TEMPLATE.md` đã có gate checkboxes (sẽ viết ở task #9). Mỗi PR bắt buộc:

```markdown
## Summary
<1-3 dòng nói WHAT + WHY>

## Linked Issue / Spec
- Closes #XXX  hoặc
- Spec: specs/NNN-<slug>/spec.md

## Gate checklist
- [ ] Constitution principles tuân thủ (đặc biệt II nếu touch prompt)
- [ ] Eval delta documented (nếu thay đổi prompt / batching / OCR post-proc)
- [ ] Security review note (nếu input → LLM, secrets, file path, shell)
- [ ] Tests added / updated cho deterministic code
- [ ] No layout regression trên hero formats (nếu touch pipeline/)
- [ ] CLAUDE.md / constitution / ADR updated nếu locked-in choice đổi
- [ ] PR title theo Conventional Commits

## Test plan
- [ ] make test-unit
- [ ] make lint && make typecheck
- [ ] Smoke test manual: <mô tả>
```

## 6. Eval-Driven rule (Principle II)

**Không đổi prompt thiếu eval delta.** Là quy tắc số 1 cho model code.

### Eval loop

```python
# backend/tests/eval/test_<area>.py
@pytest.mark.eval
def test_qwen_vn_to_en_glossary_adherence():
    # 1. Load fixture (set input + expected glossary terms applied)
    cases = load_fixture("vn_en_glossary_cases.json")
    # 2. Call translator
    scores = []
    for c in cases:
        out = translate(c.input, glossary=c.terms)
        scores.append(glossary_adherence_score(out, c.terms))
    avg = mean(scores)
    # 3. Assert against baseline
    assert avg >= 0.85, f"Glossary adherence regressed: {avg:.3f}"
```

### Flow khi thay đổi prompt

```
1. Identify metric → adherence | BLEU | format-fidelity | overflow-flag rate
2. Run baseline: make eval → record number
3. Change prompt
4. Run eval again
5. Compare; document delta in PR description:
     Baseline: 0.873
     After:    0.891   (+0.018)
6. Commit chỉ khi metric ≥ baseline (hoặc trade-off documented + approved)
```

PR reviewer block nếu thiếu eval delta.

## 7. Security review gate (Principle IV)

Mandatory cho PR nào:
- Thêm user input pathway vào prompt (upload, paste, URL).
- Touch auth, secrets, file paths, shell execution.
- Include user data trong LLM call.

Process:
1. Trong Claude Code: `/security-review` slash command (built-in skill).
2. Agent scan changes → output threat model + mitigations.
3. Paste vào PR description dưới section **Security review**.
4. Reviewer verify.

Nếu không dùng Claude Code: viết tay 1 paragraph trong PR — liệt kê (a) input source, (b) sanitization, (c) trust boundary, (d) failure mode.

## 8. Code review

| Reviewer responsibility | Author responsibility |
|---|---|
| Verify constitution compliance | Tick đủ gate checklist |
| Check tests cover happy + error path | Viết test trước khi push |
| Read ADR nếu locked-in choice đổi | Update / add ADR khi đổi |
| Run smoke test (cho UI / pipeline PR) | Cung cấp test plan trong PR body |
| Block nếu thiếu eval delta (Principle II) | Document eval delta inline |

Một maintainer approve = merge. Nếu PR > 500 lines diff, request 2 approvals.

## 9. Multi-agent practical notes

- **Skills folder ownership**: `.claude/skills/`, `.cursor/skills/`, `.github/skills/` — đừng xóa folder của agent khác trong PR của bạn.
- **`CLAUDE.md` vs agent-specific config**: `CLAUDE.md` là source-of-truth chung cho mọi AI agent (spec-kit reads it). Đừng tạo `CURSOR.md` riêng — copy/extend `CLAUDE.md` trong workflow của agent đó nếu cần.
- **Spec-kit constitution loaded by all agents**: `.specify/memory/constitution.md` đọc tự động bởi mọi `/speckit.*` command, regardless of agent. Đó là true cross-agent source-of-truth.

## 10. Khi nào skip workflow

- Hot-fix prod incident — fix trên branch, mở PR ngay, retro sau.
- 1-line typo / comment fix — PR ngắn, không cần SPEC / eval.
- Bumping dep version (passive) — chore commit, không cần SPEC.

Còn lại: theo flow. Discipline > velocity với PoC này (xem `.planning/ARCHIVED.md` để thấy tại sao GSD heavy + không scale).

## Tiếp theo

→ [deploy.md](deploy.md) — production deployment (đọc khi cần / sau probation).
