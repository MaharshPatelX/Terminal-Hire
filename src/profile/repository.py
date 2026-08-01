"""Validated, atomic storage for PROFILE.md."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import Profile, ProfileSnapshot


class ProfileFormatError(ValueError):
    """PROFILE.md cannot be parsed or does not match the supported schema."""


class MarkdownProfileRepository:
    """Treat one Markdown file as the only candidate-profile source of truth."""

    FRONT_MATTER = "---"

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()
        self.backup_path = self.path.with_suffix(f"{self.path.suffix}.bak")

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> Profile:
        text = self.read_text()
        data = self._parse_front_matter(text)
        try:
            profile = Profile.model_validate(data)
        except ValidationError as error:
            raise ProfileFormatError(f"PROFILE.md validation failed: {error}") from error
        if profile.schema_version != 1:
            raise ProfileFormatError(
                f"Unsupported PROFILE.md schema version: {profile.schema_version}"
            )
        return profile

    def read_text(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ProfileFormatError(f"PROFILE.md does not exist: {self.path}") from error
        except UnicodeDecodeError as error:
            raise ProfileFormatError("PROFILE.md must be UTF-8 text") from error

    def snapshot(self) -> ProfileSnapshot:
        text = self.read_text()
        data = self._parse_front_matter(text)
        try:
            profile = Profile.model_validate(data)
        except ValidationError as error:
            raise ProfileFormatError(f"PROFILE.md validation failed: {error}") from error
        if profile.schema_version != 1:
            raise ProfileFormatError(
                f"Unsupported PROFILE.md schema version: {profile.schema_version}"
            )
        return ProfileSnapshot.from_text(profile, text)

    def save(self, profile: Profile) -> ProfileSnapshot:
        profile = profile.model_copy(deep=True)
        profile.updated_at = datetime.now(UTC)
        text = self.render(profile)
        self._parse_front_matter(text)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            shutil.copy2(self.path, self.backup_path)
            self._restrict_to_current_user(self.backup_path)

        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.path)
            self._restrict_to_current_user(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

        return ProfileSnapshot.from_text(profile, text)

    def recover_backup(self) -> Profile:
        if not self.backup_path.exists():
            raise ProfileFormatError("No PROFILE.md backup is available")
        backup_text = self.backup_path.read_text(encoding="utf-8")
        try:
            profile = Profile.model_validate(self._parse_front_matter(backup_text))
        except ValidationError as error:
            raise ProfileFormatError(f"Backup validation failed: {error}") from error
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(self.backup_path, self.path)
        self._restrict_to_current_user(self.path)
        return profile

    @classmethod
    def render(cls, profile: Profile) -> str:
        data = profile.model_dump(mode="json")
        yaml_text = yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).strip()
        body = cls._render_readable_body(profile)
        return f"{cls.FRONT_MATTER}\n{yaml_text}\n{cls.FRONT_MATTER}\n\n{body}\n"

    @classmethod
    def _parse_front_matter(cls, text: str) -> dict:
        lines = text.lstrip("\ufeff").splitlines()
        if not lines or lines[0].strip() != cls.FRONT_MATTER:
            raise ProfileFormatError("PROFILE.md must start with YAML front matter")
        try:
            closing_index = next(
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() == cls.FRONT_MATTER
            )
        except StopIteration as error:
            raise ProfileFormatError("PROFILE.md front matter is not closed") from error
        yaml_text = "\n".join(lines[1:closing_index])
        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as error:
            raise ProfileFormatError(f"PROFILE.md YAML is invalid: {error}") from error
        if not isinstance(data, dict):
            raise ProfileFormatError("PROFILE.md front matter must contain a mapping")
        return data

    @staticmethod
    def _render_readable_body(profile: Profile) -> str:
        def mapping(title: str, values: dict[str, str]) -> list[str]:
            lines = [f"## {title}", ""]
            if not values:
                return lines + ["_Not provided._", ""]
            return lines + [f"- **{key.replace('_', ' ').title()}:** {value}" for key, value in values.items()] + [""]

        def entries(title: str, values: list[str]) -> list[str]:
            lines = [f"## {title}", ""]
            return lines + ([f"- {value}" for value in values] if values else ["_Not provided._"]) + [""]

        lines = [
            "# Candidate Profile",
            "",
            "> The YAML front matter is authoritative. Use TUI-Hire to update this file safely.",
            "",
            f"**Status:** {profile.status}  ",
            f"**Updated:** {profile.updated_at.isoformat()}",
            "",
        ]
        lines += mapping("Identity", profile.identity)
        lines += mapping("Contact", profile.contact)
        lines += mapping("Sensitive Identity", profile.sensitive_identity)
        lines += mapping("Location and Preferences", profile.location_preferences)
        lines += ["## Professional Summary", "", profile.professional_summary or "_Not provided._", ""]
        lines += entries("Education", profile.education)
        lines += entries("Work History", profile.work_history)
        lines += entries("Projects", profile.projects)
        lines += entries("Skills", profile.skills)
        lines += mapping("Work Authorization", profile.work_authorization)
        lines += mapping("Common Answers", profile.common_answers)
        lines += mapping("Answer Policies", profile.answer_policies)
        lines += entries("User Insights", profile.insights)
        lines += ["## Portal Questions and Answers", ""]
        if profile.portal_qa:
            for answer in profile.portal_qa:
                lines += [
                    f"### {answer.intent}",
                    "",
                    f"- **Questions:** {' | '.join(answer.questions)}",
                    f"- **Answer:** {answer.answer}",
                    f"- **Scope:** {answer.scope}",
                    f"- **Verified:** {'yes' if answer.verified else 'no'}",
                    "",
                ]
        else:
            lines += ["_No portal answers captured yet._", ""]
        return "\n".join(lines).rstrip()

    @staticmethod
    def _restrict_to_current_user(path: Path) -> None:
        # chmod is strongest on POSIX. On Windows it at least removes inherited
        # write bits; the data directory is deliberately outside the repository.
        try:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
