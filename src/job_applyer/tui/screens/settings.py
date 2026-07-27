"""Settings — LLM provider switch + safety flags."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Select, Static, Switch

from job_applyer.tui.screens.base import AppScreen


class SettingsScreen(AppScreen):
    """FLOW Settings: LLM_PROVIDER, models, dry-run/submit locked in MVP."""

    def body(self) -> ComposeResult:
        yield Static("Settings", classes="screen-title")
        yield Static("LLM switch · safety · paths", classes="screen-subtitle")

        with Vertical(classes="panel"):
            yield Static("LLM provider", classes="panel-title")
            yield Label("Active chat backend (OpenAI-compatible)")
            yield Select(
                options=[
                    ("LM Studio (local)", "lmstudio"),
                    ("OpenRouter (cloud)", "openrouter"),
                    ("Off (no model calls)", "off"),
                ],
                value="lmstudio",
                id="llm-provider",
                allow_blank=False,
            )
            with Horizontal(classes="form-row"):
                yield Button("Check connection", variant="primary", id="btn-llm-check")
            yield Static(
                "[dim]Both configs can stay filled in .env — flip the switch only.[/]",
                classes="muted",
                id="llm-check-result",
            )

        with Vertical(classes="panel"):
            yield Static("Safety", classes="panel-title")
            with Horizontal(classes="form-row"):
                yield Label("Dry-run")
                yield Switch(value=True, id="sw-dry-run", disabled=True)
                yield Static("[green]forced ON (MVP)[/]", classes="ok")
            with Horizontal(classes="form-row"):
                yield Label("Submit")
                yield Switch(value=False, id="sw-submit", disabled=True)
                yield Static("[dim]locked OFF (MVP)[/]", classes="muted")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "llm-provider":
            return
        provider = str(event.value)
        self.app.settings.llm_provider = provider
        try:
            strip = self.query_one("#status-strip")
            strip.provider = provider  # type: ignore[attr-defined]
        except Exception:
            pass
        self.app.notify(f"LLM_PROVIDER → {provider}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-llm-check":
            return
        provider = self.app.settings.llm_provider
        result = self.query_one("#llm-check-result", Static)
        if provider == "off":
            result.update("[dim]Provider is off — no endpoint to check.[/]")
            return
        result.update(
            f"[yellow]stub[/]  Would ping {provider} OpenAI-compatible /v1 (wire in M1)."
        )
        self.app.notify("llm-check stub", severity="information")
