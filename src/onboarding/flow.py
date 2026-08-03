"""Question policy, local validation, safe projection, and AI review."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..llm import LLMResponseError, OpenRouterClient
from ..profile import Profile, ProfileDocument

QuestionKind = Literal[
    "text",
    "name",
    "email",
    "phone",
    "country",
    "region",
    "city",
    "postal",
    "summary",
    "list",
    "yes_no",
    "file",
]
PrivacyClass = Literal["local_only", "professional"]


@dataclass(frozen=True, slots=True)
class OnboardingQuestion:
    path: str
    prompt: str
    stage: int
    kind: QuestionKind = "text"
    optional: bool = False
    privacy: PrivacyClass = "local_only"


@dataclass(frozen=True, slots=True)
class AnswerValidation:
    valid: bool
    value: str | list[str] | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class OnboardingIssue:
    path: str
    problem: str
    question: str
    source: Literal["local", "ai"] = "local"


QUESTIONS: tuple[OnboardingQuestion, ...] = (
    OnboardingQuestion(
        "identity.full_name",
        "What full legal name should applications use?",
        stage=0,
        kind="name",
    ),
    OnboardingQuestion(
        "contact.email",
        "What email address should applications use?",
        stage=1,
        kind="email",
    ),
    OnboardingQuestion(
        "contact.phone",
        "What phone number should applications use?",
        stage=1,
        kind="phone",
    ),
    OnboardingQuestion(
        "location_preferences.country",
        "What country do you currently live in?",
        stage=2,
        kind="country",
    ),
    OnboardingQuestion(
        "location_preferences.city",
        "What city do you currently live in?",
        stage=2,
        kind="city",
    ),
    OnboardingQuestion(
        "location_preferences.state",
        "What state, province, or region do you live in?",
        stage=2,
        kind="region",
    ),
    OnboardingQuestion(
        "location_preferences.postal_code",
        "What is your postal or ZIP code?",
        stage=2,
        kind="postal",
    ),
    OnboardingQuestion(
        "location_preferences.street_address",
        "Would you like to save a street address locally? You can skip this.",
        stage=2,
        optional=True,
    ),
    OnboardingQuestion(
        "professional_summary",
        "Describe your target role, experience, and strongest professional focus.",
        stage=3,
        kind="summary",
        privacy="professional",
    ),
    OnboardingQuestion(
        "work_history",
        "Tell me about your work history. Include role, employer, and dates when possible.",
        stage=3,
        kind="list",
        optional=True,
        privacy="professional",
    ),
    OnboardingQuestion(
        "education",
        "Tell me about your education, including qualification, school, and dates.",
        stage=3,
        kind="list",
        optional=True,
        privacy="professional",
    ),
    OnboardingQuestion(
        "skills",
        "What skills should recruiters see? You can use commas or vertical bars.",
        stage=3,
        kind="list",
        privacy="professional",
    ),
    OnboardingQuestion(
        "projects",
        "Describe any important projects you want applications to reference.",
        stage=3,
        kind="list",
        optional=True,
        privacy="professional",
    ),
    OnboardingQuestion(
        "work_authorization.authorized",
        "Are you currently authorized to work in the United States? Please answer yes or no.",
        stage=4,
        kind="yes_no",
    ),
    OnboardingQuestion(
        "work_authorization.sponsorship",
        "Will you now or later require employment sponsorship? Please answer yes or no.",
        stage=4,
        kind="yes_no",
    ),
    OnboardingQuestion(
        "documents.resume_source",
        "What is the local path to your primary resume? You can skip this for now.",
        stage=5,
        kind="file",
        optional=True,
    ),
)

QUESTION_BY_PATH = {question.path: question for question in QUESTIONS}
AI_REVIEWABLE_PATHS = {
    question.path for question in QUESTIONS if question.privacy == "professional"
}


class _NextTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    message: str


class _ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    problem: str
    question: str


class _ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[_ReviewIssue] = Field(default_factory=list)


class OnboardingFlow:
    """Own question completeness, validation, storage, and cloud-safe context."""

    questions = QUESTIONS
    question_by_path = QUESTION_BY_PATH

    def pending_questions(self, profile: Profile) -> list[OnboardingQuestion]:
        pending = [
            question
            for question in self.questions
            if not self._is_complete(profile, question)
        ]
        if not pending:
            return []
        stage = min(question.stage for question in pending)
        return [question for question in pending if question.stage == stage]

    def validate(
        self,
        question: OnboardingQuestion,
        raw_value: str,
        profile: Profile,
    ) -> AnswerValidation:
        value = raw_value.strip()
        if not value:
            return AnswerValidation(False, error="Please enter an answer.")

        if question.kind == "name":
            if len(value) < 2 or any(character.isdigit() for character in value):
                return AnswerValidation(
                    False,
                    error="Enter a name using letters rather than numbers.",
                )
        elif question.kind == "email":
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                return AnswerValidation(
                    False,
                    error="That does not look like a complete email address.",
                )
            value = value.casefold()
        elif question.kind == "phone":
            digits = re.sub(r"\D", "", value)
            if not 7 <= len(digits) <= 15:
                return AnswerValidation(
                    False,
                    error="Enter a phone number containing 7 to 15 digits.",
                )
        elif question.kind in {"country", "region", "city"}:
            if len(value) < 2 or not re.search(r"[A-Za-z]", value):
                return AnswerValidation(
                    False,
                    error="Enter a location name containing letters.",
                )
        elif question.kind == "postal":
            return self._validate_postal(value, profile)
        elif question.kind == "summary":
            if len(value.split()) < 6:
                return AnswerValidation(
                    False,
                    error=(
                        "Please add a little more detail about your role, experience, "
                        "and strongest focus."
                    ),
                )
        elif question.kind == "yes_no":
            normalized = value.casefold().replace(".", "")
            yes = {"yes", "y", "true", "currently yes"}
            no = {"no", "n", "false", "currently no"}
            if normalized in yes:
                value = "yes"
            elif normalized in no:
                value = "no"
            else:
                return AnswerValidation(
                    False,
                    error="Please answer yes or no so applications use the right value.",
                )
        elif question.kind == "list":
            parts = self._split_list(value)
            if not parts:
                return AnswerValidation(False, error="Add at least one item.")
            return AnswerValidation(True, value=parts)
        elif question.kind == "file":
            path = Path(value).expanduser()
            if not path.is_file():
                return AnswerValidation(
                    False,
                    error="That file does not exist. Check the path or type skip.",
                )
            value = str(path.resolve())
        return AnswerValidation(True, value=value)

    def assign(
        self,
        profile: Profile,
        question: OnboardingQuestion,
        value: str | list[str],
    ) -> None:
        path = question.path
        if path == "professional_summary":
            profile.professional_summary = str(value)
        elif path in {"education", "work_history", "projects", "skills"}:
            setattr(profile, path, list(value) if isinstance(value, list) else [value])
        elif path == "documents.resume_source":
            source = str(value)
            existing = next(
                (item for item in profile.documents if item.kind == "resume"),
                None,
            )
            if existing is None:
                profile.documents.append(
                    ProfileDocument(kind="resume", path=source, label="Primary resume")
                )
            else:
                existing.path = source
                existing.active = True
        else:
            section, key = path.split(".", maxsplit=1)
            getattr(profile, section)[key] = str(value)
        profile.verification[path] = "user_entered"
        profile.provenance[path] = "private_onboarding"

    def skip(self, profile: Profile, question: OnboardingQuestion) -> None:
        if not question.optional:
            raise ValueError("This answer is required")
        self._clear_value(profile, question.path)
        profile.provenance[question.path] = "user_skipped"
        profile.verification.pop(question.path, None)

    def local_review(self, profile: Profile) -> list[OnboardingIssue]:
        issues: list[OnboardingIssue] = []
        for question in self.questions:
            if question.optional and profile.provenance.get(question.path) == "user_skipped":
                continue
            raw_value = self._raw_value(profile, question.path)
            if not raw_value:
                if not question.optional:
                    issues.append(
                        OnboardingIssue(
                            question.path,
                            "Required information is missing.",
                            question.prompt,
                        )
                    )
                continue
            result = self.validate(question, raw_value, profile)
            if not result.valid:
                issues.append(
                    OnboardingIssue(
                        question.path,
                        result.error,
                        question.prompt,
                    )
                )

        if not profile.work_history and not profile.education:
            question = self.question_by_path["work_history"]
            issues.append(
                OnboardingIssue(
                    question.path,
                    "A job profile needs either work history or education.",
                    "Tell me about relevant work, volunteering, training, or education.",
                )
            )
        return self._deduplicate_issues(issues)

    def safe_status(self, profile: Profile) -> dict[str, Any]:
        """Return cloud-safe statuses and redacted professional content only."""
        statuses = {
            question.path: (
                "skipped"
                if profile.provenance.get(question.path) == "user_skipped"
                else "present"
                if bool(self._raw_value(profile, question.path))
                else "missing"
            )
            for question in self.questions
        }
        professional = {
            "professional_summary": self._redact(profile.professional_summary),
            "education": [self._redact(value) for value in profile.education],
            "work_history": [self._redact(value) for value in profile.work_history],
            "projects": [self._redact(value) for value in profile.projects],
            "skills": [self._redact(value) for value in profile.skills],
        }
        return {
            "field_status": statuses,
            "professional_profile": professional,
            "privacy": (
                "Identity, contact, location, authorization, documents, and "
                "sensitive identity values are excluded."
            ),
        }

    def _is_complete(self, profile: Profile, question: OnboardingQuestion) -> bool:
        if profile.provenance.get(question.path) == "user_skipped":
            return question.optional
        raw_value = self._raw_value(profile, question.path)
        if not raw_value:
            return False
        return self.validate(question, raw_value, profile).valid

    @staticmethod
    def _validate_postal(value: str, profile: Profile) -> AnswerValidation:
        country = profile.location_preferences.get("country", "").strip().casefold()
        if country in {"us", "usa", "united states", "united states of america"}:
            if not re.fullmatch(r"\d{5}(?:-\d{4})?", value):
                return AnswerValidation(
                    False,
                    error="A US ZIP code must be 5 digits, optionally followed by -1234.",
                )
        elif country in {"canada", "ca"}:
            if not re.fullmatch(r"[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d", value):
                return AnswerValidation(
                    False,
                    error="Enter a Canadian postal code such as A1A 1A1.",
                )
            value = value.upper()
        elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{1,10}[A-Za-z0-9]", value):
            return AnswerValidation(
                False,
                error="Enter a postal code containing 3 to 12 letters or digits.",
            )
        return AnswerValidation(True, value=value)

    @staticmethod
    def _split_list(value: str) -> list[str]:
        separator = "|" if "|" in value else ";" if ";" in value else ","
        parts = [part.strip(" -\t") for part in value.split(separator)]
        return [part for part in parts if part]

    @staticmethod
    def _raw_value(profile: Profile, path: str) -> str:
        if path == "professional_summary":
            return profile.professional_summary.strip()
        if path in {"education", "work_history", "projects", "skills"}:
            return " | ".join(getattr(profile, path))
        if path == "documents.resume_source":
            return next(
                (
                    item.path
                    for item in profile.documents
                    if item.kind == "resume" and item.active
                ),
                "",
            )
        section, key = path.split(".", maxsplit=1)
        return str(getattr(profile, section).get(key, "")).strip()

    @staticmethod
    def _clear_value(profile: Profile, path: str) -> None:
        if path == "professional_summary":
            profile.professional_summary = ""
        elif path in {"education", "work_history", "projects", "skills"}:
            setattr(profile, path, [])
        elif path == "documents.resume_source":
            for document in profile.documents:
                if document.kind == "resume":
                    document.active = False
        else:
            section, key = path.split(".", maxsplit=1)
            getattr(profile, section).pop(key, None)

    @staticmethod
    def _redact(value: str) -> str:
        value = re.sub(r"[^\s@]+@[^\s@]+", "<email>", value)
        value = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "<sensitive-id>", value)
        value = re.sub(r"(?<!\w)\+?\d[\d ()-]{6,}\d(?!\w)", "<phone>", value)
        return value

    @staticmethod
    def _deduplicate_issues(issues: list[OnboardingIssue]) -> list[OnboardingIssue]:
        result: list[OnboardingIssue] = []
        seen: set[str] = set()
        for issue in issues:
            if issue.path not in seen:
                result.append(issue)
                seen.add(issue.path)
        return result


class OnboardingAgent:
    """Use cloud AI only for question wording and redacted professional review."""

    def __init__(self, client: OpenRouterClient, *, model: str) -> None:
        self.client = client
        self.model = model.strip()
        if not self.model:
            raise ValueError("The onboarding AI model cannot be empty")

    def _chat(self, messages: list[dict[str, Any]]) -> str:
        return self.client.chat(
            messages,
            json_mode=True,
            model=self.model,
            use_configured_provider=False,
        )

    def choose_question(
        self,
        candidates: list[OnboardingQuestion],
        safe_status: dict[str, Any],
    ) -> tuple[OnboardingQuestion, str]:
        if not candidates:
            raise ValueError("At least one onboarding question is required")
        payload = {
            "candidates": [
                {
                    "path": item.path,
                    "base_question": item.prompt,
                    "optional": item.optional,
                }
                for item in candidates
            ],
            "profile_status": safe_status["field_status"],
        }
        response = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a concise, friendly job-profile interviewer. Choose exactly "
                        "one supplied candidate path and ask one natural question for it. "
                        "Never request SSNs, passport data, credentials, dates of birth, or "
                        "values for any field not supplied. Return JSON with path and message."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        try:
            turn = _NextTurn.model_validate(self._parse_json(response))
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            raise LLMResponseError("Invalid onboarding question response") from error
        selected = next((item for item in candidates if item.path == turn.path), None)
        if selected is None or not turn.message.strip():
            raise LLMResponseError("AI selected a field outside the allowed question set")
        return selected, turn.message.strip()

    def rephrase_question(
        self,
        question: OnboardingQuestion,
        problem: str,
    ) -> str:
        response = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Rewrite the supplied correction as one kind, concise follow-up "
                        "question. Do not request any extra personal information and do not "
                        "claim the value is correct. Return JSON with path and message."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "path": question.path,
                            "base_question": question.prompt,
                            "validation_problem": problem,
                        }
                    ),
                },
            ],
        )
        try:
            turn = _NextTurn.model_validate(self._parse_json(response))
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            raise LLMResponseError("Invalid onboarding correction response") from error
        if turn.path != question.path or not turn.message.strip():
            raise LLMResponseError("AI changed the field during correction")
        return turn.message.strip()

    def review(self, safe_projection: dict[str, Any]) -> list[OnboardingIssue]:
        response = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Review only the supplied professional job-profile content. Find "
                        "material omissions, ambiguity, or internal contradictions. Do not "
                        "request identity, contact, location, authorization, financial, "
                        "medical, credential, SSN, passport, or other sensitive values. "
                        "Return JSON: {\"issues\":[{\"path\":...,\"problem\":...,"
                        "\"question\":...}]}. Use only these paths: "
                        + ", ".join(sorted(AI_REVIEWABLE_PATHS))
                    ),
                },
                {"role": "user", "content": json.dumps(safe_projection)},
            ],
        )
        try:
            result = _ReviewResult.model_validate(self._parse_json(response))
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            raise LLMResponseError("Invalid onboarding review response") from error
        issues = [
            OnboardingIssue(
                item.path,
                item.problem.strip(),
                item.question.strip(),
                source="ai",
            )
            for item in result.issues[:5]
            if item.path in AI_REVIEWABLE_PATHS
            and item.problem.strip()
            and item.question.strip()
        ]
        return OnboardingFlow._deduplicate_issues(issues)

    @staticmethod
    def _parse_json(response: str) -> Any:
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        return json.loads(text)
