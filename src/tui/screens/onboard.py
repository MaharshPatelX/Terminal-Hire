"""Resumable first-run interview that creates and verifies PROFILE.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

from ...profile import Profile, ProfileDocument, ProfileFormatError
from .base import AppScreen


@dataclass(frozen=True, slots=True)
class OnboardQuestion:
    path: str
    prompt: str
    optional: bool = False
    sensitive: bool = False


QUESTIONS = [
    OnboardQuestion("identity.full_name", "What is your full legal name?"),
    OnboardQuestion("contact.email", "What email should applications use?"),
    OnboardQuestion("contact.phone", "What phone number should applications use?"),
    OnboardQuestion(
        "location_preferences.street_address",
        "Street address (optional).",
        optional=True,
    ),
    OnboardQuestion("location_preferences.city", "What city do you live in?"),
    OnboardQuestion(
        "location_preferences.state",
        "What state, province, or region do you live in?",
    ),
    OnboardQuestion("location_preferences.postal_code", "What is your postal / ZIP code?"),
    OnboardQuestion(
        "location_preferences.country",
        "What country do you currently live in?",
    ),
    OnboardQuestion(
        "professional_summary",
        "Give a short professional summary: role, experience, and strongest focus.",
    ),
    OnboardQuestion(
        "education",
        "List education entries. Separate multiple entries with |.",
        optional=True,
    ),
    OnboardQuestion(
        "work_history",
        "Summarize your professional history. Separate roles with |.",
        optional=True,
    ),
    OnboardQuestion(
        "projects",
        "List important projects. Separate projects with |.",
        optional=True,
    ),
    OnboardQuestion("skills", "List your skills separated with |.", optional=True),
    OnboardQuestion(
        "work_authorization.authorized",
        "Are you currently authorized to work in the United States?",
    ),
    OnboardQuestion(
        "work_authorization.sponsorship",
        "Will you now or later require employment sponsorship?",
    ),
    OnboardQuestion(
        "sensitive_identity.ssn",
        "SSN (optional). This is stored in local PROFILE.md; type skip to omit.",
        optional=True,
        sensitive=True,
    ),
    OnboardQuestion(
        "sensitive_identity.passport_number",
        "Passport number (optional); type skip to omit.",
        optional=True,
        sensitive=True,
    ),
    OnboardQuestion(
        "sensitive_identity.driver_license",
        "Driver license number (optional); type skip to omit.",
        optional=True,
        sensitive=True,
    ),
    OnboardQuestion(
        "sensitive_identity.alien_registration_number",
        "USCIS / alien registration number (optional); type skip to omit.",
        optional=True,
        sensitive=True,
    ),
    OnboardQuestion(
        "documents.resume_source",
        "Path to your primary resume source or PDF (optional).",
        optional=True,
    ),
]


class OnboardScreen(AppScreen):
    """First launch gate: collect, persist, review, and verify the profile."""

    def __init__(self) -> None:
        super().__init__()
        self._profile: Profile | None = None
        self._question_index = 0
        self._blocked = False

    def body(self) -> ComposeResult:
        yield Static("Create your PROFILE.md", classes="screen-title")
        yield Static(
            "Saved after every answer · type /back, /skip, /settings, or /help",
            classes="screen-subtitle",
        )
        with Vertical():
            yield RichLog(id="onboard-log", classes="chat-log", markup=True, wrap=True)
            with Horizontal(id="chat-input-row"):
                yield Input(
                    placeholder="Answer here…",
                    id="chat-input",
                )

    def on_mount(self) -> None:
        super().on_mount()
        log = self.query_one("#onboard-log", RichLog)
        log.write("[bold #63e6be]TUI-Hire[/]  Let’s build your application truth.")
        log.write("[dim]Your profile stays in one local Markdown file.[/]")
        try:
            self._profile = self.app.profile_service.load_or_new()
        except ProfileFormatError as error:
            self._blocked = True
            log.write(f"[bold red]PROFILE.md needs repair:[/] {error}")
            log.write(
                "[dim]Type /recover to restore the last valid backup, "
                "or move the invalid file and restart onboarding.[/]"
            )
            return
        self._question_index = self._first_unanswered_question()
        self._ask_current()
        self.query_one("#chat-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
            return
        if self._blocked or self._profile is None:
            self.app.notify("Repair PROFILE.md before continuing", severity="error")
            return

        if self._question_index >= len(QUESTIONS):
            if text.casefold() != "verify":
                self.query_one("#onboard-log", RichLog).write(
                    "[yellow]Type VERIFY to confirm these details are yours.[/]"
                )
                return
            try:
                self.app.profile_service.complete(self._profile)
            except ProfileFormatError as error:
                self.query_one("#onboard-log", RichLog).write(f"[red]{error}[/]")
                return
            self.app.profile_changed()
            self.app.notify("PROFILE.md verified and ready", severity="information")
            self.app.navigate("welcome")
            return

        question = QUESTIONS[self._question_index]
        if text.casefold() == "skip":
            if not question.optional:
                self.app.notify("This answer is required", severity="warning")
                return
            self._profile.provenance[question.path] = "user_skipped"
            shown_value = "[dim]skipped[/]"
        else:
            self._assign_answer(question.path, text)
            self._profile.verification[question.path] = "user_entered"
            self._profile.provenance[question.path] = "onboarding"
            shown_value = "[dim]saved sensitive value[/]" if question.sensitive else text

        self.app.profile_service.save_draft(self._profile)
        log = self.query_one("#onboard-log", RichLog)
        log.write(f"[bold green]you[/]  {shown_value}")
        self._question_index += 1
        self._ask_current()

    def _ask_current(self) -> None:
        if self._profile is None:
            return
        log = self.query_one("#onboard-log", RichLog)
        input_widget = self.query_one("#chat-input", Input)
        if self._question_index >= len(QUESTIONS):
            missing = self._profile.missing_required_fields()
            if missing:
                log.write(
                    "[red]Required details are still missing:[/] " + ", ".join(missing)
                )
                self._question_index = self._first_unanswered_question()
                self._ask_current()
                return
            input_widget.password = False
            input_widget.placeholder = "Type VERIFY to finish onboarding"
            log.write(
                f"[bold #63e6be]Review:[/] {self.app.settings.profile_path}\n"
                "[bold]Type VERIFY[/] to mark the profile ready."
            )
            return
        question = QUESTIONS[self._question_index]
        input_widget.password = question.sensitive
        input_widget.placeholder = "Sensitive value (hidden)" if question.sensitive else "Answer here…"
        optional = " [dim](optional; type skip)[/]" if question.optional else ""
        log.write(f"[bold cyan]onboard[/]  {question.prompt}{optional}")

    def _first_unanswered_question(self) -> int:
        if self._profile is None:
            return 0
        for index, question in enumerate(QUESTIONS):
            if not self._has_answer(question.path):
                return index
        return len(QUESTIONS)

    def _has_answer(self, path: str) -> bool:
        if self._profile is None:
            return False
        if path in self._profile.provenance:
            return True
        if path == "professional_summary":
            return bool(self._profile.professional_summary.strip())
        if path in {"education", "work_history", "projects", "skills"}:
            return bool(getattr(self._profile, path))
        if path == "documents.resume_source":
            return any(document.kind == "resume" for document in self._profile.documents)
        section, key = path.split(".", maxsplit=1)
        return bool(getattr(self._profile, section).get(key, "").strip())

    def _assign_answer(self, path: str, value: str) -> None:
        if self._profile is None:
            return
        if path == "professional_summary":
            self._profile.professional_summary = value
            return
        if path in {"education", "work_history", "projects", "skills"}:
            setattr(
                self._profile,
                path,
                [part.strip() for part in value.split("|") if part.strip()],
            )
            return
        if path == "documents.resume_source":
            source = str(Path(value).expanduser())
            existing = next(
                (document for document in self._profile.documents if document.kind == "resume"),
                None,
            )
            if existing:
                existing.path = source
                existing.active = True
            else:
                self._profile.documents.append(
                    ProfileDocument(kind="resume", path=source, label="Primary resume")
                )
            return
        section, key = path.split(".", maxsplit=1)
        getattr(self._profile, section)[key] = value

    def _handle_command(self, command: str) -> None:
        normalized = command.casefold()
        if normalized == "/help":
            self.app.notify("/back · /skip · /settings · /recover", title="Onboarding")
            return
        if normalized == "/settings":
            self.app.navigate("settings")
            return
        if normalized == "/recover":
            try:
                self._profile = self.app.profile_repository.recover_backup()
            except ProfileFormatError as error:
                self.app.notify(str(error), severity="error")
                return
            self._blocked = False
            self._question_index = self._first_unanswered_question()
            self.query_one("#onboard-log", RichLog).write("[green]Backup restored.[/]")
            self._ask_current()
            return
        if normalized == "/skip":
            if self._profile is None or self._question_index >= len(QUESTIONS):
                return
            question = QUESTIONS[self._question_index]
            if not question.optional:
                self.app.notify("This answer is required", severity="warning")
                return
            self._profile.provenance[question.path] = "user_skipped"
            self.app.profile_service.save_draft(self._profile)
            self.query_one("#onboard-log", RichLog).write(
                "[bold green]you[/]  [dim]skipped[/]"
            )
            self._question_index += 1
            self._ask_current()
            return
        if normalized == "/back":
            self._question_index = max(0, self._question_index - 1)
            self._ask_current()
            return
        self.app.notify(f"Unknown onboarding command: {command}", severity="warning")
