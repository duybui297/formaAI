# ADR-0002: Use `openai` Python SDK against DashScope compatible endpoint

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu

## Context

To call DashScope's `qwen-mt-turbo` we can use either:

1. Alibaba's first-party `dashscope` Python SDK.
2. The `openai` SDK pointed at DashScope's OpenAI-compatible endpoint
   (`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`).

Thu's existing production stack (ICOM-P3, on Azure OpenAI) already uses
the `openai` SDK heavily. Cognitive overhead and code-reuse matter on a
2–3-week PoC.

## Decision

Use the **`openai` Python SDK** against the **DashScope OpenAI-compatible
endpoint**. Pass model-specific extras (`terminology`, etc.) through
`extra_body`.

## Alternatives considered

- **`dashscope` SDK** — separate async API surface that is less mature
  than `openai`'s native async support; breaks parity with Azure OpenAI
  code; ecosystem tooling (LangChain, instructor, etc.) targets `openai`.
- **Raw HTTP calls** — full control but loses retry/back-off, streaming
  helpers, and typed responses for no real benefit.

## Consequences

- ✅ Zero new SDK to learn — drops into existing patterns.
- ✅ `extra_body` mechanism cleanly carries `terminology` and other
  DashScope-specific parameters without forking the SDK.
- ✅ Easy to swap to Azure OpenAI or AWS Bedrock in a future PoC
  iteration — just change `base_url` + model name.
- ⚠️ DashScope's compatible-mode is not 100% identical to OpenAI — some
  parameters (e.g. `seed`, logit bias) may be silently ignored. Always
  validate response shape before relying on a parameter.
- ⚠️ Alibaba can in principle change the compatible-mode contract;
  pin SDK version and run health checks on deploy.

## References

- `CLAUDE.md` → *2. DashScope SDK vs OpenAI-Compatible Endpoint*
- `backend/src/app/llm/client.py`
- Alibaba compatibility docs: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
