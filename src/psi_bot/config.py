"""Environment-based application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when a required setting is absent or invalid."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def _parse_channel_id(value: str) -> int | str:
    if value.startswith("@") and len(value) > 1:
        return value
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(
            "TELEGRAM_CHANNEL_ID must be a numeric channel ID or an @channel_username"
        ) from exc


def _parse_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false")


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        if value > 0:
            return value
    except ValueError:
        pass
    raise ConfigurationError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: int | str
    data_gov_sg_api_key: str | None = None
    send_on_startup: bool = False
    disable_night_updates: bool = False
    log_level: str = "INFO"
    max_reading_age_minutes: int = 120

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        api_key = os.getenv("DATA_GOV_SG_API_KEY", "").strip() or None
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        return cls(
            telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
            telegram_channel_id=_parse_channel_id(_required("TELEGRAM_CHANNEL_ID")),
            data_gov_sg_api_key=api_key,
            send_on_startup=_parse_bool("SEND_ON_STARTUP"),
            disable_night_updates=_parse_bool("DISABLE_NIGHT_UPDATES"),
            log_level=log_level,
            max_reading_age_minutes=_positive_int("MAX_READING_AGE_MINUTES", 120),
        )
