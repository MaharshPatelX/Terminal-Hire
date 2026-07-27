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
