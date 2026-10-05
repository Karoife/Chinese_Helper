"""Orchestrates image retrieval for a sentence: check cache -> search
Openverse by the sentence's most representative word -> fall back to a
generated hanzi+pinyin card. Manages its own short-lived DB session so
callers don't need to keep a connection open during network I/O.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from data.db import db_session
from data.models import Sentence, Word
from images import cache as image_cache
from images.fallback_card import generate_fallback_card
from images.fetch import search_image
from images.keyword import image_search_keyword, pick_card_word, pick_photo_keyword_word

logger = logging.getLogger(__name__)


def get_or_create_image(
    db_path: str, sentence: Sentence, words: List[Word]
) -> Optional[Tuple[Path, Optional[str]]]:
    card_word = pick_card_word(words)
    photo_word = pick_photo_keyword_word(words)
    subject = photo_word.simplified if photo_word else (card_word.simplified if card_word else sentence.chinese)
    strategy = "photo" if photo_word else "card"
    cache_key = f"v3:{strategy}:{subject}"

    with db_session(db_path) as conn:
        cached = image_cache.get_cached(conn, cache_key)
        if cached:
            return cached

    image_cache.IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    file_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()

    if photo_word is not None:
        keyword = image_search_keyword(photo_word)
        result = search_image(keyword)
        if result:
            image_bytes, attribution = result
            path = image_cache.IMAGE_DIR / f"{file_hash}.jpg"
            path.write_bytes(image_bytes)
            with db_session(db_path) as conn:
                image_cache.store(conn, cache_key, path, attribution)
            return path, attribution

    hanzi = card_word.simplified if card_word else sentence.chinese
    pinyin = card_word.pinyin if card_word else sentence.pinyin
    path = image_cache.IMAGE_DIR / f"{file_hash}.png"
    if generate_fallback_card(hanzi, pinyin, path):
        with db_session(db_path) as conn:
            image_cache.store(conn, cache_key, path, None)
        return path, None

    logger.error("Could not get or create any image for sentence %r", sentence.chinese)
    return None
