"""Download Tatoeba Chinese (cmn) <-> Spanish (spa) sentence pairs and
classify each sentence by HSK level, based on the vocabulary it contains.

Source: official Tatoeba per-language bulk exports (CC BY 2.0 FR / CC0),
meant exactly for this kind of offline reuse:
  https://downloads.tatoeba.org/exports/per_language/cmn/cmn_sentences.tsv.bz2
  https://downloads.tatoeba.org/exports/per_language/spa/spa_sentences.tsv.bz2
  https://downloads.tatoeba.org/exports/per_language/cmn/cmn-spa_links.tsv.bz2
"""
from __future__ import annotations

import bz2
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import jieba
from opencc import OpenCC
from pypinyin import Style, pinyin

from data.sources.http_utils import download_bytes

logger = logging.getLogger(__name__)

_traditional_to_simplified = OpenCC("t2s").convert

BASE_URL = "https://downloads.tatoeba.org/exports/per_language"
CMN_SENTENCES_URL = f"{BASE_URL}/cmn/cmn_sentences.tsv.bz2"
SPA_SENTENCES_URL = f"{BASE_URL}/spa/spa_sentences.tsv.bz2"
LINKS_URL = f"{BASE_URL}/cmn/cmn-spa_links.tsv.bz2"

MIN_SENTENCE_LENGTH = 2
MAX_SENTENCE_LENGTH = 40
MIN_KNOWN_WORD_RATIO = 0.6  # at least 60% of tokens must be known HSK words

# Characters jieba may return as separate tokens that aren't real vocabulary.
_PUNCTUATION = set("，。！？、；：“”‘’「」『』（）()[]{},.!?;:\"'…—-·《》 \t\n")


@dataclass
class ParsedSentence:
    chinese: str
    pinyin: str
    spanish: str
    hsk_level: int
    source_id: str
    word_ids: List[int]


def _download_tsv(url: str) -> List[List[str]]:
    raw = download_bytes(url)
    if raw is None:
        return []
    text = bz2.decompress(raw).decode("utf-8")
    rows = [line.split("\t") for line in text.splitlines() if line.strip()]
    return rows


def _load_sentences(url: str) -> Dict[str, str]:
    """Return {sentence_id: text} for a Tatoeba per-language sentences file."""
    result: Dict[str, str] = {}
    for row in _download_tsv(url):
        if len(row) < 3:
            continue
        sentence_id, _lang, text = row[0], row[1], row[2]
        result[sentence_id] = text
    return result


def _load_links(url: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for row in _download_tsv(url):
        if len(row) < 2:
            continue
        pairs.append((row[0], row[1]))
    return pairs


def sentence_pinyin(text: str) -> str:
    """Word-aware pinyin: segment with jieba, one space between every syllable
    (and between segments), so mis-segmented tokens never merge visually.
    """
    parts = []
    for token in jieba.cut(text):
        if all(ch in _PUNCTUATION for ch in token):
            if token.strip():
                parts.append(token.strip())
        else:
            syllables = pinyin(token, style=Style.TONE, errors="ignore")
            parts.extend(s[0] for s in syllables)
    return " ".join(parts)


def fetch_sentence_pairs() -> List[Tuple[str, str, str]]:
    """Return [(source_id, chinese_text, spanish_text), ...] for all cmn<->spa links."""
    cmn = _load_sentences(CMN_SENTENCES_URL)
    spa = _load_sentences(SPA_SENTENCES_URL)
    links = _load_links(LINKS_URL)

    pairs: List[Tuple[str, str, str]] = []
    seen_cmn_ids: set = set()
    for id_a, id_b in links:
        if id_a in cmn and id_b in spa:
            cmn_id, spa_id = id_a, id_b
        elif id_b in cmn and id_a in spa:
            cmn_id, spa_id = id_b, id_a
        else:
            continue
        if cmn_id in seen_cmn_ids:
            continue  # keep only the first Spanish translation per Chinese sentence
        seen_cmn_ids.add(cmn_id)
        pairs.append((cmn_id, cmn[cmn_id], spa[spa_id]))

    logger.info("Found %d Tatoeba cmn<->spa sentence pairs", len(pairs))
    return pairs


def classify_and_parse(
    pairs: List[Tuple[str, str, str]],
    words_by_simplified: Dict[str, Tuple[int, int]],
) -> List[ParsedSentence]:
    """Segment each sentence and keep only ones whose vocabulary we recognize.

    `words_by_simplified` maps simplified word -> (word_id, hsk_level).
    """
    parsed: List[ParsedSentence] = []
    for source_id, chinese, spanish in pairs:
        # Tatoeba's "cmn" (Mandarin) sentences may be written in Traditional
        # script; normalize everything to Simplified as required by this app.
        chinese = _traditional_to_simplified(chinese.strip())
        if not (MIN_SENTENCE_LENGTH <= len(chinese) <= MAX_SENTENCE_LENGTH):
            continue

        tokens = [t for t in jieba.cut(chinese) if t.strip() and t not in _PUNCTUATION]
        if not tokens:
            continue

        matched_word_ids: List[int] = []
        matched_levels: List[int] = []
        for token in tokens:
            match = words_by_simplified.get(token)
            if match:
                word_id, level = match
                matched_word_ids.append(word_id)
                matched_levels.append(level)

        ratio = len(matched_levels) / len(tokens)
        if ratio < MIN_KNOWN_WORD_RATIO or not matched_levels:
            continue

        parsed.append(
            ParsedSentence(
                chinese=chinese,
                pinyin=sentence_pinyin(chinese),
                spanish=spanish.strip(),
                hsk_level=max(matched_levels),
                source_id=source_id,
                word_ids=matched_word_ids,
            )
        )

    logger.info("Classified %d sentences with recognizable HSK vocabulary", len(parsed))
    return parsed
