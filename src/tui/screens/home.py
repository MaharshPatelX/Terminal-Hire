"""TUI-Hire welcome workspace with dashboard navigation and a command composer."""

from __future__ import annotations

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Input, Static

from ... import __version__
from ..logo import BRAND, PROMPT_HINT, TAGLINE
from ..nav import MENU_ITEMS, SCREEN_HOTKEYS


class MenuSelect(Message):
    """User picked a welcome menu row."""

    def __init__(self, screen_id: str) -> None:
        self.screen_id = screen_id
        super().__init__()


class WelcomePrompt(Input):
    """Composer input that preserves empty-prompt numeric navigation."""

    def on_key(self, event: events.Key) -> None:
        if event.key in SCREEN_HOTKEYS and not self.value:
            event.prevent_default()
            event.stop()
            self.app.navigate(SCREEN_HOTKEYS[event.key])


class MenuRow(Horizontal):
    """Clickable launchpad row with a right-aligned shortcut."""

    def __init__(self, screen_id: str, label: str, shortcut: str, **kwargs) -> None:
        super().__init__(classes="menu-row", **kwargs)
        self.screen_id = screen_id
        self._label = label
        self._shortcut = shortcut

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="menu-label")
        yield Static(self._shortcut, classes="menu-key")

    def on_click(self) -> None:
        self.post_message(MenuSelect(self.screen_id))

    def set_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")
        prefix = "[bold #63e6be]>[/] " if selected else "  "
        self.query_one(".menu-label", Static).update(
            f"{prefix}[bold]{self._label}[/]" if selected else f"{prefix}{self._label}"
        )


class WelcomeScreen(Screen):
    """Full welcome workspace with launchpad, readiness, and composer."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("up", "menu_up", "Up", show=False, priority=True),
        Binding("down", "menu_down", "Down", show=False, priority=True),
        Binding("enter", "menu_enter", "Open", show=False),
    ]

    selected: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        with Horizontal(id="welcome-topbar"):
            yield Static(
                f"[bold #63e6be]{BRAND}[/] [dim]/ local workspace[/]",
                id="workspace-name",
            )
            yield Static("", id="workspace-runtime")

        with Vertical(id="welcome-main"), Horizontal(id="welcome-card"):
                with Vertical(id="identity-pane"):
                    yield Static(">_", id="brand-glyph")
                    yield Static(BRAND, id="brand-name")
                    yield Static("APPLICATION COPILOT", id="brand-kicker")
                    yield Static(TAGLINE, id="brand-copy")
                    yield Static(
                        "[bold #63e6be]LOCAL-FIRST[/]\n"
                        "[dim]PROFILE.md truth\nSupervised submit only[/]",
                        id="brand-policy",
                    )

                with Vertical(id="workspace-pane"):
                    yield Static("APPLICATION WORKSPACE", classes="eyebrow")
                    yield Static("Where should we start?", id="workspace-title")
                    yield Static(
                        "Move with arrows, press enter, or use the number keys.",
                        id="workspace-subtitle",
                    )

                    with Horizontal(id="workspace-grid"):
                        with Vertical(id="launchpad"):
                            yield Static("LAUNCHPAD", classes="section-label")
                            with Vertical(id="menu"):
                                for sid, label, shortcut in MENU_ITEMS:
                                    yield MenuRow(
                                        sid,
                                        label,
                                        shortcut,
                                        id=f"menu-{sid}",
                                    )

                        with Vertical(id="readiness"):
                            yield Static("READINESS", classes="section-label")
                            yield Static("", id="readiness-provider", classes="ready-row")
                            yield Static("", id="readiness-profile", classes="ready-row")
                            yield Static("", id="readiness-resume", classes="ready-row")
                            yield Static("", id="readiness-safety", classes="ready-row")
                            yield Static("", id="readiness-packs", classes="ready-row")

        with Vertical(id="composer-shell"):
            yield Static(
                "[dim]Tip:[/] [#63e6be]/profile[/] updates your truth; "
                "[#63e6be]/apply[/] starts an audited application.",
                id="composer-tip",
            )
            yield WelcomePrompt(placeholder=PROMPT_HINT, id="welcome-prompt")
            with Horizontal(id="composer-meta"):
                yield Static(
                    "[dim]enter[/] run   [dim]up/down[/] navigate   "
                    "[dim]esc[/] home   [dim]ctrl+q[/] quit",
                    id="composer-keys",
                )
                yield Static(
                    f"[#63e6be]{BRAND}[/] [dim]v{__version__}[/]",
                    id="composer-status",
                )

    def on_mount(self) -> None:
        self._set_responsive_classes()
        self._sync_selection()
        self._refresh_status()
        prompt = self.query_one("#welcome-prompt", Input)
        prompt.focus()

    def on_resize(self) -> None:
        self._set_responsive_classes()

    def _set_responsive_classes(self) -> None:
        self.set_class(self.size.width < 92, "-compact")
        self.set_class(self.size.height < 31, "-short")

    def _refresh_status(self) -> None:
        settings = self.app.settings
        provider = settings.llm_provider
        provider_color = "#63e6be" if provider != "off" else "#8b949e"
        submit = "enabled" if settings.application_submission_enabled else "locked"
        self.query_one("#workspace-runtime", Static).update(
            f"[dim]provider[/] [bold {provider_color}]{provider}[/]  "
            f"[dim]· submit[/] [bold #63e6be]{submit}[/]"
        )
        self.query_one("#readiness-provider", Static).update(
            f"[{provider_color}]●[/]  LLM      [bold]{provider}[/]"
        )
        profile = self.app.profile_service.load_or_new()
        profile_state = "verified" if profile.is_ready else "needs review"
        profile_color = "#63e6be" if profile.is_ready else "#d29922"
        self.query_one("#readiness-profile", Static).update(
            f"[{profile_color}]●[/]  Profile  [bold]{profile_state}[/]"
        )
        active_documents = sum(document.active for document in profile.documents)
        self.query_one("#readiness-resume", Static).update(
            f"[#8b949e]○[/]  Docs     [dim]{active_documents} active[/]"
        )
        self.query_one("#readiness-safety", Static).update(
            f"[#63e6be]●[/]  Submit   [bold]{submit}[/]"
        )
        packs = getattr(self.app, "enabled_packs", "none")
        self.query_one("#readiness-packs", Static).update(
            f"[#8b949e]○[/]  Packs    [dim]{packs}[/]"
        )

    def watch_selected(self, _value: int) -> None:
        self._sync_selection()

    def _sync_selection(self) -> None:
        rows = list(self.query(MenuRow))
        for i, row in enumerate(rows):
            row.set_selected(i == self.selected)

    def action_menu_up(self) -> None:
        prompt = self.query_one("#welcome-prompt", Input)
        if prompt.has_focus and prompt.value:
            return
        self.selected = (self.selected - 1) % len(MENU_ITEMS)

    def action_menu_down(self) -> None:
        prompt = self.query_one("#welcome-prompt", Input)
        if prompt.has_focus and prompt.value:
            return
        self.selected = (self.selected + 1) % len(MENU_ITEMS)

    def action_menu_enter(self) -> None:
        prompt = self.query_one("#welcome-prompt", Input)
        if prompt.has_focus and prompt.value:
            return
        self.post_message(MenuSelect(MENU_ITEMS[self.selected][0]))

    def on_menu_select(self, message: MenuSelect) -> None:
        self.app.navigate(message.screen_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            self.post_message(MenuSelect(MENU_ITEMS[self.selected][0]))
            return
        if raw.startswith("/"):
            self.app.handle_slash(raw)
            return
        if raw in SCREEN_HOTKEYS:
            self.app.navigate(SCREEN_HOTKEYS[raw])
            return
        self.app.notify(
            "Use /profile, /apply, /apps, or /settings.",
            title=BRAND,
            severity="information",
        )
