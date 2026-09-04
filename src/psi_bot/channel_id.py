"""Safely discover Telegram channel IDs using the configured bot token."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError


async def discover_channel_ids(token: str) -> int:
    print("Waiting 30 seconds for a new channel post...")
    print("Publish a temporary message in the channel now, using the Telegram app.")
    try:
        async with Bot(token) as bot:
            updates = await bot.get_updates(timeout=30, allowed_updates=["channel_post"])
    except TelegramError as exc:
        print(f"Telegram could not be queried: {exc}")
        print("Make sure the main bot process is stopped and the token is correct.")
        return 1

    channels = {
        (update.channel_post.chat.id, update.channel_post.chat.title)
        for update in updates
        if update.channel_post is not None
    }
    if not channels:
        print("No channel post was received.")
        print("Confirm that the bot is a channel administrator, then run this command again.")
        return 1

    print("Channel details found:")
    for channel_id, title in sorted(channels):
        print(f"  {title or '(untitled channel)'}: {channel_id}")
    print("Copy the numeric value into TELEGRAM_CHANNEL_ID in .env.")
    return 0


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "PASTE_TELEGRAM_BOT_TOKEN_HERE":
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env first.")
    raise SystemExit(asyncio.run(discover_channel_ids(token)))


if __name__ == "__main__":
    main()
