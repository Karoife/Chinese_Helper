"""Simple spaced repetition: review previously studied sentences at
+1, +3, +7 and +30 days after they were first sent.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

# Days until the *next* review, indexed by current review_stage.
# Stage 0 = just sent for the first time -> review again in 1 day.
# Stage 1 = reviewed once (was due at +1d) -> review again in 3 days.
# Stage 2 = reviewed twice (+3d done) -> review again in 7 days.
# Stage 3 = reviewed three times (+7d done) -> review again in 30 days.
# Stage 4 = reviewed four times (+30d done) -> mastered, no more reviews.
INTERVALS_DAYS = {0: 1, 1: 3, 2: 7, 3: 30}
MASTERED_STAGE = 4


@dataclass
class DueReview:
    history_id: int
    sentence_id: int
    review_stage: int


def _today() -> date:
    return datetime.now().date()


def record_new_sentence_sent(conn: sqlite3.Connection, sentence_id: int) -> None:
    now = datetime.now().isoformat()
    next_review = (_today() + timedelta(days=INTERVALS_DAYS[0])).isoformat()
    conn.execute(
        """
        INSERT INTO sentence_history
            (sentence_id, first_sent_at, last_sent_at, review_stage, next_review_at, status)
        VALUES (?, ?, ?, 0, ?, 'active')
        """,
        (sentence_id, now, now, next_review),
    )


def get_due_reviews(conn: sqlite3.Connection, today: Optional[date] = None) -> List[DueReview]:
    today = today or _today()
    rows = conn.execute(
        """
        SELECT id, sentence_id, review_stage
        FROM sentence_history
        WHERE status = 'active' AND next_review_at <= ?
        ORDER BY next_review_at ASC
        """,
        (today.isoformat(),),
    ).fetchall()
    return [DueReview(row["id"], row["sentence_id"], row["review_stage"]) for row in rows]


def mark_reviewed(conn: sqlite3.Connection, history_id: int) -> None:
    row = conn.execute(
        "SELECT review_stage FROM sentence_history WHERE id = ?", (history_id,)
    ).fetchone()
    if row is None:
        return
    next_stage = row["review_stage"] + 1
    now = datetime.now().isoformat()

    if next_stage >= MASTERED_STAGE:
        conn.execute(
            "UPDATE sentence_history SET review_stage = ?, last_sent_at = ?, "
            "next_review_at = NULL, status = 'done' WHERE id = ?",
            (next_stage, now, history_id),
        )
        return

    next_review = (_today() + timedelta(days=INTERVALS_DAYS[next_stage])).isoformat()
    conn.execute(
        "UPDATE sentence_history SET review_stage = ?, last_sent_at = ?, "
        "next_review_at = ? WHERE id = ?",
        (next_stage, now, next_review, history_id),
    )


def already_studied_sentence_ids(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT DISTINCT sentence_id FROM sentence_history").fetchall()
    return {row["sentence_id"] for row in rows}
