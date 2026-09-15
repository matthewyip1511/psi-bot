from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from psi_bot.bot import build_application, scheduled_broadcast, scheduled_london_forecast
from psi_bot.config import Settings
from psi_bot.formatting import SGT
from psi_bot.open_meteo import LONDON


@pytest.fixture
def application():
    with (
        patch("psi_bot.bot.DataGovSgClient") as client,
        patch("psi_bot.bot.OpenMeteoClient") as open_meteo_client,
    ):
        client.return_value.fetch_latest = AsyncMock()
        open_meteo_client.return_value.fetch_london_forecast = AsyncMock()
        yield build_application(Settings("123456:test-token", "@test_channel"))
        client.return_value.fetch_latest.assert_not_awaited()
        open_meteo_client.return_value.fetch_london_forecast.assert_not_awaited()


def test_schedule_has_only_four_daily_slots(application) -> None:
    jobs = application.job_queue.jobs()
    assert len(jobs) == 2
    job = next(job for job in jobs if job.name == "daily-air-quality-broadcast")
    assert job.callback is scheduled_broadcast
    trigger = job.job.trigger
    assert str(trigger.timezone) == "Asia/Singapore"

    current = datetime(2026, 12, 31, tzinfo=SGT)
    previous = None
    # Cross midnight and the year boundary, including all overnight hours.
    for day in (current, current + timedelta(days=1)):
        for hour in (8, 12, 16, 20):
            upcoming = trigger.get_next_fire_time(previous, current)
            assert upcoming == day.replace(hour=hour, minute=15)
            previous = upcoming
            current = upcoming + timedelta(microseconds=1)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 6, 8, 14, 59, tzinfo=SGT), datetime(2026, 9, 6, 8, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 8, 15, tzinfo=SGT), datetime(2026, 9, 6, 8, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 8, 15, 1, tzinfo=SGT), datetime(2026, 9, 6, 12, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 9, 15, tzinfo=SGT), datetime(2026, 9, 6, 12, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 12, 15, 1, tzinfo=SGT), datetime(2026, 9, 6, 16, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 14, 15, tzinfo=SGT), datetime(2026, 9, 6, 16, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 16, 15, 1, tzinfo=SGT), datetime(2026, 9, 6, 20, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 20, 15, 1, tzinfo=SGT), datetime(2026, 9, 7, 8, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 0, 0, tzinfo=UTC), datetime(2026, 9, 6, 8, 15, tzinfo=SGT)),
    ],
)
def test_starting_bot_waits_for_next_slot(application, now, expected) -> None:
    job = next(
        job for job in application.job_queue.jobs() if job.name == "daily-air-quality-broadcast"
    )
    trigger = job.job.trigger
    assert trigger.get_next_fire_time(None, now) == expected


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (
            datetime(2026, 3, 28, 8, 0, 1, tzinfo=LONDON),
            datetime(2026, 3, 29, 8, 0, tzinfo=LONDON),
        ),
        (
            datetime(2026, 3, 29, 8, 0, 1, tzinfo=LONDON),
            datetime(2026, 3, 30, 8, 0, tzinfo=LONDON),
        ),
        (
            datetime(2026, 10, 24, 8, 0, 1, tzinfo=LONDON),
            datetime(2026, 10, 25, 8, 0, tzinfo=LONDON),
        ),
        (
            datetime(2026, 10, 25, 8, 0, 1, tzinfo=LONDON),
            datetime(2026, 10, 26, 8, 0, tzinfo=LONDON),
        ),
    ],
)
def test_london_schedule_stays_at_8am_across_dst(application, now, expected) -> None:
    job = next(job for job in application.job_queue.jobs() if job.name == "daily-london-forecast")
    assert job.callback is scheduled_london_forecast
    trigger = job.job.trigger
    assert str(trigger.timezone) == "Europe/London"
    assert trigger.get_next_fire_time(None, now) == expected


def test_startup_cannot_send_extra_broadcast(application) -> None:
    assert application.post_init is None
