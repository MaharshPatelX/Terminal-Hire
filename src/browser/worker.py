"""Playwright execution with screenshots, checkpoints, and one-use submit gates."""

from __future__ import annotations

import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Self

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from ..db import CredentialRecord, LocalStore, SubmitGateError


@dataclass(frozen=True, slots=True)
class FormField:
    selector: str
    name: str
    label: str
    field_type: str
    required: bool
    option_value: str = ""


@dataclass(frozen=True, slots=True)
class PageBlocker:
    kind: str
    message: str


class BrowserSession:
    """One browser attempt. It never retries a submit click."""

    REDACTION_STYLE_ID = "tui-hire-redactions"
    REDACTION_SELECTORS = (
        "input[type='password'], "
        "input[autocomplete*='one-time-code'], "
        "input[name*='ssn' i], "
        "input[id*='ssn' i], "
        "input[name*='social' i], "
        "input[id*='social' i], "
        "input[name*='passport' i], input[id*='passport' i], "
        "input[name*='license' i], input[id*='license' i], "
        "input[name*='alien' i], input[id*='alien' i], "
        "input[name*='uscis' i], input[id*='uscis' i], "
        "input[name*='document' i], input[id*='document' i]"
    )

    def __init__(
        self,
        *,
        store: LocalStore,
        artifact_dir: Path,
        application_id: str,
        headless: bool = False,
        submission_enabled: bool = False,
    ) -> None:
        self.store = store
        self.artifact_dir = artifact_dir.expanduser() / application_id
        self.application_id = application_id
        self.headless = headless
        self.submission_enabled = submission_enabled
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None
        self._screenshot_index = 0
        self.authentication_pending = False

    async def __aenter__(self) -> Self:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self.page = await self._context.new_page()
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def open(self, url: str) -> None:
        page = self._require_page()
        application = self.store.get_application(self.application_id)
        if application is None:
            raise KeyError(f"Unknown application: {self.application_id}")
        if application.status not in {
            "ready_to_apply",
            "applying",
            "waiting_for_credential",
        }:
            raise SubmitGateError(
                f"Cannot open browser while application is {application.status}"
            )
        self.store.set_status(self.application_id, "applying")
        await page.goto(url, wait_until="domcontentloaded")
        screenshot = await self.capture("opened")
        self.store.log_event(
            self.application_id,
            event_type="page_opened",
            target=page.url,
            screenshot_path=str(screenshot),
        )
        self.store.save_checkpoint(
            self.application_id,
            step="opened",
            url=page.url,
            state={"title": await page.title()},
        )

    async def fill_login(self, credential: CredentialRecord) -> list[str]:
        """Fill detected login fields without submitting or logging secret values."""
        page = self._require_page()
        filled: list[str] = []
        email = page.locator(
            "input[type='email'], input[autocomplete='email'], input[name*='email' i]"
        ).first
        username = page.locator(
            "input[autocomplete='username'], input[name*='user' i]"
        ).first
        passwords = page.locator("input[type='password']")

        if await email.count() and credential.email:
            await email.fill(credential.email)
            filled.append("email")
        elif await username.count() and credential.username:
            await username.fill(credential.username)
            filled.append("username")
        for index in range(await passwords.count()):
            await passwords.nth(index).fill(credential.password)
            filled.append("password" if index == 0 else "password_confirmation")

        screenshot = await self.capture("login-filled")
        self.authentication_pending = bool(filled)
        for field_name in filled:
            self.store.log_event(
                self.application_id,
                event_type="credential_filled",
                target=field_name,
                value="<credential>",
                sensitive=True,
                screenshot_path=str(screenshot),
            )
        return filled

    async def continue_login(self) -> PageBlocker | None:
        """Click one login/continue button; caller must handle OTP or CAPTCHA."""
        page = self._require_page()
        terms = page.locator(
            "input[type='checkbox'][name*='term' i], "
            "input[type='checkbox'][id*='term' i], "
            "input[type='checkbox'][name*='consent' i]"
        )
        for index in range(await terms.count()):
            if not await terms.nth(index).is_checked():
                self.store.set_status(self.application_id, "waiting_for_consent")
                return PageBlocker(
                    "consent",
                    "Review and accept account terms manually in the browser",
                )
        button = page.get_by_role(
            "button",
            name=re.compile(
                r"sign\s*in|sign\s*up|create\s*account|register|"
                r"log\s*in|continue|next|verify|submit\s*code",
                re.IGNORECASE,
            ),
        ).first
        if not await button.count():
            return PageBlocker("login", "No login/continue button was detected")
        await button.click()
        self.authentication_pending = False
        await page.wait_for_timeout(750)
        screenshot = await self.capture("login-continued")
        self.store.log_event(
            self.application_id,
            event_type="login_continued",
            target=page.url,
            screenshot_path=str(screenshot),
        )
        return await self.detect_blocker()

    async def enter_otp(self, otp: str) -> None:
        """Use an OTP once. It is never persisted."""
        page = self._require_page()
        locator = page.locator(
            "input[autocomplete='one-time-code'], "
            "input[name*='otp' i], input[id*='otp' i], "
            "input[name*='code' i]"
        ).first
        if not await locator.count():
            raise RuntimeError("No OTP input was detected")
        await locator.fill(otp)
        screenshot = await self.capture("otp-filled")
        self.store.log_event(
            self.application_id,
            event_type="otp_filled",
            target="one-time-code",
            value="<otp>",
            sensitive=True,
            screenshot_path=str(screenshot),
        )

    async def inventory_fields(self) -> list[FormField]:
        page = self._require_page()
        raw_fields: list[dict[str, Any]] = await page.locator(
            "input:not([type='hidden']):not([type='submit']), textarea, select"
        ).evaluate_all(
            """
            elements => elements.map((element, index) => {
                const id = element.id || "";
                const name = element.name || "";
                const explicit = id
                    ? document.querySelector(`label[for="${CSS.escape(id)}"]`)
                    : null;
                const wrapping = element.closest("label");
                const aria = element.getAttribute("aria-label") || "";
                const placeholder = element.getAttribute("placeholder") || "";
                const label = (
                    explicit?.innerText || wrapping?.innerText || aria || placeholder || name || id
                ).trim();
                let selector;
                if (id) {
                    selector = `#${CSS.escape(id)}`;
                } else if (name && element.type === "radio") {
                    selector = `input[name="${CSS.escape(name)}"][value="${CSS.escape(element.value)}"]`;
                } else if (name) {
                    selector = `${element.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
                } else {
                    selector = `${element.tagName.toLowerCase()}:nth-of-type(${index + 1})`;
                }
                return {
                    selector,
                    name: name || id || `field_${index + 1}`,
                    label,
                    field_type: element.type || element.tagName.toLowerCase(),
                    required: Boolean(element.required),
                    option_value: element.value || "",
                };
            })
            """
        )
        fields = [FormField(**item) for item in raw_fields]
        self.store.log_event(
            self.application_id,
            event_type="fields_inventoried",
            target=page.url,
            details={"count": len(fields)},
        )
        self.store.save_checkpoint(
            self.application_id,
            step="inventory",
            url=page.url,
            state={"fields": [asdict(field) for field in fields]},
        )
        return fields

    async def fill_field(
        self,
        field: FormField,
        *,
        value: str,
        source: str,
        confidence: float,
        sensitive: bool,
    ) -> Path | None:
        page = self._require_page()
        locator = page.locator(field.selector).first
        if field.field_type in {"select-one", "select"}:
            await locator.select_option(label=value)
        elif field.field_type == "file":
            file_path = Path(value).expanduser()
            if not file_path.is_file():
                raise FileNotFoundError(f"Upload file does not exist: {file_path}")
            await locator.set_input_files(file_path)
        elif field.field_type == "radio":
            expected = re.sub(r"[^a-z0-9]+", "", value.casefold())
            candidates = {
                re.sub(r"[^a-z0-9]+", "", field.label.casefold()),
                re.sub(r"[^a-z0-9]+", "", field.option_value.casefold()),
            }
            if expected not in candidates:
                return None
            await locator.check()
        elif field.field_type == "checkbox":
            truthy = value.strip().casefold() in {"true", "yes", "1", "on"}
            if truthy:
                await locator.check()
            else:
                await locator.uncheck()
        else:
            await locator.fill(value)
        screenshot = await self.capture(f"field-{field.name}")
        self.store.record_field_action(
            self.application_id,
            field_name=field.name,
            question=field.label,
            value=value,
            source=source,
            confidence=confidence,
            sensitive=sensitive,
            status="filled",
        )
        self.store.log_event(
            self.application_id,
            event_type="field_filled",
            target=field.name,
            value=value,
            sensitive=sensitive,
            details={"source": source, "confidence": confidence},
            screenshot_path=str(screenshot),
        )
        return screenshot

    async def detect_blocker(self) -> PageBlocker | None:
        page = self._require_page()
        body_text = (await page.locator("body").inner_text()).casefold()
        if "captcha" in body_text or "verify you are human" in body_text:
            self.store.set_status(self.application_id, "blocked_by_captcha")
            return PageBlocker("captcha", "Solve the CAPTCHA in the browser, then resume")
        terms = page.locator(
            "input[type='checkbox'][name*='term' i], "
            "input[type='checkbox'][id*='term' i], "
            "input[type='checkbox'][name*='consent' i]"
        )
        for index in range(await terms.count()):
            if not await terms.nth(index).is_checked():
                self.store.set_status(self.application_id, "waiting_for_consent")
                return PageBlocker(
                    "consent",
                    "Review and accept the terms manually in the browser",
                )
        otp_locator = page.locator(
            "input[autocomplete='one-time-code'], input[name*='otp' i], input[id*='otp' i]"
        )
        if await otp_locator.count():
            self.store.set_status(self.application_id, "waiting_for_otp")
            return PageBlocker("otp", "Enter the one-time code in TUI-Hire")
        return None

    async def submit_once(self, preview_hash: str) -> bool:
        """Consume approval before exactly one click; failures become uncertain."""
        if not self.submission_enabled:
            raise SubmitGateError("Supervised submission is disabled in Settings")
        page = self._require_page()
        self.store.assert_submit_allowed(self.application_id, preview_hash)
        button_candidates = page.get_by_role(
            "button",
            name=re.compile(
                r"^\s*(?:submit(?:\s+application)?|send\s+application)\s*$",
                re.IGNORECASE,
            ),
        )
        input_candidates = page.locator("input[type='submit']")
        targets = []
        for index in range(await button_candidates.count()):
            candidate = button_candidates.nth(index)
            if await candidate.is_visible() and await candidate.is_enabled():
                targets.append(candidate)
        for index in range(await input_candidates.count()):
            candidate = input_candidates.nth(index)
            label = (await candidate.get_attribute("value") or "").strip()
            if (
                re.fullmatch(
                    r"submit(?:\s+application)?|send\s+application",
                    label,
                    re.IGNORECASE,
                )
                and await candidate.is_visible()
                and await candidate.is_enabled()
            ):
                targets.append(candidate)
        if len(targets) != 1:
            raise SubmitGateError(
                f"Expected one unambiguous Submit control; found {len(targets)}"
            )

        self.store.claim_submit_once(self.application_id, preview_hash)
        before_url = page.url
        try:
            await targets[0].click(no_wait_after=False)
            await page.wait_for_timeout(1500)
            screenshot = await self.capture("submit-result")
            text = (await page.locator("body").inner_text()).casefold()
            confirmed = any(
                phrase in text
                for phrase in (
                    "application submitted",
                    "thank you for applying",
                    "we received your application",
                )
            )
            self.store.record_submission_result(
                self.application_id,
                confirmed=confirmed,
                details={
                    "url": page.url,
                    "url_changed": page.url != before_url,
                },
                screenshot_path=str(screenshot),
            )
            return confirmed
        except Exception as error:
            self.store.record_submission_result(
                self.application_id,
                confirmed=False,
                details={"reason": type(error).__name__},
            )
            raise SubmitGateError(
                "Submit result is uncertain; reconcile manually and do not retry"
            ) from error

    async def capture(self, label: str) -> Path:
        page = self._require_page()
        self._screenshot_index += 1
        safe_label = re.sub(r"[^a-z0-9-]+", "-", label.casefold()).strip("-")
        path = self.artifact_dir / f"{self._screenshot_index:04d}-{safe_label}.png"
        await page.evaluate(
            """
            ({styleId, selectors}) => {
                document.getElementById(styleId)?.remove();
                const style = document.createElement("style");
                style.id = styleId;
                style.textContent = `${selectors} {
                    filter: blur(10px) !important;
                    color: transparent !important;
                }`;
                document.documentElement.appendChild(style);
            }
            """,
            {"styleId": self.REDACTION_STYLE_ID, "selectors": self.REDACTION_SELECTORS},
        )
        try:
            await page.screenshot(path=path, full_page=True)
        finally:
            await page.evaluate(
                "styleId => document.getElementById(styleId)?.remove()",
                self.REDACTION_STYLE_ID,
            )
        try:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        self.store.add_artifact(
            self.application_id,
            kind="screenshot",
            path=path,
            redacted=True,
        )
        return path

    def _require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("BrowserSession must be entered before use")
        return self.page
