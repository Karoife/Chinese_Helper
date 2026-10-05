"""Download and parse HSK vocabulary lists.

Source: drkameleon/complete-hsk-vocabulary (GitHub, MIT license), which merges
the classic HSK 2.0 word lists and the new HSK 3.0 ones together with
CC-CEDICT meanings already baked in.

We use the "exclusive" wordlists (each level file lists only the words that
are new at that level, not the ones from lower levels already covered):
  - Classic HSK 1-6:      wordlists/exclusive/old/{1..6}.json
  - HSK 3.0 "7-9" band:   wordlists/exclusive/newest/7.json
    (the official HSK 3.0 exam does not split 7/8/9 into separate word lists,
    they share one combined list, so we store it as hsk_level=7)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from data.sources.http_utils import download_bytes

logger = logging.getLogger(__name__)

_LOW_QUALITY_MEANING_RE = re.compile(
    r"^(surname |old variant of|variant of|used in |also written)", re.IGNORECASE
)

BASE_URL = (
    "https://raw.githubusercontent.com/drkameleon/complete-hsk-vocabulary/main/wordlists"
)

# (hsk_level stored in our DB, path fragment in the repo)
LEVEL_SOURCES = [
    (1, "exclusive/old/1.json"),
    (2, "exclusive/old/2.json"),
    (3, "exclusive/old/3.json"),
    (4, "exclusive/old/4.json"),
    (5, "exclusive/old/5.json"),
    (6, "exclusive/old/6.json"),
    (7, "exclusive/newest/7.json"),
]


@dataclass
class RawWord:
    simplified: str
    pinyin: str
    english: str
    hsk_level: int
    pos: Optional[str]
    frequency: Optional[int]


def _is_low_quality_form(form: dict) -> bool:
    """True if every meaning of this form is a rare/auxiliary note (surname,
    variant of another character, etc.) rather than the word's real meaning.
    """
    meanings = form.get("meanings") or []
    return bool(meanings) and all(_LOW_QUALITY_MEANING_RE.match(m) for m in meanings)


def _pick_primary_form(forms: List[dict]) -> Optional[dict]:
    """Prefer a common-word reading over a surname/proper-noun/variant one.

    The source data doesn't order forms by frequency, so readings like
    "Shuǐ" (surname) or a rare "yāo" (to coerce) can appear before the common
    reading "shuǐ"/"yào". Among common-word (lowercase pinyin) forms with a
    substantive meaning, the one with the most listed meanings is a good
    proxy for "the common, central reading" of a polysemous character.
    """
    lowercase_forms = [
        f for f in forms if ((f.get("transcriptions") or {}).get("pinyin") or "")[:1].islower()
    ]
    substantive_forms = [f for f in lowercase_forms if not _is_low_quality_form(f)]
    if substantive_forms:
        return max(substantive_forms, key=lambda f: len(f.get("meanings") or []))
    if lowercase_forms:
        return lowercase_forms[0]
    return forms[0] if forms else None


def _parse_entry(entry: dict, hsk_level: int) -> Optional[RawWord]:
    forms = entry.get("forms") or []
    primary = _pick_primary_form(forms)
    if primary is None:
        return None
    pinyin = (primary.get("transcriptions") or {}).get("pinyin")
    meanings = primary.get("meanings") or []
    if not pinyin or not meanings:
        return None
    pos_list = entry.get("pos") or []
    return RawWord(
        simplified=entry["simplified"],
        pinyin=pinyin,
        english="; ".join(meanings),
        hsk_level=hsk_level,
        pos=",".join(pos_list) if pos_list else None,
        frequency=entry.get("frequency"),
    )


def fetch_level(hsk_level: int, path: str) -> List[RawWord]:
    url = f"{BASE_URL}/{path}"
    raw = download_bytes(url)
    if raw is None:
        logger.error("Could not download HSK level %d word list, skipping it", hsk_level)
        return []
    entries = json.loads(raw)
    words = [w for w in (_parse_entry(e, hsk_level) for e in entries) if w is not None]
    logger.info("Fetched %d words for HSK level %d", len(words), hsk_level)
    return words


def fetch_all_levels() -> List[RawWord]:
    words: List[RawWord] = []
    for hsk_level, path in LEVEL_SOURCES:
        words.extend(fetch_level(hsk_level, path))
    return words
