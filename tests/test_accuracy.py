from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from psi_bot.bot import (
    CHANNEL_ID_KEY,
    DATA_CLIENT_KEY,
    MAX_READING_AGE_KEY,
    broadcast_air_quality,
)
from psi_bot.config import ConfigurationError, Settings
from psi_bot.data_gov import PSI_URL, DataGovSgClient, DataGovSgError
from psi_bot.formatting import format_air_quality_message
from psi_bot.models import REGION_ORDER, AirQualitySnapshot

NOW = datetime(2026, 9, 5, 4, 5, tzinfo=UTC)
REGIONS = dict.fromkeys(REGION_ORDER, 50)


def snapshot(**changes: object) -> AirQualitySnapshot:
    base = AirQualitySnapshot(
        psi_timestamp=NOW - timedelta(minutes=5),
        pm25_timestamp=NOW - timedelta(minutes=65),
        psi_by_region=REGIONS,
        pm25_by_region=REGIONS,
    )
    return replace(base, **changes)


@pytest.mark.parametrize("field", ["psi_timestamp", "pm25_timestamp"])
@pytest.mark.parametrize(
    ("age", "accepted"),
    [
        (timedelta(minutes=120), True),
        (timedelta(minutes=120, seconds=1), False),
        (-timedelta(minutes=5), True),
        (-timedelta(minutes=5, seconds=1), False),
    ],
)
@pytest.mark.asyncio
async def test_broadcast_checks_each_feed_age(field, age, accepted) -> None:
    reading = snapshot(**{field: NOW - age})
    bot = SimpleNamespace(send_message=AsyncMock())
    application = SimpleNamespace(
        bot=bot,
        bot_data={
            DATA_CLIENT_KEY: SimpleNamespace(fetch_latest=AsyncMock(return_value=reading)),
            CHANNEL_ID_KEY: -1001234567890,
        },
    )
    assert await broadcast_air_quality(application, now=NOW) is accepted
    assert bot.send_message.await_count == int(accepted)


@pytest.mark.asyncio
async def test_configured_age_limit_is_used() -> None:
    bot = SimpleNamespace(send_message=AsyncMock())
    application = SimpleNamespace(
        bot=bot,
        bot_data={
            DATA_CLIENT_KEY: SimpleNamespace(fetch_latest=AsyncMock(return_value=snapshot())),
            CHANNEL_ID_KEY: -1001234567890,
            MAX_READING_AGE_KEY: 60,
        },
    )
    assert await broadcast_air_quality(application, now=NOW) is False
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_different_fresh_timestamps_are_preserved() -> None:
    reading = snapshot()
    reading.validate_freshness(now=NOW, max_age=timedelta(minutes=120))
    message = format_air_quality_message(reading, sent_at=NOW)
    assert "at 12:00 PM SGT" in message
    assert "at 11:00 AM SGT" in message


def payload(url: str, readings: dict) -> dict:
    key = "psi_twenty_four_hourly" if url == PSI_URL else "pm25_one_hourly"
    return {
        "code": 0,
        "data": {"items": [{"timestamp": NOW.isoformat(), "readings": {key: readings}}]},
    }


@pytest.mark.parametrize("bad", [True, False, 50.9, 50.0, "50", None, -1, [], {}])
@pytest.mark.parametrize("bad_psi", [True, False])
@pytest.mark.asyncio
async def test_invalid_reading_prevents_broadcast(bad, bad_psi) -> None:
    def handler(request):
        values = dict(REGIONS)
        if (str(request.url) == PSI_URL) == bad_psi:
            values["north"] = bad
        return httpx.Response(200, json=payload(str(request.url), values))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = DataGovSgClient(client=http_client)
        bot = SimpleNamespace(send_message=AsyncMock())
        application = SimpleNamespace(
            bot=bot, bot_data={DATA_CLIENT_KEY: client, CHANNEL_ID_KEY: -1001234567890}
        )
        assert await broadcast_air_quality(application, now=NOW) is False
        bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_region_is_rejected() -> None:
    def handler(request):
        return httpx.Response(200, json=payload(str(request.url), {"north": 50}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(DataGovSgError, match="readings"):
            await DataGovSgClient(client=http_client).fetch_latest()


@pytest.mark.asyncio
async def test_unknown_regions_do_not_affect_snapshot_or_range() -> None:
    def handler(request):
        return httpx.Response(200, json=payload(str(request.url), {**REGIONS, "extra": 999}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        reading = await DataGovSgClient(client=http_client).fetch_latest()
    assert set(reading.psi_by_region) == set(REGION_ORDER)
    assert set(reading.pm25_by_region) == set(REGION_ORDER)
    # Also protect formatting when snapshots are constructed outside the API client.
    reading = replace(reading, psi_by_region={**REGIONS, "extra": 999})
    message = format_air_quality_message(reading, sent_at=NOW)
    assert "999" not in message
    assert "Singapore range: <b>50–50</b>" in message


@pytest.mark.parametrize("bad", [True, 50.9, "50"])
def test_snapshot_rejects_coerced_values(bad) -> None:
    with pytest.raises(ValueError, match="integers"):
        snapshot(psi_by_region={**REGIONS, "north": bad})


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "bad", ""])
def test_invalid_max_age_configuration(monkeypatch, value) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@air_quality")
    monkeypatch.setenv("MAX_READING_AGE_MINUTES", value)
    with pytest.raises(ConfigurationError, match="MAX_READING_AGE_MINUTES"):
        Settings.from_env()


def test_max_age_configuration_default_and_override(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@air_quality")
    monkeypatch.delenv("MAX_READING_AGE_MINUTES", raising=False)
    assert Settings.from_env().max_reading_age_minutes == 120
    monkeypatch.setenv("MAX_READING_AGE_MINUTES", "90")
    assert Settings.from_env().max_reading_age_minutes == 90
