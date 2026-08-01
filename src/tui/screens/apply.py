"""Audited apply-by-URL workspace."""

from __future__ import annotations

from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, RichLog, Static

from ...browser import BrowserSession
from ...db import SubmitGateError
from ...profile import ProfileFormatError
from .base import AppScreen


class ApplyScreen(AppScreen):
    """Create an application, resolve fields, and run an audited browser."""

    def __init__(self) -> None:
        super().__init__()
        self._application_id: str | None = None
        self._pending_field: tuple[str, str] | None = None
        self._preview_hash: str | None = None
        self._browser_one_off: dict[tuple[str, str], str] = {}

    def body(self) -> ComposeResult:
        yield Static("Apply by URL", classes="screen-title")
        yield Static(
            "PROFILE.md truth · step evidence · explicit review before one Submit click",
            classes="screen-subtitle",
        )
        with Vertical(classes="panel"):
            yield Static("Application", classes="panel-title")
            yield Input(placeholder="https://company.com/jobs/123", id="apply-url")
            yield Input(placeholder="Company name (optional)", id="apply-company")
            with Horizontal():
                yield Button("Start audited application", variant="primary", id="btn-start-apply")
                yield Button("Run browser fill", id="btn-run-browser", disabled=True)

        with Horizontal(classes="panel"):
            with Vertical():
                yield Static("Site account (plaintext SQLite)", classes="panel-title")
                yield Input(
                    placeholder="Credential domain (blank = current application URL)",
                    id="credential-domain",
                )
                yield Input(placeholder="Login email", id="credential-email")
                yield Input(placeholder="Username (if different)", id="credential-username")
                yield Input(
                    placeholder="Password",
                    id="credential-password",
                    password=True,
                )
                yield Button("Save site credential", id="btn-save-credential")
            with Vertical():
                yield Static("OTP / blocker", classes="panel-title")
                yield Input(placeholder="One-time code (never stored)", id="apply-otp", password=True)
                with Horizontal():
                    yield Button("Enter OTP", id="btn-enter-otp", disabled=True)
                    yield Button("Resume browser", id="btn-resume-browser", disabled=True)

        with Vertical(classes="panel"):
            yield Static("Resolve one portal field", classes="panel-title")
            yield Input(placeholder="Field name, e.g. email", id="apply-field-name")
            yield Input(placeholder="Portal question / label", id="apply-question")
            with Horizontal():
                yield Button("Resolve from PROFILE.md", id="btn-resolve-field", disabled=True)
                yield Button("Build review", id="btn-build-preview", disabled=True)
            yield Input(placeholder="Answer when PROFILE.md has no match", id="apply-user-answer")
            yield Input(placeholder="Reusable intent, e.g. willing_to_relocate", id="apply-answer-intent")
            with Horizontal():
                yield Button("Use once", id="btn-use-once", disabled=True)
                yield Button("Save to PROFILE.md + use", id="btn-save-and-use", disabled=True)
        yield RichLog(id="apply-log", classes="chat-log", markup=True, wrap=True)

    def on_mount(self) -> None:
        super().on_mount()
        log = self.query_one("#apply-log", RichLog)
        log.write(
            "[dim]system[/]  Every application uses a PROFILE.md content hash."
        )
        log.write(
            "[dim]system[/]  Passwords are plaintext in local SQLite by explicit policy; "
            "values never enter event logs."
        )
        log.write("[dim]system[/]  CAPTCHA, OTP, consent, and unknown answers pause.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-start-apply":
            self._start_application()
        elif button_id == "btn-save-credential":
            self._save_credential()
        elif button_id == "btn-resolve-field":
            self._resolve_field()
        elif button_id == "btn-use-once":
            self._answer_unknown(save_to_profile=False)
        elif button_id == "btn-save-and-use":
            self._answer_unknown(save_to_profile=True)
        elif button_id == "btn-build-preview":
            self._build_preview()
        elif button_id == "btn-run-browser":
            self.run_worker(self._run_browser(), exclusive=True)
        elif button_id == "btn-enter-otp":
            self.run_worker(self._enter_otp(), exclusive=True)
        elif button_id == "btn-resume-browser":
            self.run_worker(self._resume_browser(), exclusive=True)

    def _start_application(self) -> None:
        url = self.query_one("#apply-url", Input).value.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            self.app.notify("Enter a valid http(s) application URL", severity="warning")
            return
        company = self.query_one("#apply-company", Input).value.strip()
        try:
            application = self.app.application_service.start(url=url, company=company)
        except ProfileFormatError as error:
            self.app.notify(str(error), severity="error")
            return
        self._application_id = application.id
        self._preview_hash = None
        self.query_one("#apply-log", RichLog).write(
            f"[bold cyan]application[/]  {application.id}\n"
            f"[dim]profile snapshot[/]  {application.profile_hash[:12]}…"
        )
        for selector in (
            "#btn-run-browser",
            "#btn-resolve-field",
            "#btn-build-preview",
        ):
            self.query_one(selector, Button).disabled = False
        self.app.notify("Audited application created")

    def _save_credential(self) -> None:
        url = self.query_one("#apply-url", Input).value.strip()
        domain = self.query_one("#credential-domain", Input).value.strip() or url
        email = self.query_one("#credential-email", Input).value.strip()
        username = self.query_one("#credential-username", Input).value.strip()
        password_widget = self.query_one("#credential-password", Input)
        if not domain or not password_widget.value:
            self.app.notify("Credential domain and password are required", severity="warning")
            return
        try:
            self.app.store.save_credential(
                domain=domain,
                email=email,
                username=username,
                password=password_widget.value,
            )
        except ValueError as error:
            self.app.notify(str(error), severity="error")
            return
        password_widget.value = ""
        self.query_one("#apply-log", RichLog).write(
            "[yellow]credential[/]  Saved locally as plaintext; password not logged."
        )

    def _resolve_field(self) -> None:
        if self._application_id is None:
            return
        field_name = self.query_one("#apply-field-name", Input).value.strip()
        question = self.query_one("#apply-question", Input).value.strip()
        company = self.query_one("#apply-company", Input).value.strip() or None
        if not field_name and not question:
            self.app.notify("Enter a field name or portal question", severity="warning")
            return
        planned = self.app.application_service.plan_field(
            self._application_id,
            field_name=field_name,
            question=question,
            company=company,
        )
        result = planned.result
        log = self.query_one("#apply-log", RichLog)
        if result.requires_user:
            self._pending_field = (field_name, question)
            log.write(
                f"[yellow]ask you[/]  {question or field_name}\n"
                f"[dim]{result.reason}[/]"
            )
            self.query_one("#btn-use-once", Button).disabled = False
            self.query_one("#btn-save-and-use", Button).disabled = False
            return
        shown = "<sensitive value>" if result.sensitive else result.value
        log.write(
            f"[green]resolved[/]  {field_name or question} = {shown}\n"
            f"[dim]{result.source} · confidence {result.confidence:.2f}[/]"
        )

    def _answer_unknown(self, *, save_to_profile: bool) -> None:
        if self._application_id is None or self._pending_field is None:
            return
        answer_widget = self.query_one("#apply-user-answer", Input)
        answer = answer_widget.value.strip()
        if not answer:
            self.app.notify("Enter your answer first", severity="warning")
            return
        field_name, question = self._pending_field
        intent = self.query_one("#apply-answer-intent", Input).value.strip()
        company = self.query_one("#apply-company", Input).value.strip() or None
        self.app.application_service.answer_unknown(
            self._application_id,
            field_name=field_name,
            question=question,
            answer=answer,
            save_to_profile=save_to_profile,
            intent=intent,
            company=company if save_to_profile else None,
        )
        action = "saved to PROFILE.md" if save_to_profile else "used once"
        self.query_one("#apply-log", RichLog).write(
            f"[green]user answer[/]  {field_name or question} · {action}"
        )
        answer_widget.value = ""
        self._pending_field = None
        self.query_one("#btn-use-once", Button).disabled = True
        self.query_one("#btn-save-and-use", Button).disabled = True
        if self._application_id in self.app.browser_sessions:
            if not save_to_profile:
                self._browser_one_off[(field_name, question)] = answer
            self.query_one("#btn-resume-browser", Button).disabled = False
        self.app.profile_changed()

    def _build_preview(self) -> None:
        if self._application_id is None:
            return
        try:
            self._preview_hash = self.app.application_service.build_preview(
                self._application_id
            )
        except SubmitGateError as error:
            self.app.notify(str(error), severity="warning")
            return
        self.query_one("#apply-log", RichLog).write(
            f"[bold #63e6be]review ready[/]  {self._preview_hash[:12]}…\n"
            "[dim]Open Applications to inspect sources and approve.[/]"
        )

    async def _run_browser(self) -> None:
        if self._application_id is None:
            return
        url = self.query_one("#apply-url", Input).value.strip()
        old_session = self.app.browser_sessions.pop(self._application_id, None)
        if old_session is not None:
            await old_session.__aexit__(None, None, None)
        session = BrowserSession(
            store=self.app.store,
            artifact_dir=self.app.settings.artifact_dir,
            application_id=self._application_id,
            headless=getattr(self.app.settings, "playwright_headless", False),
            submission_enabled=self.app.settings.application_submission_enabled,
        )
        log = self.query_one("#apply-log", RichLog)
        try:
            await session.__aenter__()
            self.app.browser_sessions[self._application_id] = session
            await session.open(url)
            current_url = session.page.url if session.page is not None else url
            credential = self.app.store.get_credential(current_url)
            if credential is not None:
                filled = await session.fill_login(credential)
                if filled:
                    blocker = await session.continue_login()
                    if blocker is not None:
                        log.write(f"[yellow]{blocker.kind}[/]  {blocker.message}")
                        self.query_one("#btn-enter-otp", Button).disabled = (
                            blocker.kind != "otp"
                        )
                        self.query_one("#btn-resume-browser", Button).disabled = False
                        return
            elif urlparse(current_url).hostname != urlparse(url).hostname:
                log.write(
                    "[yellow]credential paused[/]  The page redirected to "
                    f"{urlparse(current_url).hostname}; save a credential for that domain."
                )
                self.app.store.set_status(
                    self._application_id,
                    "waiting_for_credential",
                )
                return
            await self._fill_browser_fields(session)
        except (PlaywrightError, ProfileFormatError, RuntimeError, ValueError) as error:
            log.write(f"[red]browser stopped[/]  {type(error).__name__}: {error}")
            self.app.browser_sessions.pop(self._application_id, None)
            await session.__aexit__(None, None, None)
            self.app.notify(
                "Browser failed. Ensure Chromium is installed with "
                "`uv run playwright install chromium`.",
                severity="error",
            )

    async def _enter_otp(self) -> None:
        if self._application_id is None:
            return
        session = self.app.browser_sessions.get(self._application_id)
        if session is None:
            self.app.notify("No browser session is waiting", severity="warning")
            return
        otp_widget = self.query_one("#apply-otp", Input)
        otp = otp_widget.value.strip()
        if not otp:
            self.app.notify("Enter the OTP first", severity="warning")
            return
        await session.enter_otp(otp)
        otp_widget.value = ""
        blocker = await session.continue_login()
        if blocker is not None:
            self.query_one("#apply-log", RichLog).write(
                f"[yellow]{blocker.kind}[/]  {blocker.message}"
            )
            return
        await self._fill_browser_fields(session)

    async def _resume_browser(self) -> None:
        if self._application_id is None:
            return
        session = self.app.browser_sessions.get(self._application_id)
        if session is None:
            self.app.notify("No browser session is available", severity="warning")
            return
        blocker = (
            await session.continue_login()
            if session.authentication_pending
            else await session.detect_blocker()
        )
        if blocker is not None:
            self.query_one("#apply-log", RichLog).write(
                f"[yellow]{blocker.kind}[/]  {blocker.message}"
            )
            return
        await self._fill_browser_fields(session)

    async def _fill_browser_fields(self, session: BrowserSession) -> None:
        if self._application_id is None:
            return
        snapshot = self.app.profile_service.snapshot()
        application = self.app.store.get_application(self._application_id)
        if application and application.profile_hash != snapshot.content_hash:
            self.app.store.update_application_profile(
                self._application_id,
                snapshot.content_hash,
            )
        company = self.query_one("#apply-company", Input).value.strip() or None
        for field in await session.inventory_fields():
            if field.field_type in {"password", "hidden"}:
                continue
            one_off_key = (field.name, field.label)
            one_off_answer = self._browser_one_off.get(one_off_key)
            if one_off_answer is not None:
                await session.fill_field(
                    field,
                    value=one_off_answer,
                    source="user:one_off",
                    confidence=1.0,
                    sensitive=self.app.profile_retriever.is_sensitive_prompt(
                        field_name=field.name,
                        question=field.label,
                    ),
                )
                self._browser_one_off.pop(one_off_key, None)
                continue
            result = self.app.profile_retriever.resolve(
                snapshot,
                field_name=field.name,
                question=field.label,
                company=company,
            )
            if result.requires_user or result.value is None:
                self._pending_field = (field.name, field.label)
                self.query_one("#apply-field-name", Input).value = field.name
                self.query_one("#apply-question", Input).value = field.label
                self.query_one("#btn-use-once", Button).disabled = False
                self.query_one("#btn-save-and-use", Button).disabled = False
                self.query_one("#apply-log", RichLog).write(
                    f"[yellow]browser paused[/]  Need your answer: {field.label or field.name}"
                )
                self.app.store.set_status(self._application_id, "waiting_for_user_answer")
                return
            await session.fill_field(
                field,
                value=result.value,
                source=result.source,
                confidence=result.confidence,
                sensitive=result.sensitive,
            )
        self._preview_hash = self.app.store.build_preview(self._application_id)
        self.query_one("#apply-log", RichLog).write(
            f"[green]browser fill complete[/]  review {self._preview_hash[:12]}…"
        )
        self.query_one("#btn-resume-browser", Button).disabled = False
