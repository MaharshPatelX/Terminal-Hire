"""Welcome / Home — Grok Build–style hero box + prompt."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Input, Static

from job_applyer import __version__
from job_applyer.tui.logo import (
    BRAND,
    HERO_BLURB,
    HERO_LOGO,
    TIP,
    hero_title_line,
)
from job_applyer.tui.nav import MENU_ITEMS, SCREEN_HOTKEYS


class MenuSelect(Message):
    """User picked a welcome menu row."""

    def __init__(self, screen_id: str) -> None:
        self.screen_id = screen_id
        super().__init__()


class MenuRow(Static):
    """Grok-style menu row: label left, shortcut right."""

    def __init__(self, screen_id: str, label: str, shortcut: str, **kwargs) -> None:
        super().__init__(classes="menu-row", **kwargs)
        self.screen_id = screen_id
        self._label = label
        self._shortcut = shortcut

    def on_mount(self) -> None:
        self.update(
            f"[bold]{self._label}[/]"
            f"{' ' * max(2, 28 - len(self._label))}"
            f"[dim]{self._shortcut}[/]"
        )

    def on_click(self) -> None:
        self.post_message(MenuSelect(self.screen_id))


class WelcomeScreen(Screen):
    """Grok-like welcome: centered hero (logo | title+menu) + tip + prompt."""

    BINDINGS = [
        Binding("up", "menu_up", "Up", show=False),
        Binding("down", "menu_down", "Down", show=False),
        Binding("enter", "menu_enter", "Open", show=False),
    ]

    selected: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-stack"):
            with Horizontal(id="hero-box"):
                yield Static(HERO_LOGO, id="hero-logo")
                with Vertical(id="hero-right"):
                    yield Static(hero_title_line(), id="hero-title", markup=True)
                    yield Static(HERO_BLURB, id="hero-blurb")
                    with Vertical(id="menu"):
                        for sid, label, shortcut in MENU_ITEMS:
                            yield MenuRow(sid, label, shortcut, id=f"menu-{sid}")
            yield Static(TIP, id="welcome-tip")
            yield Input(placeholder="", id="welcome-prompt")
            yield Static(
                f"[dim]{BRAND}[/]                                    "
                f"[dim][{__version__}][/]",
                id="welcome-foot",
            )

    def on_mount(self) -> None:
        self._sync_selection()
        prompt = self.query_one("#welcome-prompt", Input)
        # Grok-style: prompt visible but digits still navigate until you type
        prompt.placeholder = ">  ask or press 1-6…"
        prompt.can_focus = False
        self.set_focus(None)

    def on_click(self, event) -> None:  # noqa: ANN001
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
        self.post_message(MenuSelect(MENU_ITEMS[self.selected][0]))

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
