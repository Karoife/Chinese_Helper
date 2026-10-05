"""Sends the TTS audio (full sentence + key words) for a given sentence,
used by both the daily scheduled push and the /another and /review commands.
"""
from __future__ import annotations

import logging
from typing import List

from telegram import Bot

from audio.tts import get_or_create_audio
from data.models import Sentence, Word

logger = logging.getLogger(__name__)

MAX_WORD_AUDIOS = 8  # avoid flooding the chat for unusually long sentences


async def send_sentence_audio(bot: Bot, chat_id: int, sentence: Sentence, words: List[Word]) -> None:
    sentence_audio = await get_or_create_audio(sentence.chinese)
    if sentence_audio:
        try:
            await bot.send_audio(chat_id=chat_id, audio=sentence_audio, title=sentence.chinese)
        except Exception as exc:  # noqa: BLE001 - never let a Telegram/network hiccup break the flow
            logger.warning("Failed to send sentence audio: %s", exc)
    else:
        logger.warning("No audio available for sentence %r", sentence.chinese)

    for word in words[:MAX_WORD_AUDIOS]:
        word_audio = await get_or_create_audio(word.simplified)
        if not word_audio:
            continue
        try:
            await bot.send_voice(
                chat_id=chat_id, voice=word_audio, caption=f"{word.simplified} ({word.pinyin})"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send word audio for %r: %s", word.simplified, exc)
