"""PROFILE.md editor, work-auth packs, documents, and reusable Q&A."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Static, TextArea

from ...profile import ProfileDocument, ProfileFormatError
from .base import AppScreen

PACKS = [
    ("US_CITIZEN", "US citizen / work eligible"),
    ("US_PR", "Permanent resident (green card)"),
    ("OTHER_US_AUTH", "Other US work authorization"),
    ("F1_OPT", "F-1 OPT"),
    ("STEM_OPT", "F-1 STEM OPT"),
]


class ProfileScreen(AppScreen):
    """Ongoing editor for the user's single Markdown profile."""

    def __init__(self) -> None:
        super().__init__()
        self._loading = False

    def body(self) -> ComposeResult:
        yield Static("Profile", classes="screen-title")
        yield Static(
            "Edit verified facts, documents, packs, and reusable portal answers",
            classes="screen-subtitle",
        )
        with Horizontal(id="profile-layout"):
            with VerticalScroll(id="profile-editor"):
                with Vertical(classes="panel"):
                    yield Static("", id="profile-status")
                    yield Static("", id="profile-path", classes="muted")
                    with Horizontal(classes="form-row"):
                        yield Button("Refresh", id="btn-profile-refresh")
                        yield Button(
                            "Verify profile",
                            variant="success",
                            id="btn-profile-verify",
                        )

                with Vertical(classes="panel"):
                    yield Static("Edit a field", classes="panel-title")
                    yield Input(
                        placeholder="Path, e.g. identity.full_name or contact.linkedin",
                        id="profile-field-path",
                    )
                    yield Input(placeholder="Value", id="profile-field-value")
                    yield Static(
                        "Lists use | between items. Sensitive identity values stay local "
                        "and are never sent to AI.",
                        classes="muted",
                    )
                    yield Button("Save verified field", variant="primary", id="btn-save-field")

                with Vertical(classes="panel"):
                    yield Static("Reusable portal answer", classes="panel-title")
                    yield Input(placeholder="Normalized intent, e.g. relocation", id="qa-intent")
                    yield Input(placeholder="Question as shown by the portal", id="qa-question")
                    yield Input(placeholder="Your verified answer", id="qa-answer")
                    yield Input(
                        placeholder="Company domain (blank = global)",
                        id="qa-company",
                    )
                    yield Button("Save answer", variant="primary", id="btn-save-answer")

                with Vertical(classes="panel"):
                    yield Static("Primary resume / document", classes="panel-title")
                    yield Input(placeholder=r"C:\path\to\resume.pdf", id="profile-document")
                    yield Button("Save primary resume", id="btn-save-document")

                with Vertical(classes="panel"):
                    yield Static("Work-authorization packs", classes="panel-title")
                    yield Static(
                        "Disabled packs never enter form-mapping context.",
                        classes="muted",
                    )
                    for pack_id, label in PACKS:
                        yield Checkbox(label, id=f"pack-{pack_id}", value=False)

            yield TextArea("", id="profile-preview", read_only=True)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if self._loading:
            return
        enabled = [
            pid for pid, _ in PACKS if self.query_one(f"#pack-{pid}", Checkbox).value
        ]
        profile = self.app.profile_service.load_or_new()
        profile.enabled_packs = enabled
        profile.verification["enabled_packs"] = "user_verified"
        self.app.profile_repository.save(profile)
        self.app.profile_changed()
        self._refresh_profile()

    def on_mount(self) -> None:
        super().on_mount()
        self._refresh_profile()

    def on_screen_resume(self) -> None:
        super().on_screen_resume()
        self._refresh_profile()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "profile-field-path":
            return
        value_input = self.query_one("#profile-field-value", Input)
        value_input.password = event.value.strip().startswith("sensitive_identity.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-profile-refresh":
            self._refresh_profile()
        elif button_id == "btn-profile-verify":
            self._verify_profile()
        elif button_id == "btn-save-field":
            self._save_field()
        elif button_id == "btn-save-answer":
            self._save_answer()
        elif button_id == "btn-save-document":
            self._save_document()

    def _save_field(self) -> None:
        path = self.query_one("#profile-field-path", Input).value.strip()
        value_widget = self.query_one("#profile-field-value", Input)
        value = value_widget.value.strip()
        if not path:
            self.app.notify("Enter a profile field path", severity="warning")
            return
        try:
            self.app.profile_service.set_value(path, value, verified=True)
        except (ValueError, ProfileFormatError) as error:
            self.app.notify(str(error), severity="error")
            return
        value_widget.value = ""
        self.app.profile_changed()
        self._refresh_profile()
        self.app.notify(f"Saved {path}")

    def _save_answer(self) -> None:
        intent = self.query_one("#qa-intent", Input).value.strip()
        question = self.query_one("#qa-question", Input).value.strip()
        answer = self.query_one("#qa-answer", Input).value.strip()
        company = self.query_one("#qa-company", Input).value.strip() or None
        if not all((intent, question, answer)):
            self.app.notify("Intent, question, and answer are required", severity="warning")
            return
        scope = "company" if company else "global"
        try:
            self.app.profile_service.add_portal_answer(
                intent=intent,
                question=question,
                answer=answer,
                company=company,
                scope=scope,
                verified=True,
            )
        except (ValueError, ProfileFormatError) as error:
            self.app.notify(str(error), severity="error")
            return
        for selector in ("#qa-intent", "#qa-question", "#qa-answer", "#qa-company"):
            self.query_one(selector, Input).value = ""
        self._refresh_profile()
        self.app.notify("Reusable answer saved")

    def _save_document(self) -> None:
        path = self.query_one("#profile-document", Input).value.strip()
        if not path:
            self.app.notify("Enter a document path", severity="warning")
            return
        profile = self.app.profile_service.load_or_new()
        existing = next(
            (document for document in profile.documents if document.kind == "resume"),
            None,
        )
        if existing:
            existing.path = path
            existing.active = True
        else:
            profile.documents.append(
                ProfileDocument(kind="resume", path=path, label="Primary resume")
            )
        profile.verification["documents.resume"] = "user_verified"
        self.app.profile_repository.save(profile)
        self._refresh_profile()
        self.app.notify("Primary resume saved")

    def _verify_profile(self) -> None:
        try:
            profile = self.app.profile_service.load_or_new()
            self.app.profile_service.complete(profile)
        except ProfileFormatError as error:
            self.app.notify(str(error), severity="error")
            return
        self.app.profile_changed()
        self._refresh_profile()
        self.app.notify("Profile verified")

    def _refresh_profile(self) -> None:
        try:
            profile = self.app.profile_service.load_or_new()
            text = (
                self.app.profile_repository.read_text()
                if self.app.profile_repository.exists()
                else self.app.profile_repository.render(profile)
            )
        except ProfileFormatError as error:
            self.query_one("#profile-status", Static).update(f"[red]{error}[/]")
            return
        state = "[green]ready[/]" if profile.is_ready else "[yellow]draft[/]"
        self.query_one("#profile-status", Static).update(
            f"Status: {state} · {len(profile.portal_qa)} reusable answers"
        )
        self.query_one("#profile-path", Static).update(str(self.app.settings.profile_path))
        self.query_one("#profile-preview", TextArea).load_text(text)
        self._loading = True
        try:
            for pack_id, _label in PACKS:
                self.query_one(f"#pack-{pack_id}", Checkbox).value = (
                    pack_id in profile.enabled_packs
                )
        finally:
            self._loading = False
        resume = next(
            (document.path for document in profile.documents if document.kind == "resume"),
            "",
        )
        self.query_one("#profile-document", Input).value = resume
