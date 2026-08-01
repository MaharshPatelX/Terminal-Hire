"""Deterministic-first retrieval over PROFILE.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import ClassVar

from .models import PortalAnswer, ProfileSnapshot


def normalize(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return " ".join(words)


def token_score(left: str, right: str) -> float:
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "be",
        "do",
        "for",
        "is",
        "of",
        "the",
        "this",
        "to",
        "would",
        "you",
        "your",
    }
    left_normalized = normalize(left)
    right_normalized = normalize(right)
    if not left_normalized or not right_normalized:
        return 0.0
    left_tokens = set(left_normalized.split()) - stop_words
    right_tokens = set(right_normalized.split()) - stop_words
    overlap = len(left_tokens & right_tokens) / max(
        min(len(left_tokens), len(right_tokens)),
        1,
    )
    sequence = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return (overlap * 0.65) + (sequence * 0.35)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """A value with provenance that can be shown during final review."""

    value: str | None
    source: str
    confidence: float
    sensitive: bool = False
    answer_id: str | None = None
    requires_user: bool = False
    reason: str = ""


class ProfileRetriever:
    """Resolve form fields without feeding the full profile to an LLM."""

    FIELD_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "identity.full_name": ("full name", "legal name", "name"),
        "identity.first_name": ("first name", "given name"),
        "identity.middle_name": ("middle name",),
        "identity.last_name": ("last name", "surname", "family name"),
        "contact.email": ("email", "email address", "e mail"),
        "contact.phone": ("phone", "phone number", "mobile", "telephone"),
        "contact.linkedin": ("linkedin", "linkedin url", "linkedin profile"),
        "contact.github": ("github", "github url", "portfolio github"),
        "contact.website": ("website", "portfolio", "personal website"),
        "documents.resume": (
            "resume",
            "upload resume",
            "resume upload",
            "curriculum vitae",
            "cv upload",
        ),
        "location_preferences.current_location": (
            "current location",
            "home address",
            "location",
        ),
        "location_preferences.street_address": (
            "street address",
            "address line 1",
            "home street",
        ),
        "location_preferences.city": ("city", "town"),
        "location_preferences.state": ("state", "province", "region"),
        "location_preferences.postal_code": (
            "postal code",
            "zip",
            "zip code",
        ),
        "location_preferences.country": ("country", "country of residence"),
        "location_preferences.desired_salary": (
            "desired salary",
            "salary expectation",
            "expected compensation",
        ),
        "work_authorization.authorized": (
            "authorized to work",
            "legally authorized",
            "work authorization",
        ),
        "work_authorization.sponsorship": (
            "require sponsorship",
            "need sponsorship",
            "visa sponsorship",
        ),
        "sensitive_identity.ssn": (
            "ssn",
            "social security number",
            "social security",
        ),
        "sensitive_identity.passport_number": ("passport", "passport number"),
        "sensitive_identity.driver_license": (
            "driver license",
            "drivers license",
            "driving licence",
        ),
        "sensitive_identity.alien_registration_number": (
            "alien registration number",
            "a number",
            "uscis number",
        ),
    }
    SENSITIVE_PREFIX = "sensitive_identity."

    def resolve(
        self,
        snapshot: ProfileSnapshot,
        *,
        field_name: str = "",
        question: str = "",
        company: str | None = None,
        minimum_confidence: float = 0.72,
    ) -> RetrievalResult:
        prompt = " ".join(part for part in (field_name, question) if part).strip()
        exact = self._resolve_structured(snapshot, prompt)
        if exact is not None:
            return exact

        common = self._resolve_common_answer(snapshot, prompt)
        if common is not None:
            return common

        candidate = self._resolve_portal_answer(snapshot, prompt, company)
        if candidate is not None and candidate.confidence >= minimum_confidence:
            return candidate

        return RetrievalResult(
            value=None,
            source="user",
            confidence=candidate.confidence if candidate else 0.0,
            requires_user=True,
            reason="No verified profile answer met the confidence threshold",
        )

    def safe_context(
        self,
        snapshot: ProfileSnapshot,
        query: str,
        *,
        limit: int = 5,
    ) -> list[tuple[str, str, float]]:
        """Return non-sensitive chunks suitable for local RAG or minimal LLM context."""
        profile = snapshot.profile
        chunks: list[tuple[str, str]] = [
            ("professional_summary", profile.professional_summary),
            ("education", "\n".join(profile.education)),
            ("work_history", "\n".join(profile.work_history)),
            ("projects", "\n".join(profile.projects)),
            ("skills", ", ".join(profile.skills)),
        ]
        chunks.extend((f"insight.{index}", value) for index, value in enumerate(profile.insights))
        chunks.extend(
            (f"portal_qa.{answer.id}", f"{' | '.join(answer.questions)}\n{answer.answer}")
            for answer in profile.portal_qa
            if answer.verified
        )
        scored = [
            (source, value, token_score(query, value))
            for source, value in chunks
            if value.strip()
        ]
        return sorted(scored, key=lambda item: item[2], reverse=True)[:limit]

    def structured_path(self, *, field_name: str = "", question: str = "") -> str | None:
        """Return the best exact-profile path even when that value is missing."""
        prompt = " ".join(part for part in (field_name, question) if part).strip()
        score, path = self._match_structured_path(prompt)
        return path if score >= 0.84 else None

    def is_sensitive_prompt(self, *, field_name: str = "", question: str = "") -> bool:
        path = self.structured_path(field_name=field_name, question=question)
        return bool(path and path.startswith(self.SENSITIVE_PREFIX))

    def _resolve_structured(
        self, snapshot: ProfileSnapshot, prompt: str
    ) -> RetrievalResult | None:
        score, path = self._match_structured_path(prompt)
        if score < 0.84:
            return None
        value = self._value_at_path(snapshot, path)
        if not value:
            return None
        return RetrievalResult(
            value=value,
            source=f"PROFILE.md:{path}",
            confidence=score,
            sensitive=path.startswith(self.SENSITIVE_PREFIX),
            reason="Exact local structured lookup",
        )

    def _match_structured_path(self, prompt: str) -> tuple[float, str]:
        normalized_prompt = normalize(prompt)
        prompt_tokens = set(normalized_prompt.split())
        matches: list[tuple[float, str]] = []
        for path, aliases in self.FIELD_ALIASES.items():
            for alias in aliases:
                alias_normalized = normalize(alias)
                alias_tokens = set(alias_normalized.split())
                if normalized_prompt == alias_normalized:
                    score = 1.0
                elif alias_tokens and alias_tokens.issubset(prompt_tokens):
                    score = 0.96
                else:
                    score = token_score(normalized_prompt, alias_normalized)
                matches.append((score, path))
        return max(matches, default=(0.0, ""))

    @staticmethod
    def _resolve_common_answer(
        snapshot: ProfileSnapshot, prompt: str
    ) -> RetrievalResult | None:
        best_score = 0.0
        best_key = ""
        best_value = ""
        for key, value in snapshot.profile.common_answers.items():
            score = token_score(prompt, key)
            if score > best_score:
                best_score, best_key, best_value = score, key, value
        if best_score < 0.88 or not best_value:
            return None
        return RetrievalResult(
            value=best_value,
            source=f"PROFILE.md:common_answers.{best_key}",
            confidence=best_score,
            reason="Matched a common verified answer",
        )

    @staticmethod
    def _resolve_portal_answer(
        snapshot: ProfileSnapshot,
        prompt: str,
        company: str | None,
    ) -> RetrievalResult | None:
        best: tuple[float, PortalAnswer] | None = None
        for answer in snapshot.profile.portal_qa:
            if not answer.verified:
                continue
            if answer.scope == "application":
                continue
            if answer.scope == "company" and normalize(answer.company or "") != normalize(company or ""):
                continue
            candidates = [answer.intent, *answer.questions]
            score = max(token_score(prompt, candidate) for candidate in candidates)
            if best is None or score > best[0]:
                best = (score, answer)
        if best is None:
            return None
        score, answer = best
        return RetrievalResult(
            value=answer.answer,
            source=f"PROFILE.md:portal_qa.{answer.id}",
            confidence=score,
            answer_id=answer.id,
            reason="Matched a verified portal answer",
        )

    @staticmethod
    def _value_at_path(snapshot: ProfileSnapshot, path: str) -> str:
        section, key = path.split(".", maxsplit=1)
        if section == "documents" and key == "resume":
            return next(
                (
                    document.path
                    for document in snapshot.profile.documents
                    if document.kind == "resume" and document.active
                ),
                "",
            )
        values = getattr(snapshot.profile, section, {})
        value = str(values.get(key, "")).strip()
        if value or section != "identity":
            return value
        full_name = snapshot.profile.identity.get("full_name", "").strip()
        parts = full_name.split()
        if key == "first_name" and parts:
            return parts[0]
        if key == "last_name" and len(parts) > 1:
            return parts[-1]
        if key == "middle_name" and len(parts) > 2:
            return " ".join(parts[1:-1])
        return ""
