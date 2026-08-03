from __future__ import annotations

import json

import pytest

from src.onboarding import OnboardingAgent, OnboardingFlow
from src.profile import Profile


class FakeChatClient:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls: list[
            tuple[list[dict[str, object]], bool, str | None, bool]
        ] = []

    def chat(
        self,
        messages: list[dict[str, object]],
        *,
        json_mode: bool = False,
        model: str | None = None,
        use_configured_provider: bool = True,
    ) -> str:
        self.calls.append((messages, json_mode, model, use_configured_provider))
        return self.responses.pop(0)


def profile_through_country() -> Profile:
    return Profile(
        identity={"full_name": "Ada Lovelace"},
        contact={"email": "ada@example.com", "phone": "+1 214 555 0100"},
        location_preferences={"country": "United States"},
    )


def test_us_zip_is_rejected_until_five_digits() -> None:
    flow = OnboardingFlow()
    profile = profile_through_country()
    question = flow.question_by_path["location_preferences.postal_code"]

    invalid = flow.validate(question, "1234", profile)
    valid = flow.validate(question, "75201", profile)

    assert invalid.valid is False
    assert "5 digits" in invalid.error
    assert valid.valid is True
    assert valid.value == "75201"


@pytest.mark.parametrize(
    ("path", "answer", "expected"),
    [
        ("contact.email", "not-an-email", False),
        ("contact.email", "ADA@EXAMPLE.COM", True),
        ("contact.phone", "1234", False),
        ("contact.phone", "+1 (214) 555-0100", True),
        ("work_authorization.authorized", "maybe", False),
        ("work_authorization.authorized", "Yes", True),
    ],
)
def test_structured_answers_are_validated(path: str, answer: str, expected: bool) -> None:
    flow = OnboardingFlow()
    result = flow.validate(flow.question_by_path[path], answer, Profile())

    assert result.valid is expected


def test_invalid_existing_value_is_still_pending() -> None:
    flow = OnboardingFlow()
    profile = profile_through_country()
    profile.location_preferences.update(
        {"city": "Dallas", "state": "Texas", "postal_code": "1234"}
    )

    pending = flow.pending_questions(profile)

    assert [question.path for question in pending] == [
        "location_preferences.postal_code",
        "location_preferences.street_address",
    ]


def test_safe_projection_excludes_private_values_and_redacts_professional_text() -> None:
    flow = OnboardingFlow()
    profile = profile_through_country()
    profile.location_preferences.update(
        {"city": "Dallas", "state": "Texas", "postal_code": "75201"}
    )
    profile.work_authorization = {"authorized": "yes", "sponsorship": "no"}
    profile.sensitive_identity = {"ssn": "111-22-3333", "passport_number": "P123456"}
    profile.professional_summary = (
        "Engineer available at ada@example.com or +1 214 555 0100 for platform work"
    )

    encoded = json.dumps(flow.safe_status(profile))

    for private_value in (
        "Ada Lovelace",
        "ada@example.com",
        "+1 214 555 0100",
        "Dallas",
        "Texas",
        "75201",
        "111-22-3333",
        "P123456",
    ):
        assert private_value not in encoded
    assert "<email>" in encoded
    assert "<phone>" in encoded


def test_local_review_requires_education_or_experience() -> None:
    flow = OnboardingFlow()
    profile = profile_through_country()
    profile.location_preferences.update(
        {"city": "Dallas", "state": "Texas", "postal_code": "75201"}
    )
    profile.professional_summary = "Software engineer focused on reliable platform systems"
    profile.skills = ["Python"]
    profile.work_authorization = {"authorized": "yes", "sponsorship": "no"}
    for path in (
        "location_preferences.street_address",
        "education",
        "work_history",
        "projects",
        "documents.resume_source",
    ):
        profile.provenance[path] = "user_skipped"

    issues = flow.local_review(profile)

    assert any(issue.path == "work_history" for issue in issues)


def test_ai_chooses_only_an_allowed_question() -> None:
    flow = OnboardingFlow()
    candidates = [
        flow.question_by_path["contact.email"],
        flow.question_by_path["contact.phone"],
    ]
    fake = FakeChatClient(
        '{"path":"contact.phone","message":"What is the best phone number to use?"}'
    )

    question, message = OnboardingAgent(  # type: ignore[arg-type]
        fake,
        model="deepseek/deepseek-v4-flash",
    ).choose_question(
        candidates,
        flow.safe_status(Profile()),
    )

    assert question.path == "contact.phone"
    assert message == "What is the best phone number to use?"
    assert fake.calls[0][1] is True
    assert fake.calls[0][2] == "deepseek/deepseek-v4-flash"
    assert fake.calls[0][3] is False


def test_ai_review_discards_private_or_unknown_paths() -> None:
    fake = FakeChatClient(
        json.dumps(
            {
                "issues": [
                    {
                        "path": "professional_summary",
                        "problem": "Target role is unclear",
                        "question": "Which role are you targeting?",
                    },
                    {
                        "path": "sensitive_identity.ssn",
                        "problem": "Missing",
                        "question": "What is your SSN?",
                    },
                ]
            }
        )
    )

    issues = OnboardingAgent(  # type: ignore[arg-type]
        fake,
        model="deepseek/deepseek-v4-flash",
    ).review(
        OnboardingFlow().safe_status(Profile())
    )

    assert [issue.path for issue in issues] == ["professional_summary"]
