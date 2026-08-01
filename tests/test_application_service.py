from __future__ import annotations

from datetime import UTC, datetime

from src.apply import ApplicationService
from src.db import LocalStore
from src.profile import (
    MarkdownProfileRepository,
    Profile,
    ProfileRetriever,
    ProfileService,
)


def make_service(tmp_path) -> tuple[ApplicationService, MarkdownProfileRepository, LocalStore]:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    repository.save(
        Profile(
            status="complete",
            verified_at=datetime.now(UTC),
            identity={"full_name": "Ada Lovelace"},
            contact={"email": "ada@example.com", "phone": "555-0100"},
            professional_summary="Engineer",
        )
    )
    profiles = ProfileService(repository)
    store = LocalStore(tmp_path / "app.sqlite")
    return (
        ApplicationService(
            profiles=profiles,
            retriever=ProfileRetriever(),
            store=store,
        ),
        repository,
        store,
    )


def test_unknown_sensitive_answer_is_redacted_and_saved_structurally(tmp_path) -> None:
    service, repository, store = make_service(tmp_path)
    application = service.start(url="https://jobs.example.com/1")

    planned = service.answer_unknown(
        application.id,
        field_name="ssn",
        question="Social Security Number",
        answer="111-22-3333",
        save_to_profile=True,
    )

    assert planned.result.sensitive is True
    assert repository.load().sensitive_identity["ssn"] == "111-22-3333"
    assert store.field_actions(application.id)[0]["value"] == "<redacted>"
    event = next(
        event
        for event in store.application_events(application.id)
        if event["event_type"] == "user_answer_recorded"
    )
    assert event["value"] == "<redacted>"
