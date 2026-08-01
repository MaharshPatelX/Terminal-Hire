"""Typed contract for the Markdown-only candidate profile."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProfileDocument(BaseModel):
    """A resume or supporting document referenced by the profile."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    path: str
    label: str = ""
    sha256: str = ""
    active: bool = True


class PortalAnswer(BaseModel):
    """A verified reusable answer learned from one or more portal questions."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    intent: str
    questions: list[str]
    answer: str
    scope: Literal["global", "company", "application"] = "global"
    company: str | None = None
    verified: bool = False
    source: str = "user"
    first_seen_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime | None = None

    @field_validator("questions")
    @classmethod
    def require_question(cls, value: list[str]) -> list[str]:
        cleaned = [question.strip() for question in value if question.strip()]
        if not cleaned:
            raise ValueError("At least one portal question is required")
        return cleaned


class Profile(BaseModel):
    """All user details stored in one strict PROFILE.md document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    status: Literal["draft", "complete"] = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    verified_at: datetime | None = None

    identity: dict[str, str] = Field(default_factory=dict)
    contact: dict[str, str] = Field(default_factory=dict)
    sensitive_identity: dict[str, str] = Field(default_factory=dict)
    location_preferences: dict[str, str] = Field(default_factory=dict)
    professional_summary: str = ""
    education: list[str] = Field(default_factory=list)
    work_history: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    work_authorization: dict[str, str] = Field(default_factory=dict)
    enabled_packs: list[str] = Field(default_factory=list)
    documents: list[ProfileDocument] = Field(default_factory=list)
    common_answers: dict[str, str] = Field(default_factory=dict)
    portal_qa: list[PortalAnswer] = Field(default_factory=list)
    answer_policies: dict[str, str] = Field(default_factory=dict)
    insights: list[str] = Field(default_factory=list)
    verification: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)

    def missing_required_fields(self) -> list[str]:
        required = {
            "identity.full_name": self.identity.get("full_name", ""),
            "contact.email": self.contact.get("email", ""),
            "contact.phone": self.contact.get("phone", ""),
            "professional_summary": self.professional_summary,
        }
        return [key for key, value in required.items() if not value.strip()]

    @property
    def is_ready(self) -> bool:
        return (
            self.status == "complete"
            and self.verified_at is not None
            and not self.missing_required_fields()
        )


class ProfileSnapshot(BaseModel):
    """Immutable profile state used for one application attempt."""

    profile: Profile
    content_hash: str
    loaded_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def from_text(cls, profile: Profile, text: str) -> ProfileSnapshot:
        return cls(
            profile=profile.model_copy(deep=True),
            content_hash=sha256(text.encode("utf-8")).hexdigest(),
        )
