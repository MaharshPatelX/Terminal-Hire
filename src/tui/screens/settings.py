"""Settings — LLM provider switch + safety flags."""

from __future__ import annotations

from openai import OpenAIError
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, Label, Select, Static, Switch

from ...llm import LLMConfigurationError, LLMResponseError, OpenRouterClient
from .base import AppScreen


class SettingsScreen(AppScreen):
    """Provider, local storage, and supervised-submit policy."""

    def __init__(self) -> None:
        super().__init__()
        self._loading = False

    def body(self) -> ComposeResult:
        yield Static("Settings", classes="screen-title")
        yield Static("LLM switch · local storage · supervised-submit safety", classes="screen-subtitle")

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
            yield Static("Local data", classes="panel-title")
            yield Static("", id="settings-data-dir")
            yield Static("", id="settings-profile-path")
            yield Static("", id="settings-database-path")
            yield Static(
                "[yellow]Credential passwords are plaintext in SQLite by explicit policy.[/]",
                classes="warn",
            )

        with Vertical(classes="panel"):
            yield Static("Application safety", classes="panel-title")
            with Horizontal(classes="form-row"):
                yield Label("Evidence capture")
                yield Switch(value=True, id="sw-dry-run", disabled=True)
                yield Static("[green]always ON[/]", classes="ok")
            with Horizontal(classes="form-row"):
                yield Label("Supervised submit")
                yield Switch(value=False, id="sw-submit")
                yield Static(
                    "Requires a matching preview hash and one-use approval.",
                    classes="muted",
                )

    def on_mount(self) -> None:
        super().on_mount()
        self._loading = True
        try:
            self.query_one("#llm-provider", Select).value = self.app.settings.llm_provider
            self.query_one("#sw-submit", Switch).value = (
                self.app.settings.application_submission_enabled
            )
        finally:
            self._loading = False
        self.query_one("#settings-data-dir", Static).update(
            f"Data: [bold]{self.app.settings.data_dir}[/]"
        )
        self.query_one("#settings-profile-path", Static).update(
            f"Profile: [bold]{self.app.settings.profile_path}[/]"
        )
        self.query_one("#settings-database-path", Static).update(
            f"Database: [bold]{self.app.settings.database_path}[/]"
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if self._loading or event.select.id != "llm-provider":
            return
        provider = str(event.value)
        self.app.settings.llm_provider = provider
        try:
            strip = self.query_one("#status-strip")
            strip.provider = provider  # type: ignore[attr-defined]
        except NoMatches:
            return
        self.app.notify(f"LLM_PROVIDER → {provider}")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if self._loading or event.switch.id != "sw-submit":
            return
        enabled = event.value
        self.app.settings.application_submission_enabled = enabled
        self.app.store.set_setting(
            "application_submission_enabled",
            "true" if enabled else "false",
        )
        if enabled:
            self.app.notify(
                "Supervised submit enabled. Every application still requires review.",
                severity="warning",
            )
        else:
            self.app.notify("Supervised submit disabled")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-llm-check":
            return
        provider = self.app.settings.llm_provider
        result = self.query_one("#llm-check-result", Static)
        if provider == "off":
            result.update("[dim]Provider is off — no endpoint to check.[/]")
            return
        if provider == "openrouter":
            result.update("[yellow]checking[/]  Calling the configured OpenRouter model…")
            self._check_openrouter()
            return
        result.update(
            f"[yellow]not implemented[/]  {provider} connection check is not wired yet."
        )
        self.app.notify(f"{provider} check is not implemented", severity="information")

    @work(thread=True, exclusive=True, group="llm-check")
    def _check_openrouter(self) -> None:
        try:
            response = OpenRouterClient(self.app.settings).check_connection()
        except (LLMConfigurationError, LLMResponseError, OpenAIError) as error:
            self.app.call_from_thread(
                self._show_openrouter_result,
                False,
                f"{type(error).__name__}: {error}",
            )
            return
        self.app.call_from_thread(self._show_openrouter_result, True, response)

    def _show_openrouter_result(self, succeeded: bool, detail: str) -> None:
        result = self.query_one("#llm-check-result", Static)
        if succeeded:
            result.update(
                f"[green]connected[/]  {self.app.settings.openrouter_model} "
                f"via {self.app.settings.openrouter_provider} · {detail}"
            )
            self.app.notify("OpenRouter connection succeeded")
            return
        result.update(f"[red]OpenRouter check failed[/]  {detail}")
        self.app.notify("OpenRouter connection failed", severity="error")
