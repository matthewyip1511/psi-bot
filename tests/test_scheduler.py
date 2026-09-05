from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from psi_bot.bot import build_application, scheduled_broadcast
from psi_bot.config import Settings
from psi_bot.formatting import SGT


@pytest.fixture
def application():
    with patch("psi_bot.bot.DataGovSgClient") as client:
        client.return_value.fetch_latest = AsyncMock()
        yield build_application(Settings("123456:test-token", "@test_channel"))
        client.return_value.fetch_latest.assert_not_awaited()


def test_schedule_has_only_three_daily_slots(application) -> None:
    jobs = application.job_queue.jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.callback is scheduled_broadcast
    trigger = job.job.trigger
    assert str(trigger.timezone) == "Asia/Singapore"

    current = datetime(2026, 12, 31, tzinfo=SGT)
    previous = None
    # Cross midnight and the year boundary, including all overnight hours.
    for day in (current, current + timedelta(days=1)):
        for hour in (9, 14, 20):
            upcoming = trigger.get_next_fire_time(previous, current)
            assert upcoming == day.replace(hour=hour, minute=15)
            previous = upcoming
            current = upcoming + timedelta(microseconds=1)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 6, 9, 14, 59, tzinfo=SGT), datetime(2026, 9, 6, 9, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 9, 15, tzinfo=SGT), datetime(2026, 9, 6, 9, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 9, 15, 1, tzinfo=SGT), datetime(2026, 9, 6, 14, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 14, 15, 1, tzinfo=SGT), datetime(2026, 9, 6, 20, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 20, 15, 1, tzinfo=SGT), datetime(2026, 9, 7, 9, 15, tzinfo=SGT)),
        (datetime(2026, 9, 6, 1, 0, tzinfo=UTC), datetime(2026, 9, 6, 9, 15, tzinfo=SGT)),
    ],
)
def test_starting_bot_waits_for_next_slot(application, now, expected) -> None:
    trigger = application.job_queue.jobs()[0].job.trigger
    assert trigger.get_next_fire_time(None, now) == expected


def test_startup_cannot_send_extra_broadcast(application) -> None:
    assert application.post_init is None
