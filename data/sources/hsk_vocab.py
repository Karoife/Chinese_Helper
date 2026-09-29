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
from dataclasses import dataclass
from typing import List, Optional

from data.sources.http_utils import download_bytes

logger = logging.getLogger(__name__)

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


def _parse_entry(entry: dict, hsk_level: int) -> Optional[RawWord]:
    forms = entry.get("forms") or []
    if not forms:
        return None
    primary = forms[0]
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
