from __future__ import annotations

from datetime import date

import httpx
import pytest

from psi_bot.open_meteo import AIR_QUALITY_URL, WEATHER_URL, OpenMeteoClient, OpenMeteoError

FORECAST_DATE = date(2026, 9, 15)


def _weather_payload() -> dict:
    return {
        "daily": {
            "time": ["2026-09-15"],
            "temperature_2m_min": [10.2],
            "temperature_2m_max": [18.7],
            "precipitation_probability_max": [70],
        }
    }


def _air_quality_payload(values: list[object] | None = None) -> dict:
    return {
        "hourly": {
            "time": ["2026-09-15T00:00", "2026-09-15T01:00", "2026-09-15T02:00"],
            "european_aqi": values if values is not None else [18, 42.5, 31],
        }
    }


@pytest.mark.asyncio
async def test_fetch_combines_weather_and_air_quality_forecasts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["latitude"] == "51.5072"
        assert request.url.params["longitude"] == "-0.1276"
        assert request.url.params["timezone"] == "Europe/London"
        assert request.url.params["forecast_days"] == "1"
        if str(request.url).startswith(WEATHER_URL):
            assert "temperature_2m_max" in request.url.params["daily"]
            return httpx.Response(200, json=_weather_payload())
        assert str(request.url).startswith(AIR_QUALITY_URL)
        assert request.url.params["hourly"] == "european_aqi"
        return httpx.Response(200, json=_air_quality_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        forecast = await OpenMeteoClient(client=http_client).fetch_london_forecast(
            for_date=FORECAST_DATE
        )

    assert forecast.date == FORECAST_DATE
    assert forecast.temperature_min_c == 10.2
    assert forecast.temperature_max_c == 18.7
    assert forecast.precipitation_probability_max == 70
    assert forecast.european_aqi_max == 42.5


@pytest.mark.parametrize("bad_value", [None, True, "42", float("nan"), float("inf")])
@pytest.mark.asyncio
async def test_invalid_air_quality_value_rejects_entire_forecast(bad_value: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(WEATHER_URL):
            return httpx.Response(200, json=_weather_payload())
        return httpx.Response(200, json=_air_quality_payload([18, bad_value, 31]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenMeteoClient(client=http_client, attempts=1)
        with pytest.raises(OpenMeteoError):
            await client.fetch_london_forecast(for_date=FORECAST_DATE)


@pytest.mark.asyncio
async def test_upstream_error_is_wrapped() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": True, "reason": "temporarily unavailable"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenMeteoClient(client=http_client, attempts=1)
        with pytest.raises(OpenMeteoError, match="after 1 attempts"):
            await client.fetch_london_forecast(for_date=FORECAST_DATE)
