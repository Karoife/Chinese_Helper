"""Schedules the daily Telegram message using APScheduler's AsyncIOScheduler,
which shares the same asyncio event loop as python-telegram-bot.
"""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from bot.telegram_bot import send_daily_update

logger = logging.getLogger(__name__)

JOB_ID = "daily_send"


def _cron_trigger(send_time: str, timezone: str) -> CronTrigger:
    hour, minute = send_time.split(":")
    return CronTrigger(hour=int(hour), minute=int(minute), timezone=ZoneInfo(timezone))


def start_scheduler(application: Application, send_time: str, timezone: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def job() -> None:
        logger.info("Running daily job")
        await send_daily_update(application)

    scheduler.add_job(job, trigger=_cron_trigger(send_time, timezone), id=JOB_ID, replace_existing=True)

    def reschedule(new_send_time: str) -> None:
        scheduler.add_job(
            job, trigger=_cron_trigger(new_send_time, timezone), id=JOB_ID, replace_existing=True
        )
        logger.info("Rescheduled daily job to %s (%s)", new_send_time, timezone)

    application.bot_data["reschedule_callback"] = reschedule
    scheduler.start()
    logger.info("Daily job scheduled at %s (%s)", send_time, timezone)
    return scheduler
