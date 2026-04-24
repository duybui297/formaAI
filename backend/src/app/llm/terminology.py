"""
Glossary / terminology mapper for qwen-mt-turbo.

Converts a plain {source_term: target_term} dict into the DashScope
translation_options.terms list format.

Migration note: This format is DashScope-specific. If swapping to Azure OpenAI,
inject glossary as prompt text instead (Azure does not have a native terminology API).
"""
from __future__ import annotations


def glossary_to_terms(glossary: dict[str, str]) -> list[dict[str, str]]:
    """
    Convert {source_term: target_term} dict to qwen-mt-turbo translation_options.terms list.

    Example:
        glossary_to_terms({"contract": "Hợp đồng"})
        → [{"source": "contract", "target": "Hợp đồng"}]
    """
    return [{"source": src, "target": tgt} for src, tgt in glossary.items()]
