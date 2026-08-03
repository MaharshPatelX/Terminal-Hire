from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from textual.widgets import Input

from src.app import TerminalHireApp
from src.config import Settings
from src.profile import MarkdownProfileRepository, Profile


def test_first_launch_forces_onboarding(tmp_path) -> None:
    async def run() -> None:
        app = TerminalHireApp(Settings(data_dir=tmp_path, llm_provider="off"))
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.screen.__class__.__name__ == "OnboardScreen"
            await pilot.pause()
            assert app.focused is app.screen.query_one("#chat-input", Input)
            await pilot.press("1", "2", "3")
            assert app.screen.query_one("#chat-input", Input).value == "123"

    asyncio.run(run())


def test_ready_profile_opens_four_item_workspace(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, llm_provider="off")
    MarkdownProfileRepository(settings.profile_path).save(
        Profile(
            status="complete",
            verified_at=datetime.now(UTC),
            identity={"full_name": "Ada Lovelace"},
            contact={"email": "ada@example.com", "phone": "555-0100"},
            professional_summary="Engineer",
        )
    )

    async def run() -> None:
        app = TerminalHireApp(settings)
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.screen.__class__.__name__ == "WelcomeScreen"
            for key, screen_name in (
                ("1", "ProfileScreen"),
                ("2", "ApplyScreen"),
                ("3", "AppsScreen"),
                ("4", "SettingsScreen"),
            ):
                await pilot.press(key)
                await pilot.pause()
                assert app.screen.__class__.__name__ == screen_name
                await pilot.press("escape")
                await pilot.pause()
                assert app.screen.__class__.__name__ == "WelcomeScreen"

    asyncio.run(run())


def test_onboarding_rejects_invalid_zip_before_saving(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, llm_provider="off")
    MarkdownProfileRepository(settings.profile_path).save(
        Profile(
            identity={"full_name": "Ada Lovelace"},
            contact={"email": "ada@example.com", "phone": "+1 214 555 0100"},
            location_preferences={
                "country": "United States",
                "city": "Dallas",
                "state": "Texas",
            },
        )
    )

    async def run() -> None:
        app = TerminalHireApp(settings)
        async with app.run_test(size=(120, 40)) as pilot:
            answer = app.screen.query_one("#chat-input", Input)
            answer.value = "1234"
            await pilot.press("enter")
            await pilot.pause()
            profile = app.profile_repository.load()
            assert profile.location_preferences.get("postal_code") is None

            answer.value = "75201"
            await pilot.press("enter")
            await pilot.pause()
            profile = app.profile_repository.load()
            assert profile.location_preferences["postal_code"] == "75201"

    asyncio.run(run())
