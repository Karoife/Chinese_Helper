"""Plain dataclasses shared across the data/, bot/ and scheduler/ modules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Word:
    id: int
    simplified: str
    pinyin: str
    english: str
    spanish: Optional[str]
    hsk_level: int
    pos: Optional[str] = None
    frequency: Optional[int] = None


@dataclass
class Sentence:
    id: int
    chinese: str
    pinyin: str
    spanish: str
    hsk_level: int
    source: str = "tatoeba"
    source_id: Optional[str] = None


@dataclass
class UserState:
    chat_id: Optional[int]
    level: int
    mode: str
    send_time: str
    timezone: str
