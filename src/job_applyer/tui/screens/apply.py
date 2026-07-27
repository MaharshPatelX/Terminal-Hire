"""Apply-by-URL screen — dry-run pipeline shell."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, RichLog, Static

from job_applyer.tui.screens.base import AppScreen


class ApplyScreen(AppScreen):
    """Paste US career URL → start dry-run (Playwright in M4/M5)."""

    def body(self) -> ComposeResult:
        yield Static("Apply by URL", classes="screen-title")
        yield Static(
            "US career pages only · dry-run · preview before any future submit",
            classes="screen-subtitle",
        )
        with Vertical(classes="panel"):
            yield Static("Career / application URL", classes="panel-title")
            yield Input(placeholder="https://company.com/jobs/123", id="apply-url")
            with Horizontal():
                yield Button("Start dry-run", variant="primary", id="btn-dry-run")
                yield Button("Cancel", id="btn-cancel", disabled=True)
        yield RichLog(id="apply-log", classes="chat-log", markup=True, wrap=True)

    def on_mount(self) -> None:
        super().on_mount()
        log = self.query_one("#apply-log", RichLog)
        log.write(
            "[dim]system[/]  MVP never clicks Submit "
            "(APPLICATION_SUBMISSION_ENABLED=false)."
        )
        log.write("[dim]system[/]  CAPTCHA / site OTP / unknown → pause for you.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-dry-run":
            return
        url = self.query_one("#apply-url", Input).value.strip()
        log = self.query_one("#apply-log", RichLog)
        if not url:
            self.app.notify("Paste a URL first", severity="warning")
            return
        log.write(f"[bold green]you[/]  {url}")
        log.write("[bold cyan]apply[/]  status → [yellow]ready_to_apply[/] (stub)")
        log.write(
            "[bold cyan]apply[/]  Playwright inventory lands in M4; mapper + fill in M5."
        )
        self.app.notify("Dry-run pipeline not wired yet", severity="information")
