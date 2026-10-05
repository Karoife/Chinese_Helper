"""Sends the illustrative image (fetched photo or generated fallback card)
for a sentence, used by the daily push and the /another and /review commands.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List

from telegram import Bot

from data.models import Sentence, Word
from images.pipeline import get_or_create_image

logger = logging.getLogger(__name__)


async def send_sentence_image(bot: Bot, chat_id: int, db_path: str, sentence: Sentence, words: List[Word]) -> None:
    # get_or_create_image does blocking network/file I/O, so it runs off the event loop.
    result = await asyncio.to_thread(get_or_create_image, db_path, sentence, words)
    if result is None:
        return

    path, attribution = result
    try:
        await bot.send_photo(chat_id=chat_id, photo=path, caption=attribution)
    except Exception as exc:  # noqa: BLE001 - never let a Telegram/network hiccup break the flow
        logger.warning("Failed to send sentence image: %s", exc)
