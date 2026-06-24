"""
GET /api/v1/languages — return qwen-mt-turbo supported languages from DB.

US-3.2 AC-3: Falls back to hardcoded list if DB table is empty.
_VALID_CODES / _VALID_TARGET_CODES are computed per-request via Depends() so
they always reflect the current DB state without needing cache invalidation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Language
from app.db.session import get_session

router = APIRouter()

# Fallback — used if DB table is empty (e.g. fresh install before seed)
_FALLBACK_LANGUAGES: list[dict[str, str]] = [
    {"code": "auto", "name": "Auto-detect", "qwen_code": "auto"},
    {"code": "vi", "name": "Vietnamese", "qwen_code": "Vietnamese"},
    {"code": "en", "name": "English", "qwen_code": "English"},
    {"code": "ja", "name": "Japanese", "qwen_code": "Japanese"},
    {"code": "zh", "name": "Chinese (Simplified)", "qwen_code": "Chinese (Simplified)"},
    {"code": "zh-tw", "name": "Chinese (Traditional)", "qwen_code": "Chinese (Traditional)"},
    {"code": "af", "name": "Afrikaans", "qwen_code": "Afrikaans"},
    {"code": "sq", "name": "Albanian", "qwen_code": "Albanian"},
    {"code": "am", "name": "Amharic", "qwen_code": "Amharic"},
    {"code": "ar", "name": "Arabic", "qwen_code": "Arabic"},
    {"code": "az", "name": "Azerbaijani", "qwen_code": "Azerbaijani"},
    {"code": "eu", "name": "Basque", "qwen_code": "Basque"},
    {"code": "be", "name": "Belarusian", "qwen_code": "Belarusian"},
    {"code": "bn", "name": "Bengali", "qwen_code": "Bengali"},
    {"code": "bs", "name": "Bosnian", "qwen_code": "Bosnian"},
    {"code": "bg", "name": "Bulgarian", "qwen_code": "Bulgarian"},
    {"code": "ca", "name": "Catalan", "qwen_code": "Catalan"},
    {"code": "hr", "name": "Croatian", "qwen_code": "Croatian"},
    {"code": "cs", "name": "Czech", "qwen_code": "Czech"},
    {"code": "da", "name": "Danish", "qwen_code": "Danish"},
    {"code": "nl", "name": "Dutch", "qwen_code": "Dutch"},
    {"code": "eo", "name": "Esperanto", "qwen_code": "Esperanto"},
    {"code": "et", "name": "Estonian", "qwen_code": "Estonian"},
    {"code": "fi", "name": "Finnish", "qwen_code": "Finnish"},
    {"code": "fr", "name": "French", "qwen_code": "French"},
    {"code": "gl", "name": "Galician", "qwen_code": "Galician"},
    {"code": "ka", "name": "Georgian", "qwen_code": "Georgian"},
    {"code": "de", "name": "German", "qwen_code": "German"},
    {"code": "el", "name": "Greek", "qwen_code": "Greek"},
    {"code": "gu", "name": "Gujarati", "qwen_code": "Gujarati"},
    {"code": "ht", "name": "Haitian Creole", "qwen_code": "Haitian Creole"},
    {"code": "he", "name": "Hebrew", "qwen_code": "Hebrew"},
    {"code": "hi", "name": "Hindi", "qwen_code": "Hindi"},
    {"code": "hu", "name": "Hungarian", "qwen_code": "Hungarian"},
    {"code": "is", "name": "Icelandic", "qwen_code": "Icelandic"},
    {"code": "id", "name": "Indonesian", "qwen_code": "Indonesian"},
    {"code": "ga", "name": "Irish", "qwen_code": "Irish"},
    {"code": "it", "name": "Italian", "qwen_code": "Italian"},
    {"code": "kn", "name": "Kannada", "qwen_code": "Kannada"},
    {"code": "ko", "name": "Korean", "qwen_code": "Korean"},
    {"code": "ku", "name": "Kurdish", "qwen_code": "Kurdish"},
    {"code": "lv", "name": "Latvian", "qwen_code": "Latvian"},
    {"code": "lt", "name": "Lithuanian", "qwen_code": "Lithuanian"},
    {"code": "mk", "name": "Macedonian", "qwen_code": "Macedonian"},
    {"code": "ms", "name": "Malay", "qwen_code": "Malay"},
    {"code": "ml", "name": "Malayalam", "qwen_code": "Malayalam"},
    {"code": "mt", "name": "Maltese", "qwen_code": "Maltese"},
    {"code": "mr", "name": "Marathi", "qwen_code": "Marathi"},
    {"code": "mn", "name": "Mongolian", "qwen_code": "Mongolian"},
    {"code": "ne", "name": "Nepali", "qwen_code": "Nepali"},
    {"code": "no", "name": "Norwegian", "qwen_code": "Norwegian"},
    {"code": "fa", "name": "Persian", "qwen_code": "Persian"},
    {"code": "pl", "name": "Polish", "qwen_code": "Polish"},
    {"code": "pt", "name": "Portuguese", "qwen_code": "Portuguese"},
    {"code": "pa", "name": "Punjabi", "qwen_code": "Punjabi"},
    {"code": "ro", "name": "Romanian", "qwen_code": "Romanian"},
    {"code": "ru", "name": "Russian", "qwen_code": "Russian"},
    {"code": "sr", "name": "Serbian", "qwen_code": "Serbian"},
    {"code": "si", "name": "Sinhala", "qwen_code": "Sinhala"},
    {"code": "sk", "name": "Slovak", "qwen_code": "Slovak"},
    {"code": "sl", "name": "Slovenian", "qwen_code": "Slovenian"},
    {"code": "so", "name": "Somali", "qwen_code": "Somali"},
    {"code": "es", "name": "Spanish", "qwen_code": "Spanish"},
    {"code": "sw", "name": "Swahili", "qwen_code": "Swahili"},
    {"code": "sv", "name": "Swedish", "qwen_code": "Swedish"},
    {"code": "ta", "name": "Tamil", "qwen_code": "Tamil"},
    {"code": "te", "name": "Telugu", "qwen_code": "Telugu"},
    {"code": "th", "name": "Thai", "qwen_code": "Thai"},
    {"code": "tr", "name": "Turkish", "qwen_code": "Turkish"},
    {"code": "uk", "name": "Ukrainian", "qwen_code": "Ukrainian"},
    {"code": "ur", "name": "Urdu", "qwen_code": "Urdu"},
    {"code": "uz", "name": "Uzbek", "qwen_code": "Uzbek"},
    {"code": "cy", "name": "Welsh", "qwen_code": "Welsh"},
    {"code": "xh", "name": "Xhosa", "qwen_code": "Xhosa"},
    {"code": "yo", "name": "Yoruba", "qwen_code": "Yoruba"},
    {"code": "zu", "name": "Zulu", "qwen_code": "Zulu"},
]


async def _load_from_db(session: AsyncSession) -> list[dict[str, str]]:
    result = await session.execute(
        select(Language)
        .where(Language.is_active.is_(True))
        .order_by(Language.popularity_rank, Language.code)
    )
    rows: list[Language] = list(result.scalars().all())
    if not rows:
        return _FALLBACK_LANGUAGES
    return [
        {
            "code": row.code,
            "name": row.name,
            "qwen_code": row.qwen_code,
        }
        for row in rows
    ]


# Fallback valid codes computed once from the hardcoded list
_FALLBACK_VALID_CODES: frozenset[str] = frozenset(l["code"] for l in _FALLBACK_LANGUAGES)


@router.get("/languages")
async def get_languages(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Return active languages sorted by popularity_rank from the DB.
    Falls back to hardcoded list if DB is empty.
    """
    languages = await _load_from_db(session)
    return {
        "languages": languages,
        "auto_detect_option": "auto",
    }


# Sync helpers for callers that already have a session via Depends().
# These are only safe to call from within FastAPI route handlers (which provide
# a valid session via dependency injection). They fall back to the hardcoded
# list if the DB query fails.


async def get_valid_codes_async(session: AsyncSession) -> frozenset[str]:
    """Return valid language codes from DB, falling back to hardcoded list."""
    try:
        result = await session.execute(
            select(Language.code)
            .where(Language.is_active.is_(True))
            .order_by(Language.popularity_rank)
        )
        rows = list(result.scalars().all())
        if rows:
            return frozenset(rows)
    except Exception:
        pass
    return _FALLBACK_VALID_CODES


async def get_valid_target_codes_async(session: AsyncSession) -> frozenset[str]:
    """Return valid target language codes (all - 'auto') from DB."""
    return await get_valid_codes_async(session) - {"auto"}
