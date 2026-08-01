from __future__ import annotations

import sqlite3

import pytest

from src.db import LocalStore, SubmitGateError


def test_credentials_are_stored_but_never_returned_in_repr(tmp_path) -> None:
    path = tmp_path / "app.sqlite"
    store = LocalStore(path)
    store.save_credential(
        domain="https://jobs.example.com/login",
        email="user@example.com",
        username="candidate",
        password="plain-secret",
    )

    credential = store.get_credential("jobs.example.com")

    assert credential is not None
    assert credential.password == "plain-secret"
    assert "plain-secret" not in repr(credential)
    with sqlite3.connect(path) as connection:
        stored = connection.execute("SELECT password FROM credentials").fetchone()[0]
    assert stored == "plain-secret"


def test_sensitive_event_and_field_values_are_redacted(tmp_path) -> None:
    store = LocalStore(tmp_path / "app.sqlite")
    application = store.create_application(
        job_url="https://jobs.example.com/1",
        profile_hash="profile-hash",
    )
    store.log_event(
        application.id,
        event_type="field_filled",
        target="ssn",
        value="111-22-3333",
        sensitive=True,
    )
    store.record_field_action(
        application.id,
        field_name="ssn",
        question="SSN",
        value="111-22-3333",
        source="PROFILE.md:sensitive_identity.ssn",
        confidence=1.0,
        sensitive=True,
    )

    with store.connection() as connection:
        event_value = connection.execute(
            "SELECT value FROM application_events WHERE event_type = 'field_filled'"
        ).fetchone()[0]
    action = store.field_actions(application.id)[0]

    assert event_value == "<redacted>"
    assert action["value"] == "<redacted>"
    assert action["value_hash"] != "111-22-3333"


def test_preview_approval_is_hash_bound_and_one_use(tmp_path) -> None:
    store = LocalStore(tmp_path / "app.sqlite")
    application = store.create_application(
        job_url="https://jobs.example.com/1",
        profile_hash="profile-hash",
    )
    store.record_field_action(
        application.id,
        field_name="email",
        question="Email",
        value="user@example.com",
        source="PROFILE.md:contact.email",
        confidence=1.0,
        sensitive=False,
    )
    preview_hash = store.build_preview(application.id)

    with pytest.raises(SubmitGateError):
        store.approve_preview(application.id, "wrong-hash")

    store.approve_preview(application.id, preview_hash)
    store.claim_submit_once(application.id, preview_hash)

    with pytest.raises(SubmitGateError, match="already consumed"):
        store.claim_submit_once(application.id, preview_hash)


def test_profile_update_invalidates_old_submit_approval(tmp_path) -> None:
    store = LocalStore(tmp_path / "app.sqlite")
    application = store.create_application(
        job_url="https://jobs.example.com/1",
        profile_hash="old-profile",
    )
    store.record_field_action(
        application.id,
        field_name="email",
        question="Email",
        value="user@example.com",
        source="PROFILE.md:contact.email",
        confidence=1.0,
        sensitive=False,
    )
    preview_hash = store.build_preview(application.id)
    store.approve_preview(application.id, preview_hash)

    store.update_application_profile(application.id, "new-profile")

    current = store.get_application(application.id)
    assert current is not None
    assert current.profile_hash == "new-profile"
    assert current.preview_hash is None
    with pytest.raises(SubmitGateError):
        store.claim_submit_once(application.id, preview_hash)


def test_field_change_invalidates_preview_and_approval(tmp_path) -> None:
    store = LocalStore(tmp_path / "app.sqlite")
    application = store.create_application(
        job_url="https://jobs.example.com/1",
        profile_hash="profile-hash",
    )
    store.record_field_action(
        application.id,
        field_name="email",
        question="Email",
        value="user@example.com",
        source="PROFILE.md:contact.email",
        confidence=1.0,
        sensitive=False,
    )
    preview_hash = store.build_preview(application.id)
    store.approve_preview(application.id, preview_hash)

    store.record_field_action(
        application.id,
        field_name="phone",
        question="Phone",
        value="555-0100",
        source="PROFILE.md:contact.phone",
        confidence=1.0,
        sensitive=False,
    )

    current = store.get_application(application.id)
    assert current is not None
    assert current.status == "applying"
    assert current.preview_hash is None
    with pytest.raises(SubmitGateError):
        store.claim_submit_once(application.id, preview_hash)


@pytest.mark.parametrize(
    "blocked_status",
    ["waiting_for_otp", "waiting_for_user_answer", "blocked_by_captcha", "cancelled"],
)
def test_blockers_cannot_be_previewed_or_submitted(tmp_path, blocked_status) -> None:
    store = LocalStore(tmp_path / f"{blocked_status}.sqlite")
    application = store.create_application(
        job_url="https://jobs.example.com/1",
        profile_hash="profile-hash",
    )
    store.record_field_action(
        application.id,
        field_name="email",
        question="Email",
        value="user@example.com",
        source="PROFILE.md:contact.email",
        confidence=1.0,
        sensitive=False,
    )
    store.set_status(application.id, blocked_status)

    with pytest.raises(SubmitGateError, match="Cannot build review"):
        store.build_preview(application.id)


def test_cancelled_application_cannot_consume_existing_approval(tmp_path) -> None:
    store = LocalStore(tmp_path / "app.sqlite")
    application = store.create_application(
        job_url="https://jobs.example.com/1",
        profile_hash="profile-hash",
    )
    store.record_field_action(
        application.id,
        field_name="email",
        question="Email",
        value="user@example.com",
        source="PROFILE.md:contact.email",
        confidence=1.0,
        sensitive=False,
    )
    preview_hash = store.build_preview(application.id)
    store.approve_preview(application.id, preview_hash)
    store.set_status(application.id, "cancelled")

    with pytest.raises(SubmitGateError, match="cancelled"):
        store.claim_submit_once(application.id, preview_hash)
