"""Entry point: ``python -m src`` or ``terminal-hire``."""

from __future__ import annotations


def main() -> None:
    from .app import TerminalHireApp

    TerminalHireApp().run()


if __name__ == "__main__":
    main()
