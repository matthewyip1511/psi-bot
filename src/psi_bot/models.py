"""Air-quality data models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

REGION_ORDER = ("north", "south", "east", "west", "central")


@dataclass(frozen=True, slots=True)
class AirQualitySnapshot:
    psi_timestamp: datetime
    pm25_timestamp: datetime
    psi_by_region: Mapping[str, int]
    pm25_by_region: Mapping[str, int]

    def __post_init__(self) -> None:
        missing_psi = set(REGION_ORDER) - self.psi_by_region.keys()
        missing_pm25 = set(REGION_ORDER) - self.pm25_by_region.keys()
        if missing_psi:
            raise ValueError(f"PSI data is missing regions: {sorted(missing_psi)}")
        if missing_pm25:
            raise ValueError(f"PM2.5 data is missing regions: {sorted(missing_pm25)}")
        if self.psi_timestamp.tzinfo is None or self.pm25_timestamp.tzinfo is None:
            raise ValueError("Reading timestamps must include a timezone")
        if any(value < 0 for value in self.psi_by_region.values()):
            raise ValueError("PSI readings cannot be negative")
        if any(value < 0 for value in self.pm25_by_region.values()):
            raise ValueError("PM2.5 readings cannot be negative")

        object.__setattr__(self, "psi_by_region", MappingProxyType(dict(self.psi_by_region)))
        object.__setattr__(self, "pm25_by_region", MappingProxyType(dict(self.pm25_by_region)))

