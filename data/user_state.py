"""Read/write the single-row `user_state` table."""
from __future__ import annotations

import sqlite3
from typing import Optional

from data.models import UserState


def get_user_state(conn: sqlite3.Connection) -> UserState:
    row = conn.execute(
        "SELECT chat_id, level, mode, send_time, timezone FROM user_state WHERE id = 1"
    ).fetchone()
    return UserState(
        chat_id=row["chat_id"],
        level=row["level"],
        mode=row["mode"],
        send_time=row["send_time"],
        timezone=row["timezone"],
    )


def set_chat_id(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute("UPDATE user_state SET chat_id = ? WHERE id = 1", (chat_id,))


def set_level(conn: sqlite3.Connection, level: int, mode: Optional[str] = None) -> None:
    if mode:
        conn.execute("UPDATE user_state SET level = ?, mode = ? WHERE id = 1", (level, mode))
    else:
        conn.execute("UPDATE user_state SET level = ? WHERE id = 1", (level,))


def set_send_time(conn: sqlite3.Connection, send_time: str) -> None:
    conn.execute("UPDATE user_state SET send_time = ? WHERE id = 1", (send_time,))
