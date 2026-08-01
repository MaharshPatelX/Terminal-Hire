"""Navigation map shared by welcome menu and app hotkeys."""

from __future__ import annotations

# Ready-state number keys 1-4 → screens (Onboarding is a startup gate).
SCREEN_HOTKEYS = {
    "1": "profile",
    "2": "apply",
    "3": "apps",
    "4": "settings",
}

# (id, label, shortcut)
MENU_ITEMS: list[tuple[str, str, str]] = [
    ("profile", "Profile", "1"),
    ("apply", "Apply by URL", "2"),
    ("apps", "Applications", "3"),
    ("settings", "Settings", "4"),
]
