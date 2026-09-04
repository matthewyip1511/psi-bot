from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from psi_bot.bot import next_broadcast_time, should_suppress_night_update

SGT = ZoneInfo("Asia/Singapore")


def test_next_broadcast_time_before_five_past() -> None:
    now = datetime(2026, 9, 4, 22, 1, 42, 123, tzinfo=SGT)
    assert next_broadcast_time(now) == datetime(2026, 9, 4, 22, 5, tzinfo=SGT)


def test_next_broadcast_time_after_five_past() -> None:
    now = datetime(2026, 9, 4, 22, 17, 42, 123, tzinfo=SGT)
    assert next_broadcast_time(now) == datetime(2026, 9, 4, 23, 5, tzinfo=SGT)


def test_next_broadcast_time_rolls_to_next_day() -> None:
    now = datetime(2026, 9, 4, 23, 59, tzinfo=SGT)
    assert next_broadcast_time(now) == datetime(2026, 9, 5, 0, 5, tzinfo=SGT)


@pytest.mark.parametrize(
    ("hour", "suppressed"),
    [(0, False), (1, False), (2, True), (7, True), (8, False), (23, False)],
)
def test_optional_night_update_boundaries(hour: int, suppressed: bool) -> None:
    timestamp = datetime(2026, 9, 5, hour, 0, tzinfo=SGT)
    assert should_suppress_night_update(timestamp, disabled=True) is suppressed


def test_night_updates_continue_when_flag_is_disabled() -> None:
    timestamp = datetime(2026, 9, 5, 3, 0, tzinfo=SGT)
    assert should_suppress_night_update(timestamp, disabled=False) is False
