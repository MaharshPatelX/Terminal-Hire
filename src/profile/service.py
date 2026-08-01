"""Application-facing operations for the Markdown profile."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from .models import PortalAnswer, Profile, ProfileDocument, ProfileSnapshot
from .repository import MarkdownProfileRepository, ProfileFormatError


class ProfileService:
    """The only writer used by onboarding, profile editing, and learned Q&A."""

    MAPPING_SECTIONS: ClassVar[frozenset[str]] = frozenset({
        "identity",
        "contact",
        "sensitive_identity",
        "location_preferences",
        "work_authorization",
        "common_answers",
        "answer_policies",
        "verification",
        "provenance",
    })
    LIST_SECTIONS: ClassVar[frozenset[str]] = frozenset({
        "education",
        "work_history",
        "projects",
        "skills",
        "insights",
        "enabled_packs",
    })

    def __init__(self, repository: MarkdownProfileRepository) -> None:
        self.repository = repository

    def new_profile(self) -> Profile:
        return Profile(
            answer_policies={
                "demographic_questions": "ask",
                "disability": "ask",
                "veteran_status": "ask",
                "salary": "use_verified_or_ask",
                "consent_and_terms": "manual_only",
            }
        )

    def load_or_new(self) -> Profile:
        if not self.repository.exists():
            return self.new_profile()
        return self.repository.load()

    def is_ready(self) -> bool:
        try:
            return self.repository.load().is_ready
        except ProfileFormatError:
            return False

    def snapshot(self) -> ProfileSnapshot:
        snapshot = self.repository.snapshot()
        if not snapshot.profile.is_ready:
            missing = ", ".join(snapshot.profile.missing_required_fields()) or "verification"
            raise ProfileFormatError(f"Profile is not ready; missing: {missing}")
        return snapshot

    def save_draft(self, profile: Profile) -> ProfileSnapshot:
        profile.status = "draft"
        return self.repository.save(profile)

    def complete(self, profile: Profile) -> ProfileSnapshot:
        missing = profile.missing_required_fields()
        if missing:
            raise ProfileFormatError(
                f"Cannot complete profile; missing: {', '.join(missing)}"
            )
        now = datetime.now(UTC)
        profile.status = "complete"
        profile.verified_at = now
        profile.verification["profile"] = f"user_verified:{now.isoformat()}"
        return self.repository.save(profile)

    def set_value(self, path: str, value: str, *, verified: bool = True) -> ProfileSnapshot:
        profile = self.load_or_new()
        cleaned_path = path.strip()
        cleaned_value = value.strip()
        if "." in cleaned_path:
            section, key = cleaned_path.split(".", maxsplit=1)
            if section not in self.MAPPING_SECTIONS:
                raise ValueError(f"Unsupported profile mapping section: {section}")
            mapping = getattr(profile, section)
            if cleaned_value:
                mapping[key] = cleaned_value
            else:
                mapping.pop(key, None)
        elif cleaned_path == "professional_summary":
            profile.professional_summary = cleaned_value
        elif cleaned_path == "documents.resume":
            existing = next(
                (document for document in profile.documents if document.kind == "resume"),
                None,
            )
            if existing:
                existing.path = cleaned_value
                existing.active = bool(cleaned_value)
            elif cleaned_value:
                profile.documents.append(
                    ProfileDocument(
                        kind="resume",
                        path=cleaned_value,
                        label="Primary resume",
                    )
                )
        elif cleaned_path in self.LIST_SECTIONS:
            values = [item.strip() for item in cleaned_value.split("|") if item.strip()]
            setattr(profile, cleaned_path, values)
        else:
            raise ValueError(f"Unsupported profile path: {cleaned_path}")

        if verified:
            profile.verification[cleaned_path] = (
                f"user_verified:{datetime.now(UTC).isoformat()}"
            )
        if profile.status == "complete" and profile.missing_required_fields():
            profile.status = "draft"
            profile.verified_at = None
        return self.repository.save(profile)

    def add_portal_answer(
        self,
        *,
        question: str,
        answer: str,
        intent: str,
        scope: str = "global",
        company: str | None = None,
        verified: bool = True,
    ) -> ProfileSnapshot:
        profile = self.load_or_new()
        normalized_intent = intent.strip().casefold()
        existing = next(
            (
                item
                for item in profile.portal_qa
                if item.intent.strip().casefold() == normalized_intent
                and item.scope == scope
                and (item.company or "").casefold() == (company or "").casefold()
            ),
            None,
        )
        now = datetime.now(UTC)
        if existing:
            if question.strip() not in existing.questions:
                existing.questions.append(question.strip())
            existing.answer = answer.strip()
            existing.verified = verified
            existing.updated_at = now
        else:
            profile.portal_qa.append(
                PortalAnswer(
                    intent=intent.strip(),
                    questions=[question],
                    answer=answer.strip(),
                    scope=scope,  # type: ignore[arg-type]
                    company=company,
                    verified=verified,
                    updated_at=now,
                )
            )
        return self.repository.save(profile)

    def mark_answer_used(self, answer_id: str) -> ProfileSnapshot:
        profile = self.load_or_new()
        answer = next((item for item in profile.portal_qa if item.id == answer_id), None)
        if answer is None:
            raise KeyError(f"Unknown profile answer: {answer_id}")
        answer.last_used_at = datetime.now(UTC)
        return self.repository.save(profile)
