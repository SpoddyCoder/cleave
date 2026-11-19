"""The preset browser for one layer: keys, typed filter, live preview, keep or revert.

Opening takes a snapshot of the layer's browse position. Moving the selection
onto a preset plays it on the layer after :data:`PREVIEW_DELAY_SEC`, through
the same path as stepping the preset row. Enter keeps the preset; Esc puts the
snapshot back.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pygame

from cleave.preset_library import PresetLibrary
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.key_repeat import KeyRepeatController, mod_alt, mod_ctrl
from cleave.viz.layer_mutations import BrowseSnapshot, LayerMutations
from cleave.viz.preset_browser import (
    BrowserAction,
    BrowserOutcome,
    BrowserViewState,
    PresetBrowser,
)
from cleave.viz.preset_browser_surface import BrowserPointerIntent, BrowserPointerKind
from cleave.viz.preset_switching import panel_layer_number
from cleave.viz.session import TuningSession

PREVIEW_DELAY_SEC = 0.15

_KEY_ACTIONS: dict[int, BrowserAction] = {
    pygame.K_UP: BrowserAction.MOVE_UP,
    pygame.K_DOWN: BrowserAction.MOVE_DOWN,
    pygame.K_PAGEUP: BrowserAction.PAGE_UP,
    pygame.K_PAGEDOWN: BrowserAction.PAGE_DOWN,
    pygame.K_HOME: BrowserAction.HOME,
    pygame.K_END: BrowserAction.END,
    pygame.K_RETURN: BrowserAction.OPEN,
    pygame.K_KP_ENTER: BrowserAction.OPEN,
    pygame.K_RIGHT: BrowserAction.ENTER_FOLDER,
    pygame.K_LEFT: BrowserAction.PARENT,
    pygame.K_BACKSPACE: BrowserAction.BACKSPACE,
    pygame.K_ESCAPE: BrowserAction.CANCEL,
}
_REPEAT_ACTIONS = frozenset(
    {
        BrowserAction.MOVE_UP,
        BrowserAction.MOVE_DOWN,
        BrowserAction.PAGE_UP,
        BrowserAction.PAGE_DOWN,
        BrowserAction.BACKSPACE,
    }
)


_FUNCTION_KEYS = frozenset(
    getattr(pygame, f"K_F{number}") for number in range(1, 16)
)


def browser_action_for(key: int) -> BrowserAction | None:
    return _KEY_ACTIONS.get(key)


def _passes_through(event: pygame.event.Event, filter_text: str) -> bool:
    """Keys the browser leaves to the editor: shortcuts, F-keys, idle Space."""
    if mod_ctrl(event.mod) or mod_alt(event.mod):
        return True
    if event.key in _FUNCTION_KEYS:
        return True
    return event.key == pygame.K_SPACE and not filter_text


class PresetBrowserControls:
    """Owns the open browser, its snapshot, and the pending preview."""

    def __init__(
        self,
        session: TuningSession,
        preset_root: Path,
        library: PresetLibrary,
        layer_mutations: LayerMutations,
        *,
        start_text_input: Callable[[], None],
        stop_text_input: Callable[[], None],
        text_input_shared: Callable[[], bool],
    ) -> None:
        self._session = session
        self._preset_root = preset_root
        self._library = library
        self._mutations = layer_mutations
        self._start_text_input = start_text_input
        self._stop_text_input = stop_text_input
        self._text_input_shared = text_input_shared
        self._repeat = KeyRepeatController()
        self._browser: PresetBrowser | None = None
        self._slot: str | None = None
        self._snapshot: BrowseSnapshot | None = None
        self._shown: Path | None = None
        self._pending: Path | None = None
        self._pending_sec = 0.0
        self._previewed = False
        self._revision = -1

    # -- state -------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._browser is not None

    @property
    def slot(self) -> str | None:
        return self._slot

    @property
    def key_repeat_armed(self) -> bool:
        return self._repeat.is_armed

    @property
    def browser(self) -> PresetBrowser | None:
        return self._browser

    def view_state(self) -> BrowserViewState | None:
        if self._browser is None:
            return None
        return self._browser.view_state()

    def _marker(self, slot: str) -> Callable[[Path], str]:
        def marker(path: Path) -> str:
            layer = self._session.layers.get(slot)
            in_list = (
                layer is not None
                and not is_preset_curation_mode(self._session.settings.editor_mode)
                and any(Path(entry).name == path.name for entry in layer.preset_list)
            )
            return self._library.marker(path, in_preset_list=in_list).strip()

        return marker

    # -- open / close ------------------------------------------------------

    def open(self, slot: str) -> None:
        """Browse *slot*'s presets from the folder or collection it is on."""
        if slot not in self._session.layers:
            return
        if self._browser is not None:
            self.cancel()
        layer = self._session.layers[slot]
        playlist = layer.playlist
        number = panel_layer_number(self._session.layer_z_order, slot)
        self._browser = PresetBrowser(
            preset_root=self._preset_root,
            catalog=playlist.catalog,
            title=f"Browse presets: Layer {number}",
            folder=playlist.current_dir,
            collection=playlist.collection,
            select=playlist.current,
            marker=self._marker(slot),
        )
        self._slot = slot
        self._snapshot = self._mutations.browse_snapshot(slot)
        self._shown = playlist.current
        self._pending = None
        self._pending_sec = 0.0
        self._previewed = False
        self._revision = self._library.revision
        self._repeat.disarm()
        self._start_text_input()

    def cancel(self) -> None:
        """Close and put back the folder and preset the layer had on opening."""
        slot = self._slot
        snapshot = self._snapshot
        if (
            slot is not None
            and snapshot is not None
            and self._previewed
            and slot in self._session.layers
        ):
            self._mutations.restore_browse(slot, snapshot)
        self._close()

    def commit(self) -> None:
        """Keep the selected preset (playing it now if the preview was pending)."""
        browser = self._browser
        if browser is not None:
            path = browser.selected_preset()
            if path is not None and path != self._shown:
                self._show(path)
        self._close()

    def _close(self) -> None:
        self._browser = None
        self._slot = None
        self._snapshot = None
        self._pending = None
        self._repeat.disarm()
        # A dialog opened over the browser owns text input now.
        if not self._text_input_shared():
            self._stop_text_input()

    # -- preview -----------------------------------------------------------

    def _show(self, path: Path) -> None:
        browser = self._browser
        slot = self._slot
        if browser is None or slot is None:
            return
        self._mutations.browse_to_preset(slot, path, collection=browser.collection)
        self._shown = path
        self._pending = None
        self._previewed = True

    def _after_change(self) -> None:
        browser = self._browser
        if browser is None:
            return
        path = browser.selected_preset()
        if path is None or path == self._shown:
            self._pending = None
            return
        if path != self._pending:
            self._pending = path
            self._pending_sec = 0.0

    def _apply(self, outcome: BrowserOutcome) -> None:
        if outcome is BrowserOutcome.COMMIT:
            self.commit()
        elif outcome is BrowserOutcome.CANCEL:
            self.cancel()
        else:
            self._after_change()

    # -- input -------------------------------------------------------------

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Apply one key. False leaves it to the editor (shortcuts, idle Space)."""
        browser = self._browser
        if browser is None or event.type != pygame.KEYDOWN:
            return False
        if _passes_through(event, browser.filter_text):
            return False
        action = browser_action_for(event.key)
        if action is None:
            # Letters and digits arrive as text input; the key is swallowed so
            # editor hotkeys do not fire while typing a filter.
            return True
        self._apply(browser.handle(action))
        if self._browser is not None and action in _REPEAT_ACTIONS:
            self._repeat.on_keydown(event.key, event.mod, on_repeat=self._on_repeat)
        return True

    def handle_keyup(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            self._repeat.on_keyup(event.key)

    def handle_text_input(self, text: str) -> bool:
        browser = self._browser
        if browser is None:
            return False
        browser.type_text(text)
        self._after_change()
        return True

    def _on_repeat(self, key: int, _mod: int) -> None:
        browser = self._browser
        action = browser_action_for(key)
        if browser is None or action not in _REPEAT_ACTIONS:
            return
        self._apply(browser.handle(action))

    def apply_pointer(self, intent: BrowserPointerIntent | None) -> None:
        browser = self._browser
        if browser is None or intent is None:
            return
        kind = intent.kind
        if kind is BrowserPointerKind.SELECT_ROW and intent.index is not None:
            browser.select_row(intent.index)
            self._after_change()
        elif kind is BrowserPointerKind.OPEN_ROW and intent.index is not None:
            browser.select_row(intent.index)
            self._apply(browser.open_selected())
        elif kind is BrowserPointerKind.GOTO_CRUMB and intent.index is not None:
            browser.goto_crumb(intent.index)
            self._after_change()

    # -- per frame ---------------------------------------------------------

    def tick(self, dt_sec: float) -> None:
        browser = self._browser
        if browser is None:
            return
        if self._slot not in self._session.layers:
            self._close()
            return
        self._repeat.tick(dt_sec)
        if self._browser is None:
            return
        if self._library.revision != self._revision:
            self._revision = self._library.revision
            browser.refresh()
            self._after_change()
        pending = self._pending
        if pending is None:
            return
        self._pending_sec += dt_sec
        if self._pending_sec >= PREVIEW_DELAY_SEC:
            self._show(pending)
