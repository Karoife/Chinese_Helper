"""Build (or update) the local study library: HSK words + Tatoeba sentences.

Usage:
    python -m data.build_library                # first run / update everything
    python -m data.build_library --skip-sentences
    python -m data.build_library --limit-words 50 --limit-sentences 200  # quick smoke test
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config_loader import load_config
from data.db import db_session, init_db
from data.sources import hsk_vocab, tatoeba, translate

logger = logging.getLogger(__name__)


def _setup_logging(level: str, log_file: str) -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
    )


def build_words(db_path: str, limit: int | None, skip_translate: bool = False) -> None:
    raw_words = hsk_vocab.fetch_all_levels()
    if limit:
        raw_words = raw_words[:limit]
    if not raw_words:
        logger.error("No HSK words downloaded, skipping word import")
        return

    if skip_translate:
        spanish = [None] * len(raw_words)
    else:
        logger.info("Translating %d word meanings to Spanish...", len(raw_words))
        spanish = translate.translate_to_spanish([w.english for w in raw_words])
        missing = sum(1 for s in spanish if s is None)
        if missing:
            logger.warning(
                "%d/%d words could not be translated now; their Spanish meanings will be translated "
                "on demand when they appear in lessons. Run `python -m data.build_library "
                "--retry-translations` later to retry bulk translation.",
                missing,
                len(spanish),
            )

    with db_session(db_path) as conn:
        for word, spanish_text in zip(raw_words, spanish):
            conn.execute(
                """
                INSERT OR IGNORE INTO words
                    (simplified, pinyin, english, spanish, hsk_level, pos, frequency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    word.simplified,
                    word.pinyin,
                    word.english,
                    spanish_text,
                    word.hsk_level,
                    word.pos,
                    word.frequency,
                ),
            )
    logger.info("Imported %d words into the database", len(raw_words))


def _load_words_by_simplified(db_path: str) -> Dict[str, Tuple[int, int]]:
    with db_session(db_path) as conn:
        rows = conn.execute("SELECT id, simplified, hsk_level FROM words").fetchall()
    result: Dict[str, Tuple[int, int]] = {}
    for row in rows:
        # Keep the lowest level if a word somehow appears more than once.
        existing = result.get(row["simplified"])
        if existing is None or row["hsk_level"] < existing[1]:
            result[row["simplified"]] = (row["id"], row["hsk_level"])
    return result


def build_sentences(db_path: str, limit: int | None) -> None:
    words_by_simplified = _load_words_by_simplified(db_path)
    if not words_by_simplified:
        logger.error("No words in the database yet, cannot classify sentences. Run word import first.")
        return

    pairs = tatoeba.fetch_sentence_pairs()
    if limit:
        pairs = pairs[:limit]
    parsed = tatoeba.classify_and_parse(pairs, words_by_simplified)

    with db_session(db_path) as conn:
        inserted = 0
        for sentence in parsed:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO sentences
                    (chinese, pinyin, spanish, hsk_level, source, source_id)
                VALUES (?, ?, ?, ?, 'tatoeba', ?)
                """,
                (sentence.chinese, sentence.pinyin, sentence.spanish, sentence.hsk_level, sentence.source_id),
            )
            if cur.rowcount == 0:
                continue
            sentence_id = cur.lastrowid
            inserted += 1
            for word_id in set(sentence.word_ids):
                conn.execute(
                    "INSERT OR IGNORE INTO sentence_words (sentence_id, word_id) VALUES (?, ?)",
                    (sentence_id, word_id),
                )
    logger.info("Imported %d sentences into the database", inserted)


def backfill_translations(db_path: str, limit: int | None = None) -> None:
    """Retry Spanish translation for words that don't have one yet."""
    with db_session(db_path) as conn:
        query = "SELECT id, english FROM words WHERE spanish IS NULL"
        if limit:
            query += f" LIMIT {int(limit)}"
        rows = conn.execute(query).fetchall()

    if not rows:
        logger.info("No missing Spanish translations, nothing to do.")
        return

    logger.info("Retrying Spanish translation for %d words...", len(rows))
    spanish = translate.translate_to_spanish([row["english"] for row in rows])

    with db_session(db_path) as conn:
        updated = 0
        for row, spanish_text in zip(rows, spanish):
            if spanish_text is None:
                continue
            conn.execute("UPDATE words SET spanish = ? WHERE id = ?", (spanish_text, row["id"]))
            updated += 1
    logger.info("Updated %d/%d words with a Spanish translation", updated, len(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/update the HSK study library")
    parser.add_argument("--skip-words", action="store_true")
    parser.add_argument("--skip-sentences", action="store_true")
    parser.add_argument("--skip-translate", action="store_true", help="Import words without translating (faster, for testing)")
    parser.add_argument("--retry-translations", action="store_true", help="Only retry missing Spanish translations and exit")
    parser.add_argument("--limit-words", type=int, default=None, help="For quick smoke tests")
    parser.add_argument("--limit-sentences", type=int, default=None, help="For quick smoke tests")
    args = parser.parse_args()

    config = load_config()
    _setup_logging(config.log_level, config.log_file)
    init_db(config.db_path)

    if args.retry_translations:
        backfill_translations(config.db_path, args.limit_words)
        return

    if not args.skip_words:
        build_words(config.db_path, args.limit_words, skip_translate=args.skip_translate)
    if not args.skip_sentences:
        build_sentences(config.db_path, args.limit_sentences)

    logger.info("Library build finished.")


if __name__ == "__main__":
    main()
