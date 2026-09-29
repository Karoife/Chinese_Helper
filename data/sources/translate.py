"""Best-effort English -> Spanish translation for HSK word meanings.

Uses `deep-translator`'s free Google Translate wrapper (no API key needed).
This is only used once per unique word during the initial library build (and
subsequent updates for new words); results are stored in SQLite, so we never
re-translate the same word twice. Requests are batched and paced to be a good
citizen of the free endpoint.
"""
from __future__ import annotations

import logging
import time
from typing import List

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

CHUNK_SIZE = 40
PAUSE_BETWEEN_CHUNKS = 1.0
MAX_RETRIES = 3


def translate_to_spanish(texts: List[str]) -> List[str]:
    """Translate a list of short English strings to Spanish.

    Returns a list of the same length. On failure for a given chunk, the
    original English text is kept as a fallback so the pipeline never stops.
    """
    translator = GoogleTranslator(source="en", target="es")
    results: List[str] = []

    for start in range(0, len(texts), CHUNK_SIZE):
        chunk = texts[start : start + CHUNK_SIZE]
        translated_chunk = _translate_chunk_with_retries(translator, chunk)
        results.extend(translated_chunk)
        if start + CHUNK_SIZE < len(texts):
            time.sleep(PAUSE_BETWEEN_CHUNKS)

    return results


def _translate_chunk_with_retries(translator: GoogleTranslator, chunk: List[str]) -> List[str]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            translated = translator.translate_batch(chunk)
            # The library can return None entries for empty/odd input; guard for it.
            return [t if t else original for t, original in zip(translated, chunk)]
        except Exception as exc:  # noqa: BLE001 - translation lib raises various errors
            logger.warning("Translation batch attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            time.sleep(2.0 * attempt)
    logger.error("Giving up translating a batch of %d texts, keeping English", len(chunk))
    return list(chunk)
