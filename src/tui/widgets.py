"""Shared top-bar, status, and shortcut-hint widgets."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from .logo import BRAND


class TopBar(Static):
    """Display the product brand and current version."""

    DEFAULT_CSS = """
    TopBar {
        height: 1;
        width: 100%;
    }
    """

    def __init__(self, version: str = "0.1.0", **kwargs) -> None:
        super().__init__(id="top-bar", **kwargs)
        self._version = version

    def on_mount(self) -> None:
        self.update(
            f"[bold]{BRAND}[/]  [dim]local[/]                  [dim]v{self._version}[/]"
        )


class StatusStrip(Static):
    """LLM · dry-run · packs strip under the top bar."""

    provider: reactive[str] = reactive("lmstudio")
    dry_run: reactive[bool] = reactive(True)
    submit_enabled: reactive[bool] = reactive(False)
    packs: reactive[str] = reactive("none")

    def __init__(self, **kwargs) -> None:
        super().__init__(id="status-strip", **kwargs)

    def watch_provider(self, _value: str) -> None:
        self._refresh()

    def watch_dry_run(self, _value: bool) -> None:
        self._refresh()

    def watch_submit_enabled(self, _value: bool) -> None:
        self._refresh()

    def watch_packs(self, _value: str) -> None:
        self._refresh()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        dry = "[green]ON[/]" if self.dry_run else "[yellow]OFF[/]"
        submit = "[dim]locked[/]" if not self.submit_enabled else "[red]ENABLED[/]"
        self.update(
            f"LLM=[cyan]{self.provider}[/]  ·  "
            f"Dry-run {dry}  ·  "
            f"Submit {submit}  ·  "
            f"Packs: [dim]{self.packs}[/]"
        )


class FooterHints(Static):
    """Display the bottom shortcut legend."""

    def __init__(self, hints: str | None = None, **kwargs) -> None:
        super().__init__(id="footer-hints", **kwargs)
        self._hints = hints or (
            "[bold cyan]1-4[/] screens  "
            "[bold cyan]esc[/] home  "
            "[bold cyan]ctrl+q[/] quit  "
            "[bold cyan]/[/] command"
        )

    def on_mount(self) -> None:
        self.update(self._hints)

    def set_hints(self, hints: str) -> None:
        self._hints = hints
        self.update(hints)
