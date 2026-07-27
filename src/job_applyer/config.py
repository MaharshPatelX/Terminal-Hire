"""Minimal settings for the TUI shell (full config lands in M1)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "lmstudio"
    application_dry_run: bool = True
    application_submission_enabled: bool = False
    app_timezone: str = "America/Chicago"


def load_settings() -> Settings:
    return Settings()
