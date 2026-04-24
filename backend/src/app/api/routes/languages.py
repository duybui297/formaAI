"""
GET /languages — return qwen-mt-turbo supported languages.

LANG-01: B5 fix — returns list[dict[str, str]] not list[str].
Each entry has: code (form value), name (display label), qwen_code (API value).

Client caches for 24h (staleTime: 24h in TanStack Query per UI-SPEC).
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

# qwen-mt-turbo supported languages.
# code: used as form value in frontend and for upload validation
# name: display label in LanguageSelect dropdown
# qwen_code: value sent to qwen-mt-turbo source_lang/target_lang params
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    # "auto" is source-only — not valid as target_lang
    {"code": "auto", "name": "Auto-detect", "qwen_code": "auto"},
    # Priority languages (UI-SPEC Recommended group)
    {"code": "vi", "name": "Vietnamese", "qwen_code": "Vietnamese"},
    {"code": "en", "name": "English", "qwen_code": "English"},
    {"code": "ja", "name": "Japanese", "qwen_code": "Japanese"},
    {"code": "zh", "name": "Chinese (Simplified)", "qwen_code": "Chinese (Simplified)"},
    {"code": "zh-tw", "name": "Chinese (Traditional)", "qwen_code": "Chinese (Traditional)"},
    # Full alphabetical list
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

# Valid codes for upload validation
_VALID_CODES: frozenset[str] = frozenset(lang["code"] for lang in SUPPORTED_LANGUAGES)
# "auto" is source-only — not valid as target_lang
_VALID_TARGET_CODES: frozenset[str] = _VALID_CODES - {"auto"}


@router.get("/languages")
async def get_languages() -> dict:
    """
    LANG-01: Return qwen-mt-turbo supported languages as code+name+qwen_code dicts.

    Response shape: {languages: [{code, name, qwen_code}], auto_detect_option: "auto"}
    Client caches for 24h (TanStack Query staleTime).
    # TODO(phase-2): add JWT auth
    """
    return {
        "languages": SUPPORTED_LANGUAGES,
        "auto_detect_option": "auto",
    }
