"""Onboard screen — chat-style interview shell (agent wired later)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

from job_applyer.tui.screens.base import AppScreen


class OnboardScreen(AppScreen):
    """FLOW: US scope → core facts → packs → verify."""

    def body(self) -> ComposeResult:
        yield Static("Onboard", classes="screen-title")
        yield Static(
            "Interview for a verified US profile · optional work-auth packs",
            classes="screen-subtitle",
        )
        with Vertical():
            yield RichLog(id="onboard-log", classes="chat-log", markup=True, wrap=True)
            with Horizontal(id="chat-input-row"):
                yield Input(
                    placeholder="Answer here… (agent runtime lands in M2)",
                    id="chat-input",
                )

    def on_mount(self) -> None:
        super().on_mount()
        log = self.query_one("#onboard-log", RichLog)
        log.write("[bold cyan]agent[/]  Applying to US jobs in this phase?")
        log.write(
            "[dim]system[/]  Core facts first. Packs (citizen / OPT / STEM OPT / …) "
            "only if you enable them."
        )
        log.write("[dim]system[/]  Model cannot mark facts verified — only you can.")
        log.write("[dim]system[/]  OTP on career sites ≠ OPT visa pack.")
        self.query_one("#chat-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        log = self.query_one("#onboard-log", RichLog)
        log.write(f"[bold green]you[/]  {text}")
        log.write(
            "[bold cyan]agent[/]  [dim](stub)[/] Saved as draft — wire onboarder agent in M2."
        )
        event.input.value = ""
