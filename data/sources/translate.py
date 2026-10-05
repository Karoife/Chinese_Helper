"""Best-effort English -> Spanish translation for HSK word meanings.

Uses `deep-translator`'s free Google Translate wrapper (no API key needed).
Bulk translation uses `deep-translator` during library creation. Lesson words
still missing Spanish use MyMemory on demand and are cached in SQLite.

The free endpoint is rate-limited and sometimes unavailable entirely (e.g.
shared/blocked IPs). Translation is best-effort and never blocks the pipeline.
Words still missing Spanish show a Spanish "translation pending" notice in
lessons; the English source meaning is not displayed to the learner.
"""
from __future__ import annotations

import logging
import time
from html import unescape
from typing import List, Optional

from deep_translator import GoogleTranslator
import requests

logger = logging.getLogger(__name__)

CHUNK_SIZE = 5
PAUSE_BETWEEN_CHUNKS = 1.5
MAX_RETRIES = 2
MAX_CONSECUTIVE_FAILURES = 3  # circuit breaker: stop trying if the service seems down
MYMEMORY_URL = "https://api.mymemory.translated.net/get"


def _clean_spanish_translation(text: str) -> str:
    text = unescape(text).replace("~'s", "posesivo").replace("~’s", "posesivo")
    text = text.replace("~s", "posesivo")
    parts = []
    seen = set()
    for part in text.split(";"):
        cleaned = " ".join(part.split()).strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            parts.append(cleaned)
    return "; ".join(parts)


def translate_to_spanish(texts: List[str]) -> List[Optional[str]]:
    """Translate a list of short English strings to Spanish.

    Returns a list of the same length, with None where translation failed
    (caller should store NULL and fall back to the English text).
    """
    translator = GoogleTranslator(source="en", target="es")
    results: List[Optional[str]] = []
    consecutive_failures = 0
    service_down = False

    for start in range(0, len(texts), CHUNK_SIZE):
        chunk = texts[start : start + CHUNK_SIZE]

        if service_down:
            results.extend([None] * len(chunk))
            continue

        translated_chunk = _translate_chunk_with_retries(translator, chunk)
        if translated_chunk is None:
            consecutive_failures += 1
            results.extend([None] * len(chunk))
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    "Spanish translation service seems unavailable; skipping the rest "
                    "of this batch (affected words will keep their English meaning for now)."
                )
                service_down = True
        else:
            consecutive_failures = 0
            results.extend(translated_chunk)

        if start + CHUNK_SIZE < len(texts) and not service_down:
            time.sleep(PAUSE_BETWEEN_CHUNKS)

    return results


def _translate_chunk_with_retries(translator: GoogleTranslator, chunk: List[str]) -> Optional[List[str]]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            translated = translator.translate_batch(chunk)
            return [
                value if value and value.casefold() != original.casefold() else None
                for value, original in zip(translated, chunk)
            ]
        except Exception as exc:  # noqa: BLE001 - translation lib raises various errors
            logger.warning("Translation batch attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(3.0 * attempt)
    return None


def _translate_with_mymemory(text: str, language_pair: str) -> Optional[str]:
    query = "; ".join(text.split(";")[:5]).strip()[:450]
    if not query:
        return None

    for attempt in range(2):
        try:
            response = requests.get(
                MYMEMORY_URL,
                params={"q": query, "langpair": language_pair},
                timeout=12,
                headers={"User-Agent": "MandarinStudyBot/1.0"},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("responseStatus") != 200:
                return None
            translated = _clean_spanish_translation(
                payload.get("responseData", {}).get("translatedText", "")
            )
            if not translated or translated.casefold() == query.casefold():
                return None
            return translated
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            logger.warning("MyMemory translation attempt %d failed: %s", attempt + 1, exc)
            if attempt == 0:
                time.sleep(1)
    return None


def translate_one_to_spanish(text: str) -> Optional[str]:
    """Translate one missing English glossary meaning into Spanish."""
    return _translate_with_mymemory(text, "en|es")


def translate_chinese_to_spanish(text: str) -> Optional[str]:
    """Translate a Chinese token outside the HSK dictionary into Spanish."""
    return _translate_with_mymemory(text, "zh-CN|es")


def translate_missing_word_meanings(db_path: str, words: list) -> None:
    """Translate lesson tokens on demand and cache HSK and non-HSK meanings."""
    pending_words = []
    pending_tokens = {}
    translated_tokens = {}
    for word in words:
        if word.spanish:
            cleaned = _clean_spanish_translation(word.spanish)
            if cleaned != word.spanish:
                word.spanish = cleaned
                if word.id > 0:
                    pending_words.append((cleaned, word.id))
                else:
                    pending_tokens[word.simplified] = (word.pinyin, cleaned)
            continue
        if word.id > 0:
            translated = translate_one_to_spanish(word.english)
        else:
            translated = translated_tokens.get(word.simplified)
            if translated is None:
                translated = translate_chinese_to_spanish(word.simplified)
                if translated:
                    translated_tokens[word.simplified] = translated
        if translated:
            word.spanish = translated
            if word.id > 0:
                pending_words.append((translated, word.id))
            else:
                pending_tokens[word.simplified] = (word.pinyin, translated)

    if not pending_words and not pending_tokens:
        return

    from data.db import db_session

    with db_session(db_path) as conn:
        conn.executemany("UPDATE words SET spanish = ? WHERE id = ?", pending_words)
        conn.executemany(
            """
            INSERT INTO token_translation_cache (simplified, pinyin, spanish)
            VALUES (?, ?, ?)
            ON CONFLICT (simplified) DO UPDATE SET
                pinyin = excluded.pinyin,
                spanish = excluded.spanish
            """,
            [(token, pinyin_text, spanish_text) for token, (pinyin_text, spanish_text) in pending_tokens.items()],
        )
    logger.info(
        "Cached Spanish translations for %d lesson tokens",
        len(pending_words) + len(pending_tokens),
    )
