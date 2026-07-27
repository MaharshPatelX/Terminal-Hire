"""Welcome logos — ASCII-only so Windows CMD / ConHost render cleanly.

Box-drawing FIGlet (╗╚═█) is avoided: many Windows console fonts give those
glyphs the wrong cell width and the banner collapses into noise.
"""

from __future__ import annotations

# Readable wordmark (~54 cols) — pure ASCII, no box-drawing
LOGO = r"""
+----------------------------------------------------+
|                                                    |
|                  TERMINAL-HIRE                     |
|                                                    |
+----------------------------------------------------+
""".strip(
    "\n"
)

LOGO_SMALL = LOGO

# Narrow mark for tight terminals
LOGO_COMPACT = r"""
+----------------------+
|    TERMINAL-HIRE     |
+----------------------+
""".strip(
    "\n"
)

TAGLINE = "hire from the terminal | verified profile | dry-run first"
BRAND = "Terminal-Hire"
BRAND_SLUG = "terminal-hire"


def welcome_logo(width: int) -> str:
    """Pick a logo that fits the current terminal width."""
    if width >= 56:
        return LOGO
    return LOGO_COMPACT
