"""Screen registry — maps FLOW.md screens to modules."""

from __future__ import annotations

from job_applyer.tui.screens.apply import ApplyScreen
from job_applyer.tui.screens.apps import AppsScreen
from job_applyer.tui.screens.home import WelcomeScreen
from job_applyer.tui.screens.onboard import OnboardScreen
from job_applyer.tui.screens.profile import ProfileScreen
from job_applyer.tui.screens.resume import ResumeScreen
from job_applyer.tui.screens.settings import SettingsScreen

SCREENS = {
    "welcome": WelcomeScreen,
    "onboard": OnboardScreen,
    "profile": ProfileScreen,
    "resume": ResumeScreen,
    "apply": ApplyScreen,
    "apps": AppsScreen,
    "settings": SettingsScreen,
}

# Number keys 1-6 → screens (FLOW navigation)
SCREEN_HOTKEYS = {
    "1": "onboard",
    "2": "profile",
    "3": "resume",
    "4": "apply",
    "5": "apps",
    "6": "settings",
}

MENU_ITEMS: list[tuple[str, str, str]] = [
    # (id, label, shortcut)
    ("onboard", "Onboard", "1"),
    ("profile", "Profile / Packs", "2"),
    ("resume", "Resume (LaTeX → PDF)", "3"),
    ("apply", "Apply by URL", "4"),
    ("apps", "Applications", "5"),
    ("settings", "Settings", "6"),
]
