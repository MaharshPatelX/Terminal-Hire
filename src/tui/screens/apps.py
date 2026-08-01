"""Application audit, field review, approval, and supervised submit."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, RichLog, Static

from ...db import SubmitGateError
from .base import AppScreen


class AppsScreen(AppScreen):
    """Review every field source before granting one-use submit approval."""

    def __init__(self) -> None:
        super().__init__()
        self._selected_application_id: str | None = None
        self._selected_preview_hash: str | None = None

    def body(self) -> ComposeResult:
        yield Static("Applications", classes="screen-title")
        yield Static(
            "Values · sources · evidence · one-use supervised submit",
            classes="screen-subtitle",
        )
        with Horizontal(id="apps-layout"):
            with Vertical(classes="panel", id="apps-list-panel"):
                yield DataTable(id="apps-table", zebra_stripes=True, cursor_type="row")
            yield RichLog(id="application-review", markup=True, wrap=True)
        with Horizontal(classes="panel"):
            yield Button("Refresh", id="btn-apps-refresh")
            yield Button(
                "Approve preview", variant="success", id="btn-approve", disabled=True
            )
            yield Button("Submit once", variant="error", id="btn-submit-once", disabled=True)
            yield Button("Cancel", id="btn-cancel-app", disabled=True)

    def on_mount(self) -> None:
        super().on_mount()
        table = self.query_one("#apps-table", DataTable)
        table.add_columns("Company", "URL", "Status", "Updated")
        self._refresh_table()

    def on_screen_resume(self) -> None:
        super().on_screen_resume()
        self._refresh_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        application_id = str(event.row_key.value)
        if application_id == "empty":
            return
        self._selected_application_id = application_id
        self._show_application(application_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-apps-refresh":
            self._refresh_table()
        elif button_id == "btn-approve":
            self._approve_selected()
        elif button_id == "btn-submit-once":
            self.run_worker(self._submit_selected(), exclusive=True)
        elif button_id == "btn-cancel-app":
            self._cancel_selected()

    def _refresh_table(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.clear(columns=False)
        applications = self.app.store.list_applications()
        if not applications:
            table.add_row("—", "No applications yet", "—", "—", key="empty")
            return
        for application in applications:
            table.add_row(
                application.company or "—",
                application.job_url,
                application.status,
                application.updated_at[:19],
                key=application.id,
            )
        if self._selected_application_id:
            self._show_application(self._selected_application_id)

    def _show_application(self, application_id: str) -> None:
        application = self.app.store.get_application(application_id)
        review = self.query_one("#application-review", RichLog)
        review.clear()
        if application is None:
            review.write("[red]Application no longer exists.[/]")
            return
        self._selected_preview_hash = application.preview_hash
        review.write(f"[bold]{application.company or 'Application'}[/]")
        review.write(f"[dim]{application.job_url}[/]")
        review.write(
            f"status=[bold]{application.status}[/]  "
            f"profile={application.profile_hash[:12]}…"
        )
        if application.preview_hash:
            review.write(f"preview={application.preview_hash[:12]}…")
        actions = self.app.store.field_actions(application_id)
        if not actions:
            review.write("\n[yellow]No field actions recorded yet.[/]")
        for action in actions:
            value = "<sensitive value>" if action["sensitive"] else action["value"]
            review.write(
                f"\n[bold #63e6be]{action['field_name']}[/] = {value}\n"
                f"[dim]{action['source']} · confidence {action['confidence']:.2f} "
                f"· {action['status']}[/]"
            )
        artifacts = self.app.store.artifacts(application_id)
        events = self.app.store.application_events(application_id)
        review.write(
            f"\n\n[bold]Evidence[/]  {len(events)} events · "
            f"{len(artifacts)} redacted artifacts"
        )
        for artifact in artifacts[-5:]:
            review.write(f"[dim]{artifact['kind']} · {artifact['path']}[/]")
        can_approve = (
            bool(application.preview_hash)
            and application.status == "waiting_for_user_review"
        )
        self.query_one("#btn-approve", Button).disabled = not can_approve
        has_session = application_id in self.app.browser_sessions
        self.query_one("#btn-submit-once", Button).disabled = not (
            has_session
            and application.preview_hash
            and self.app.settings.application_submission_enabled
            and application.status == "approved"
        )
        self.query_one("#btn-cancel-app", Button).disabled = application.status in {
            "submitted",
            "cancelled",
        }

    def _approve_selected(self) -> None:
        if not self._selected_application_id or not self._selected_preview_hash:
            return
        try:
            self.app.application_service.approve(
                self._selected_application_id,
                self._selected_preview_hash,
            )
        except SubmitGateError as error:
            self.app.notify(str(error), severity="error")
            return
        self.app.notify("Preview approved for one Submit click")
        self._show_application(self._selected_application_id)

    async def _submit_selected(self) -> None:
        if not self._selected_application_id or not self._selected_preview_hash:
            return
        session = self.app.browser_sessions.get(self._selected_application_id)
        if session is None:
            self.app.notify(
                "The audited browser session is no longer active",
                severity="error",
            )
            return
        session.submission_enabled = self.app.settings.application_submission_enabled
        try:
            confirmed = await session.submit_once(self._selected_preview_hash)
        except SubmitGateError as error:
            self.app.notify(str(error), severity="error")
            self._refresh_table()
            return
        finally:
            await session.__aexit__(None, None, None)
            self.app.browser_sessions.pop(self._selected_application_id, None)
        self.app.notify(
            "Submission confirmed" if confirmed else "Submission result is uncertain",
            severity="information" if confirmed else "warning",
        )
        self._refresh_table()

    def _cancel_selected(self) -> None:
        if not self._selected_application_id:
            return
        self.app.store.set_status(self._selected_application_id, "cancelled")
        self.app.store.log_event(
            self._selected_application_id,
            event_type="application_cancelled",
        )
        self.app.notify("Application cancelled")
        self._refresh_table()
