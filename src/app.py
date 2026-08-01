"""Textual App — Grok Build–inspired shell for TUI-Hire."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App
from textual.binding import Binding
from textual.widgets import Input, TextArea

from .apply import ApplicationService
from .config import Settings, load_settings
from .db import LocalStore
from .profile import (
    MarkdownProfileRepository,
    ProfileFormatError,
    ProfileRetriever,
    ProfileService,
)
from .tui.logo import BRAND
from .tui.screens import SCREENS
from .tui.theme import TERMINAL_HIRE_THEME

THEME_PATH = Path(__file__).parent / "tui" / "theme.tcss"


class TerminalHireApp(App[None]):
    """Fullscreen TUI: Grok-style welcome + FLOW screens."""

    CSS_PATH = THEME_PATH
    TITLE = BRAND
    SUB_TITLE = "US job applications"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("escape", "go_home", "Home", show=True),
        Binding("1", "goto_screen('profile')", "Profile", show=False),
        Binding("2", "goto_screen('apply')", "Apply", show=False),
        Binding("3", "goto_screen('apps')", "Applications", show=False),
        Binding("4", "goto_screen('settings')", "Settings", show=False),
        Binding("question_mark", "help", "Help", show=False),
    ]

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or load_settings()
        self.profile_repository = MarkdownProfileRepository(self.settings.profile_path)
        self.profile_service = ProfileService(self.profile_repository)
        self.profile_retriever = ProfileRetriever()
        self.store = LocalStore(self.settings.database_path)
        stored_submit = self.store.get_setting("application_submission_enabled")
        if stored_submit is not None:
            self.settings.application_submission_enabled = stored_submit == "true"
        self.application_service = ApplicationService(
            profiles=self.profile_service,
            retriever=self.profile_retriever,
            store=self.store,
        )
        self.browser_sessions: dict[str, object] = {}
        self.enabled_packs = self._enabled_packs()

    def on_mount(self) -> None:
        self.register_theme(TERMINAL_HIRE_THEME)
        self.theme = "terminal-hire"
        for name, screen_cls in SCREENS.items():
            self.install_screen(screen_cls(), name=name)
        self.push_screen("welcome" if self.profile_service.is_ready() else "onboard")

    def navigate(self, screen_id: str) -> None:
        if screen_id not in SCREENS:
            self.notify(f"Unknown screen: {screen_id}", severity="error")
            return
        if not self.profile_service.is_ready() and screen_id not in {"onboard", "settings"}:
            self.notify(
                "Complete and verify onboarding before using this screen.",
                severity="warning",
            )
            screen_id = "onboard"
        # Base Textual screen + one active workspace screen
        while len(self.screen_stack) > 1:
            self.pop_screen()
        if screen_id == "welcome":
            self.push_screen("welcome")
            return
        self.push_screen(screen_id)

    def action_go_home(self) -> None:
        self.navigate("welcome" if self.profile_service.is_ready() else "onboard")

    def action_goto_screen(self, screen_id: str) -> None:
        focused = self.focused
        if isinstance(focused, (Input, TextArea)):
            if focused.id != "welcome-prompt":
                digit = {
                    "profile": "1",
                    "apply": "2",
                    "apps": "3",
                    "settings": "4",
                }[screen_id]
                focused.insert_text_at_cursor(digit)
                return
            self.set_focus(None)
        self.navigate(screen_id)

    def action_help(self) -> None:
        self.handle_slash("/help")

    def handle_slash(self, command: str) -> None:
        cmd = command.strip().lower()
        if cmd in {"/help", "/?"}:
            self.notify(
                "1–4 screens · esc home · ctrl+q quit · /settings /apply /onboard",
                title="Help",
                timeout=6,
            )
            return
        if cmd.startswith("/"):
            name = cmd[1:]
            aliases = {
                "home": "welcome",
                "start": "onboard",
                "packs": "profile",
                "config": "settings",
            }
            target = aliases.get(name, name)
            if target in SCREENS:
                self.navigate(target)
                return
        self.notify(f"Unknown command: {command}", severity="warning")

    def profile_changed(self) -> None:
        """Refresh app-level readiness after onboarding/profile writes."""
        self.enabled_packs = self._enabled_packs()

    def _enabled_packs(self) -> str:
        try:
            packs = self.profile_service.load_or_new().enabled_packs
        except ProfileFormatError:
            return "none"
        return ",".join(packs) if packs else "none"
