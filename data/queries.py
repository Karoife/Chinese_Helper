"""Sentence selection queries: pick new sentences respecting level/mode and
avoiding repeats; fetch word breakdowns; compute progress stats.
"""
from __future__ import annotations

import random
import sqlite3
import unicodedata
from typing import List, Optional

import jieba
from pypinyin import Style, pinyin

from data.models import Sentence, Word
from srs.spaced_repetition import already_studied_sentence_ids


def _level_filter_sql(level: int, mode: str) -> tuple:
    if mode == "level_only":
        return "hsk_level = ?", (level,)
    return "hsk_level <= ?", (level,)


def pick_new_sentence(conn: sqlite3.Connection, level: int, mode: str) -> Optional[Sentence]:
    """Pick a random sentence matching level/mode that hasn't been sent yet."""
    studied_ids = already_studied_sentence_ids(conn)
    where_clause, params = _level_filter_sql(level, mode)

    rows = conn.execute(
        f"SELECT id, chinese, pinyin, spanish, hsk_level, source, source_id "
        f"FROM sentences WHERE {where_clause}",
        params,
    ).fetchall()

    candidates = [row for row in rows if row["id"] not in studied_ids]
    if not candidates:
        return None

    row = random.choice(candidates)
    return Sentence(
        id=row["id"],
        chinese=row["chinese"],
        pinyin=row["pinyin"],
        spanish=row["spanish"],
        hsk_level=row["hsk_level"],
        source=row["source"],
        source_id=row["source_id"],
    )


def get_sentence(conn: sqlite3.Connection, sentence_id: int) -> Optional[Sentence]:
    row = conn.execute(
        "SELECT id, chinese, pinyin, spanish, hsk_level, source, source_id "
        "FROM sentences WHERE id = ?",
        (sentence_id,),
    ).fetchone()
    if row is None:
        return None
    return Sentence(
        id=row["id"],
        chinese=row["chinese"],
        pinyin=row["pinyin"],
        spanish=row["spanish"],
        hsk_level=row["hsk_level"],
        source=row["source"],
        source_id=row["source_id"],
    )


def get_sentence_words(conn: sqlite3.Connection, sentence_id: int) -> List[Word]:
    sentence = conn.execute(
        "SELECT chinese FROM sentences WHERE id = ?", (sentence_id,)
    ).fetchone()
    if sentence is None:
        return []

    tokens = [
        token.strip()
        for token in jieba.cut(sentence["chinese"])
        if token.strip() and not all(unicodedata.category(char)[0] in {"P", "S", "Z"} for char in token)
    ]
    if not tokens:
        return []

    placeholders = ",".join("?" for _ in set(tokens))
    token_values = tuple(dict.fromkeys(tokens))
    rows = conn.execute(
        "SELECT id, simplified, pinyin, english, spanish, hsk_level, pos, frequency "
        f"FROM words WHERE simplified IN ({placeholders}) "
        "ORDER BY hsk_level ASC, frequency ASC",
        token_values,
    ).fetchall()
    word_by_token = {}
    for row in rows:
        word_by_token.setdefault(
            row["simplified"],
            Word(
                id=row["id"],
                simplified=row["simplified"],
                pinyin=row["pinyin"],
                english=row["english"],
                spanish=row["spanish"],
                hsk_level=row["hsk_level"],
                pos=row["pos"],
                frequency=row["frequency"],
            ),
        )

    cached_rows = conn.execute(
        f"SELECT simplified, pinyin, spanish FROM token_translation_cache "
        f"WHERE simplified IN ({placeholders})",
        token_values,
    ).fetchall()
    cache_by_token = {row["simplified"]: row for row in cached_rows}

    result = []
    for token in tokens:
        word = word_by_token.get(token)
        if word is not None:
            result.append(word)
            continue
        cached = cache_by_token.get(token)
        token_pinyin = " ".join(
            syllable[0]
            for syllable in pinyin(token, style=Style.TONE, errors="ignore")
            if syllable
        ) or token
        result.append(
            Word(
                id=-1,
                simplified=token,
                pinyin=cached["pinyin"] if cached else token_pinyin,
                english="",
                spanish=cached["spanish"] if cached else None,
                hsk_level=0,
            )
        )
    return result


def get_progress(conn: sqlite3.Connection) -> dict:
    total_sent = conn.execute("SELECT COUNT(*) FROM sentence_history").fetchone()[0]
    mastered = conn.execute(
        "SELECT COUNT(*) FROM sentence_history WHERE status = 'done'"
    ).fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM sentence_history WHERE status = 'active'"
    ).fetchone()[0]
    due_today = conn.execute(
        "SELECT COUNT(*) FROM sentence_history WHERE status = 'active' AND next_review_at <= date('now')"
    ).fetchone()[0]
    return {
        "total_sent": total_sent,
        "mastered": mastered,
        "active": active,
        "due_today": due_today,
    }
