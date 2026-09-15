"""Async client for Open-Meteo's London weather and air-quality forecasts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from psi_bot.models import LondonForecast

LOGGER = logging.getLogger(__name__)

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
LONDON = ZoneInfo("Europe/London")
LONDON_LATITUDE = 51.5072
LONDON_LONGITUDE = -0.1276


class OpenMeteoError(RuntimeError):
    """Raised when Open-Meteo cannot provide a complete London forecast."""


class OpenMeteoClient:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        attempts: int = 3,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        headers = {"Accept": "application/json", "User-Agent": "singapore-psi-telegram-bot/1.0"}
        self._client = client or httpx.AsyncClient(timeout=15, headers=headers)
        self._owns_client = client is None
        self._attempts = attempts

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_london_forecast(self, *, for_date: date | None = None) -> LondonForecast:
        forecast_date = for_date or datetime.now(LONDON).date()
        common_params: dict[str, str | int | float] = {
            "latitude": LONDON_LATITUDE,
            "longitude": LONDON_LONGITUDE,
            "timezone": str(LONDON),
            "forecast_days": 1,
        }
        weather_payload, air_quality_payload = await asyncio.gather(
            self._get_json(
                WEATHER_URL,
                params={
                    **common_params,
                    "daily": (
                        "temperature_2m_max,temperature_2m_min,"
                        "precipitation_probability_max"
                    ),
                },
            ),
            self._get_json(
                AIR_QUALITY_URL,
                params={**common_params, "hourly": "european_aqi"},
            ),
        )

        try:
            daily = _mapping(weather_payload, "daily")
            daily_times = _sequence(daily, "time")
            day_index = daily_times.index(forecast_date.isoformat())
            minimum = _number_at(daily, "temperature_2m_min", day_index)
            maximum = _number_at(daily, "temperature_2m_max", day_index)
            rain_chance = _integer_at(daily, "precipitation_probability_max", day_index)

            hourly = _mapping(air_quality_payload, "hourly")
            times = _sequence(hourly, "time")
            values = _sequence(hourly, "european_aqi")
            if len(times) != len(values):
                raise ValueError("hourly time and European AQI arrays have different lengths")
            date_prefix = f"{forecast_date.isoformat()}T"
            daily_aqi = []
            for timestamp, value in zip(times, values, strict=True):
                if not isinstance(timestamp, str) or not timestamp.startswith(date_prefix):
                    raise ValueError("European AQI contains a time outside the forecast date")
                daily_aqi.append(_number(value, "european_aqi"))
            if not daily_aqi:
                raise ValueError("European AQI has no values for the forecast date")

            return LondonForecast(
                date=forecast_date,
                temperature_min_c=minimum,
                temperature_max_c=maximum,
                precipitation_probability_max=rain_chance,
                european_aqi_max=max(daily_aqi),
            )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise OpenMeteoError(f"Invalid London forecast data: {exc}") from exc

    async def _get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float],
    ) -> Mapping[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                response = await self._client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise OpenMeteoError("API response is not a JSON object")
                if payload.get("error") is True:
                    raise OpenMeteoError(str(payload.get("reason") or "unknown API error"))
                return payload
            except (httpx.HTTPError, ValueError, OpenMeteoError) as exc:
                last_error = exc
                if attempt < self._attempts:
                    delay = 2 ** (attempt - 1)
                    LOGGER.warning(
                        "Open-Meteo request failed (attempt %d/%d); retrying in %ds: %s",
                        attempt,
                        self._attempts,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        raise OpenMeteoError(
            f"Open-Meteo request failed after {self._attempts} attempts"
        ) from last_error


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload[key]
    if not isinstance(value, dict):
        raise TypeError(f"{key} is not an object")
    return value


def _sequence(payload: Mapping[str, Any], key: str) -> Sequence[Any]:
    value = payload[key]
    if not isinstance(value, list):
        raise TypeError(f"{key} is not an array")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _number_at(payload: Mapping[str, Any], key: str, index: int) -> float:
    return _number(_sequence(payload, key)[index], key)


def _integer_at(payload: Mapping[str, Any], key: str, index: int) -> int:
    value = _sequence(payload, key)[index]
    if type(value) is not int:
        raise ValueError(f"{key} must be an integer")
    return value
