"""Entry point: ``python -m job_applyer`` or ``job-applyer``."""

from __future__ import annotations


def main() -> None:
    from job_applyer.app import JobApplyerApp

    JobApplyerApp().run()


if __name__ == "__main__":
    main()
