"""Welcome brand + Grok-style hero mark for TUI-Hire.

ASCII-only (no box-drawing FIGlet) so Windows CMD renders cleanly.
"""

from __future__ import annotations

from job_applyer import __version__

BRAND = "TUI-Hire"
BRAND_MARK = "TUI-Hire"
BRAND_SLUG = "tui-hire"
TAGLINE = "US job applications | verified profile | dry-run first"

# Left column mark — compact, intentional, Windows-safe
HERO_LOGO = r"""
      .oOOo.
    oO------Oo
   o   TUI    o
   O   HIRE   O
    Oo------oO
      'oOOo'
""".strip(
    "\n"
)

HERO_BLURB = (
    "Interview, resume PDF, and dry-run US career pages from the terminal. "
    "Submit stays locked until you say so."
)

TIP = "Tip: Press 1-6 or click a menu row | type /help in the prompt | esc returns here"


def hero_title_line() -> str:
    return f"[bold]{BRAND}[/]  [dim]{__version__}[/]"
