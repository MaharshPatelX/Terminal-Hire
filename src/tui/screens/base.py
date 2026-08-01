"""Shared screen chrome — top bar, status strip, footer hints."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer

from ... import __version__
from ..widgets import FooterHints, StatusStrip, TopBar


class AppScreen(Screen):
    """Base screen with shared application chrome around subclass body()."""

    def compose(self) -> ComposeResult:
        yield TopBar(version=__version__)
        yield StatusStrip()
        yield from self.body()
        yield FooterHints()
        yield Footer()

    def body(self) -> ComposeResult:
        """Override to yield main content widgets."""
        return
        yield  # pragma: no cover

    def on_screen_resume(self) -> None:
        self._sync_status()

    def on_mount(self) -> None:
        self._sync_status()

    def _sync_status(self) -> None:
        app = self.app
        try:
            strip = self.query_one(StatusStrip)
        except NoMatches:
            return
        settings = getattr(app, "settings", None)
        if settings is None:
            return
        strip.provider = settings.llm_provider
        strip.dry_run = settings.application_dry_run
        strip.submit_enabled = settings.application_submission_enabled
        packs = getattr(app, "enabled_packs", "none")
        strip.packs = packs
