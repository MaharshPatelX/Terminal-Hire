"""Applications list — preview / Approve / OTP / Cancel shell."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static


class AppsScreen(Screen):
    """List applications by status; detail actions later."""

    def compose(self) -> ComposeResult:
        yield Static("Applications", classes="screen-title")
        yield Static(
            "Preview · Approve · site OTP · CAPTCHA resume · Cancel",
            classes="screen-subtitle",
        )
        with Vertical(classes="panel"):
            table = DataTable(id="apps-table", zebra_stripes=True)
            yield table
        with Horizontal(classes="panel"):
            yield Button("Approve preview", variant="success", id="btn-approve", disabled=True)
            yield Button("Enter OTP", id="btn-otp", disabled=True)
            yield Button("Resume", id="btn-resume", disabled=True)
            yield Button("Cancel", id="btn-cancel-app", disabled=True)

    def on_mount(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.add_columns("Company", "Title", "Status", "Updated")
        table.add_row("—", "No applications yet", "—", "—")
