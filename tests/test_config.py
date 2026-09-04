import pytest

from psi_bot.config import ConfigurationError, Settings


def test_settings_accept_numeric_channel_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-1001234567890")
    monkeypatch.setenv("SEND_ON_STARTUP", "yes")

    settings = Settings.from_env()

    assert settings.telegram_channel_id == -1001234567890
    assert settings.send_on_startup is True


def test_settings_accept_public_channel_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@air_quality")

    assert Settings.from_env().telegram_channel_id == "@air_quality"


def test_invalid_channel_id_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "air quality")

    with pytest.raises(ConfigurationError, match="TELEGRAM_CHANNEL_ID"):
        Settings.from_env()

