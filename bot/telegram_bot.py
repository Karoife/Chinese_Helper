"""Telegram bot wiring: builds the Application and registers command handlers.

Also exposes `send_daily_update`, used by the scheduler to push the daily
sentence + any due reviews without waiting for a user command.
"""
from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot import commands
from bot.audio_delivery import send_sentence_audio
from bot.formatting import format_sentence_message
from bot.image_delivery import send_sentence_image
from config.config_loader import AppConfig
from data.db import db_session
from data.queries import get_sentence, get_sentence_words, pick_new_sentence
from data.user_state import get_user_state
from data.sources.translate import translate_missing_word_meanings
from srs.spaced_repetition import get_due_reviews, mark_reviewed, record_new_sentence_sent

logger = logging.getLogger(__name__)


def build_application(token: str, db_path: str, config: AppConfig) -> Application:
    application = Application.builder().token(token).build()
    application.bot_data["db_path"] = db_path
    application.bot_data["config"] = config

    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("level", commands.set_level_command))
    application.add_handler(CommandHandler("time", commands.set_time_command))
    application.add_handler(CommandHandler("another", commands.another_command))
    application.add_handler(CommandHandler("review", commands.review_command))
    application.add_handler(CommandHandler("progress", commands.progress_command))
    application.add_handler(CommandHandler("reset", commands.reset_progress_command))
    application.add_handler(CommandHandler("stop", commands.stop_practice_command))
    application.add_handler(CallbackQueryHandler(commands.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, commands.text_input_handler))
    application.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, commands.voice_message_handler)
    )

    return application


async def send_daily_update(application: Application) -> None:
    """Send today's new sentence plus any due reviews to the configured chat."""
    db_path = application.bot_data["db_path"]

    with db_session(db_path) as conn:
        state = get_user_state(conn)
        if state.chat_id is None:
            logger.warning("No chat_id registered yet; run /start in Telegram first.")
            return

        chat_id = state.chat_id
        items = []  # (sentence, words, heading)

        sentence = pick_new_sentence(conn, state.level, state.mode)
        if sentence is not None:
            words = get_sentence_words(conn, sentence.id)
            items.append((sentence, words, "Frase de hoy"))
            record_new_sentence_sent(conn, sentence.id)
        else:
            logger.warning("No new sentences available for level=%s mode=%s", state.level, state.mode)

        due = get_due_reviews(conn)
        for item in due:
            review_sentence = get_sentence(conn, item.sentence_id)
            if review_sentence is None:
                continue
            words = get_sentence_words(conn, review_sentence.id)
            items.append((review_sentence, words, "Repaso"))
            mark_reviewed(conn, item.history_id)

    for sentence, words, heading in items:
        await asyncio.to_thread(translate_missing_word_meanings, db_path, words)
        text = format_sentence_message(sentence, words, heading=heading)
        await application.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=commands.pronunciation_practice_keyboard(sentence.id),
        )
        await send_sentence_image(application.bot, chat_id, db_path, sentence, words)
        await send_sentence_audio(application.bot, chat_id, sentence, words)

