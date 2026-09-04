from datetime import datetime
from zoneinfo import ZoneInfo

from psi_bot.bot import next_top_of_hour

SGT = ZoneInfo("Asia/Singapore")


def test_next_top_of_hour() -> None:
    now = datetime(2026, 9, 4, 22, 17, 42, 123, tzinfo=SGT)
    assert next_top_of_hour(now) == datetime(2026, 9, 4, 23, 0, tzinfo=SGT)


def test_next_top_of_hour_rolls_to_next_day() -> None:
    now = datetime(2026, 9, 4, 23, 59, tzinfo=SGT)
    assert next_top_of_hour(now) == datetime(2026, 9, 5, 0, 0, tzinfo=SGT)

