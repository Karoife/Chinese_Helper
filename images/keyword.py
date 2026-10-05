"""Pick the single word from a sentence's breakdown that best represents its
meaning, and clean its English gloss into a short search query.

Photo search only makes sense for concrete nouns (a "cup" or "airport" photo
is meaningful; a photo for an abstract verb like "to know" usually isn't, and
free keyword image search tends to return irrelevant/meme results for those).
Abstract words always fall back to the generated hanzi+pinyin card instead.
"""
from __future__ import annotations

import re
from typing import List, Optional

from data.models import Word

_NOUN_POS = {"n", "ns", "nz", "ng", "nr", "nt", "nx"}
_VERB_POS = {"v", "vd", "vn", "vg", "vi", "vq", "vshi", "vyou"}
_CONTENT_POS = _NOUN_POS | {"v", "a", "vn", "an"}
# Function-word tags: some entries carry a stray "n" from an unrelated rare
# reading of the character (e.g. 的 is mostly the particle "u", but the
# dataset's entry-level pos list also includes "n" from its rare "target"
# reading). Excluding these prevents picking particles as photo subjects.
_FUNCTION_POS = {"u", "r", "d", "p", "c", "y", "w", "e"}
_LEADING_NOTE_RE = re.compile(r"^\([^)]*\)\s*")


def pick_photo_keyword_word(words: List[Word]) -> Optional[Word]:
    """Return the best concrete noun to search a photo for, if any."""
    nouns = [
        w
        for w in words
        if (pos_set := set((w.pos or "").split(","))) & _NOUN_POS
        and not (pos_set & _FUNCTION_POS)
        and not (pos_set & _VERB_POS)
    ]
    if not nouns:
        return None
    return max(nouns, key=lambda w: w.hsk_level)


def pick_card_word(words: List[Word]) -> Optional[Word]:
    """Return the best word to show on a generated fallback card."""
    if not words:
        return None

    def score(word: Word) -> tuple:
        pos_set = set((word.pos or "").split(","))
        is_content = bool(pos_set & _CONTENT_POS)
        return (is_content, word.hsk_level)

    return max(words, key=score)


def image_search_keyword(word: Word) -> str:
    """Turn a word's English gloss into a short, image-searchable phrase."""
    first_clause = word.english.split(";")[0].split(",")[0].strip()
    cleaned = _LEADING_NOTE_RE.sub("", first_clause).strip(" .?!")
    return cleaned or word.simplified

