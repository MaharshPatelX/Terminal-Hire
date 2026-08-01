from __future__ import annotations

import asyncio
from urllib.parse import quote

import pytest

from src.browser import BrowserSession
from src.db import LocalStore, SubmitGateError


def test_browser_fill_evidence_and_one_click_submit(tmp_path) -> None:
    html = """
    <html>
      <body>
        <label for="email">Email</label>
        <input id="email" name="email" type="email">
        <label for="ssn">Social Security Number</label>
        <input id="ssn" name="ssn" type="text">
        <label for="resume">Resume</label>
        <input id="resume" name="resume" type="file">
        <span>Authorized to work?</span>
        <label><input name="authorized" type="radio" value="Yes">Yes</label>
        <label><input name="authorized" type="radio" value="No">No</label>
        <button onclick="document.body.innerHTML='<h1>Application submitted</h1>'">
          Submit Application
        </button>
      </body>
    </html>
    """
    url = f"data:text/html,{quote(html)}"
    store = LocalStore(tmp_path / "app.sqlite")
    application = store.create_application(job_url=url, profile_hash="profile-hash")
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 synthetic")

    async def run() -> None:
        async with BrowserSession(
            store=store,
            artifact_dir=tmp_path / "artifacts",
            application_id=application.id,
            headless=True,
            submission_enabled=True,
        ) as session:
            await session.open(url)
            fields = await session.inventory_fields()
            by_name = {field.name: field for field in fields}
            await session.fill_field(
                by_name["email"],
                value="user@example.com",
                source="PROFILE.md:contact.email",
                confidence=1.0,
                sensitive=False,
            )
            await session.fill_field(
                by_name["ssn"],
                value="111-22-3333",
                source="PROFILE.md:sensitive_identity.ssn",
                confidence=1.0,
                sensitive=True,
            )
            await session.fill_field(
                by_name["resume"],
                value=str(resume_path),
                source="PROFILE.md:documents.resume",
                confidence=1.0,
                sensitive=False,
            )
            radio_fields = [field for field in fields if field.name == "authorized"]
            radio_results = [
                await session.fill_field(
                    field,
                    value="Yes",
                    source="PROFILE.md:work_authorization.authorized",
                    confidence=1.0,
                    sensitive=False,
                )
                for field in radio_fields
            ]
            assert sum(result is not None for result in radio_results) == 1
            preview_hash = store.build_preview(application.id)
            store.approve_preview(application.id, preview_hash)

            assert await session.submit_once(preview_hash) is True
            with pytest.raises(SubmitGateError, match="already consumed"):
                await session.submit_once(preview_hash)

    asyncio.run(run())

    current = store.get_application(application.id)
    actions = store.field_actions(application.id)
    artifacts = store.artifacts(application.id)

    assert current is not None
    assert current.status == "submitted"
    assert next(action for action in actions if action["field_name"] == "ssn")[
        "value"
    ] == "<redacted>"
    assert len(artifacts) >= 4
    assert all(artifact["redacted"] for artifact in artifacts)


def test_submit_requires_one_unambiguous_control(tmp_path) -> None:
    html = """
    <html><body>
      <button>Submit</button>
      <button>Submit Application</button>
    </body></html>
    """
    url = f"data:text/html,{quote(html)}"
    store = LocalStore(tmp_path / "app.sqlite")
    application = store.create_application(job_url=url, profile_hash="profile-hash")
    store.record_field_action(
        application.id,
        field_name="email",
        question="Email",
        value="user@example.com",
        source="PROFILE.md:contact.email",
        confidence=1.0,
        sensitive=False,
    )
    async def run() -> None:
        async with BrowserSession(
            store=store,
            artifact_dir=tmp_path / "artifacts",
            application_id=application.id,
            headless=True,
            submission_enabled=True,
        ) as session:
            await session.open(url)
            preview_hash = store.build_preview(application.id)
            store.approve_preview(application.id, preview_hash)
            with pytest.raises(SubmitGateError, match="found 2"):
                await session.submit_once(preview_hash)

    asyncio.run(run())

    current = store.get_application(application.id)
    assert current is not None
    assert current.status == "approved"
