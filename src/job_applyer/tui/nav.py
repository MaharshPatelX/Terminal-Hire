"""Navigation map shared by welcome menu and app hotkeys."""

from __future__ import annotations

# Number keys 1-6 → screens (FLOW.md)
SCREEN_HOTKEYS = {
    "1": "onboard",
    "2": "profile",
    "3": "resume",
    "4": "apply",
    "5": "apps",
    "6": "settings",
}

# (id, label, shortcut)
MENU_ITEMS: list[tuple[str, str, str]] = [
    ("onboard", "Onboard", "1"),
    ("profile", "Profile / Packs", "2"),
    ("resume", "Resume (LaTeX → PDF)", "3"),
    ("apply", "Apply by URL", "4"),
    ("apps", "Applications", "5"),
    ("settings", "Settings", "6"),
]
