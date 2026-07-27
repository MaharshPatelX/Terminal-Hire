"""Terminal-Hire dark theme registration."""

from __future__ import annotations

from textual.theme import Theme

TERMINAL_HIRE_THEME = Theme(
    name="terminal-hire",
    primary="#58a6ff",
    secondary="#8b949e",
    accent="#3fb950",
    foreground="#e6edf3",
    background="#0d1117",
    success="#3fb950",
    warning="#d29922",
    error="#f85149",
    surface="#161b22",
    panel="#1c2128",
    dark=True,
)
