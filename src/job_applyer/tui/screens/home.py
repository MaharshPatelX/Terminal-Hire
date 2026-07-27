"""Welcome / Home — Grok Build–style: logo → menu → prompt."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Input, Static

from job_applyer.tui.logo import LOGO_SMALL, TAGLINE
from job_applyer.tui.nav import MENU_ITEMS, SCREEN_HOTKEYS


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
        self.update(
            f"[bold]{self._label}[/]"
            f"{' ' * max(2, 40 - len(self._label))}"
            f"[dim]{self._shortcut}[/]"
        )

    def on_click(self) -> None:
        self.post_message(MenuSelect(self.screen_id))


class WelcomeScreen(Screen):
    """First screen — logo, shortcut menu, prompt (Grok welcome pattern)."""

    BINDINGS = [
        Binding("up", "menu_up", "Up", show=False),
        Binding("down", "menu_down", "Down", show=False),
        Binding("enter", "menu_enter", "Open", show=False),
        Binding("escape", "blur_prompt", "Blur", show=False),
    ]

    selected: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-wrap"):
            yield Static(LOGO_SMALL, id="logo")
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
        self._sync_selection()

    def watch_selected(self, _value: int) -> None:
        self._sync_selection()

    def _sync_selection(self) -> None:
        rows = list(self.query(MenuRow))
        for i, row in enumerate(rows):
            row.set_class(i == self.selected, "-selected")

    def action_menu_up(self) -> None:
        if self.query_one("#welcome-prompt", Input).has_focus:
            return
        self.selected = (self.selected - 1) % len(MENU_ITEMS)

    def action_menu_down(self) -> None:
        if self.query_one("#welcome-prompt", Input).has_focus:
            return
        self.selected = (self.selected + 1) % len(MENU_ITEMS)

    def action_menu_enter(self) -> None:
        if self.query_one("#welcome-prompt", Input).has_focus:
            return
        sid = MENU_ITEMS[self.selected][0]
        self.post_message(MenuSelect(sid))

    def action_blur_prompt(self) -> None:
        prompt = self.query_one("#welcome-prompt", Input)
        if prompt.has_focus:
            self.set_focus(None)

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
        # bare number or screen name
        if raw in SCREEN_HOTKEYS:
            self.app.navigate(SCREEN_HOTKEYS[raw])
            return
        self.app.notify(f"Unknown command: {raw}", severity="warning")
