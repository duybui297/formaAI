"""
Placeholder extraction and restoration for CORE-05.

Non-translatable tokens (URLs, emails, template variables, version strings, ISO dates)
are replaced with ⟦T{n}⟧ markers before sending to qwen-mt-turbo. After the LLM
returns the translated text, restore_placeholders replaces markers back to originals.

Usage:
    masked_text, tokens = extract_placeholders(source_text)
    translated = await translate_batch(client, [masked_text], ...)
    final_text = restore_placeholders(translated[0], tokens)

Threat T-04-03: if a ⟦T{n}⟧ marker is missing from tokens, the marker is kept
visible in the output (never silently dropped) so reviewers can catch it.
"""
from __future__ import annotations

import re

# Patterns from RESEARCH.md §5. Order matters: more specific patterns first.
# URL pattern is intentionally broad to catch query strings and fragments.
_PROTECTED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"https?://\S+"),
    re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}"),
    re.compile(r"\{\{[^}]+\}\}"),
    re.compile(r"\$\{[^}]+\}"),
    re.compile(r"<%=?\s*[^%]+%>"),
    re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:Z.+\-]+)?"),
    re.compile(r"v\d+\.\d+[\.\d\w\-]*"),
    # PDF format-fidelity: protect HTML markup tags emitted by spans_to_html
    # (<b>, </b>, <i>, </i>, <h1>, </h1>, <h2>, </h2>, <span style="...">)
    # so Qwen-MT preserves them verbatim instead of stripping during translation.
    re.compile(r"</?[a-zA-Z][^>]*>"),
]

_PLACEHOLDER_RE: re.Pattern[str] = re.compile(r"⟦T(\d+)⟧")


class PlaceholderRestoreError(Exception):
    """
    Raised when ⟦T{n}⟧ markers remain in the output after restore_placeholders.

    Use this in strict mode when missing markers are a hard error rather than
    a visible fallback (see the mitigate disposition in threat T-04-03).
    """


def extract_placeholders(text: str) -> tuple[str, dict[int, str]]:
    """
    Replace all non-translatable tokens with ⟦T{n}⟧ markers.

    Returns (modified_text, {n: original_token}).
    Call before sending segment text to translate_batch.

    The counter is maintained via a mutable list cell to avoid Python's
    late-binding closure issue with nonlocal inside nested loops.
    """
    tokens: dict[int, str] = {}
    counter: list[int] = [0]  # mutable cell avoids late-binding closure issue

    for pattern in _PROTECTED_PATTERNS:

        def _make_replacer(
            _tokens: dict[int, str] = tokens,
            _counter: list[int] = counter,
        ):
            def replacer(m: re.Match[str]) -> str:
                idx = _counter[0]
                _counter[0] += 1
                _tokens[idx] = m.group(0)
                return f"⟦T{idx}⟧"

            return replacer

        text = pattern.sub(_make_replacer(), text)

    return text, tokens


def restore_placeholders(text: str, tokens: dict[int, str]) -> str:
    """
    Restore ⟦T{n}⟧ markers back to original tokens.

    Fallback behavior (T-04-03 mitigate): if marker index missing in tokens,
    keeps the ⟦T{n}⟧ marker visible in output. This surfaces the error to the
    reviewer rather than silently dropping a URL/email/template variable.

    Use PlaceholderRestoreError in strict pipelines after calling this
    if any markers remain (check with `re.search(r'⟦T\\d+⟧', result)`).
    """

    def restorer(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        return tokens.get(idx, m.group(0))

    return _PLACEHOLDER_RE.sub(restorer, text)
