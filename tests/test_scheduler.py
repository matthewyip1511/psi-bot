from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from telegram import Chat, Message, Update
from telegram.constants import ChatType

from psi_bot.bot import (
    build_application,
    private_air_quality_update,
    scheduled_broadcast,
    scheduled_london_forecast,
    scheduled_threshold_broadcast,
)
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


def test_regular_schedule_has_only_four_daily_slots(application) -> None:
    jobs = application.job_queue.jobs()
    assert len(jobs) == 3
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
            assert upcoming == day.replace(hour=hour, minute=5)
            previous = upcoming
            current = upcoming + timedelta(microseconds=1)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 6, 8, 4, 59, tzinfo=SGT), datetime(2026, 9, 6, 8, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 8, 5, tzinfo=SGT), datetime(2026, 9, 6, 8, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 8, 5, 1, tzinfo=SGT), datetime(2026, 9, 6, 12, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 9, 5, tzinfo=SGT), datetime(2026, 9, 6, 12, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 12, 5, 1, tzinfo=SGT), datetime(2026, 9, 6, 16, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 14, 5, tzinfo=SGT), datetime(2026, 9, 6, 16, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 16, 5, 1, tzinfo=SGT), datetime(2026, 9, 6, 20, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 20, 5, 1, tzinfo=SGT), datetime(2026, 9, 7, 8, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 0, 0, tzinfo=UTC), datetime(2026, 9, 6, 8, 5, tzinfo=SGT)),
    ],
)
def test_starting_bot_waits_for_next_slot(application, now, expected) -> None:
    job = next(
        job for job in application.job_queue.jobs() if job.name == "daily-air-quality-broadcast"
    )
    trigger = job.job.trigger
    assert trigger.get_next_fire_time(None, now) == expected


def test_hourly_checks_cover_daytime_without_duplicate_regular_slots(application) -> None:
    regular_job = next(
        job for job in application.job_queue.jobs() if job.name == "daily-air-quality-broadcast"
    )
    threshold_job = next(
        job
        for job in application.job_queue.jobs()
        if job.name == "hourly-air-quality-threshold-check"
    )
    assert threshold_job.callback is scheduled_threshold_broadcast
    assert str(threshold_job.job.trigger.timezone) == "Asia/Singapore"
    start = datetime(2026, 12, 31, tzinfo=SGT)
    end = start + timedelta(days=2)
    slots = []
    for job in (regular_job, threshold_job):
        previous = None
        current = start
        while (upcoming := job.job.trigger.get_next_fire_time(previous, current)) < end:
            slots.append(upcoming)
            previous = upcoming
            current = upcoming + timedelta(microseconds=1)
    assert sorted(slots) == [
        day.replace(hour=hour, minute=5)
        for day in (start, start + timedelta(days=1))
        for hour in range(8, 24)
    ]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 6, 9, 4, 59, tzinfo=SGT), datetime(2026, 9, 6, 9, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 9, 5, tzinfo=SGT), datetime(2026, 9, 6, 9, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 9, 5, 1, tzinfo=SGT), datetime(2026, 9, 6, 10, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 11, 5, 1, tzinfo=SGT), datetime(2026, 9, 6, 13, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 23, 5, tzinfo=SGT), datetime(2026, 9, 6, 23, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 23, 5, 1, tzinfo=SGT), datetime(2026, 9, 7, 9, 5, tzinfo=SGT)),
        (datetime(2026, 9, 6, 1, 0, tzinfo=UTC), datetime(2026, 9, 6, 9, 5, tzinfo=SGT)),
    ],
)
def test_threshold_checks_wait_for_next_slot(application, now, expected) -> None:
    job = next(
        job
        for job in application.job_queue.jobs()
        if job.name == "hourly-air-quality-threshold-check"
    )
    assert job.job.trigger.get_next_fire_time(None, now) == expected


@pytest.mark.asyncio
async def test_scheduled_callbacks_apply_thresholds_only_to_extra_slots() -> None:
    application = SimpleNamespace()
    context = SimpleNamespace(application=application)
    with patch("psi_bot.bot.broadcast_air_quality", new_callable=AsyncMock) as broadcast:
        await scheduled_broadcast(context)
        broadcast.assert_awaited_once_with(application)
        broadcast.reset_mock()
        await scheduled_threshold_broadcast(context)
        broadcast.assert_awaited_once_with(application, threshold_only=True)


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


@pytest.mark.parametrize("text", ["hi", "/start"])
@pytest.mark.parametrize("chat_type", [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP])
def test_air_quality_requests_are_handled_only_in_private_chats(
    application, text, chat_type
) -> None:
    update = Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=datetime(2026, 9, 6, tzinfo=SGT),
            chat=Chat(id=123, type=chat_type),
            text=text,
        ),
    )
    handlers = application.handlers[0]
    assert len(handlers) == 1
    assert handlers[0].callback is private_air_quality_update
    assert bool(handlers[0].check_update(update)) is (chat_type == ChatType.PRIVATE)


def test_channel_posts_are_ignored(application) -> None:
    update = Update(
        update_id=1,
        channel_post=Message(
            message_id=1,
            date=datetime(2026, 9, 6, tzinfo=SGT),
            chat=Chat(id=-100123, type=ChatType.CHANNEL),
            text="channel post",
        ),
    )
    assert not application.handlers[0][0].check_update(update)
