"""Screen registry — maps FLOW.md screens to modules."""

from __future__ import annotations

from .apply import ApplyScreen
from .apps import AppsScreen
from .home import WelcomeScreen
from .onboard import OnboardScreen
from .profile import ProfileScreen
from .resume import ResumeScreen
from .settings import SettingsScreen

SCREENS = {
    "welcome": WelcomeScreen,
    "onboard": OnboardScreen,
    "profile": ProfileScreen,
    "resume": ResumeScreen,
    "apply": ApplyScreen,
    "apps": AppsScreen,
    "settings": SettingsScreen,
}
