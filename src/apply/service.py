"""Profile-backed field planning and supervised-application state."""

from __future__ import annotations

from dataclasses import dataclass

from ..db import ApplicationRecord, LocalStore
from ..profile import ProfileRetriever, ProfileService, RetrievalResult


@dataclass(frozen=True, slots=True)
class PlannedField:
    application_id: str
    field_name: str
    question: str
    result: RetrievalResult


class ApplicationService:
    """Coordinate profile truth and SQLite audit state."""

    def __init__(
        self,
        *,
        profiles: ProfileService,
        retriever: ProfileRetriever,
        store: LocalStore,
    ) -> None:
        self.profiles = profiles
        self.retriever = retriever
        self.store = store

    def start(self, *, url: str, company: str = "") -> ApplicationRecord:
        snapshot = self.profiles.snapshot()
        return self.store.create_application(
            job_url=url,
            company=company,
            profile_hash=snapshot.content_hash,
        )

    def plan_field(
        self,
        application_id: str,
        *,
        field_name: str,
        question: str,
        company: str | None = None,
    ) -> PlannedField:
        application = self._require_application(application_id)
        snapshot = self.profiles.snapshot()
        if snapshot.content_hash != application.profile_hash:
            self.store.update_application_profile(application_id, snapshot.content_hash)
            self.store.log_event(
                application_id,
                event_type="profile_snapshot_updated",
                target=snapshot.content_hash,
            )
        result = self.retriever.resolve(
            snapshot,
            field_name=field_name,
            question=question,
            company=company,
        )
        if result.requires_user:
            self.store.set_status(application_id, "waiting_for_user_answer")
            self.store.log_event(
                application_id,
                event_type="user_answer_required",
                target=field_name or question,
                details={"reason": result.reason},
            )
            return PlannedField(application_id, field_name, question, result)

        assert result.value is not None
        self.store.record_field_action(
            application_id,
            field_name=field_name,
            question=question,
            value=result.value,
            source=result.source,
            confidence=result.confidence,
            sensitive=result.sensitive,
        )
        self.store.log_event(
            application_id,
            event_type="field_planned",
            target=field_name,
            value=result.value,
            sensitive=result.sensitive,
            details={"source": result.source, "confidence": result.confidence},
        )
        if result.answer_id:
            self.profiles.mark_answer_used(result.answer_id)
            refreshed = self.profiles.snapshot()
            self.store.update_application_profile(application_id, refreshed.content_hash)
        return PlannedField(application_id, field_name, question, result)

    def answer_unknown(
        self,
        application_id: str,
        *,
        field_name: str,
        question: str,
        answer: str,
        save_to_profile: bool,
        intent: str = "",
        company: str | None = None,
        browser_pending: bool = False,
    ) -> PlannedField:
        source = "user:one_off"
        observed_question = question or field_name
        structured_path = self.retriever.structured_path(
            field_name=field_name,
            question=question,
        )
        sensitive = bool(
            structured_path
            and structured_path.startswith(self.retriever.SENSITIVE_PREFIX)
        )
        if save_to_profile:
            if structured_path:
                self.profiles.set_value(structured_path, answer, verified=True)
                source = f"PROFILE.md:{structured_path}"
            else:
                self.profiles.add_portal_answer(
                    question=observed_question,
                    answer=answer,
                    intent=intent or field_name or question,
                    scope="company" if company else "global",
                    company=company,
                    verified=True,
                )
                source = "PROFILE.md:new_portal_answer"
            snapshot = self.profiles.snapshot()
            self.store.update_application_profile(application_id, snapshot.content_hash)
        self.store.record_field_action(
            application_id,
            field_name=field_name,
            question=observed_question,
            value=answer,
            source=source,
            confidence=1.0,
            sensitive=sensitive,
        )
        self.store.log_event(
            application_id,
            event_type="user_answer_recorded",
            target=field_name or observed_question,
            value=answer,
            sensitive=sensitive,
            details={"saved_to_profile": save_to_profile, "source": source},
        )
        if browser_pending:
            self.store.set_status(application_id, "waiting_for_browser_fill")
        return PlannedField(
            application_id,
            field_name,
            observed_question,
            RetrievalResult(
                value=answer,
                source=source,
                confidence=1.0,
                sensitive=sensitive,
                reason="User supplied this application answer",
            ),
        )

    def build_preview(self, application_id: str) -> str:
        return self.store.build_preview(application_id)

    def approve(self, application_id: str, preview_hash: str) -> None:
        self.store.approve_preview(application_id, preview_hash)

    def _require_application(self, application_id: str) -> ApplicationRecord:
        application = self.store.get_application(application_id)
        if application is None:
            raise KeyError(f"Unknown application: {application_id}")
        return application
