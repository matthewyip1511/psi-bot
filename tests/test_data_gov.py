from __future__ import annotations

import httpx
import pytest

from psi_bot.data_gov import PM25_URL, PSI_URL, DataGovSgClient, DataGovSgError

REGIONS = {"north": 1, "south": 2, "east": 3, "west": 4, "central": 5}


@pytest.mark.asyncio
async def test_fetch_latest_combines_both_endpoints() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == PSI_URL:
            key = "psi_twenty_four_hourly"
            timestamp = "2026-09-04T23:00:00+08:00"
        else:
            assert str(request.url) == PM25_URL
            key = "pm25_one_hourly"
            timestamp = "2026-09-04T22:00:00+08:00"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "items": [
                        {"timestamp": timestamp, "readings": {key: REGIONS}},
                    ]
                },
                "errorMsg": "",
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = DataGovSgClient(client=http_client)

    snapshot = await client.fetch_latest()

    assert snapshot.psi_by_region["central"] == 5
    assert snapshot.pm25_by_region["west"] == 4
    assert snapshot.psi_timestamp.hour == 23
    assert snapshot.pm25_timestamp.hour == 22
    await http_client.aclose()


@pytest.mark.asyncio
async def test_api_error_is_wrapped() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1, "errorMsg": "rate limited"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = DataGovSgClient(client=http_client, attempts=1)

    with pytest.raises(DataGovSgError, match="after 1 attempts"):
        await client.fetch_latest()
    await http_client.aclose()

