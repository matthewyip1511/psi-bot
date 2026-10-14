"""Telegram application and scheduled Singapore and London broadcasts."""

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
from psi_bot.formatting import SGT, format_air_quality_message, format_london_forecast
from psi_bot.models import REGION_ORDER, AirQualitySnapshot
from psi_bot.open_meteo import LONDON, OpenMeteoClient, OpenMeteoError

LOGGER = logging.getLogger(__name__)
AIR_QUALITY_UNAVAILABLE = "Current air-quality readings are unavailable. Please try again later."
DATA_CLIENT_KEY = "data_gov_sg_client"
CHANNEL_ID_KEY = "telegram_channel_id"
MAX_READING_AGE_KEY = "max_reading_age_minutes"
OPEN_METEO_CLIENT_KEY = "open_meteo_client"


async def _fetch_fresh_air_quality(
    application: Application[Any, Any, Any, Any, Any, Any],
    *,
    now: datetime | None = None,
) -> tuple[AirQualitySnapshot, datetime]:
    client: DataGovSgClient = application.bot_data[DATA_CLIENT_KEY]
    snapshot = await client.fetch_latest()
    # Check after fetching so request delays count toward the reading age.
    sent_at = now or datetime.now(SGT)
    try:
        snapshot.validate_freshness(
            now=sent_at,
            max_age=timedelta(minutes=application.bot_data.get(MAX_READING_AGE_KEY, 120)),
        )
    except ValueError as exc:
        raise DataGovSgError(f"Unusable air-quality timestamps: {exc}") from exc
    return snapshot, sent_at


async def private_air_quality_update(
    update: Update,
    context: CallbackContext[Any, Any, Any, Any],
) -> None:
    """Fetch the latest official readings for every DM, at any time of day."""
    if update.effective_message is None:
        return
    try:
        snapshot, sent_at = await _fetch_fresh_air_quality(context.application)
    except DataGovSgError as exc:
        LOGGER.warning("Could not fetch the requested air-quality update: %s", exc)
        message = AIR_QUALITY_UNAVAILABLE
    else:
        message = format_air_quality_message(snapshot, sent_at=sent_at)
    try:
        await update.effective_message.reply_text(message, parse_mode=ParseMode.HTML)
    except TelegramError as exc:
        LOGGER.exception("Could not send the requested air-quality reply: %s", exc)


async def broadcast_air_quality(
    application: Application[Any, Any, Any, Any, Any, Any],
    *,
    now: datetime | None = None,
    threshold_only: bool = False,
) -> bool:
    channel_id: int | str = application.bot_data[CHANNEL_ID_KEY]
    try:
        snapshot, sent_at = await _fetch_fresh_air_quality(application, now=now)
        if threshold_only and not any(
            snapshot.psi_by_region[region] > 200 or snapshot.pm25_by_region[region] > 150
            for region in REGION_ORDER
        ):
            LOGGER.info("Skipped extra air-quality update: no region exceeds the thresholds")
            return False
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


async def scheduled_threshold_broadcast(context: CallbackContext[Any, Any, Any, Any]) -> None:
    await broadcast_air_quality(context.application, threshold_only=True)


async def broadcast_london_forecast(
    application: Application[Any, Any, Any, Any, Any, Any],
    *,
    now: datetime | None = None,
) -> bool:
    client: OpenMeteoClient = application.bot_data[OPEN_METEO_CLIENT_KEY]
    channel_id: int | str = application.bot_data[CHANNEL_ID_KEY]
    london_now = (now or datetime.now(LONDON)).astimezone(LONDON)
    try:
        forecast = await client.fetch_london_forecast(for_date=london_now.date())
        await application.bot.send_message(
            chat_id=channel_id,
            text=format_london_forecast(forecast),
            parse_mode=ParseMode.HTML,
        )
    except (OpenMeteoError, TelegramError) as exc:
        LOGGER.exception("Could not send the scheduled London forecast: %s", exc)
        return False

    LOGGER.info("Sent London forecast to %s", channel_id)
    return True


async def scheduled_london_forecast(context: CallbackContext[Any, Any, Any, Any]) -> None:
    await broadcast_london_forecast(context.application)


async def on_error(_update: object, context: CallbackContext[Any, Any, Any, Any]) -> None:
    LOGGER.error("Unhandled Telegram update error", exc_info=context.error)


def build_application(settings: Settings) -> Application[Any, Any, Any, Any, Any, Any]:
    client = DataGovSgClient(settings.data_gov_sg_api_key)
    open_meteo_client = OpenMeteoClient()

    async def on_shutdown(_application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        await client.aclose()
        await open_meteo_client.aclose()

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .defaults(Defaults(tzinfo=SGT))
        .post_shutdown(on_shutdown)
        .build()
    )
    application.bot_data[DATA_CLIENT_KEY] = client
    application.bot_data[OPEN_METEO_CLIENT_KEY] = open_meteo_client
    application.bot_data[CHANNEL_ID_KEY] = settings.telegram_channel_id
    application.bot_data[MAX_READING_AGE_KEY] = settings.max_reading_age_minutes
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE, private_air_quality_update))
    application.add_error_handler(on_error)

    if application.job_queue is None:
        raise RuntimeError("JobQueue is unavailable; install the project with its dependencies")
    application.job_queue.run_custom(
        scheduled_broadcast,
        name="daily-air-quality-broadcast",
        job_kwargs={
            "trigger": "cron",
            "hour": "8,12,16,20",
            "minute": 5,
            "second": 0,
            "timezone": SGT,
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )
    application.job_queue.run_custom(
        scheduled_threshold_broadcast,
        name="hourly-air-quality-threshold-check",
        job_kwargs={
            "trigger": "cron",
            # Regular slots already send an update, so do not check them twice.
            "hour": "9-11,13-15,17-19,21-23",
            "minute": 5,
            "second": 0,
            "timezone": SGT,
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )
    application.job_queue.run_custom(
        scheduled_london_forecast,
        name="daily-london-forecast",
        job_kwargs={
            "trigger": "cron",
            "hour": 8,
            "minute": 0,
            "second": 0,
            "timezone": LONDON,
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )
    LOGGER.info("Broadcasts scheduled for 08:05, 12:05, 16:05, and 20:05 Asia/Singapore")
    LOGGER.info(
        "Extra updates checked hourly at :05 from 08:05 through 23:05 Asia/Singapore "
        "when any region has PSI > 200 or PM2.5 > 150; regular slots send only once"
    )
    LOGGER.info("London forecast scheduled for 08:00 Europe/London")
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
