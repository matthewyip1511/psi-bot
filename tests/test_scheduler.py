from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from psi_bot.bot import next_top_of_hour, should_suppress_night_update

SGT = ZoneInfo("Asia/Singapore")


def test_next_top_of_hour() -> None:
    now = datetime(2026, 9, 4, 22, 17, 42, 123, tzinfo=SGT)
    assert next_top_of_hour(now) == datetime(2026, 9, 4, 23, 0, tzinfo=SGT)


def test_next_top_of_hour_rolls_to_next_day() -> None:
    now = datetime(2026, 9, 4, 23, 59, tzinfo=SGT)
    assert next_top_of_hour(now) == datetime(2026, 9, 5, 0, 0, tzinfo=SGT)


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
