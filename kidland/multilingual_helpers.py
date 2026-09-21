"""Helpers for resolving and snapshotting multilingual KidLand values."""

from dbzero_modelkit import LanguageCode, ML_String


def resolve_multilingual_text(
    text: ML_String,
    language: LanguageCode,
) -> str:
    """Resolve a translation and fall back to the primary stored value."""

    translation = text.get(language)
    return text.value if translation is None else translation


def snapshot_multilingual_text(
    text: ML_String,
    primary_language: LanguageCode,
) -> ML_String:
    """Create an independent multilingual snapshot using modelkit's public API."""

    if text.get(primary_language) != text.value:
        raise ValueError("primary_language must identify the primary text value")

    translations = {
        language: translation
        for language in LanguageCode.values()
        if language != primary_language
        if (translation := text.get(language)) is not None
    }
    return ML_String(text.value, primary_language, translations or None)
