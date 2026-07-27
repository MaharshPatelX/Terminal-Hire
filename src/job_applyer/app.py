"""Textual App — Grok Build–inspired shell for Job Applyer."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer

from job_applyer import __version__
from job_applyer.config import Settings, load_settings
from job_applyer.tui.screens import SCREENS
from job_applyer.tui.widgets import FooterHints, StatusStrip, TopBar

THEME_PATH = Path(__file__).parent / "tui" / "theme.tcss"


class JobApplyerApp(App[None]):
    """Fullscreen TUI: welcome + FLOW screens. Services land in later milestones."""

    CSS_PATH = THEME_PATH
    TITLE = "job-applyer"
    SUB_TITLE = "US job applications"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("escape", "go_home", "Home", show=True),
        Binding("1", "goto_screen('onboard')", "Onboard", show=False),
        Binding("2", "goto_screen('profile')", "Profile", show=False),
        Binding("3", "goto_screen('resume')", "Resume", show=False),
        Binding("4", "goto_screen('apply')", "Apply", show=False),
        Binding("5", "goto_screen('apps')", "Apps", show=False),
        Binding("6", "goto_screen('settings')", "Settings", show=False),
        Binding("question_mark", "help", "Help", show=False),
    ]

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or load_settings()

    def compose(self) -> ComposeResult:
        yield TopBar(version=__version__)
        yield StatusStrip()
        yield FooterHints()
        yield Footer()

    def on_mount(self) -> None:
        strip = self.query_one(StatusStrip)
        strip.provider = self.settings.llm_provider
        strip.dry_run = self.settings.application_dry_run
        strip.submit_enabled = self.settings.application_submission_enabled
        strip.packs = "none"

        for name, screen_cls in SCREENS.items():
            self.install_screen(screen_cls(), name=name)
        self.push_screen("welcome")

    def navigate(self, screen_id: str) -> None:
        if screen_id not in SCREENS and screen_id != "welcome":
            self.notify(f"Unknown screen: {screen_id}", severity="error")
            return
        # Pop back to welcome, then push target (keeps stack shallow)
        while len(self.screen_stack) > 1:
            self.pop_screen()
        if screen_id == "welcome":
            return
        self.push_screen(screen_id)

    def action_go_home(self) -> None:
        self.navigate("welcome")

    def action_goto_screen(self, screen_id: str) -> None:
        # Don't steal digit keys while typing in an Input
        focused = self.focused
        if focused is not None and focused.__class__.__name__ in {"Input", "TextArea"}:
            return
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
            if name in SCREENS or name == "welcome":
                self.navigate(name)
                return
            # aliases
            aliases = {
                "home": "welcome",
                "start": "onboard",
                "packs": "profile",
                "config": "settings",
            }
            if name in aliases:
                self.navigate(aliases[name])
                return
        self.notify(f"Unknown command: {command}", severity="warning")
