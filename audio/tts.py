"""Mandarin text-to-speech with on-disk caching.

Primary engine: `edge-tts` (Microsoft Edge's online TTS, free, natural-sounding
zh-CN voices). Falls back to `gTTS` (Google Translate TTS) if edge-tts fails
or is unreachable, so the app keeps working even if one provider is down.

Every generated clip is cached in `storage/audio/` keyed by a hash of its
text, so the same sentence/word is never synthesized twice.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional

import edge_tts

logger = logging.getLogger(__name__)

VOICE = "zh-CN-XiaoxiaoNeural"
AUDIO_DIR = Path("storage/audio")
MAX_EDGE_TTS_ATTEMPTS = 2


def _cache_path(text: str) -> Path:
    key = hashlib.sha256(f"{VOICE}:{text}".encode("utf-8")).hexdigest()
    return AUDIO_DIR / f"{key}.mp3"


async def _generate_with_edge_tts(text: str, path: Path) -> bool:
    for attempt in range(1, MAX_EDGE_TTS_ATTEMPTS + 1):
        try:
            communicate = edge_tts.Communicate(text, VOICE)
            await communicate.save(str(path))
            if path.exists() and path.stat().st_size > 0:
                return True
        except Exception as exc:  # noqa: BLE001 - network/service errors of many kinds
            logger.warning("edge-tts attempt %d/%d failed for %r: %s", attempt, MAX_EDGE_TTS_ATTEMPTS, text, exc)
    return False


def _generate_with_gtts_sync(text: str, path: Path) -> bool:
    try:
        from gtts import gTTS

        tts = gTTS(text=text, lang="zh-CN")
        tts.save(str(path))
        return path.exists() and path.stat().st_size > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("gTTS fallback failed for %r: %s", text, exc)
        return False


async def get_or_create_audio(text: str) -> Optional[Path]:
    """Return a cached mp3 Path for `text`, generating it if needed."""
    text = text.strip()
    if not text:
        return None

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(text)
    if path.exists():
        return path

    if await _generate_with_edge_tts(text, path):
        return path

    logger.info("Falling back to gTTS for %r", text)
    if await asyncio.to_thread(_generate_with_gtts_sync, text, path):
        return path

    logger.error("Could not generate audio for %r with any TTS provider", text)
    path.unlink(missing_ok=True)
    return None
