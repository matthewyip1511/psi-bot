from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from telegram.constants import ParseMode
from telegram.error import TelegramError

from psi_bot.bot import (
    AIR_QUALITY_UNAVAILABLE,
    CHANNEL_ID_KEY,
    DATA_CLIENT_KEY,
    MAX_READING_AGE_KEY,
    OPEN_METEO_CLIENT_KEY,
    broadcast_air_quality,
    broadcast_london_forecast,
    private_air_quality_update,
)
from psi_bot.data_gov import DataGovSgError
from psi_bot.formatting import format_air_quality_message
from psi_bot.models import REGION_ORDER, AirQualitySnapshot, LondonForecast


@pytest.fixture
def air_quality_application():
    now = datetime(2026, 9, 4, 9, 5, tzinfo=ZoneInfo("Asia/Singapore"))

    def create(psi=200, pm25=150, region="north", **timestamps):
        snapshot = AirQualitySnapshot(
            psi_timestamp=timestamps.get("psi_timestamp", now - timedelta(minutes=5)),
            pm25_timestamp=timestamps.get("pm25_timestamp", now - timedelta(minutes=65)),
            psi_by_region={**dict.fromkeys(REGION_ORDER, 50), region: psi},
            pm25_by_region={**dict.fromkeys(REGION_ORDER, 50), region: pm25},
        )
        return SimpleNamespace(
            bot=SimpleNamespace(send_message=AsyncMock()),
            bot_data={
                DATA_CLIENT_KEY: SimpleNamespace(fetch_latest=AsyncMock(return_value=snapshot)),
                CHANNEL_ID_KEY: "@test_channel",
            },
        )

    return now, create


@pytest.mark.parametrize("region", REGION_ORDER)
@pytest.mark.parametrize(
    ("psi", "pm25", "expected"),
    [(199, 149, False), (200, 150, False), (201, 150, True), (200, 151, True), (201, 151, True)],
)
@pytest.mark.asyncio
async def test_extra_posts_use_strict_thresholds_in_any_region(
    air_quality_application, region, psi, pm25, expected
) -> None:
    now, create = air_quality_application
    application = create(psi, pm25, region)
    assert await broadcast_air_quality(application, now=now, threshold_only=True) is expected
    application.bot_data[DATA_CLIENT_KEY].fetch_latest.assert_awaited_once()
    assert application.bot.send_message.await_count == int(expected)


@pytest.mark.parametrize(("psi", "pm25"), [(50, 50), (200, 150), (201, 151)])
@pytest.mark.asyncio
async def test_regular_posts_ignore_thresholds(air_quality_application, psi, pm25) -> None:
    now, create = air_quality_application
    application = create(psi, pm25)
    assert await broadcast_air_quality(application, now=now) is True
    application.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_persistent_high_readings_send_again_at_next_hour(air_quality_application) -> None:
    now, create = air_quality_application
    application = create(201, 151, pm25_timestamp=now - timedelta(minutes=5))
    for sent_at in (now, now + timedelta(hours=1)):
        assert await broadcast_air_quality(application, now=sent_at, threshold_only=True) is True
    assert application.bot_data[DATA_CLIENT_KEY].fetch_latest.await_count == 2
    assert application.bot.send_message.await_count == 2


@pytest.mark.parametrize("field", ["psi_timestamp", "pm25_timestamp"])
@pytest.mark.parametrize("age", [timedelta(minutes=121), -timedelta(minutes=6)])
@pytest.mark.asyncio
async def test_extra_posts_reject_unusable_feed_timestamps(
    air_quality_application, field, age
) -> None:
    now, create = air_quality_application
    application = create(201, 151, **{field: now - age})
    assert await broadcast_air_quality(application, now=now, threshold_only=True) is False
    application.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_extra_post_skips_failed_fetch_after_success(air_quality_application) -> None:
    now, create = air_quality_application
    application = create(201, 151)
    assert await broadcast_air_quality(application, now=now, threshold_only=True) is True
    application.bot.send_message.reset_mock()
    client = application.bot_data[DATA_CLIENT_KEY]
    client.fetch_latest.side_effect = DataGovSgError("Feed unavailable")
    assert await broadcast_air_quality(application, now=now, threshold_only=True) is False
    application.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_extra_post_handles_telegram_failure(air_quality_application) -> None:
    now, create = air_quality_application
    application = create(201, 151)
    application.bot.send_message.side_effect = TelegramError("Send failed")
    assert await broadcast_air_quality(application, now=now, threshold_only=True) is False


@pytest.mark.parametrize("hour", [0, 7, 9, 23])
@pytest.mark.asyncio
async def test_private_messages_fetch_current_readings_at_any_hour(
    air_quality_application, hour
) -> None:
    now, create = air_quality_application
    now = now.replace(hour=hour)
    application = create(
        50, 50,
        psi_timestamp=now - timedelta(minutes=5),
        pm25_timestamp=now - timedelta(minutes=65),
    )
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(application=application)
    client = application.bot_data[DATA_CLIENT_KEY]

    with patch("psi_bot.bot.datetime") as clock:
        clock.now.return_value = now
        await private_air_quality_update(update, context)

    client.fetch_latest.assert_awaited_once()
    message.reply_text.assert_awaited_once_with(
        format_air_quality_message(client.fetch_latest.return_value, sent_at=now),
        parse_mode=ParseMode.HTML,
    )
    application.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_each_dm_fetches_new_readings_and_does_not_reuse_last_reply(
    air_quality_application,
) -> None:
    now, create = air_quality_application
    application = create(50, 50)
    client = application.bot_data[DATA_CLIENT_KEY]
    next_snapshot = create(201, 151).bot_data[DATA_CLIENT_KEY].fetch_latest.return_value
    client.fetch_latest.side_effect = [client.fetch_latest.return_value, next_snapshot]
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(application=application)
    with patch("psi_bot.bot.datetime") as clock:
        clock.now.return_value = now
        await private_air_quality_update(update, context)
        await private_air_quality_update(update, context)
    assert client.fetch_latest.await_count == 2
    assert message.reply_text.await_count == 2
    first, second = message.reply_text.await_args_list
    assert first.args[0] != second.args[0]
    assert second.args[0] == format_air_quality_message(next_snapshot, sent_at=now)
    application.bot.send_message.assert_not_awaited()


@pytest.mark.parametrize("field", ["psi_timestamp", "pm25_timestamp"])
@pytest.mark.parametrize("age", [timedelta(minutes=121), -timedelta(minutes=6)])
@pytest.mark.asyncio
async def test_dm_rejects_unusable_feed_timestamps(air_quality_application, field, age) -> None:
    now, create = air_quality_application
    application = create(201, 151, **{field: now - age})
    message = SimpleNamespace(reply_text=AsyncMock())
    with patch("psi_bot.bot.datetime") as clock:
        clock.now.return_value = now
        await private_air_quality_update(
            SimpleNamespace(effective_message=message),
            SimpleNamespace(application=application),
        )
    message.reply_text.assert_awaited_once_with(AIR_QUALITY_UNAVAILABLE, parse_mode=ParseMode.HTML)
    application.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_uses_configured_freshness_limit(air_quality_application) -> None:
    now, create = air_quality_application
    application = create()
    application.bot_data[MAX_READING_AGE_KEY] = 60
    message = SimpleNamespace(reply_text=AsyncMock())
    with patch("psi_bot.bot.datetime") as clock:
        clock.now.return_value = now
        await private_air_quality_update(
            SimpleNamespace(effective_message=message),
            SimpleNamespace(application=application),
        )
    message.reply_text.assert_awaited_once_with(AIR_QUALITY_UNAVAILABLE, parse_mode=ParseMode.HTML)
    application.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_reports_failed_fetch_without_reusing_previous_readings(
    air_quality_application,
) -> None:
    now, create = air_quality_application
    application = create()
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(application=application)
    with patch("psi_bot.bot.datetime") as clock:
        clock.now.return_value = now
        await private_air_quality_update(update, context)
        message.reply_text.reset_mock()
        client = application.bot_data[DATA_CLIENT_KEY]
        client.fetch_latest.side_effect = DataGovSgError("API failed")
        await private_air_quality_update(update, context)
    message.reply_text.assert_awaited_once_with(AIR_QUALITY_UNAVAILABLE, parse_mode=ParseMode.HTML)
    application.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_handles_telegram_reply_failure(air_quality_application) -> None:
    now, create = air_quality_application
    application = create()
    message = SimpleNamespace(reply_text=AsyncMock(side_effect=TelegramError("Reply failed")))
    with patch("psi_bot.bot.datetime") as clock:
        clock.now.return_value = now
        await private_air_quality_update(
            SimpleNamespace(effective_message=message),
            SimpleNamespace(application=application),
        )
    message.reply_text.assert_awaited_once()
    application.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_without_message_does_not_fetch(air_quality_application) -> None:
    _now, create = air_quality_application
    application = create()
    await private_air_quality_update(
        SimpleNamespace(effective_message=None), SimpleNamespace(application=application)
    )
    application.bot_data[DATA_CLIENT_KEY].fetch_latest.assert_not_awaited()
    application.bot.send_message.assert_not_awaited()


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
