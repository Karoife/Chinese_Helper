"""Offline Mandarin transcription and an approximate character-match score."""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

from opencc import OpenCC

_to_simplified = OpenCC("t2s").convert


@lru_cache(maxsize=1)
def _load_model():
    from faster_whisper import WhisperModel

    return WhisperModel("base", device="cpu", compute_type="int8")


def transcribe_mandarin(audio_path: str | Path) -> str:
    segments, _ = _load_model().transcribe(
        str(audio_path), language="zh", beam_size=3, vad_filter=True
    )
    return "".join(segment.text for segment in segments).strip()


def normalize_transcription(text: str) -> str:
    simplified = _to_simplified(text).casefold()
    return "".join(
        char for char in simplified
        if not char.isspace() and not unicodedata.category(char).startswith(("P", "S", "Z"))
    )


def score_transcription(expected: str, recognized: str) -> int:
    target = normalize_transcription(expected)
    attempt = normalize_transcription(recognized)
    if not target or not attempt:
        return 0

    previous = list(range(len(attempt) + 1))
    for target_index, target_char in enumerate(target, start=1):
        current = [target_index]
        for attempt_index, attempt_char in enumerate(attempt, start=1):
            substitution_cost = 0 if target_char == attempt_char else 1
            current.append(
                min(
                    current[-1] + 1,
                    previous[attempt_index] + 1,
                    previous[attempt_index - 1] + substitution_cost,
                )
            )
        previous = current

    distance = previous[-1]
    return max(0, round(100 * (1 - distance / max(len(target), len(attempt)))) )