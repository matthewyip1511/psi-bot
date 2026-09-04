"""Async client for data.gov.sg real-time air-quality APIs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import httpx

from psi_bot.models import AirQualitySnapshot

LOGGER = logging.getLogger(__name__)

PSI_URL = "https://api-open.data.gov.sg/v2/real-time/api/psi"
PM25_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25"


class DataGovSgError(RuntimeError):
    """Raised when data.gov.sg cannot provide a usable reading."""


class DataGovSgClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        attempts: int = 3,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        headers = {"Accept": "application/json", "User-Agent": "singapore-psi-telegram-bot/1.0"}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = client or httpx.AsyncClient(timeout=15, headers=headers)
        self._owns_client = client is None
        self._attempts = attempts

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> DataGovSgClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def fetch_latest(self) -> AirQualitySnapshot:
        psi_payload, pm25_payload = await asyncio.gather(
            self._get_json(PSI_URL),
            self._get_json(PM25_URL),
        )
        psi_item = _latest_item(psi_payload, "PSI")
        pm25_item = _latest_item(pm25_payload, "PM2.5")

        psi_readings = _reading_map(psi_item, "psi_twenty_four_hourly", "PSI")
        pm25_readings = _reading_map(pm25_item, "pm25_one_hourly", "PM2.5")

        try:
            return AirQualitySnapshot(
                psi_timestamp=datetime.fromisoformat(str(psi_item["timestamp"])),
                pm25_timestamp=datetime.fromisoformat(str(pm25_item["timestamp"])),
                psi_by_region=psi_readings,
                pm25_by_region=pm25_readings,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataGovSgError(f"Invalid air-quality data: {exc}") from exc

    async def _get_json(self, url: str) -> Mapping[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise DataGovSgError("API response is not a JSON object")
                if payload.get("code") != 0:
                    message = payload.get("errorMsg") or "unknown API error"
                    raise DataGovSgError(f"data.gov.sg returned: {message}")
                return payload
            except (httpx.HTTPError, ValueError, DataGovSgError) as exc:
                last_error = exc
                if attempt < self._attempts:
                    delay = 2 ** (attempt - 1)
                    LOGGER.warning(
                        "data.gov.sg request failed (attempt %d/%d); retrying in %ds: %s",
                        attempt,
                        self._attempts,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        raise DataGovSgError(
            f"data.gov.sg request failed after {self._attempts} attempts"
        ) from last_error


def _latest_item(payload: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    try:
        items = payload["data"]["items"]
        if not isinstance(items, list) or not items:
            raise TypeError("items is empty or not a list")
        item = max(items, key=lambda candidate: datetime.fromisoformat(candidate["timestamp"]))
        if not isinstance(item, dict):
            raise TypeError("latest item is not an object")
        return item
    except (KeyError, TypeError, ValueError) as exc:
        raise DataGovSgError(f"Invalid {label} response: {exc}") from exc


def _reading_map(item: Mapping[str, Any], key: str, label: str) -> dict[str, int]:
    try:
        readings = item["readings"][key]
        if not isinstance(readings, dict):
            raise TypeError(f"{key} is not an object")
        return {str(region): int(value) for region, value in readings.items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise DataGovSgError(f"Invalid {label} readings: {exc}") from exc
