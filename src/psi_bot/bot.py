"""Telegram application and hourly scheduler."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    Defaults,
    MessageHandler,
    filters,
)

from psi_bot.config import ConfigurationError, Settings
from psi_bot.data_gov import DataGovSgClient, DataGovSgError
from psi_bot.formatting import SGT, format_air_quality_message

LOGGER = logging.getLogger(__name__)
PRIVATE_NOTICE = "This bot is for blasting messages only."
DATA_CLIENT_KEY = "data_gov_sg_client"
CHANNEL_ID_KEY = "telegram_channel_id"
DISABLE_NIGHT_UPDATES_KEY = "disable_night_updates"
NIGHT_START_HOUR = 2
NIGHT_END_HOUR = 8
BROADCAST_MINUTE = 5


def next_broadcast_time(now: datetime | None = None) -> datetime:
    """Return the next HH:05 broadcast time in Singapore."""
    current = (now or datetime.now(SGT)).astimezone(SGT)
    candidate = current.replace(minute=BROADCAST_MINUTE, second=0, microsecond=0)
    if candidate <= current:
        candidate += timedelta(hours=1)
    return candidate


def should_suppress_night_update(timestamp: datetime, *, disabled: bool) -> bool:
    """Return whether a broadcast falls within the optional 02:00–07:59 SGT quiet period."""
    hour = timestamp.astimezone(SGT).hour
    return disabled and NIGHT_START_HOUR <= hour < NIGHT_END_HOUR


async def private_message_notice(
    update: Update,
    _context: CallbackContext[Any, Any, Any, Any],
) -> None:
    """Reply to DMs without exposing any interactive bot features."""
    if update.effective_message is not None:
        await update.effective_message.reply_text(PRIVATE_NOTICE)


async def broadcast_air_quality(
    application: Application[Any, Any, Any, Any, Any, Any],
    *,
    now: datetime | None = None,
) -> bool:
    sent_at = now or datetime.now(SGT)
    if should_suppress_night_update(
        sent_at,
        disabled=application.bot_data.get(DISABLE_NIGHT_UPDATES_KEY, False),
    ):
        LOGGER.info("Skipping air-quality update during the 02:00–07:59 SGT quiet period")
        return False

    client: DataGovSgClient = application.bot_data[DATA_CLIENT_KEY]
    channel_id: int | str = application.bot_data[CHANNEL_ID_KEY]
    try:
        snapshot = await client.fetch_latest()
        message = format_air_quality_message(snapshot, sent_at=sent_at)
        await application.bot.send_message(
            chat_id=channel_id,
            text=message,
            parse_mode=ParseMode.HTML,
        )
    except (DataGovSgError, TelegramError) as exc:
        LOGGER.exception("Could not send the scheduled air-quality update: %s", exc)
        return False

    LOGGER.info("Sent air-quality update to %s", channel_id)
    return True


async def scheduled_broadcast(context: CallbackContext[Any, Any, Any, Any]) -> None:
    await broadcast_air_quality(context.application)


async def on_error(_update: object, context: CallbackContext[Any, Any, Any, Any]) -> None:
    LOGGER.error("Unhandled Telegram update error", exc_info=context.error)


def build_application(settings: Settings) -> Application[Any, Any, Any, Any, Any, Any]:
    client = DataGovSgClient(settings.data_gov_sg_api_key)

    async def on_startup(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        if settings.send_on_startup:
            LOGGER.info("SEND_ON_STARTUP is enabled; attempting an initial update")
            await broadcast_air_quality(application)

    async def on_shutdown(_application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        await client.aclose()

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .defaults(Defaults(tzinfo=SGT))
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )
    application.bot_data[DATA_CLIENT_KEY] = client
    application.bot_data[CHANNEL_ID_KEY] = settings.telegram_channel_id
    application.bot_data[DISABLE_NIGHT_UPDATES_KEY] = settings.disable_night_updates
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE, private_message_notice))
    application.add_error_handler(on_error)

    if application.job_queue is None:
        raise RuntimeError("JobQueue is unavailable; install the project with its dependencies")
    first_run = next_broadcast_time()
    application.job_queue.run_repeating(
        scheduled_broadcast,
        interval=timedelta(hours=1),
        first=first_run,
        name="hourly-air-quality-broadcast",
        job_kwargs={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )
    LOGGER.info("First hourly broadcast scheduled for %s", first_run.isoformat())
    return application


def main() -> None:
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    application = build_application(settings)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
