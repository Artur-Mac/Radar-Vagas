"""Central typed configuration for Radar-Vagas using Pydantic BaseSettings."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    environment: Literal["development", "testing", "production"] = Field(
        default="development", description="Application execution environment"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging output level"
    )
    db_path: Path = Field(
        default=Path("data/radar_vagas.db"),
        description="Path to local database",
    )
    ollama_base_url: AnyHttpUrl = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama API server",
    )
    ollama_model: str = Field(
        default="gemma4:26b",
        description="Configured Ollama model name (e.g. gemma4:26b or llama3.2)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    """Instantiate and return application settings."""
    return Settings()
