"""The preset browser for one layer: keys, the filter field, live preview, keep or revert.

Opening takes a snapshot of the layer's browse position. Moving the selection
onto a preset plays it on the layer after :data:`PREVIEW_DELAY_SEC`, through
the same path as stepping the preset row. Enter keeps the preset; Esc puts the
snapshot back. Opened to replace a preset list entry, it starts in that
entry's folder, and Enter also puts the chosen preset in the entry's place.
Inside Favourites, the New tag… row, F2 (rename) and Delete on a tag folder
hand off to :class:`TagActions`.

Listings build on a worker thread so the panel can show its spinner while a
large folder or a library-wide search is read. One listing runs at a time;
while it does, newer requests (each letter typed into the filter) wait, and
only the newest is built next.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pygame

from cleave.preset_library import PresetCollection, PresetLibrary
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.key_repeat import KeyRepeatController, mod_alt, mod_ctrl
from cleave.viz.layer_mutations import LayerMutations
from cleave.viz.preset_browser import (
    BrowserAction,
    BrowserOutcome,
    BrowserRow,
    BrowserRowKind,
    BrowserViewState,
    ListingRequest,
    PresetBrowser,
)
from cleave.viz.preset_browser_surface import BrowserPointerIntent, BrowserPointerKind
from cleave.viz.preset_list_controls import PresetListController
from cleave.viz.preset_switching import panel_layer_number
from cleave.viz.session import BrowseSnapshot, TuningSession
from cleave.viz.user_presets import preview_anchor

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
    pygame.K_F2: BrowserAction.RENAME,
    pygame.K_DELETE: BrowserAction.DELETE,
}
_REPEAT_ACTIONS = frozenset(
    {
        BrowserAction.MOVE_UP,
        BrowserAction.MOVE_DOWN,
        BrowserAction.PAGE_UP,
        BrowserAction.PAGE_DOWN,
    }
)
_EDIT_KEYS = frozenset({pygame.K_BACKSPACE, pygame.K_LEFT, pygame.K_RIGHT})
_FUNCTION_KEYS = frozenset(
    getattr(pygame, f"K_F{number}") for number in range(1, 16)
)
# Global keys the browser leaves alone while the filter is not being edited.
_GLOBAL_KEYS = frozenset({pygame.K_SPACE, pygame.K_h})


def browser_action_for(key: int) -> BrowserAction | None:
    return _KEY_ACTIONS.get(key)


def _passes_through(event: pygame.event.Event, *, editing: bool) -> bool:
    """Keys the browser leaves to the editor: shortcuts, F-keys, Space, H."""
    if mod_ctrl(event.mod) or mod_alt(event.mod):
        return True
    if event.key in _FUNCTION_KEYS and event.key not in _KEY_ACTIONS:
        return True
    return not editing and event.key in _GLOBAL_KEYS


class _ListingJob:
    """One listing built on a worker thread."""

    def __init__(self, browser: PresetBrowser, request: ListingRequest) -> None:
        self.browser = browser
        self.request = request
        self.rows: tuple[BrowserRow, ...] = ()
        self.done = threading.Event()
        threading.Thread(
            target=self._run, name="preset-browser-listing", daemon=True
        ).start()

    def _run(self) -> None:
        try:
            self.rows = self.browser.build(self.request)
        except Exception as exc:  # noqa: BLE001 - shown in the list, not raised
            self.rows = (
                BrowserRow(BrowserRowKind.NOTE, f"Could not list presets: {exc}"),
            )
        finally:
            self.done.set()


@dataclass(frozen=True)
class TagActions:
    """What the browser's tag rows and keys run: each opens a dialog."""

    new_tag: Callable[[], None]
    rename_tag: Callable[[str], None]
    delete_tag: Callable[[str], None]


class PresetBrowserControls:
    """Owns the open browser, its snapshot, listings, and the pending preview."""

    def __init__(
        self,
        session: TuningSession,
        preset_root: Path,
        library: PresetLibrary,
        layer_mutations: LayerMutations,
        *,
        preset_list: PresetListController | None = None,
        start_text_input: Callable[[], None],
        stop_text_input: Callable[[], None],
        text_input_shared: Callable[[], bool],
        tag_actions: TagActions | None = None,
        synchronous: bool = False,
    ) -> None:
        self._session = session
        self._preset_root = preset_root
        self._library = library
        self._mutations = layer_mutations
        self._preset_list = preset_list
        self._start_text_input = start_text_input
        self._stop_text_input = stop_text_input
        self._text_input_shared = text_input_shared
        self._tag_actions = tag_actions
        self._synchronous = synchronous
        self._repeat = KeyRepeatController()
        self._browser: PresetBrowser | None = None
        self._slot: str | None = None
        # The preset list entry Enter replaces, or None for a plain browse.
        self._replace_index: int | None = None
        self._on_choose: Callable[[Path], None] | None = None
        self._snapshot: BrowseSnapshot | None = None
        self._shown: Path | None = None
        self._pending: Path | None = None
        self._pending_sec = 0.0
        self._previewed = False
        self._revision = -1
        self._jobs: list[_ListingJob] = []
        self._text_input_on = False

    # -- state -------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._browser is not None

    @property
    def slot(self) -> str | None:
        return self._slot

    @property
    def replace_index(self) -> int | None:
        return self._replace_index

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
                and any(
                    path.name in (entry.file.name, entry.display_name)
                    for entry in layer.preset_list
                )
            )
            return self._library.marker(path, in_preset_list=in_list).strip()

        return marker

    # -- open / close ------------------------------------------------------

    def open(
        self,
        slot: str,
        *,
        replace_index: int | None = None,
        on_choose: Callable[[Path], None] | None = None,
        collection: PresetCollection | None = None,
    ) -> None:
        """Browse *slot*'s presets from the folder or collection it is on.

        With *replace_index*, start at that preset list entry's folder, and
        Enter replaces the entry with the chosen preset. *on_choose* runs with
        the preset Enter keeps. *collection* starts in that collection instead.
        """
        if slot not in self._session.layers:
            return
        if self._browser is not None:
            self.cancel()
        layer = self._session.layers[slot]
        playlist = layer.playlist
        number = panel_layer_number(self._session.layer_z_order, slot)
        title = f"Browse presets: Layer {number}"
        folder = playlist.current_dir
        select = playlist.current
        if collection is None:
            collection = playlist.collection
        elif collection != playlist.collection:
            select = None
        if replace_index is not None:
            if not 0 <= replace_index < len(layer.preset_list):
                return
            anchor = preview_anchor(layer.preset_list[replace_index])
            title = f"Replace preset {replace_index + 1}: Layer {number}"
            folder, collection, select = anchor.parent, None, anchor
        self._browser = PresetBrowser(
            preset_root=self._preset_root,
            catalog=playlist.catalog,
            title=title,
            folder=folder,
            collection=collection,
            select=select,
            marker=self._marker(slot),
            synchronous=self._synchronous,
        )
        self._slot = slot
        self._replace_index = replace_index
        self._on_choose = on_choose
        self._snapshot = self._mutations.browse_snapshot(slot)
        self._shown = playlist.current
        self._pending = None
        self._pending_sec = 0.0
        self._previewed = False
        self._revision = self._library.revision
        self._repeat.disarm()
        self._pump()

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
        """Keep the selected preset (playing it now if the preview was pending).

        In replace mode the preset also takes the entry's place in the list,
        and keeps playing as a preview.
        """
        browser = self._browser
        slot = self._slot
        replace_index = self._replace_index
        on_choose = self._on_choose
        path = browser.selected_preset() if browser is not None else None
        if path is not None and path != self._shown:
            self._show(path)
        self._close()
        if (
            path is not None
            and slot is not None
            and replace_index is not None
            and self._preset_list is not None
        ):
            self._preset_list.replace(slot, replace_index, path)
        elif path is not None and on_choose is not None:
            on_choose(path)

    def _close(self) -> None:
        self._browser = None
        self._slot = None
        self._replace_index = None
        self._on_choose = None
        self._snapshot = None
        self._pending = None
        self._jobs.clear()
        self._repeat.disarm()
        self._sync_text_input()

    def _sync_text_input(self) -> None:
        """Text input is on only while the filter field is being edited."""
        editing = self._browser is not None and self._browser.editing
        if editing and not self._text_input_on:
            self._text_input_on = True
            self._start_text_input()
        elif not editing and self._text_input_on:
            self._text_input_on = False
            # A dialog opened over the browser owns text input now.
            if not self._text_input_shared():
                self._stop_text_input()

    # -- listings ------------------------------------------------------------

    def _pump(self) -> None:
        """Start the browser's queued listing, and show any that finished."""
        browser = self._browser
        if browser is None:
            return
        delivered = False
        for job in [job for job in self._jobs if job.done.is_set()]:
            self._jobs.remove(job)
            if job.browser is browser and browser.deliver(job.request, job.rows):
                delivered = True
        if not self._jobs:
            request = browser.take_request()
            if request is not None:
                self._jobs.append(_ListingJob(browser, request))
        if delivered:
            self._after_change()

    def wait_for_listing(self, timeout_sec: float = 5.0) -> None:
        """Block until every queued listing is built and shown (tests)."""
        while self._jobs:
            for job in list(self._jobs):
                job.done.wait(timeout_sec)
            self._pump()

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
            return
        if outcome is BrowserOutcome.CANCEL:
            self.cancel()
            return
        self._run_tag_action(outcome)
        self._sync_text_input()
        self._pump()
        self._after_change()

    def _run_tag_action(self, outcome: BrowserOutcome) -> None:
        actions = self._tag_actions
        browser = self._browser
        if actions is None or browser is None:
            return
        tag = browser.selected_tag
        if outcome is BrowserOutcome.NEW_TAG:
            actions.new_tag()
        elif outcome is BrowserOutcome.RENAME_TAG and tag is not None:
            actions.rename_tag(tag)
        elif outcome is BrowserOutcome.DELETE_TAG and tag is not None:
            actions.delete_tag(tag)

    # -- input -------------------------------------------------------------

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Apply one key. False leaves it to the editor (shortcuts, Space, H)."""
        browser = self._browser
        if browser is None or event.type != pygame.KEYDOWN:
            return False
        if _passes_through(event, editing=browser.editing):
            return False
        if browser.editing:
            self._edit_keydown(browser, event)
            return True
        action = browser_action_for(event.key)
        if action is None:
            return True
        self._apply(browser.handle(action))
        if self._browser is not None and action in _REPEAT_ACTIONS:
            self._repeat.on_keydown(event.key, event.mod, on_repeat=self._on_repeat)
        return True

    def _edit_keydown(self, browser: PresetBrowser, event: pygame.event.Event) -> None:
        key = event.key
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_DOWN):
            browser.commit_edit()
        elif key == pygame.K_ESCAPE:
            browser.cancel_edit()
        elif key in (pygame.K_HOME, pygame.K_END):
            browser.caret_home(end=key == pygame.K_END)
        elif key in _EDIT_KEYS:
            browser.edit_key(key)
            self._pump()
            self._repeat.on_keydown(key, event.mod, on_repeat=self._on_edit_repeat)
            return
        else:
            # Characters arrive as text input; the key itself does nothing.
            return
        self._apply(BrowserOutcome.NONE)

    def handle_keyup(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            self._repeat.on_keyup(event.key)

    def handle_text_input(self, text: str) -> bool:
        browser = self._browser
        if browser is None or not browser.editing:
            return False
        browser.type_text(text)
        self._pump()
        return True

    def _on_repeat(self, key: int, _mod: int) -> None:
        browser = self._browser
        action = browser_action_for(key)
        if browser is None or browser.editing or action not in _REPEAT_ACTIONS:
            return
        self._apply(browser.handle(action))

    def _on_edit_repeat(self, key: int, _mod: int) -> None:
        browser = self._browser
        if browser is not None and browser.editing:
            browser.edit_key(key)
            self._pump()

    def apply_pointer(self, intent: BrowserPointerIntent | None) -> None:
        browser = self._browser
        if browser is None or intent is None:
            return
        kind = intent.kind
        if kind is BrowserPointerKind.CLOSE:
            self.commit()
            return
        if kind is BrowserPointerKind.EDIT_FILTER:
            if not browser.editing:
                browser.begin_edit()
            self._apply(BrowserOutcome.NONE)
            return
        # A click away from the field searches for what was typed.
        browser.commit_edit()
        if kind is BrowserPointerKind.SELECT_ROW and intent.index is not None:
            browser.select_row(intent.index)
            self._apply(BrowserOutcome.NONE)
        elif kind is BrowserPointerKind.OPEN_ROW and intent.index is not None:
            browser.select_row(intent.index)
            self._apply(browser.open_selected())
        elif kind is BrowserPointerKind.GOTO_CRUMB and intent.index is not None:
            browser.goto_crumb(intent.index)
            self._apply(BrowserOutcome.NONE)
        else:
            self._apply(BrowserOutcome.NONE)

    # -- per frame ---------------------------------------------------------

    def tick(self, dt_sec: float) -> None:
        browser = self._browser
        if browser is None:
            return
        if self._slot not in self._session.layers:
            self._close()
            return
        browser.tick(dt_sec)
        self._repeat.tick(dt_sec)
        if self._browser is None:
            return
        if self._library.revision != self._revision:
            self._revision = self._library.revision
            browser.refresh()
        self._pump()
        pending = self._pending
        if pending is None:
            return
        self._pending_sec += dt_sec
        if self._pending_sec >= PREVIEW_DELAY_SEC:
            self._show(pending)
