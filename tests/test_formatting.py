from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from psi_bot.formatting import format_air_quality_message, format_sgt
from psi_bot.models import AirQualitySnapshot

SGT = ZoneInfo("Asia/Singapore")


def make_snapshot() -> AirQualitySnapshot:
    return AirQualitySnapshot(
        psi_timestamp=datetime(2026, 9, 4, 23, 0, tzinfo=SGT),
        pm25_timestamp=datetime(2026, 9, 4, 22, 0, tzinfo=SGT),
        psi_by_region={"north": 88, "south": 87, "east": 104, "west": 99, "central": 123},
        pm25_by_region={"north": 56, "south": 60, "east": 63, "west": 54, "central": 83},
    )


def test_format_sgt_converts_and_labels_timezone() -> None:
    utc_time = datetime(2026, 9, 4, 15, 0, tzinfo=UTC)
    assert format_sgt(utc_time) == "Friday, 4 September 2026 at 11:00 PM SGT"


def test_message_contains_timestamps_values_and_bands() -> None:
    message = format_air_quality_message(
        make_snapshot(),
        sent_at=datetime(2026, 9, 4, 23, 5, tzinfo=SGT),
    )

    assert "Sent: Friday, 4 September 2026 at 11:05 PM SGT" in message
    assert "Data time: Friday, 4 September 2026 at 11:00 PM SGT" in message
    assert "Singapore range: <b>87–123</b> (<b>Moderate to Unhealthy</b>)" in message
    assert "• East: <b>104</b> — <b>Unhealthy</b>" in message
    assert "Data time: Friday, 4 September 2026 at 10:00 PM SGT" in message
    assert "Singapore range: <b>54–83</b> µg/m³ (<b>Normal to Elevated</b>)" in message
    assert "• North: <b>56</b> µg/m³ — <b>Band 2 — Elevated</b>" in message
