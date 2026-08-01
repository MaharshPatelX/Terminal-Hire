from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.profile import (
    MarkdownProfileRepository,
    Profile,
    ProfileFormatError,
    ProfileRetriever,
    ProfileService,
)


def ready_profile() -> Profile:
    return Profile(
        status="complete",
        verified_at=datetime.now(UTC),
        identity={"full_name": "Ada Lovelace"},
        contact={"email": "ada@example.com", "phone": "555-0100"},
        sensitive_identity={"ssn": "111-22-3333"},
        professional_summary="Engineer focused on reliable analytical systems.",
        skills=["Python", "Mathematics"],
    )


def test_profile_round_trip_and_readable_markdown(tmp_path) -> None:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    snapshot = repository.save(ready_profile())

    loaded = repository.load()
    text = repository.read_text()

    assert loaded.is_ready
    assert loaded.identity["full_name"] == "Ada Lovelace"
    assert loaded.sensitive_identity["ssn"] == "111-22-3333"
    assert "# Candidate Profile" in text
    assert "## Sensitive Identity" in text
    assert snapshot.content_hash


def test_atomic_save_keeps_recoverable_backup(tmp_path) -> None:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    original = ready_profile()
    repository.save(original)
    changed = original.model_copy(deep=True)
    changed.identity["full_name"] = "Grace Hopper"
    repository.save(changed)
    repository.path.write_text("broken", encoding="utf-8")

    with pytest.raises(ProfileFormatError):
        repository.load()

    recovered = repository.recover_backup()
    assert recovered.identity["full_name"] == "Ada Lovelace"
    assert repository.load().identity["full_name"] == "Ada Lovelace"


def test_sensitive_values_use_deterministic_lookup_not_rag(tmp_path) -> None:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    repository.save(ready_profile())
    snapshot = repository.snapshot()
    retriever = ProfileRetriever()

    result = retriever.resolve(snapshot, question="Social Security Number")
    context = retriever.safe_context(snapshot, "social security")

    assert result.value == "111-22-3333"
    assert result.sensitive is True
    assert result.source == "PROFILE.md:sensitive_identity.ssn"
    assert all("111-22-3333" not in value for _source, value, _score in context)


def test_verified_portal_answer_matches_different_wording(tmp_path) -> None:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    service = ProfileService(repository)
    repository.save(ready_profile())
    service.add_portal_answer(
        intent="willing_to_relocate",
        question="Are you willing to relocate?",
        answer="Yes, for the right role.",
        verified=True,
    )

    result = ProfileRetriever().resolve(
        repository.snapshot(),
        question="Would you relocate for this position?",
        minimum_confidence=0.45,
    )

    assert result.value == "Yes, for the right role."
    assert result.answer_id is not None


def test_completion_requires_core_verified_details(tmp_path) -> None:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    service = ProfileService(repository)
    profile = service.new_profile()

    with pytest.raises(ProfileFormatError, match="missing"):
        service.complete(profile)


def test_camel_case_name_aliases_do_not_match_username(tmp_path) -> None:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    repository.save(ready_profile())
    snapshot = repository.snapshot()
    retriever = ProfileRetriever()

    first_name = retriever.resolve(snapshot, field_name="firstName")
    username = retriever.resolve(snapshot, field_name="username")

    assert first_name.value == "Ada"
    assert first_name.source == "PROFILE.md:identity.first_name"
    assert username.requires_user is True


def test_snapshot_rejects_unsupported_schema_version(tmp_path) -> None:
    repository = MarkdownProfileRepository(tmp_path / "PROFILE.md")
    repository.save(ready_profile())
    text = repository.read_text().replace("schema_version: 1", "schema_version: 99", 1)
    repository.path.write_text(text, encoding="utf-8")

    with pytest.raises(ProfileFormatError, match="Unsupported"):
        repository.snapshot()
