"""Entry point: on first run, downloads the study library, then starts the
Telegram bot and the daily-message scheduler.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand

from bot.telegram_bot import build_application
from config.config_loader import load_config
from data.build_library import build_sentences, build_words
from data.db import init_db, library_is_populated

logger = logging.getLogger(__name__)


def _setup_logging(level: str, log_file: str) -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token.startswith("123456"):
        raise SystemExit(
            "Falta configurar TELEGRAM_BOT_TOKEN en el archivo .env (ver README.md)."
        )

    config = load_config()
    _setup_logging(config.log_level, config.log_file)
    init_db(config.db_path)

    if not library_is_populated(config.db_path):
        logger.info(
            "Primera ejecucion detectada: descargando la biblioteca de HSK y Tatoeba. "
            "Esto puede tardar bastantes minutos (se traduce cada palabra una sola vez)."
        )
        build_words(config.db_path, limit=None)
        build_sentences(config.db_path, limit=None)
        logger.info("Biblioteca lista.")

    application = build_application(token, config.db_path, config)

    from scheduler.daily_job import start_scheduler

    async def post_init(app):
        await app.bot.set_my_commands(
            [
                BotCommand("start", "Mostrar bienvenida y botones"),
                BotCommand("level", "Cambiar nivel HSK"),
                BotCommand("time", "Cambiar hora diaria"),
                BotCommand("another", "Recibir otra frase"),
                BotCommand("review", "Repasar frases pendientes"),
                BotCommand("progress", "Ver mi progreso"),
                BotCommand("reset", "Reiniciar progreso (con confirmación)"),
                BotCommand("stop", "Terminar práctica de pronunciación"),
            ]
        )
        start_scheduler(app, config.study.send_time, config.study.timezone)

    application.post_init = post_init
    application.run_polling()


if __name__ == "__main__":
    main()
