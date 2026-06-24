"""
Seed script for language_catalogue.

Run with: uv run python -m app.db.seed_languages

Usage in Docker: docker compose exec backend python -m app.db.seed_languages
"""
from __future__ import annotations

import asyncio
import os
import sys

# Add src to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Language


LANGUAGES = [
    # Priority: 5 most popular for AICore market (VI/EN/JA/ZH/ZH-TW)
    {"code": "auto", "name": "Auto-detect", "qwen_code": "auto", "is_auto_detect": True, "popularity_rank": 0},
    {"code": "vi", "name": "Vietnamese", "qwen_code": "Vietnamese", "is_auto_detect": False, "popularity_rank": 1},
    {"code": "en", "name": "English", "qwen_code": "English", "is_auto_detect": False, "popularity_rank": 2},
    {"code": "ja", "name": "Japanese", "qwen_code": "Japanese", "is_auto_detect": False, "popularity_rank": 3},
    {"code": "zh", "name": "Chinese (Simplified)", "qwen_code": "Chinese (Simplified)", "is_auto_detect": False, "popularity_rank": 4},
    {"code": "zh-tw", "name": "Chinese (Traditional)", "qwen_code": "Chinese (Traditional)", "is_auto_detect": False, "popularity_rank": 5},
    # Rest of the list
    {"code": "af", "name": "Afrikaans", "qwen_code": "Afrikaans", "is_auto_detect": False, "popularity_rank": 10},
    {"code": "sq", "name": "Albanian", "qwen_code": "Albanian", "is_auto_detect": False, "popularity_rank": 11},
    {"code": "am", "name": "Amharic", "qwen_code": "Amharic", "is_auto_detect": False, "popularity_rank": 12},
    {"code": "ar", "name": "Arabic", "qwen_code": "Arabic", "is_auto_detect": False, "popularity_rank": 13},
    {"code": "az", "name": "Azerbaijani", "qwen_code": "Azerbaijani", "is_auto_detect": False, "popularity_rank": 14},
    {"code": "eu", "name": "Basque", "qwen_code": "Basque", "is_auto_detect": False, "popularity_rank": 15},
    {"code": "be", "name": "Belarusian", "qwen_code": "Belarusian", "is_auto_detect": False, "popularity_rank": 16},
    {"code": "bn", "name": "Bengali", "qwen_code": "Bengali", "is_auto_detect": False, "popularity_rank": 17},
    {"code": "bs", "name": "Bosnian", "qwen_code": "Bosnian", "is_auto_detect": False, "popularity_rank": 18},
    {"code": "bg", "name": "Bulgarian", "qwen_code": "Bulgarian", "is_auto_detect": False, "popularity_rank": 19},
    {"code": "ca", "name": "Catalan", "qwen_code": "Catalan", "is_auto_detect": False, "popularity_rank": 20},
    {"code": "hr", "name": "Croatian", "qwen_code": "Croatian", "is_auto_detect": False, "popularity_rank": 21},
    {"code": "cs", "name": "Czech", "qwen_code": "Czech", "is_auto_detect": False, "popularity_rank": 22},
    {"code": "da", "name": "Danish", "qwen_code": "Danish", "is_auto_detect": False, "popularity_rank": 23},
    {"code": "nl", "name": "Dutch", "qwen_code": "Dutch", "is_auto_detect": False, "popularity_rank": 24},
    {"code": "eo", "name": "Esperanto", "qwen_code": "Esperanto", "is_auto_detect": False, "popularity_rank": 25},
    {"code": "et", "name": "Estonian", "qwen_code": "Estonian", "is_auto_detect": False, "popularity_rank": 26},
    {"code": "fi", "name": "Finnish", "qwen_code": "Finnish", "is_auto_detect": False, "popularity_rank": 27},
    {"code": "fr", "name": "French", "qwen_code": "French", "is_auto_detect": False, "popularity_rank": 28},
    {"code": "gl", "name": "Galician", "qwen_code": "Galician", "is_auto_detect": False, "popularity_rank": 29},
    {"code": "ka", "name": "Georgian", "qwen_code": "Georgian", "is_auto_detect": False, "popularity_rank": 30},
    {"code": "de", "name": "German", "qwen_code": "German", "is_auto_detect": False, "popularity_rank": 31},
    {"code": "el", "name": "Greek", "qwen_code": "Greek", "is_auto_detect": False, "popularity_rank": 32},
    {"code": "gu", "name": "Gujarati", "qwen_code": "Gujarati", "is_auto_detect": False, "popularity_rank": 33},
    {"code": "ht", "name": "Haitian Creole", "qwen_code": "Haitian Creole", "is_auto_detect": False, "popularity_rank": 34},
    {"code": "he", "name": "Hebrew", "qwen_code": "Hebrew", "is_auto_detect": False, "popularity_rank": 35},
    {"code": "hi", "name": "Hindi", "qwen_code": "Hindi", "is_auto_detect": False, "popularity_rank": 36},
    {"code": "hu", "name": "Hungarian", "qwen_code": "Hungarian", "is_auto_detect": False, "popularity_rank": 37},
    {"code": "is", "name": "Icelandic", "qwen_code": "Icelandic", "is_auto_detect": False, "popularity_rank": 38},
    {"code": "id", "name": "Indonesian", "qwen_code": "Indonesian", "is_auto_detect": False, "popularity_rank": 39},
    {"code": "ga", "name": "Irish", "qwen_code": "Irish", "is_auto_detect": False, "popularity_rank": 40},
    {"code": "it", "name": "Italian", "qwen_code": "Italian", "is_auto_detect": False, "popularity_rank": 41},
    {"code": "kn", "name": "Kannada", "qwen_code": "Kannada", "is_auto_detect": False, "popularity_rank": 42},
    {"code": "ko", "name": "Korean", "qwen_code": "Korean", "is_auto_detect": False, "popularity_rank": 43},
    {"code": "ku", "name": "Kurdish", "qwen_code": "Kurdish", "is_auto_detect": False, "popularity_rank": 44},
    {"code": "lv", "name": "Latvian", "qwen_code": "Latvian", "is_auto_detect": False, "popularity_rank": 45},
    {"code": "lt", "name": "Lithuanian", "qwen_code": "Lithuanian", "is_auto_detect": False, "popularity_rank": 46},
    {"code": "mk", "name": "Macedonian", "qwen_code": "Macedonian", "is_auto_detect": False, "popularity_rank": 47},
    {"code": "ms", "name": "Malay", "qwen_code": "Malay", "is_auto_detect": False, "popularity_rank": 48},
    {"code": "ml", "name": "Malayalam", "qwen_code": "Malayalam", "is_auto_detect": False, "popularity_rank": 49},
    {"code": "mt", "name": "Maltese", "qwen_code": "Maltese", "is_auto_detect": False, "popularity_rank": 50},
    {"code": "mr", "name": "Marathi", "qwen_code": "Marathi", "is_auto_detect": False, "popularity_rank": 51},
    {"code": "mn", "name": "Mongolian", "qwen_code": "Mongolian", "is_auto_detect": False, "popularity_rank": 52},
    {"code": "ne", "name": "Nepali", "qwen_code": "Nepali", "is_auto_detect": False, "popularity_rank": 53},
    {"code": "no", "name": "Norwegian", "qwen_code": "Norwegian", "is_auto_detect": False, "popularity_rank": 54},
    {"code": "fa", "name": "Persian", "qwen_code": "Persian", "is_auto_detect": False, "popularity_rank": 55},
    {"code": "pl", "name": "Polish", "qwen_code": "Polish", "is_auto_detect": False, "popularity_rank": 56},
    {"code": "pt", "name": "Portuguese", "qwen_code": "Portuguese", "is_auto_detect": False, "popularity_rank": 57},
    {"code": "pa", "name": "Punjabi", "qwen_code": "Punjabi", "is_auto_detect": False, "popularity_rank": 58},
    {"code": "ro", "name": "Romanian", "qwen_code": "Romanian", "is_auto_detect": False, "popularity_rank": 59},
    {"code": "ru", "name": "Russian", "qwen_code": "Russian", "is_auto_detect": False, "popularity_rank": 60},
    {"code": "sr", "name": "Serbian", "qwen_code": "Serbian", "is_auto_detect": False, "popularity_rank": 61},
    {"code": "si", "name": "Sinhala", "qwen_code": "Sinhala", "is_auto_detect": False, "popularity_rank": 62},
    {"code": "sk", "name": "Slovak", "qwen_code": "Slovak", "is_auto_detect": False, "popularity_rank": 63},
    {"code": "sl", "name": "Slovenian", "qwen_code": "Slovenian", "is_auto_detect": False, "popularity_rank": 64},
    {"code": "so", "name": "Somali", "qwen_code": "Somali", "is_auto_detect": False, "popularity_rank": 65},
    {"code": "es", "name": "Spanish", "qwen_code": "Spanish", "is_auto_detect": False, "popularity_rank": 66},
    {"code": "sw", "name": "Swahili", "qwen_code": "Swahili", "is_auto_detect": False, "popularity_rank": 67},
    {"code": "sv", "name": "Swedish", "qwen_code": "Swedish", "is_auto_detect": False, "popularity_rank": 68},
    {"code": "ta", "name": "Tamil", "qwen_code": "Tamil", "is_auto_detect": False, "popularity_rank": 69},
    {"code": "te", "name": "Telugu", "qwen_code": "Telugu", "is_auto_detect": False, "popularity_rank": 70},
    {"code": "th", "name": "Thai", "qwen_code": "Thai", "is_auto_detect": False, "popularity_rank": 71},
    {"code": "tr", "name": "Turkish", "qwen_code": "Turkish", "is_auto_detect": False, "popularity_rank": 72},
    {"code": "uk", "name": "Ukrainian", "qwen_code": "Ukrainian", "is_auto_detect": False, "popularity_rank": 73},
    {"code": "ur", "name": "Urdu", "qwen_code": "Urdu", "is_auto_detect": False, "popularity_rank": 74},
    {"code": "uz", "name": "Uzbek", "qwen_code": "Uzbek", "is_auto_detect": False, "popularity_rank": 75},
    {"code": "cy", "name": "Welsh", "qwen_code": "Welsh", "is_auto_detect": False, "popularity_rank": 76},
    {"code": "xh", "name": "Xhosa", "qwen_code": "Xhosa", "is_auto_detect": False, "popularity_rank": 77},
    {"code": "yo", "name": "Yoruba", "qwen_code": "Yoruba", "is_auto_detect": False, "popularity_rank": 78},
    {"code": "zu", "name": "Zulu", "qwen_code": "Zulu", "is_auto_detect": False, "popularity_rank": 79},
]


async def run() -> None:
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./translation.db")
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Upsert: insert or update existing
        for lang in LANGUAGES:
            result = await session.execute(
                select(Language).where(Language.code == lang["code"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.name = lang["name"]
                existing.qwen_code = lang["qwen_code"]
                existing.is_auto_detect = lang["is_auto_detect"]
                existing.popularity_rank = lang["popularity_rank"]
            else:
                session.add(Language(**lang))

        await session.commit()

    print(f"Seeded {len(LANGUAGES)} languages into language_catalogue.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
