"""NEA air-quality band classifications."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Band:
    number: int | None
    descriptor: str

    def pm25_label(self) -> str:
        if self.number is None:
            return self.descriptor
        return f"Band {self.number} — {self.descriptor}"


def psi_band(value: int | float) -> Band:
    """Return the official 24-hour PSI descriptor for a reading."""
    if value < 0:
        raise ValueError("PSI cannot be negative")
    if value <= 50:
        return Band(None, "Good")
    if value <= 100:
        return Band(None, "Moderate")
    if value <= 200:
        return Band(None, "Unhealthy")
    if value <= 300:
        return Band(None, "Very Unhealthy")
    return Band(None, "Hazardous")


def pm25_band(value: int | float) -> Band:
    """Return the official 1-hour PM2.5 band and descriptor for a reading."""
    if value < 0:
        raise ValueError("PM2.5 cannot be negative")
    if value <= 55:
        return Band(1, "Normal")
    if value <= 150:
        return Band(2, "Elevated")
    if value <= 250:
        return Band(3, "High")
    return Band(4, "Very High")

