# Onboarding — AI Translation PoC

Chào mừng. Doc này là entry point để bạn join dự án nhanh nhất có thể.

## Đọc gì trước

Theo thứ tự:

1. **[../PROJECT.md](../PROJECT.md)** — 5 phút. Hiểu *cái gì* + *tại sao*.
2. **[../STATE.md](../STATE.md)** — 3 phút. Project đang ở đâu, ai làm gì.
3. **[setup.md](setup.md)** — 1 giờ. Clone + chạy local.
4. **[architecture.md](architecture.md)** — 30 phút. Codebase tour.
5. **[workflow.md](workflow.md)** — 20 phút. Spec-Kit + PR + commit rules.
6. **[deploy.md](deploy.md)** — đọc khi cần (sau probation).

Tham khảo sâu hơn:
- **[../../CLAUDE.md](../../CLAUDE.md)** — tech stack chi tiết, do/don't list.
- **[../decisions/README.md](../decisions/README.md)** — 10 quyết định
  kiến trúc (qwen-mt-turbo, arq, PyMuPDF, ...) — đọc khi gặp câu hỏi
  "tại sao chọn X".
- **[../../.specify/memory/constitution.md](../../.specify/memory/constitution.md)**
  — 5 nguyên tắc không thương lượng.

## Checklist Day 1

```
[ ] Clone repo, đọc PROJECT.md + STATE.md
[ ] Tạo DashScope international API key (setup.md §2)
[ ] Tạo .env từ .env.example, fill DASHSCOPE_API_KEY
[ ] docker compose up --build → chờ ~5 phút (PaddleOCR bake)
[ ] docker compose exec api alembic upgrade head
[ ] Mở http://localhost:8080 → upload 1 file DOCX sample → kiểm tra
    translated DOCX download được
[ ] Cài AI agent của bạn (Claude Code | Cursor | Copilot | Codex | ...)
[ ] specify init . --here --integration <agent_của_bạn>  (xem workflow.md)
[ ] Đọc lướt architecture.md → biết code chính ở đâu
```

## Checklist Week 1

```
[ ] Đọc 10 ADR trong docs/decisions/ — không cần thuộc, biết nó ở đâu
[ ] Đọc 1-2 phase summary trong .planning/phases/ để hiểu lịch sử
    (Phase 1 + Phase 2 là 2 nền tảng quan trọng nhất)
[ ] Pick 1 task nhỏ từ GitHub Issues hoặc xin maintainer giao
[ ] Chạy thử full Spec-Kit flow trên task đó:
      /speckit.specify → /speckit.clarify → /speckit.plan
      → /speckit.tasks → /speckit.implement
[ ] Mở PR đầu tiên — tick đủ checkboxes trong PR template
[ ] Pair-review với maintainer
```

## Pre-first-PR checklist

Trước khi mở PR đầu tiên, đảm bảo:

- [ ] Đã đọc `constitution.md` — hiểu 5 nguyên tắc, đặc biệt
      **Principle II (Eval-Driven for Model Code)** nếu PR touch prompt
      hoặc translation logic
- [ ] Có Linked Issue hoặc Spec
- [ ] Test pass: `make test-unit` (backend), `npm test` (frontend)
- [ ] Lint pass: `make lint`, `make typecheck` (backend)
- [ ] Nếu sửa prompt → có **eval delta** documented
- [ ] Nếu sửa surface có user input → đã chạy security-review hoặc note
      trong PR description tại sao không cần
- [ ] Commit message theo Conventional Commits (xem workflow.md)

## Hỏi ở đâu

| Loại câu hỏi | Channel |
|---|---|
| Setup local bị lỗi | Setup troubleshoot section, sau đó ping maintainer |
| "Tại sao chọn X thay vì Y?" | Đọc `docs/decisions/` trước, hỏi sau |
| "Code này ở đâu?" | `codegraph_search` (nếu dùng Claude Code) hoặc `grep`/IDE search |
| Domain question (translation, glossary, format) | Ping Thu (owner) |
| Production deploy | Senior duy nhất có SSH; xem deploy.md |

## Khi nào doc này cần update

- Thêm requirement mới cho onboarding (ví dụ: cần thêm tool gì).
- Thay đổi workflow / Spec-Kit version.
- Thay đổi tech stack chính (cần kèm ADR).
- Tìm thấy bug trong setup flow mà nhiều dev mắc.

Edit trực tiếp file này → mở PR. Không cần SPEC riêng cho doc fix.
