"""Textual App — Grok Build–inspired shell for Terminal-Hire."""

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

from job_applyer.config import Settings, load_settings
from job_applyer.tui.logo import BRAND
from job_applyer.tui.screens import SCREENS
from job_applyer.tui.theme import TERMINAL_HIRE_THEME

THEME_PATH = Path(__file__).parent / "tui" / "theme.tcss"


class TerminalHireApp(App[None]):
    """Fullscreen TUI: welcome + FLOW screens. Services land in later milestones."""

    CSS_PATH = THEME_PATH
    TITLE = BRAND
    SUB_TITLE = "US job applications"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("escape", "go_home", "Home", show=True),
        Binding("1", "goto_screen('onboard')", "Onboard", show=False, priority=True),
        Binding("2", "goto_screen('profile')", "Profile", show=False, priority=True),
        Binding("3", "goto_screen('resume')", "Resume", show=False, priority=True),
        Binding("4", "goto_screen('apply')", "Apply", show=False, priority=True),
        Binding("5", "goto_screen('apps')", "Apps", show=False, priority=True),
        Binding("6", "goto_screen('settings')", "Settings", show=False, priority=True),
        Binding("question_mark", "help", "Help", show=False),
    ]

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or load_settings()
        self.enabled_packs = "none"

    def on_mount(self) -> None:
        self.register_theme(TERMINAL_HIRE_THEME)
        self.theme = "terminal-hire"
        for name, screen_cls in SCREENS.items():
            self.install_screen(screen_cls(), name=name)
        self.push_screen("welcome")

    def navigate(self, screen_id: str) -> None:
        if screen_id not in SCREENS:
            self.notify(f"Unknown screen: {screen_id}", severity="error")
            return
        # Base Textual screen + one active workspace screen
        while len(self.screen_stack) > 1:
            self.pop_screen()
        if screen_id == "welcome":
            self.push_screen("welcome")
            return
        self.push_screen(screen_id)

    def action_go_home(self) -> None:
        self.navigate("welcome")

    def action_goto_screen(self, screen_id: str) -> None:
        focused = self.focused
        # Allow 1–6 nav unless the user is mid-typing in an input
        if focused is not None and focused.__class__.__name__ in {"Input", "TextArea"}:
            value = getattr(focused, "value", "") or ""
            if value.strip():
                return
            # Empty prompt: blur and navigate (Grok-style shortcut menu)
            self.set_focus(None)
        self.navigate(screen_id)

    def action_help(self) -> None:
        self.handle_slash("/help")

    def handle_slash(self, command: str) -> None:
        cmd = command.strip().lower()
        if cmd in {"/help", "/?"}:
            self.notify(
                "1–6 screens · esc home · ctrl+q quit · /settings /apply /onboard",
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


# Back-compat alias
JobApplyerApp = TerminalHireApp
