"""Runtime settings and local data paths for TUI-Hire."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    """Return an OS-local directory that is outside the repository by default."""
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "TUI-Hire"
    if os.name == "posix":
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return root / "tui-hire"
    return Path.home() / ".tui-hire"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "lmstudio"
    application_dry_run: bool = True
    application_submission_enabled: bool = False
    playwright_headless: bool = False
    app_timezone: str = "America/Chicago"
    data_dir: Path = default_data_dir()
    profile_filename: str = "PROFILE.md"
    database_filename: str = "terminal_hire.sqlite"
    artifact_dirname: str = "artifacts"
    database_url: str | None = None

    @property
    def profile_path(self) -> Path:
        return self.data_dir.expanduser() / self.profile_filename

    @property
    def database_path(self) -> Path:
        if self.database_url:
            prefix = "sqlite:///"
            if not self.database_url.startswith(prefix):
                raise ValueError("Only sqlite:/// DATABASE_URL values are supported")
            return Path(self.database_url.removeprefix(prefix)).expanduser().resolve()
        return self.data_dir.expanduser() / self.database_filename

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir.expanduser() / self.artifact_dirname


def load_settings() -> Settings:
    return Settings()
