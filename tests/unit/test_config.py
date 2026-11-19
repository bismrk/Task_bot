"""Unit tests for application configuration settings."""

from unittest.mock import patch

from src.core import Settings, get_settings


def test_settings_default_values() -> None:
    """Verifies REQ-USR-01: Settings provides default values for all required fields."""
    with patch.dict("os.environ", {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.BOT_TOKEN == ""
        assert settings.GEMINI_API_KEY == ""
        assert settings.DATABASE_URL == "sqlite+aiosqlite:///tasks.db"
        assert settings.WEBAPP_URL is None
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000
        assert settings.DEBUG is True


def test_settings_env_override() -> None:
    """Verifies REQ-USR-01: Settings correctly overrides fields from environment variables."""
    custom_env = {
        "BOT_TOKEN": "test_bot_token_12345",
        "GEMINI_API_KEY": "test_gemini_key_67890",
        "DATABASE_URL": "sqlite+aiosqlite:///custom.db",
        "WEBAPP_URL": "https://app.example.com",
        "HOST": "127.0.0.1",
        "PORT": "9000",
        "DEBUG": "false",
    }
    with patch.dict("os.environ", custom_env, clear=True):
        settings = Settings(_env_file=None)
        assert settings.BOT_TOKEN == "test_bot_token_12345"
        assert settings.GEMINI_API_KEY == "test_gemini_key_67890"
        assert settings.DATABASE_URL == "sqlite+aiosqlite:///custom.db"
        assert settings.WEBAPP_URL == "https://app.example.com"
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 9000
        assert settings.DEBUG is False


def test_get_settings_caching() -> None:
    """Verifies REQ-USR-01: get_settings returns a cached Settings instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
