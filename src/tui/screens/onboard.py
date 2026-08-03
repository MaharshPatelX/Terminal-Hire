"""Resumable private interview with local validation and redacted AI review."""

from __future__ import annotations

from openai import OpenAIError
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

from ...llm import LLMConfigurationError, LLMResponseError, OpenRouterClient
from ...onboarding import OnboardingAgent, OnboardingFlow, OnboardingIssue, OnboardingQuestion
from ...profile import Profile, ProfileFormatError
from .base import AppScreen


class OnboardScreen(AppScreen):
    """Collect locally, validate deterministically, and review through safe AI context."""

    AUTO_FOCUS = "#chat-input"

    def __init__(self) -> None:
        super().__init__()
        self._flow = OnboardingFlow()
        self._profile: Profile | None = None
        self._active_question: OnboardingQuestion | None = None
        self._active_issue: OnboardingIssue | None = None
        self._review_queue: list[OnboardingIssue] = []
        self._history: list[str] = []
        self._review_fingerprints: set[tuple[tuple[str, str], ...]] = set()
        self._review_round = 0
        self._blocked = False
        self._awaiting_ai = False
        self._ready_for_verify = False

    def body(self) -> ComposeResult:
        yield Static("Create your PROFILE.md", classes="screen-title")
        yield Static(
            "Validated before save · /back · /skip · /settings · /help",
            classes="screen-subtitle",
        )
        with Vertical():
            yield RichLog(id="onboard-log", classes="chat-log", markup=True, wrap=True)
            with Horizontal(id="chat-input-row"):
                yield Input(placeholder="Answer here…", id="chat-input")

    def on_mount(self) -> None:
        super().on_mount()
        log = self.query_one("#onboard-log", RichLog)
        log.write("[bold #63e6be]TUI-Hire[/]  Let’s build a reliable application profile.")
        log.write(
            "[dim]Identity, contact, location, authorization, documents, SSNs, "
            "passport data, and credentials are never sent to OpenRouter.[/]"
        )
        log.write(
            "[dim]AI may phrase questions and review only a redacted professional profile. "
            "Python validates every structured answer before it is saved.[/]"
        )
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
        self._continue_interview()
        self._focus_answer_box()

    def on_screen_resume(self) -> None:
        self._focus_answer_box()

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
        if self._awaiting_ai:
            self.app.notify("Wait for the interviewer to finish", severity="warning")
            return
        if self._ready_for_verify:
            self._finish_if_verified(text)
            return
        question = self._active_question
        if question is None:
            return
        if text.casefold() == "skip":
            self._skip_active()
            return

        result = self._flow.validate(question, text, self._profile)
        if not result.valid or result.value is None:
            self.query_one("#onboard-log", RichLog).write(
                f"[yellow]check[/]  {result.error}"
            )
            self._ask_specific(question, result.error)
            return

        was_review = self._active_issue is not None
        self._flow.assign(self._profile, question, result.value)
        self.app.profile_service.save_draft(self._profile)
        if not self._history or self._history[-1] != question.path:
            self._history.append(question.path)
        shown = (
            "[dim]saved locally[/]"
            if question.privacy == "local_only"
            else self._display_value(result.value)
        )
        self.query_one("#onboard-log", RichLog).write(f"[bold green]you[/]  {shown}")
        self._active_question = None
        self._active_issue = None
        if was_review:
            self._continue_review_queue()
        else:
            self._continue_interview()

    def _continue_interview(self) -> None:
        if self._profile is None:
            return
        self._ready_for_verify = False
        candidates = self._flow.pending_questions(self._profile)
        if not candidates:
            self._start_review()
            return
        if self._ai_enabled():
            self._set_waiting("AI interviewer is choosing the next safe question…")
            self._request_ai_question(candidates)
            return
        self._show_question(candidates[0], candidates[0].prompt)

    def _ask_specific(self, question: OnboardingQuestion, problem: str) -> None:
        if self._ai_enabled():
            self._set_waiting("AI interviewer is preparing a correction…")
            self._request_ai_rephrase(question, problem)
            return
        self._show_question(question, f"{problem} {question.prompt}")

    def _start_review(self) -> None:
        if self._profile is None:
            return
        local_issues = self._flow.local_review(self._profile)
        if local_issues:
            self.query_one("#onboard-log", RichLog).write(
                f"[bold yellow]local review[/]  Found {len(local_issues)} item(s) to fix."
            )
            self._review_queue = local_issues
            self._continue_review_queue()
            return
        if not self._ai_enabled():
            self._ready_for_confirmation("Local validation passed; AI review is off.")
            return
        max_rounds = max(1, self.app.settings.onboarding_ai_max_review_rounds)
        if self._review_round >= max_rounds:
            self._ready_for_confirmation(
                "AI review reached its configured round limit; local validation passed."
            )
            return
        self._review_round += 1
        self._set_waiting(
            f"Redacted professional review {self._review_round}/{max_rounds}…"
        )
        self._request_ai_review(self._flow.safe_status(self._profile))

    def _continue_review_queue(self) -> None:
        if not self._review_queue:
            self._start_review()
            return
        issue = self._review_queue.pop(0)
        question = self._flow.question_by_path.get(issue.path)
        if question is None:
            self._continue_review_queue()
            return
        self._active_issue = issue
        self.query_one("#onboard-log", RichLog).write(
            f"[bold yellow]{issue.source} review[/]  {issue.problem}"
        )
        self._ask_specific(question, issue.question)

    def _ready_for_confirmation(self, message: str) -> None:
        if self._profile is None:
            return
        self._ready_for_verify = True
        self._active_question = None
        self._active_issue = None
        input_widget = self.query_one("#chat-input", Input)
        input_widget.disabled = False
        input_widget.password = False
        input_widget.placeholder = "Type VERIFY to finish, or /back to revise"
        self.query_one("#onboard-log", RichLog).write(
            f"[green]review complete[/]  {message}\n"
            f"[bold #63e6be]Review the local file:[/] {self.app.settings.profile_path}\n"
            "[bold]Type VERIFY[/] only when the profile is accurate."
        )
        self._focus_answer_box()

    def _finish_if_verified(self, text: str) -> None:
        if text.casefold() != "verify":
            self.query_one("#onboard-log", RichLog).write(
                "[yellow]Type VERIFY to confirm, or /back to revise an answer.[/]"
            )
            return
        assert self._profile is not None
        local_issues = self._flow.local_review(self._profile)
        if local_issues:
            self._ready_for_verify = False
            self._review_queue = local_issues
            self._continue_review_queue()
            return
        try:
            self.app.profile_service.complete(self._profile)
        except ProfileFormatError as error:
            self.query_one("#onboard-log", RichLog).write(f"[red]{error}[/]")
            return
        self.app.profile_changed()
        self.app.notify("PROFILE.md verified and ready", severity="information")
        self.app.navigate("welcome")

    def _skip_active(self) -> None:
        if self._profile is None or self._active_question is None:
            return
        question = self._active_question
        if not question.optional:
            self.app.notify("This answer is required", severity="warning")
            return
        if self._active_issue is not None and self._active_issue.source == "local":
            self.app.notify("The local review requires an answer here", severity="warning")
            return
        self._flow.skip(self._profile, question)
        self.app.profile_service.save_draft(self._profile)
        self.query_one("#onboard-log", RichLog).write(
            "[bold green]you[/]  [dim]skipped[/]"
        )
        was_review = self._active_issue is not None
        self._active_question = None
        self._active_issue = None
        if was_review:
            self._continue_review_queue()
        else:
            self._continue_interview()

    def _set_waiting(self, message: str) -> None:
        self._awaiting_ai = True
        input_widget = self.query_one("#chat-input", Input)
        input_widget.disabled = True
        input_widget.password = False
        input_widget.placeholder = message

    def _show_question(self, question: OnboardingQuestion, message: str) -> None:
        self._awaiting_ai = False
        self._active_question = question
        input_widget = self.query_one("#chat-input", Input)
        input_widget.disabled = False
        input_widget.password = False
        input_widget.placeholder = "Answer locally…"
        optional = " [dim](optional; type skip)[/]" if question.optional else ""
        self.query_one("#onboard-log", RichLog).write(
            f"[bold cyan]interviewer[/]  {message}{optional}"
        )
        self._focus_answer_box()

    def _focus_answer_box(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        if not input_widget.disabled:
            self.call_after_refresh(input_widget.focus)

    def _ai_enabled(self) -> bool:
        return bool(
            self.app.settings.onboarding_ai_enabled
            and self.app.settings.llm_provider == "openrouter"
        )

    def _agent(self) -> OnboardingAgent:
        return OnboardingAgent(
            OpenRouterClient(self.app.settings),
            model=self.app.settings.onboarding_ai_model,
        )

    @work(thread=True, exclusive=True, group="onboarding-question")
    def _request_ai_question(self, candidates: list[OnboardingQuestion]) -> None:
        try:
            assert self._profile is not None
            question, message = self._agent().choose_question(
                candidates,
                self._flow.safe_status(self._profile),
            )
        except (LLMConfigurationError, LLMResponseError, OpenAIError, ValueError):
            question = candidates[0]
            message = question.prompt
            self.app.call_from_thread(
                self.app.notify,
                "AI interviewer unavailable; using the validated local question.",
                severity="warning",
            )
        self.app.call_from_thread(self._show_question, question, message)

    @work(thread=True, exclusive=True, group="onboarding-question")
    def _request_ai_rephrase(
        self,
        question: OnboardingQuestion,
        problem: str,
    ) -> None:
        try:
            message = self._agent().rephrase_question(question, problem)
        except (LLMConfigurationError, LLMResponseError, OpenAIError, ValueError):
            message = f"{problem} {question.prompt}"
        self.app.call_from_thread(self._show_question, question, message)

    @work(thread=True, exclusive=True, group="onboarding-review")
    def _request_ai_review(self, safe_projection: dict[str, object]) -> None:
        error = ""
        try:
            issues = self._agent().review(safe_projection)
        except (LLMConfigurationError, LLMResponseError, OpenAIError, ValueError) as caught:
            issues = []
            error = type(caught).__name__
        self.app.call_from_thread(self._receive_ai_review, issues, error)

    def _receive_ai_review(self, issues: list[OnboardingIssue], error: str) -> None:
        self._awaiting_ai = False
        if error:
            self._ready_for_confirmation(
                f"AI review was unavailable ({error}); local validation passed."
            )
            return
        if not issues:
            self._ready_for_confirmation("Local and redacted AI reviews passed.")
            return
        fingerprint = tuple(sorted((issue.path, issue.problem.casefold()) for issue in issues))
        if fingerprint in self._review_fingerprints:
            self._ready_for_confirmation(
                "AI review repeated the same advice; local validation passed."
            )
            return
        self._review_fingerprints.add(fingerprint)
        self.query_one("#onboard-log", RichLog).write(
            f"[bold yellow]AI review[/]  Found {len(issues)} professional item(s) to improve."
        )
        self._review_queue = issues
        self._continue_review_queue()

    def _handle_command(self, command: str) -> None:
        normalized = command.casefold()
        if normalized == "/help":
            self.app.notify(
                "/back · /skip · /settings · /recover",
                title="Onboarding",
            )
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
            self._ready_for_verify = False
            self._active_question = None
            self._review_queue = []
            self.query_one("#onboard-log", RichLog).write("[green]Backup restored.[/]")
            self._continue_interview()
            return
        if normalized == "/skip":
            self._skip_active()
            return
        if normalized == "/back":
            if self._profile is None or not self._history:
                self.app.notify("No earlier answer is available", severity="warning")
                return
            path = self._history.pop()
            question = self._flow.question_by_path[path]
            self._ready_for_verify = False
            self._review_queue = []
            self._active_issue = None
            self._ask_specific(question, "Let’s revise your previous answer.")
            return
        self.app.notify(f"Unknown onboarding command: {command}", severity="warning")

    @staticmethod
    def _display_value(value: str | list[str]) -> str:
        if isinstance(value, list):
            return " | ".join(value)
        return value
