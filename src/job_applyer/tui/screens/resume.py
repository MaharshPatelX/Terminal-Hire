"""Resume screen — LaTeX → PDF shell."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static

from job_applyer.tui.screens.base import AppScreen


class ResumeScreen(AppScreen):
    """Store .tex path, build PDF, show hash (compiler in M3)."""

    def body(self) -> ComposeResult:
        yield Static("Resume", classes="screen-title")
        yield Static(
            "LaTeX source → PDF for career-page uploads",
            classes="screen-subtitle",
        )
        with Vertical(classes="panel"):
            yield Static("LaTeX source", classes="panel-title")
            yield Input(placeholder=r"C:\path\to\resume.tex", id="tex-path")
            with Horizontal(classes="form-row"):
                yield Button("Build PDF", variant="primary", id="btn-build")
                yield Button("Open folder", id="btn-open", disabled=True)
        with Vertical(classes="panel"):
            yield Static("Output", classes="panel-title")
            yield Static("PDF: [dim]not built[/]", id="pdf-status")
            yield Static("SHA256: [dim]—[/]", id="pdf-hash")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-build":
            return
        path = self.query_one("#tex-path", Input).value.strip()
        if not path:
            self.app.notify("Set a .tex path first", severity="warning")
            return
        self.query_one("#pdf-status", Static).update(
            f"PDF: [yellow]stub[/] — compile lands in M3 ([dim]{path}[/])"
        )
        self.app.notify("Resume compile not wired yet (M3)", severity="information")
