from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from telegram.constants import ParseMode

from psi_bot.bot import (
    CHANNEL_ID_KEY,
    DATA_CLIENT_KEY,
    OPEN_METEO_CLIENT_KEY,
    PRIVATE_NOTICE,
    broadcast_air_quality,
    broadcast_london_forecast,
    private_message_notice,
)
from psi_bot.models import AirQualitySnapshot, LondonForecast


@pytest.mark.asyncio
async def test_private_messages_receive_only_broadcast_notice() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message)

    await private_message_notice(update, None)  # type: ignore[arg-type]

    message.reply_text.assert_awaited_once_with(PRIVATE_NOTICE)
    assert PRIVATE_NOTICE == "This bot is for blasting messages only."


@pytest.mark.asyncio
async def test_broadcast_sends_message_with_html_formatting() -> None:
    sgt = ZoneInfo("Asia/Singapore")
    snapshot = AirQualitySnapshot(
        psi_timestamp=datetime(2026, 9, 4, 23, 0, tzinfo=sgt),
        pm25_timestamp=datetime(2026, 9, 4, 23, 0, tzinfo=sgt),
        psi_by_region={"north": 88, "south": 87, "east": 104, "west": 99, "central": 123},
        pm25_by_region={"north": 45, "south": 43, "east": 57, "west": 62, "central": 76},
    )
    client = SimpleNamespace(fetch_latest=AsyncMock(return_value=snapshot))
    bot = SimpleNamespace(send_message=AsyncMock())
    application = SimpleNamespace(
        bot=bot,
        bot_data={DATA_CLIENT_KEY: client, CHANNEL_ID_KEY: -1001234567890},
    )

    sent = await broadcast_air_quality(
        application, now=datetime(2026, 9, 4, 23, 5, tzinfo=sgt)
    )  # type: ignore[arg-type]

    assert sent is True
    bot.send_message.assert_awaited_once()
    call = bot.send_message.await_args
    assert call.kwargs["chat_id"] == -1001234567890
    assert call.kwargs["parse_mode"] == ParseMode.HTML
    assert "<b>123</b> — <b>Unhealthy</b>" in call.kwargs["text"]


@pytest.mark.asyncio
async def test_london_broadcast_sends_complete_forecast() -> None:
    forecast = LondonForecast(
        date=date(2026, 9, 15),
        temperature_min_c=12,
        temperature_max_c=19,
        precipitation_probability_max=30,
        european_aqi_max=35,
    )
    client = SimpleNamespace(fetch_london_forecast=AsyncMock(return_value=forecast))
    bot = SimpleNamespace(send_message=AsyncMock())
    application = SimpleNamespace(
        bot=bot,
        bot_data={OPEN_METEO_CLIENT_KEY: client, CHANNEL_ID_KEY: "@test_channel"},
    )

    sent = await broadcast_london_forecast(
        application,
        now=datetime(2026, 9, 15, 8, 0, tzinfo=ZoneInfo("Europe/London")),
    )  # type: ignore[arg-type]

    assert sent is True
    client.fetch_london_forecast.assert_awaited_once_with(for_date=date(2026, 9, 15))
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs["parse_mode"] == ParseMode.HTML
    assert "London Daily Forecast" in bot.send_message.await_args.kwargs["text"]
