"""DB-backed cache for illustrative images (fetched photos or generated
fallback cards), so the same sentence/keyword is never looked up twice.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Tuple

IMAGE_DIR = Path("storage/images")


def get_cached(conn: sqlite3.Connection, cache_key: str) -> Optional[Tuple[Path, Optional[str]]]:
    row = conn.execute(
        "SELECT file_path, attribution FROM media_cache WHERE media_type = 'image' AND cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is None:
        return None
    path = Path(row["file_path"])
    if not path.exists():
        return None
    return path, row["attribution"]


def store(conn: sqlite3.Connection, cache_key: str, file_path: Path, attribution: Optional[str]) -> None:
    conn.execute(
        """
        INSERT INTO media_cache (media_type, cache_key, file_path, attribution)
        VALUES ('image', ?, ?, ?)
        ON CONFLICT (cache_key) DO UPDATE SET file_path = excluded.file_path, attribution = excluded.attribution
        """,
        (cache_key, str(file_path), attribution),
    )
