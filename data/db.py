"""SQLite schema and connection helper for the study library.

Single-user app: `user_state` always has exactly one row with id=1.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simplified TEXT NOT NULL,
    pinyin TEXT NOT NULL,
    english TEXT NOT NULL,
    spanish TEXT,
    hsk_level INTEGER NOT NULL,
    pos TEXT,
    frequency INTEGER,
    UNIQUE (simplified, hsk_level)
);
CREATE INDEX IF NOT EXISTS idx_words_simplified ON words (simplified);
CREATE INDEX IF NOT EXISTS idx_words_level ON words (hsk_level);

CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chinese TEXT NOT NULL UNIQUE,
    pinyin TEXT NOT NULL,
    spanish TEXT NOT NULL,
    hsk_level INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'tatoeba',
    source_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_sentences_level ON sentences (hsk_level);

CREATE TABLE IF NOT EXISTS sentence_words (
    sentence_id INTEGER NOT NULL REFERENCES sentences (id) ON DELETE CASCADE,
    word_id INTEGER NOT NULL REFERENCES words (id) ON DELETE CASCADE,
    PRIMARY KEY (sentence_id, word_id)
);

CREATE TABLE IF NOT EXISTS user_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    chat_id INTEGER,
    level INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL DEFAULT 'level_and_below',
    send_time TEXT NOT NULL DEFAULT '08:00',
    timezone TEXT NOT NULL DEFAULT 'America/Costa_Rica'
);

CREATE TABLE IF NOT EXISTS sentence_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL REFERENCES sentences (id) ON DELETE CASCADE,
    first_sent_at TEXT NOT NULL,
    last_sent_at TEXT NOT NULL,
    review_stage INTEGER NOT NULL DEFAULT 0,
    next_review_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_history_next_review ON sentence_history (next_review_at, status);

CREATE TABLE IF NOT EXISTS media_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_type TEXT NOT NULL,
    cache_key TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    attribution TEXT
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO user_state (id, level, mode, send_time, timezone) "
            "VALUES (1, 1, 'level_and_below', '08:00', 'America/Costa_Rica')"
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_session(db_path: str) -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and rolls back on error."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def library_is_populated(db_path: str) -> bool:
    """Return True if words/sentences have already been downloaded."""
    if not Path(db_path).exists():
        return False
    conn = get_connection(db_path)
    try:
        word_count = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        sentence_count = conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0]
        return word_count > 0 and sentence_count > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()
