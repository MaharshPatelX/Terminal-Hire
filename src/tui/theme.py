"""TUI-Hire's local-first midnight theme."""

from __future__ import annotations

from textual.theme import Theme

TERMINAL_HIRE_THEME = Theme(
    name="terminal-hire",
    primary="#63e6be",
    secondary="#a78bfa",
    accent="#f2cc60",
    foreground="#e6edf3",
    background="#0b0f14",
    success="#63e6be",
    warning="#f2cc60",
    error="#ff7b72",
    surface="#111820",
    panel="#17212b",
    dark=True,
)
