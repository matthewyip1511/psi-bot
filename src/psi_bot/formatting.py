"""Telegram message rendering."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from psi_bot.bands import Band, pm25_band, psi_band
from psi_bot.models import REGION_ORDER, AirQualitySnapshot

SGT = ZoneInfo("Asia/Singapore")


def format_sgt(timestamp: datetime) -> str:
    localized = timestamp.astimezone(SGT)
    hour = localized.strftime("%I").lstrip("0") or "12"
    return (
        f"{localized.strftime('%A')}, {localized.day} {localized.strftime('%B %Y')} "
        f"at {hour}:{localized.strftime('%M %p')} SGT"
    )


def _descriptor_range(values: list[int], classifier: Callable[[int], Band]) -> str:
    low = classifier(min(values)).descriptor
    high = classifier(max(values)).descriptor
    return low if low == high else f"{low} to {high}"


def format_air_quality_message(
    snapshot: AirQualitySnapshot,
    *,
    sent_at: datetime | None = None,
) -> str:
    sent_at = sent_at or datetime.now(SGT)
    psi_values = [snapshot.psi_by_region[region] for region in REGION_ORDER]
    pm25_values = [snapshot.pm25_by_region[region] for region in REGION_ORDER]

    lines = [
        "🇸🇬 Singapore Air Quality Update",
        f"Sent: {format_sgt(sent_at)}",
        "",
        "24-hour PSI",
        f"Data time: {format_sgt(snapshot.psi_timestamp)}",
        (
            f"Singapore range: <b>{min(psi_values)}–{max(psi_values)}</b> "
            f"(<b>{_descriptor_range(psi_values, psi_band)}</b>)"
        ),
    ]
    for region in REGION_ORDER:
        value = snapshot.psi_by_region[region]
        lines.append(f"• {region.title()}: <b>{value}</b> — <b>{psi_band(value).descriptor}</b>")

    lines.extend(
        [
            "",
            "1-hour PM2.5",
            f"Data time: {format_sgt(snapshot.pm25_timestamp)}",
            (
                f"Singapore range: <b>{min(pm25_values)}–{max(pm25_values)}</b> µg/m³ "
                f"(<b>{_descriptor_range(pm25_values, pm25_band)}</b>)"
            ),
        ]
    )
    for region in REGION_ORDER:
        value = snapshot.pm25_by_region[region]
        lines.append(
            f"• {region.title()}: <b>{value}</b> µg/m³ — "
            f"<b>{pm25_band(value).pm25_label()}</b>"
        )

    lines.extend(["", "Source: NEA via data.gov.sg"])
    return "\n".join(lines)
