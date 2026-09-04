from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from telegram.constants import ParseMode

from psi_bot.bot import (
    CHANNEL_ID_KEY,
    DATA_CLIENT_KEY,
    PRIVATE_NOTICE,
    broadcast_air_quality,
    private_message_notice,
)
from psi_bot.models import AirQualitySnapshot


@pytest.mark.asyncio
async def test_private_messages_receive_only_broadcast_notice() -> None:
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message)

    await private_message_notice(update, None)  # type: ignore[arg-type]

    message.reply_text.assert_awaited_once_with(PRIVATE_NOTICE)
    assert PRIVATE_NOTICE == "This bot is for blasting messages only."


@pytest.mark.asyncio
async def test_broadcast_sends_message_with_html_formatting() -> None:
    sgt = ZoneInfo("Asia/Singapore")
    snapshot = AirQualitySnapshot(
        psi_timestamp=datetime(2026, 9, 4, 23, 0, tzinfo=sgt),
        pm25_timestamp=datetime(2026, 9, 4, 23, 0, tzinfo=sgt),
        psi_by_region={"north": 88, "south": 87, "east": 104, "west": 99, "central": 123},
        pm25_by_region={"north": 45, "south": 43, "east": 57, "west": 62, "central": 76},
    )
    client = SimpleNamespace(fetch_latest=AsyncMock(return_value=snapshot))
    bot = SimpleNamespace(send_message=AsyncMock())
    application = SimpleNamespace(
        bot=bot,
        bot_data={DATA_CLIENT_KEY: client, CHANNEL_ID_KEY: -1001234567890},
    )

    sent = await broadcast_air_quality(application)  # type: ignore[arg-type]

    assert sent is True
    bot.send_message.assert_awaited_once()
    call = bot.send_message.await_args
    assert call.kwargs["chat_id"] == -1001234567890
    assert call.kwargs["parse_mode"] == ParseMode.HTML
    assert "<b>123</b> — <b>Unhealthy</b>" in call.kwargs["text"]
