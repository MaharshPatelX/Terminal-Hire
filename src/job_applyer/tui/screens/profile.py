"""Profile / Packs screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Static

from job_applyer.tui.screens.base import AppScreen

PACKS = [
    ("US_CITIZEN", "US citizen / work eligible"),
    ("US_PR", "Permanent resident (green card)"),
    ("OTHER_US_AUTH", "Other US work authorization"),
    ("F1_OPT", "F-1 OPT"),
    ("STEM_OPT", "F-1 STEM OPT"),
]


class ProfileScreen(AppScreen):
    """Browse facts + enable/disable work-auth packs."""

    def body(self) -> ComposeResult:
        yield Static("Profile / Packs", classes="screen-title")
        yield Static(
            "Core facts always on · packs only when you need them",
            classes="screen-subtitle",
        )
        with Vertical(classes="panel"):
            yield Static("Work-authorization packs", classes="panel-title")
            yield Static(
                "[dim]Disabled packs: no questions, no mapper context, no STEM/H-1B framing.[/]",
                classes="muted",
            )
            for pack_id, label in PACKS:
                yield Checkbox(label, id=f"pack-{pack_id}", value=False)
        with Vertical(classes="panel"):
            yield Static("Core profile", classes="panel-title")
            yield Static("Status: [yellow]not onboarded[/]  ·  Market: [bold]US[/]")
            yield Static(
                "[dim]Facts appear here after Onboard (M1/M2).[/]",
                classes="muted",
            )
            with Horizontal():
                yield Button("Refresh", id="btn-refresh")
                yield Button("Verify selected…", id="btn-verify", disabled=True)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        enabled = [
            pid for pid, _ in PACKS if self.query_one(f"#pack-{pid}", Checkbox).value
        ]
        packs = ",".join(enabled) if enabled else "none"
        self.app.enabled_packs = packs
        try:
            strip = self.query_one("#status-strip")
            strip.packs = packs  # type: ignore[attr-defined]
        except Exception:
            pass
        self.app.notify(f"Packs: {packs}")
