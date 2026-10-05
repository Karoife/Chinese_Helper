"""Telegram command handlers. Shared objects (db path, config, scheduler
reschedule callback) are stashed in `context.application.bot_data`.
"""
from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from datetime import datetime
from html import escape
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from audio.pronunciation import score_transcription, transcribe_mandarin
from config.config_loader import save_config
from data.db import db_session
from data.queries import get_progress, get_sentence, get_sentence_words, pick_new_sentence
from data.sources.hsk_vocab import LEVEL_SOURCES
from data.user_state import get_user_state, set_chat_id, set_level, set_send_time
from srs.spaced_repetition import get_due_reviews, mark_reviewed, record_new_sentence_sent
from bot.audio_delivery import send_sentence_audio
from bot.formatting import format_progress, format_sentence_message
from bot.image_delivery import send_sentence_image
from data.sources.translate import translate_missing_word_meanings

logger = logging.getLogger(__name__)

MIN_LEVEL = min(level for level, _ in LEVEL_SOURCES)
MAX_LEVEL = max(level for level, _ in LEVEL_SOURCES)
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📖 Otra frase", callback_data="action:another"),
                InlineKeyboardButton("🔁 Repasar", callback_data="action:review"),
            ],
            [
                InlineKeyboardButton("📊 Progreso", callback_data="action:progress"),
                InlineKeyboardButton("🎚 Nivel", callback_data="menu:level"),
                InlineKeyboardButton("🕒 Hora", callback_data="menu:time"),
            ],
            [InlineKeyboardButton("🗑 Reiniciar progreso", callback_data="action:reset")],
            [InlineKeyboardButton("🧹 Vaciar chat", callback_data="action:clear_chat")],
        ]
    )


def pronunciation_practice_keyboard(sentence_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎤 Practicar pronunciación", callback_data=f"practice:start:{sentence_id}")]]
    )


def stop_practice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Terminar práctica", callback_data="practice:stop")]]
    )


def reset_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Sí, reiniciar", callback_data="progress:reset:confirm"),
            InlineKeyboardButton("Cancelar", callback_data="progress:reset:cancel"),
        ]]
    )


def _mode_label(mode: str) -> str:
    return "solo el nivel elegido" if mode == "level_only" else "ese nivel y los anteriores"


def _level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"HSK {level}", callback_data=f"level:{level}") for level in range(1, 8)]]
    )


def _mode_keyboard(level: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Solo ese nivel", callback_data=f"mode:only:{level}"),
            InlineKeyboardButton("Ese nivel y anteriores", callback_data=f"mode:below:{level}"),
        ]]
    )


def _time_keyboard() -> InlineKeyboardMarkup:
    choices = ("06:00", "08:00", "12:00", "18:00")
    rows = [[InlineKeyboardButton(value, callback_data=f"time:{value}") for value in choices[:2]]]
    rows.append([InlineKeyboardButton(value, callback_data=f"time:{value}") for value in choices[2:]])
    rows.append([InlineKeyboardButton("Escribir otra hora", callback_data="time:custom")])
    return InlineKeyboardMarkup(rows)


def _db_path(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.application.bot_data["db_path"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_path = _db_path(context)
    chat_id = update.effective_chat.id
    with db_session(db_path) as conn:
        set_chat_id(conn, chat_id)
        state = get_user_state(conn)

    await update.effective_message.reply_html(
        "¡Bienvenido/a a tu práctica diaria de chino! 🀄\n\n"
        f"Nivel actual: HSK {state.level}\n"
        f"Modo: {_mode_label(state.mode)}\n"
        "\n"
        "Usa los botones para estudiar o cambiar tu configuración. También puedes "
        "escribir /level, /time, /reset o /stop en el menú de comandos. Reiniciar "
        "borra el historial de estudio, pero conserva tu nivel y horario.",
        reply_markup=main_menu_keyboard(),
    )


async def set_level_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text(
            f"Uso: /level N [only|below], con N entre {MIN_LEVEL} y {MAX_LEVEL}. "
            "Usa only para estudiar solo ese nivel o below para incluir los anteriores."
        )
        return

    level = int(args[0])
    if not (MIN_LEVEL <= level <= MAX_LEVEL):
        await update.effective_message.reply_text(f"El nivel debe estar entre {MIN_LEVEL} y {MAX_LEVEL}.")
        return

    mode = None
    if len(args) > 1:
        choice = args[1].lower()
        if choice == "only":
            mode = "level_only"
        elif choice == "below":
            mode = "level_and_below"
        else:
            await update.effective_message.reply_text(
                "El segundo argumento debe ser 'only' (solo ese nivel) o 'below' (ese nivel y los anteriores)."
            )
            return

    db_path = _db_path(context)
    with db_session(db_path) as conn:
        set_level(conn, level, mode)
        state = get_user_state(conn)

    config = context.application.bot_data["config"]
    config.study.level = state.level
    config.study.mode = state.mode
    save_config(config)

    await update.effective_message.reply_text(
        f"Listo. Nivel: HSK {state.level}; modo: {_mode_label(state.mode)}."
    )


async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not TIME_RE.match(args[0]):
        await update.effective_message.reply_text(
            "Uso: /time HH:MM (formato de 24 horas, por ejemplo /time 08:30)."
        )
        return

    send_time = args[0]
    db_path = _db_path(context)
    with db_session(db_path) as conn:
        set_send_time(conn, send_time)

    config = context.application.bot_data["config"]
    config.study.send_time = send_time
    save_config(config)

    reschedule = context.application.bot_data.get("reschedule_callback")
    if reschedule:
        reschedule(send_time)

    await update.effective_message.reply_text(f"La hora de envío diario cambió a las {send_time}.")


async def another_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_path = _db_path(context)
    with db_session(db_path) as conn:
        state = get_user_state(conn)
        sentence = pick_new_sentence(conn, state.level, state.mode)
        if sentence is None:
            await update.effective_message.reply_text(
                "No quedan frases nuevas para tu nivel. Prueba subir de nivel o "
                "ejecuta `python -m data.build_library` para ampliar la biblioteca."
            )
            return
        words = get_sentence_words(conn, sentence.id)
        record_new_sentence_sent(conn, sentence.id)

    await asyncio.to_thread(translate_missing_word_meanings, db_path, words)
    text = format_sentence_message(sentence, words, heading="Otra frase")
    await update.effective_message.reply_html(
        text, reply_markup=pronunciation_practice_keyboard(sentence.id)
    )
    await send_sentence_image(context.bot, update.effective_chat.id, db_path, sentence, words)
    await send_sentence_audio(context.bot, update.effective_chat.id, sentence, words)


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_path = _db_path(context)
    with db_session(db_path) as conn:
        due = get_due_reviews(conn)
        if not due:
            await update.effective_message.reply_text("No tienes repasos pendientes hoy. 🎉")
            return

        to_review = []
        for item in due[:5]:  # avoid flooding the chat in one command
            sentence = get_sentence(conn, item.sentence_id)
            if sentence is None:
                continue
            words = get_sentence_words(conn, sentence.id)
            to_review.append((sentence, words))
            mark_reviewed(conn, item.history_id)

    unique_words = {
        (word.id if word.id > 0 else word.simplified): word
        for _, words in to_review
        for word in words
    }
    await asyncio.to_thread(
        translate_missing_word_meanings, db_path, list(unique_words.values())
    )

    for sentence, words in to_review:
        text = format_sentence_message(sentence, words, heading="Repaso")
        await update.effective_message.reply_html(
            text, reply_markup=pronunciation_practice_keyboard(sentence.id)
        )
        await send_sentence_image(context.bot, update.effective_chat.id, db_path, sentence, words)
        await send_sentence_audio(context.bot, update.effective_chat.id, sentence, words)

    if len(due) > 5:
        await update.effective_message.reply_text(
            f"Quedan {len(due) - 5} repasos pendientes. Pulsa Repasar de nuevo para continuar."
        )


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_path = _db_path(context)
    with db_session(db_path) as conn:
        state = get_user_state(conn)
        stats = get_progress(conn)
    await update.effective_message.reply_html(format_progress(stats, state.level, state.mode))


async def reset_progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "¿Seguro que quieres borrar todo el historial de estudio y las prácticas activas? "
        "Tu nivel, horario y biblioteca no cambiarán.",
        reply_markup=reset_confirmation_keyboard(),
    )


async def clear_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Telegram no permite que el bot borre todo el historial del chat. "
        "Para vaciarlo, abre el menú del chat en Telegram y elige «Vaciar chat» "
        "o «Borrar historial». Esta acción la confirma Telegram."
    )


def _finish_practice(db_path: str, chat_id: int) -> str:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT attempts, last_score FROM pronunciation_practice WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        conn.execute("DELETE FROM pronunciation_practice WHERE chat_id = ?", (chat_id,))
    if row is None:
        return "No hay una práctica de pronunciación activa."
    if row["attempts"]:
        return (
            f"Práctica terminada: {row['attempts']} intentos. "
            f"Última puntuación: {row['last_score']}/100."
        )
    return "Práctica terminada. No se recibieron audios."


async def stop_practice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = _finish_practice(_db_path(context), update.effective_chat.id)
    await update.effective_message.reply_text(result, reply_markup=main_menu_keyboard())


async def voice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    db_path = _db_path(context)
    with db_session(db_path) as conn:
        session = conn.execute(
            """
            SELECT p.sentence_id, p.attempts, s.chinese, s.pinyin
            FROM pronunciation_practice p
            JOIN sentences s ON s.id = p.sentence_id
            WHERE p.chat_id = ?
            """,
            (chat_id,),
        ).fetchone()

    if session is None:
        await update.effective_message.reply_text(
            "Primero pulsa «Practicar pronunciación» debajo de una frase."
        )
        return

    media = update.effective_message.voice or update.effective_message.audio
    audio_path = None
    try:
        telegram_file = await media.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temporary_file:
            audio_path = Path(temporary_file.name)
        await telegram_file.download_to_drive(custom_path=str(audio_path))
        transcript = await asyncio.to_thread(transcribe_mandarin, audio_path)
    except Exception as exc:
        logger.warning("Pronunciation audio transcription failed: %s", exc)
        await update.effective_message.reply_text(
            "No pude reconocer ese audio. Inténtalo otra vez o pulsa «Terminar práctica»."
        )
        return
    finally:
        if audio_path is not None:
            audio_path.unlink(missing_ok=True)

    score = score_transcription(session["chinese"], transcript)
    attempt_number = session["attempts"] + 1
    with db_session(db_path) as conn:
        updated = conn.execute(
            """
            UPDATE pronunciation_practice
            SET attempts = ?, last_score = ?
            WHERE chat_id = ? AND sentence_id = ?
            """,
            (attempt_number, score, chat_id, session["sentence_id"]),
        )
    if updated.rowcount == 0:
        await update.effective_message.reply_text("La práctica ya terminó; no guardé este intento.")
        return

    recognized = escape(transcript) if transcript else "No se reconoció ninguna frase."
    await update.effective_message.reply_html(
        f"Intento {attempt_number}: <b>{score}/100</b> de coincidencia aproximada.\n"
        f"Frase objetivo: {escape(session['chinese'])}\n"
        f"Pinyin: <i>{escape(session['pinyin'])}</i>\n"
        f"Transcripción: {recognized}",
        reply_markup=stop_practice_keyboard(),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    actions = {
        "action:another": another_command,
        "action:review": review_command,
        "action:progress": progress_command,
        "action:reset": reset_progress_command,
        "action:clear_chat": clear_chat_command,
    }
    if data in actions:
        await actions[data](update, context)
    elif data == "menu:level":
        await query.message.reply_text("Elige tu nivel HSK:", reply_markup=_level_keyboard())
    elif data.startswith("level:"):
        level = int(data.split(":", 1)[1])
        await query.message.reply_text(
            f"Para HSK {level}, ¿quieres estudiar solo ese nivel o también los anteriores?",
            reply_markup=_mode_keyboard(level),
        )
    elif data.startswith("mode:"):
        _, mode_choice, level_text = data.split(":")
        level = int(level_text)
        mode = "level_only" if mode_choice == "only" else "level_and_below"
        with db_session(_db_path(context)) as conn:
            set_level(conn, level, mode)
        config = context.application.bot_data["config"]
        config.study.level = level
        config.study.mode = mode
        save_config(config)
        await query.message.reply_text(f"Listo. Nivel HSK {level}; modo: {_mode_label(mode)}.")
    elif data == "menu:time":
        await query.message.reply_text(
            "Elige una hora para Costa Rica o escribe otra hora:", reply_markup=_time_keyboard()
        )
    elif data == "time:custom":
        context.user_data["awaiting_time"] = True
        await query.message.reply_text("Escribe la hora en formato de 24 horas, por ejemplo 08:30.")
    elif data.startswith("time:"):
        send_time = data.split(":", 1)[1]
        context.user_data.pop("awaiting_time", None)
        await _save_send_time(context, send_time)
        await query.message.reply_text(f"La hora de envío diario cambió a las {send_time}.")
    elif data.startswith("practice:start:"):
        sentence_id = int(data.rsplit(":", 1)[1])
        with db_session(_db_path(context)) as conn:
            sentence = get_sentence(conn, sentence_id)
            if sentence is None:
                await query.message.reply_text("No encontré esa frase en la biblioteca.")
                return
            conn.execute(
                """
                INSERT INTO pronunciation_practice (chat_id, sentence_id, started_at, attempts, last_score)
                VALUES (?, ?, ?, 0, NULL)
                ON CONFLICT (chat_id) DO UPDATE SET
                    sentence_id = excluded.sentence_id,
                    started_at = excluded.started_at,
                    attempts = 0,
                    last_score = NULL
                """,
                (update.effective_chat.id, sentence_id, datetime.now().isoformat()),
            )
        await query.message.reply_html(
            f"Práctica iniciada. Lee esta misma frase en voz alta y envíala como audio:\n\n"
            f"<b>{escape(sentence.chinese)}</b>\n"
            f"<i>{escape(sentence.pinyin)}</i>\n"
            "Puedes repetirla cuantas veces quieras; pulsa «Terminar práctica» cuando decidas parar.",
            reply_markup=stop_practice_keyboard(),
        )
    elif data == "practice:stop":
        result = _finish_practice(_db_path(context), update.effective_chat.id)
        await query.message.reply_text(result, reply_markup=main_menu_keyboard())
    elif data == "progress:reset:confirm":
        with db_session(_db_path(context)) as conn:
            conn.execute("DELETE FROM sentence_history")
            conn.execute("DELETE FROM pronunciation_practice")
        await query.message.reply_text(
            "Progreso reiniciado. Se conservaron tu nivel, horario y biblioteca.",
            reply_markup=main_menu_keyboard(),
        )
    elif data == "progress:reset:cancel":
        await query.message.reply_text("No se borró tu progreso.", reply_markup=main_menu_keyboard())


async def _save_send_time(context: ContextTypes.DEFAULT_TYPE, send_time: str) -> None:
    with db_session(_db_path(context)) as conn:
        set_send_time(conn, send_time)
    config = context.application.bot_data["config"]
    config.study.send_time = send_time
    save_config(config)
    reschedule = context.application.bot_data.get("reschedule_callback")
    if reschedule:
        reschedule(send_time)


async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_time"):
        return
    send_time = (update.effective_message.text or "").strip()
    if not TIME_RE.fullmatch(send_time):
        await update.effective_message.reply_text(
            "No reconozco esa hora. Escríbela como HH:MM, por ejemplo 08:30."
        )
        return
    context.user_data.pop("awaiting_time", None)
    await _save_send_time(context, send_time)
    await update.effective_message.reply_text(f"La hora de envío diario cambió a las {send_time}.")
