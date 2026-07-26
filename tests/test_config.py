"""Unit tests for typed application configuration."""

from pathlib import Path

from radar_vagas.core.config import Settings, get_settings


def test_default_settings() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.db_path == Path("data/radar_vagas.db")
    assert str(settings.ollama_base_url) == "http://localhost:11434/"
    assert settings.ollama_model == "gemma4:26b"


def test_settings_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    monkeypatch.setenv("DB_PATH", "test_data/test.db")

    settings = Settings(_env_file=None)
    assert settings.environment == "testing"
    assert settings.log_level == "DEBUG"
    assert settings.ollama_model == "llama3.2"
    assert settings.db_path == Path("test_data/test.db")


def test_get_settings_returns_instance() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)
