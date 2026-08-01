"""SQLite store for credentials, applications, events, and submit gates."""

from __future__ import annotations

import json
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


class SubmitGateError(RuntimeError):
    """A supervised submit was attempted without a valid one-use approval."""


@dataclass(frozen=True, slots=True)
class CredentialRecord:
    domain: str
    email: str
    username: str
    password: str = field(repr=False)
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class ApplicationRecord:
    id: str
    job_url: str
    company: str
    status: str
    profile_hash: str
    preview_hash: str | None
    created_at: str
    updated_at: str


class LocalStore:
    """Own all SQLite writes; PROFILE.md data never lives in these tables."""

    PLAINTEXT_CREDENTIAL_WARNING = (
        "Passwords are stored as plaintext by explicit configuration. "
        "Keep this OS-local database private."
    )

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._restrict_to_current_user()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_credential(
        self,
        *,
        domain: str,
        email: str,
        username: str,
        password: str,
    ) -> None:
        normalized_domain = self._normalize_domain(domain)
        now = utc_iso()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO credentials(domain, email, username, password, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    email = excluded.email,
                    username = excluded.username,
                    password = excluded.password,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_domain,
                    email.strip(),
                    username.strip(),
                    password,
                    now,
                    now,
                ),
            )

    def get_credential(self, domain: str) -> CredentialRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT domain, email, username, password, updated_at
                FROM credentials
                WHERE domain = ?
                """,
                (self._normalize_domain(domain),),
            ).fetchone()
        return CredentialRecord(**dict(row)) if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO runtime_settings(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, utc_iso()),
            )

    def get_setting(self, key: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM runtime_settings WHERE key = ?",
                (key,),
            ).fetchone()
        return str(row["value"]) if row else None

    def create_application(
        self,
        *,
        job_url: str,
        profile_hash: str,
        company: str = "",
    ) -> ApplicationRecord:
        application_id = str(uuid4())
        now = utc_iso()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO applications(
                    id, job_url, company, status, profile_hash, created_at, updated_at
                )
                VALUES (?, ?, ?, 'ready_to_apply', ?, ?, ?)
                """,
                (application_id, job_url.strip(), company.strip(), profile_hash, now, now),
            )
        self.log_event(
            application_id,
            event_type="application_created",
            target=job_url,
            details={"company": company},
        )
        record = self.get_application(application_id)
        if record is None:
            raise RuntimeError("Application record was not created")
        return record

    def get_application(self, application_id: str) -> ApplicationRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT id, job_url, company, status, profile_hash, preview_hash,
                       created_at, updated_at
                FROM applications
                WHERE id = ?
                """,
                (application_id,),
            ).fetchone()
        return ApplicationRecord(**dict(row)) if row else None

    def list_applications(self, *, limit: int = 100) -> list[ApplicationRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, job_url, company, status, profile_hash, preview_hash,
                       created_at, updated_at
                FROM applications
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [ApplicationRecord(**dict(row)) for row in rows]

    def set_status(self, application_id: str, status: str) -> None:
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_iso(), application_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown application: {application_id}")

    def update_application_profile(self, application_id: str, profile_hash: str) -> None:
        """Adopt a newly verified profile snapshot and invalidate any old preview."""
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE applications
                SET profile_hash = ?, preview_hash = NULL,
                    status = 'applying', updated_at = ?
                WHERE id = ?
                """,
                (profile_hash, utc_iso(), application_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown application: {application_id}")
            connection.execute(
                "DELETE FROM submit_approvals WHERE application_id = ?",
                (application_id,),
            )

    def log_event(
        self,
        application_id: str,
        *,
        event_type: str,
        target: str = "",
        value: str | None = None,
        sensitive: bool = False,
        details: dict[str, Any] | None = None,
        screenshot_path: str | None = None,
    ) -> None:
        stored_value = "<redacted>" if sensitive and value is not None else value
        with self.connection() as connection:
            sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM application_events
                WHERE application_id = ?
                """,
                (application_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO application_events(
                    application_id, sequence, event_type, target, value,
                    sensitive, details_json, screenshot_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    sequence,
                    event_type,
                    target,
                    stored_value,
                    int(sensitive),
                    json.dumps(details or {}, sort_keys=True),
                    screenshot_path,
                    utc_iso(),
                ),
            )

    def record_field_action(
        self,
        application_id: str,
        *,
        field_name: str,
        question: str,
        value: str,
        source: str,
        confidence: float,
        sensitive: bool,
        status: str = "planned",
    ) -> None:
        value_hash = sha256(value.encode("utf-8")).hexdigest()
        stored_value = "<redacted>" if sensitive else value
        with self.connection() as connection:
            application = connection.execute(
                "SELECT status FROM applications WHERE id = ?",
                (application_id,),
            ).fetchone()
            if application is None:
                raise KeyError(f"Unknown application: {application_id}")
            if application["status"] in {
                "cancelled",
                "submitted",
                "submission_uncertain",
            }:
                raise SubmitGateError(
                    f"Cannot change fields while application is {application['status']}"
                )
            connection.execute(
                """
                INSERT INTO field_actions(
                    application_id, field_name, question, value, value_hash,
                    source, confidence, sensitive, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    field_name,
                    question,
                    stored_value,
                    value_hash,
                    source,
                    confidence,
                    int(sensitive),
                    status,
                    utc_iso(),
                ),
            )
            connection.execute(
                """
                UPDATE applications
                SET preview_hash = NULL, status = 'applying', updated_at = ?
                WHERE id = ?
                """,
                (utc_iso(), application_id),
            )
            connection.execute(
                "DELETE FROM submit_approvals WHERE application_id = ?",
                (application_id,),
            )

    def field_actions(self, application_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, field_name, question, value, value_hash, source,
                       confidence, sensitive, status, created_at
                FROM field_actions
                WHERE application_id = ?
                ORDER BY id
                """,
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def application_events(self, application_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_type, target, value, sensitive,
                       details_json, screenshot_path, created_at
                FROM application_events
                WHERE application_id = ?
                ORDER BY sequence
                """,
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def artifacts(self, application_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT kind, path, redacted, created_at
                FROM artifacts
                WHERE application_id = ?
                ORDER BY id
                """,
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def build_preview(self, application_id: str) -> str:
        application = self.get_application(application_id)
        if application is None:
            raise KeyError(f"Unknown application: {application_id}")
        if application.status != "applying":
            raise SubmitGateError(
                f"Cannot build review while application is {application.status}"
            )
        actions = self.field_actions(application_id)
        if not actions:
            raise SubmitGateError("Cannot review an application with no field actions")
        payload = json.dumps(actions, sort_keys=True, separators=(",", ":"))
        preview_hash = sha256(payload.encode("utf-8")).hexdigest()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE applications
                SET preview_hash = ?, status = 'waiting_for_user_review', updated_at = ?
                WHERE id = ?
                """,
                (preview_hash, utc_iso(), application_id),
            )
        self.log_event(
            application_id,
            event_type="preview_built",
            target=preview_hash,
        )
        return preview_hash

    def approve_preview(self, application_id: str, preview_hash: str) -> None:
        application = self.get_application(application_id)
        if application is None:
            raise KeyError(f"Unknown application: {application_id}")
        if application.preview_hash != preview_hash:
            raise SubmitGateError("Preview changed; review the current fields again")
        if application.status != "waiting_for_user_review":
            raise SubmitGateError(
                f"Cannot approve while application is {application.status}"
            )
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO submit_approvals(
                    application_id, preview_hash, approved_at, consumed_at
                )
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(application_id) DO UPDATE SET
                    preview_hash = excluded.preview_hash,
                    approved_at = excluded.approved_at,
                    consumed_at = NULL
                """,
                (application_id, preview_hash, utc_iso()),
            )
            connection.execute(
                """
                UPDATE applications
                SET status = 'approved', updated_at = ?
                WHERE id = ?
                """,
                (utc_iso(), application_id),
            )
        self.log_event(
            application_id,
            event_type="submit_approved",
            target=preview_hash,
        )

    def claim_submit_once(self, application_id: str, preview_hash: str) -> None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT approval.preview_hash AS approved_preview,
                       approval.consumed_at,
                       application.preview_hash AS current_preview,
                       application.status
                FROM submit_approvals AS approval
                JOIN applications AS application
                  ON application.id = approval.application_id
                WHERE approval.application_id = ?
                """,
                (application_id,),
            ).fetchone()
            if (
                row is None
                or row["approved_preview"] != preview_hash
                or row["current_preview"] != preview_hash
            ):
                raise SubmitGateError("No approval exists for this preview")
            if row["consumed_at"] is not None:
                raise SubmitGateError("This submit approval was already consumed")
            if row["status"] != "approved":
                raise SubmitGateError(
                    f"Cannot submit while application is {row['status']}"
                )
            now = utc_iso()
            connection.execute(
                """
                UPDATE submit_approvals
                SET consumed_at = ?
                WHERE application_id = ? AND consumed_at IS NULL
                """,
                (now, application_id),
            )
            connection.execute(
                """
                UPDATE applications
                SET status = 'submitting', updated_at = ?
                WHERE id = ?
                """,
                (now, application_id),
            )
        self.log_event(
            application_id,
            event_type="submit_claimed",
            target=preview_hash,
        )

    def assert_submit_allowed(self, application_id: str, preview_hash: str) -> None:
        """Check a one-use approval without consuming it."""
        application = self.get_application(application_id)
        if application is None:
            raise KeyError(f"Unknown application: {application_id}")
        with self.connection() as connection:
            approval = connection.execute(
                """
                SELECT preview_hash, consumed_at
                FROM submit_approvals
                WHERE application_id = ?
                """,
                (application_id,),
            ).fetchone()
        if (
            approval is None
            or approval["preview_hash"] != preview_hash
            or application.preview_hash != preview_hash
        ):
            raise SubmitGateError("No approval exists for this preview")
        if approval["consumed_at"] is not None:
            raise SubmitGateError("This submit approval was already consumed")
        if application.status != "approved":
            raise SubmitGateError(
                f"Cannot submit while application is {application.status}"
            )

    def record_submission_result(
        self,
        application_id: str,
        *,
        confirmed: bool,
        details: dict[str, Any] | None = None,
        screenshot_path: str | None = None,
    ) -> None:
        status = "submitted" if confirmed else "submission_uncertain"
        self.set_status(application_id, status)
        self.log_event(
            application_id,
            event_type="submission_result",
            target=status,
            details=details,
            screenshot_path=screenshot_path,
        )

    def save_checkpoint(
        self,
        application_id: str,
        *,
        step: str,
        url: str,
        state: dict[str, Any],
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO browser_checkpoints(
                    application_id, step, url, state_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (application_id, step, url, json.dumps(state, sort_keys=True), utc_iso()),
            )

    def add_artifact(
        self,
        application_id: str,
        *,
        kind: str,
        path: Path,
        redacted: bool,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO artifacts(application_id, kind, path, redacted, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (application_id, kind, str(path), int(redacted), utc_iso()),
            )

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL DEFAULT '',
                    username TEXT NOT NULL DEFAULT '',
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    job_url TEXT NOT NULL,
                    company TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    profile_hash TEXT NOT NULL,
                    preview_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS application_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT '',
                    value TEXT,
                    sensitive INTEGER NOT NULL DEFAULT 0,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    screenshot_path TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(application_id, sequence)
                );

                CREATE TABLE IF NOT EXISTS field_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    field_name TEXT NOT NULL,
                    question TEXT NOT NULL DEFAULT '',
                    value TEXT NOT NULL,
                    value_hash TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    sensitive INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS browser_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    step TEXT NOT NULL,
                    url TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS submit_approvals (
                    application_id TEXT PRIMARY KEY REFERENCES applications(id),
                    preview_hash TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    consumed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id),
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    redacted INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _restrict_to_current_user(self) -> None:
        try:
            self.path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    @staticmethod
    def _normalize_domain(value: str) -> str:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        domain = parsed.netloc.casefold().split("@")[-1].split(":")[0]
        if not domain:
            raise ValueError("A credential domain is required")
        return domain
