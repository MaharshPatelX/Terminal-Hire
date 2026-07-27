"""Welcome / Home — Grok Build–style: logo → menu → prompt."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Static

from job_applyer.tui.logo import LOGO_COMPACT, LOGO_SMALL, TAGLINE
from job_applyer.tui.nav import MENU_ITEMS, SCREEN_HOTKEYS
from job_applyer.tui.screens.base import AppScreen


def _welcome_logo(width: int) -> str:
    # Full "TERMINAL HIRE" block needs ~90 cols; fall back on narrow terminals.
    return LOGO_SMALL if width >= 92 else LOGO_COMPACT


class MenuSelect(Message):
    """User picked a welcome menu row."""

    def __init__(self, screen_id: str) -> None:
        self.screen_id = screen_id
        super().__init__()


class MenuRow(Static):
    """One Grok-style menu row: label … shortcut."""

    def __init__(self, screen_id: str, label: str, shortcut: str, **kwargs) -> None:
        super().__init__(classes="menu-row", **kwargs)
        self.screen_id = screen_id
        self._label = label
        self._shortcut = shortcut

    def on_mount(self) -> None:
        pad = max(2, 36 - len(self._label))
        self.update(
            f"[bold]{self._label}[/]{' ' * pad}[dim]{self._shortcut}[/]"
        )

    def on_click(self) -> None:
        self.post_message(MenuSelect(self.screen_id))


class WelcomeScreen(AppScreen):
    """First screen — logo, shortcut menu, prompt (Grok welcome pattern)."""

    BINDINGS = [
        Binding("up", "menu_up", "Up", show=False),
        Binding("down", "menu_down", "Down", show=False),
        Binding("enter", "menu_enter", "Open", show=False),
    ]

    selected: reactive[int] = reactive(0)

    def body(self) -> ComposeResult:
        with Vertical(id="welcome-wrap"):
            yield Static(LOGO_COMPACT, id="logo")
            yield Static(TAGLINE, id="tagline")
            with Vertical(id="menu"):
                for sid, label, shortcut in MENU_ITEMS:
                    yield MenuRow(sid, label, shortcut, id=f"menu-{sid}")
            yield Input(
                placeholder="Type a command or press 1–6…  (/help)",
                id="welcome-prompt",
            )
            yield Static(
                "[dim]↑↓ select  ·  enter open  ·  esc home  ·  ctrl+q quit[/]",
                id="welcome-hint",
            )

    def on_mount(self) -> None:
        super().on_mount()
        self._sync_selection()
        logo = self.query_one("#logo", Static)
        logo.update(_welcome_logo(self.size.width or 80))
        prompt = self.query_one("#welcome-prompt", Input)
        prompt.can_focus = False
        if self.focused is prompt:
            self.set_focus(None)

    def on_resize(self) -> None:
        try:
            logo = self.query_one("#logo", Static)
        except Exception:
            return
        logo.update(_welcome_logo(self.size.width or 80))

    def on_click(self, event) -> None:  # noqa: ANN001
        # Clicking the prompt enables focus (Grok: click to type)
        if getattr(event.widget, "id", None) == "welcome-prompt":
            prompt = self.query_one("#welcome-prompt", Input)
            prompt.can_focus = True
            prompt.focus()

    def watch_selected(self, _value: int) -> None:
        self._sync_selection()

    def _sync_selection(self) -> None:
        rows = list(self.query(MenuRow))
        for i, row in enumerate(rows):
            row.set_class(i == self.selected, "-selected")

    def action_menu_up(self) -> None:
        prompt = self.query_one("#welcome-prompt", Input)
        if prompt.has_focus:
            return
        self.selected = (self.selected - 1) % len(MENU_ITEMS)

    def action_menu_down(self) -> None:
        prompt = self.query_one("#welcome-prompt", Input)
        if prompt.has_focus:
            return
        self.selected = (self.selected + 1) % len(MENU_ITEMS)

    def action_menu_enter(self) -> None:
        prompt = self.query_one("#welcome-prompt", Input)
        if prompt.has_focus:
            return
        sid = MENU_ITEMS[self.selected][0]
        self.post_message(MenuSelect(sid))

    def on_menu_select(self, message: MenuSelect) -> None:
        self.app.navigate(message.screen_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return
        if raw.startswith("/"):
            self.app.handle_slash(raw)
            return
        if raw in SCREEN_HOTKEYS:
            self.app.navigate(SCREEN_HOTKEYS[raw])
            return
        self.app.notify(f"Unknown command: {raw}", severity="warning")
