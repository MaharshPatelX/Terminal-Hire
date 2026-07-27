"""Entry point: ``python -m job_applyer`` or ``terminal-hire``."""

from __future__ import annotations


def main() -> None:
    from job_applyer.app import TerminalHireApp

    TerminalHireApp().run()


if __name__ == "__main__":
    main()
