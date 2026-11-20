"""Preset browser state: one layer's folders, collections, and presets.

Pure state and view state: no pygame or ImGui import. The controller maps keys
onto :class:`BrowserAction` and the filter's edit methods, previews
:meth:`PresetBrowser.selected_preset` on the layer, and draws
:meth:`PresetBrowser.view_state`.

The list is MilkDrop style: ``..``, then (at the top level) the library
collections, then subfolders with their preset counts, then presets. The
filter is a field above the list: Up from the first row highlights it, and
Enter or a click edits it. While it is being edited the list follows every
change, searching every preset under the folder being shown, matched on its
path below that folder; leaving the field keeps that search.

Listing a large folder or filtering the whole library takes a moment, so a
browser built with ``synchronous=False`` only queues a :class:`ListingRequest`;
the controller runs :meth:`PresetBrowser.build` on a worker and hands the rows
back with :meth:`PresetBrowser.deliver`. ``loading`` is true in between.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from cleave.preset_library import COLLECTION_LABEL, PresetCatalog, PresetCollection
from cleave.preset_playlist import list_navigable_dirs, milk_files_in_dir
from cleave.viz.text_edit import (
    apply_text_edit_key,
    insert_text_at_caret,
    reset_caret_blink,
    text_caret_visible,
)

ROOT_LABEL = "presets"
PARENT_LABEL = ".."
FILTER_PLACEHOLDER = "Enter or click to filter"
MAX_ROWS = 512
PAGE_SIZE = 12


def browser_legend(*, editing: bool) -> tuple[tuple[str, str], ...]:
    """Key hints under the list."""
    if editing:
        return (("Enter", "done"), ("Esc", "cancel"))
    return (
        ("Enter", "open / keep"),
        ("Left", "parent"),
        ("Esc", "go back"),
    )


class BrowserAction(Enum):
    """Payload-free browser commands the controller can issue."""

    MOVE_UP = "move-up"
    MOVE_DOWN = "move-down"
    PAGE_UP = "page-up"
    PAGE_DOWN = "page-down"
    HOME = "home"
    END = "end"
    OPEN = "open"
    ENTER_FOLDER = "enter-folder"
    PARENT = "parent"
    BACKSPACE = "backspace"
    CANCEL = "cancel"


class BrowserRowKind(Enum):
    """What a listed row points at."""

    PARENT = "parent"
    COLLECTION = "collection"
    FOLDER = "folder"
    PRESET = "preset"
    NOTE = "note"


class BrowserOutcome(Enum):
    """What an action asks the controller to do with the layer."""

    NONE = "none"
    COMMIT = "commit"
    CANCEL = "cancel"


class BrowserFocus(Enum):
    """Where the keys act: the filter field or the list."""

    FILTER = "filter"
    LIST = "list"


@dataclass(frozen=True)
class BrowserRow:
    """One row in the current listing. ``detail`` sits after the label."""

    kind: BrowserRowKind
    label: str
    detail: str = ""
    path: Path | None = None
    collection: PresetCollection | None = None


@dataclass(frozen=True)
class BrowserCrumb:
    """One breadcrumb segment: a folder, or the collection being shown."""

    label: str
    path: Path | None = None


@dataclass(frozen=True)
class ListingRequest:
    """One listing to build. Only the newest request's rows are kept."""

    serial: int
    folder: Path
    collection: PresetCollection | None
    filter_text: str
    keep: Path | None = None
    keep_collection: PresetCollection | None = None


@dataclass(frozen=True)
class BrowserViewState:
    """Everything the surface needs to draw the browser."""

    title: str
    crumbs: tuple[BrowserCrumb, ...]
    filter_text: str
    rows: tuple[BrowserRow, ...]
    selected_index: int
    legend: tuple[tuple[str, str], ...]
    location_key: str
    focus: BrowserFocus = BrowserFocus.LIST
    editing: bool = False
    draft: str = ""
    caret_index: int = 0
    caret_visible: bool = False
    loading: bool = False


def preset_count_text(count: int) -> str:
    return "1 preset" if count == 1 else f"{count:,} presets"


def _sort_key(path: Path) -> str:
    return path.name.casefold()


def _first_entry_index(rows: tuple[BrowserRow, ...]) -> int:
    """The first collection, folder, or preset: not ``..`` or a note."""
    for index, row in enumerate(rows):
        if row.kind not in (BrowserRowKind.PARENT, BrowserRowKind.NOTE):
            return index
    return 0


def filter_terms(text: str) -> tuple[str, ...]:
    """Case-folded, space-separated terms; every one must match."""
    return tuple(text.casefold().split())


def matches_terms(label: str, terms: tuple[str, ...]) -> bool:
    folded = label.casefold()
    return all(term in folded for term in terms)


def _relative_label(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


@dataclass(frozen=True)
class PresetLister:
    """Builds rows for a folder, collection, and filter. Safe on a worker thread."""

    preset_root: Path
    catalog: PresetCatalog
    marker: Callable[[Path], str]

    def rows(
        self,
        folder: Path,
        collection: PresetCollection | None,
        filter_text: str,
    ) -> tuple[BrowserRow, ...]:
        if filter_text.strip():
            return self._filtered(folder, collection, filter_text)
        return self._listing(folder, collection)

    def _child_folders(self, folder: Path) -> tuple[tuple[Path, int], ...]:
        """Subfolders that hold visible presets, with how many, by name."""
        counts = self.catalog.preset_counts_by_dir()
        if counts:
            try:
                children = [
                    child
                    for child in folder.iterdir()
                    if child.is_dir()
                    and not child.name.startswith(".")
                    and counts.get(child.resolve(), 0) > 0
                ]
            except OSError:
                return ()
            return tuple(
                (child.resolve(), counts[child.resolve()])
                for child in sorted(children, key=_sort_key)
            )
        return tuple(
            (child.resolve(), len(self.catalog.visible(child.rglob("*.milk"))))
            for child in sorted(list_navigable_dirs(folder), key=_sort_key)
        )

    def _presets_below(self, folder: Path) -> tuple[Path, ...]:
        """Every preset under *folder*, sorted by path (blacklist not applied)."""
        indexed = self.catalog.indexed_paths()
        if indexed:
            prefix = os.path.join(str(folder), "")
            return tuple(path for path in indexed if str(path).startswith(prefix))
        return tuple(sorted(p.resolve() for p in folder.rglob("*.milk")))

    def _preset_row(self, path: Path, label: str) -> BrowserRow:
        return BrowserRow(
            BrowserRowKind.PRESET, label, detail=self.marker(path), path=path
        )

    def _listing(
        self, folder: Path, collection: PresetCollection | None
    ) -> tuple[BrowserRow, ...]:
        at_top = collection is None and folder == self.preset_root
        rows: list[BrowserRow] = []
        if not at_top:
            rows.append(BrowserRow(BrowserRowKind.PARENT, PARENT_LABEL))
        if collection is not None:
            presets = tuple(
                self._preset_row(path, _relative_label(path, self.preset_root))
                for path in self.catalog.collection_paths(collection)
            )
            if not presets:
                rows.append(
                    BrowserRow(BrowserRowKind.NOTE, "No presets in this collection")
                )
            return (*rows, *presets)
        if at_top:
            for entry in self.catalog.collections():
                rows.append(
                    BrowserRow(
                        BrowserRowKind.COLLECTION,
                        COLLECTION_LABEL[entry],
                        collection=entry,
                    )
                )
        for child, count in self._child_folders(folder):
            rows.append(
                BrowserRow(
                    BrowserRowKind.FOLDER,
                    child.name,
                    detail=preset_count_text(count),
                    path=child,
                )
            )
        presets = self.catalog.visible(p.resolve() for p in milk_files_in_dir(folder))
        rows.extend(self._preset_row(path, path.name) for path in presets)
        if all(row.kind is BrowserRowKind.PARENT for row in rows):
            rows.append(BrowserRow(BrowserRowKind.NOTE, "No presets here"))
        return tuple(rows)

    def _filtered(
        self,
        folder: Path,
        collection: PresetCollection | None,
        filter_text: str,
    ) -> tuple[BrowserRow, ...]:
        terms = filter_terms(filter_text)
        if collection is not None:
            base = self.preset_root
            candidates = self.catalog.collection_paths(collection)
        else:
            base = folder
            candidates = self._presets_below(folder)
        prefix = os.path.join(str(base), "")
        cut = len(prefix)
        labelled = [
            (
                path,
                text[cut:].replace(os.sep, "/")
                if (text := str(path)).startswith(prefix)
                else path.name,
            )
            for path in candidates
        ]
        matched = [(p, label) for p, label in labelled if matches_terms(label, terms)]
        if collection is None:
            visible = set(self.catalog.visible(p for p, _label in matched))
            matched = [(p, label) for p, label in matched if p in visible]
        if not matched:
            return (BrowserRow(BrowserRowKind.NOTE, "No presets match"),)
        rows = [self._preset_row(p, label) for p, label in matched[:MAX_ROWS]]
        if len(matched) > MAX_ROWS:
            rows.append(
                BrowserRow(
                    BrowserRowKind.NOTE,
                    f"Showing the first {MAX_ROWS:,} of {len(matched):,} matches",
                )
            )
        return tuple(rows)


@dataclass
class PresetBrowser:
    """Browse one layer's presets from *preset_root* down.

    ``folder`` is the folder listed, or the folder a collection was entered
    from while ``collection`` is set. ``marker`` returns a preset's curation
    tags (``"[F] [L]"``), as on the preset row. ``filter_text`` is the search
    applied to the list; ``draft`` is the field's text while ``editing``.
    """

    preset_root: Path
    catalog: PresetCatalog
    title: str = "Browse presets"
    folder: Path | None = None
    collection: PresetCollection | None = None
    select: Path | None = None
    marker: Callable[[Path], str] = field(default=lambda _path: "", repr=False)
    synchronous: bool = True
    filter_text: str = ""
    selected_index: int = 0
    focus: BrowserFocus = BrowserFocus.LIST
    editing: bool = False
    draft: str = ""
    caret_index: int = 0
    error: str | None = None
    caret_blink_sec: float = 0.0
    loading: bool = False
    _filter_before_edit: str = field(default="", repr=False)
    _rows: tuple[BrowserRow, ...] = field(default_factory=tuple, repr=False)
    _serial: int = field(default=0, repr=False)
    _pending: ListingRequest | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.preset_root = self.preset_root.resolve()
        folder = (self.folder or self.preset_root).resolve()
        if not self._within_root(folder):
            folder = self.preset_root
        self.folder = folder
        self._request(keep=self.select)

    # -- listing -----------------------------------------------------------

    def _within_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.preset_root)
        except ValueError:
            return False
        return True

    @property
    def at_top(self) -> bool:
        """True at the preset root, where the collections are listed."""
        return self.collection is None and self.folder == self.preset_root

    @property
    def lister(self) -> PresetLister:
        return PresetLister(self.preset_root, self.catalog, self.marker)

    def build(self, request: ListingRequest) -> tuple[BrowserRow, ...]:
        """Rows for *request*. Reads no browser state, so a worker may call it."""
        return self.lister.rows(request.folder, request.collection, request.filter_text)

    def _request(
        self,
        *,
        keep: Path | None = None,
        keep_collection: PresetCollection | None = None,
    ) -> None:
        assert self.folder is not None
        self._serial += 1
        request = ListingRequest(
            serial=self._serial,
            folder=self.folder,
            collection=self.collection,
            filter_text=self.filter_text,
            keep=keep,
            keep_collection=keep_collection,
        )
        if self.synchronous:
            self.deliver(request, self.build(request))
            return
        self._pending = request
        self.loading = True

    def take_request(self) -> ListingRequest | None:
        """The listing to build next, once; None when nothing is queued."""
        request = self._pending
        self._pending = None
        return request

    def deliver(self, request: ListingRequest, rows: tuple[BrowserRow, ...]) -> bool:
        """Show *rows* for *request*. False (and ignored) when a newer one is queued."""
        if request.serial != self._serial:
            return False
        self._rows = rows
        self.loading = False
        self.selected_index = _first_entry_index(rows)
        for index, row in enumerate(rows):
            if (request.keep is not None and row.path == request.keep) or (
                request.keep_collection is not None
                and row.collection == request.keep_collection
            ):
                self.selected_index = index
                break
        return True

    def refresh(self) -> None:
        """Re-list after curation changes, keeping the selected row."""
        row = self.selected_row
        self._request(
            keep=row.path if row is not None else None,
            keep_collection=row.collection if row is not None else None,
        )

    # -- reads -------------------------------------------------------------

    @property
    def rows(self) -> tuple[BrowserRow, ...]:
        return self._rows

    @property
    def selected_row(self) -> BrowserRow | None:
        if not self._rows:
            return None
        return self._rows[self.selected_index]

    def selected_preset(self) -> Path | None:
        """The preset row the list has selected; None while loading or on the filter."""
        if self.loading or self.focus is not BrowserFocus.LIST:
            return None
        row = self.selected_row
        if row is None or row.kind is not BrowserRowKind.PRESET:
            return None
        return row.path

    def crumbs(self) -> tuple[BrowserCrumb, ...]:
        assert self.folder is not None
        out = [BrowserCrumb(ROOT_LABEL, self.preset_root)]
        if self.collection is not None:
            out.append(BrowserCrumb(COLLECTION_LABEL[self.collection]))
            return tuple(out)
        path = self.preset_root
        for part in self.folder.relative_to(self.preset_root).parts:
            path = path / part
            out.append(BrowserCrumb(part, path))
        return tuple(out)

    def view_state(self) -> BrowserViewState:
        location = (
            f"collection:{self.collection}"
            if self.collection is not None
            else str(self.folder)
        )
        return BrowserViewState(
            title=self.title,
            crumbs=self.crumbs(),
            filter_text=self.filter_text,
            rows=self._rows,
            selected_index=self.selected_index,
            legend=browser_legend(editing=self.editing),
            location_key=f"{location}?{self.filter_text}#{self._serial}",
            focus=self.focus,
            editing=self.editing,
            draft=self.draft,
            caret_index=self.caret_index,
            caret_visible=text_caret_visible(self),
            loading=self.loading,
        )

    # -- list actions --------------------------------------------------------

    def handle(self, action: BrowserAction) -> BrowserOutcome:
        """Apply *action*. COMMIT keeps the selected preset; CANCEL reverts.

        While a listing loads, only moves to and from the filter, the parent
        folder, and Esc act: the rows on screen are about to change.
        """
        on_filter = self.focus is BrowserFocus.FILTER
        if action is BrowserAction.MOVE_UP:
            if on_filter:
                return BrowserOutcome.NONE
            if self.loading or self.selected_index <= 0:
                self.focus = BrowserFocus.FILTER
            else:
                self._move(-1)
        elif action is BrowserAction.MOVE_DOWN:
            if on_filter:
                self.focus = BrowserFocus.LIST
            elif not self.loading:
                self._move(1)
        elif action is BrowserAction.OPEN:
            if on_filter:
                self.begin_edit()
            elif not self.loading:
                return self.open_selected()
        elif action is BrowserAction.PARENT or action is BrowserAction.BACKSPACE:
            self.go_parent()
        elif action is BrowserAction.CANCEL:
            if self.filter_text:
                self.set_filter("")
            else:
                return BrowserOutcome.CANCEL
        elif on_filter or self.loading:
            return BrowserOutcome.NONE
        elif action is BrowserAction.PAGE_UP:
            self._move(-PAGE_SIZE)
        elif action is BrowserAction.PAGE_DOWN:
            self._move(PAGE_SIZE)
        elif action is BrowserAction.HOME:
            self._move(-len(self._rows))
        elif action is BrowserAction.END:
            self._move(len(self._rows))
        elif action is BrowserAction.ENTER_FOLDER:
            row = self.selected_row
            if row is not None and row.kind is not BrowserRowKind.PRESET:
                self.open_selected()
        return BrowserOutcome.NONE

    def _move(self, delta: int) -> None:
        if not self._rows:
            return
        self.selected_index = max(
            0, min(len(self._rows) - 1, self.selected_index + delta)
        )

    def select_row(self, index: int) -> None:
        """Highlight a row. Does not open it."""
        if self.loading:
            return
        self.focus = BrowserFocus.LIST
        if 0 <= index < len(self._rows):
            self.selected_index = index

    def open_selected(self) -> BrowserOutcome:
        """Open a folder, collection, or ``..``; COMMIT on a preset."""
        if self.loading:
            return BrowserOutcome.NONE
        row = self.selected_row
        if row is None or row.kind is BrowserRowKind.NOTE:
            return BrowserOutcome.NONE
        if row.kind is BrowserRowKind.PRESET:
            return BrowserOutcome.COMMIT
        if row.kind is BrowserRowKind.PARENT:
            self.go_parent()
        elif row.kind is BrowserRowKind.COLLECTION and row.collection is not None:
            self._show(collection=row.collection)
        elif row.kind is BrowserRowKind.FOLDER and row.path is not None:
            self._show(folder=row.path)
        return BrowserOutcome.NONE

    def go_parent(self) -> None:
        """Leave a collection for the top level, or go up one folder."""
        assert self.folder is not None
        if self.collection is not None:
            self._show(folder=self.preset_root, keep_collection=self.collection)
            return
        if self.at_top:
            return
        child = self.folder
        self._show(folder=child.parent, keep=child)

    def goto_crumb(self, index: int) -> None:
        crumbs = self.crumbs()
        if not 0 <= index < len(crumbs) - 1:
            return
        target = crumbs[index].path
        if target is None:
            return
        self._show(folder=target, keep=crumbs[index + 1].path)

    def _show(
        self,
        *,
        folder: Path | None = None,
        collection: PresetCollection | None = None,
        keep: Path | None = None,
        keep_collection: PresetCollection | None = None,
    ) -> None:
        self.filter_text = ""
        self.editing = False
        self.focus = BrowserFocus.LIST
        self.collection = collection
        if folder is not None:
            self.folder = folder.resolve()
        self._request(keep=keep, keep_collection=keep_collection)

    def set_filter(self, text: str) -> None:
        """Apply *text* as the search, keeping the selected preset if it matches."""
        text = text.strip()
        if text == self.filter_text:
            return
        row = self.selected_row
        keep = row.path if row is not None and not self.loading else None
        self.filter_text = text
        self._request(keep=keep)

    # -- the filter field ------------------------------------------------------

    def focus_filter(self) -> None:
        self.focus = BrowserFocus.FILTER

    def begin_edit(self) -> None:
        """Edit the filter, starting from the search applied now."""
        self.focus = BrowserFocus.FILTER
        self.editing = True
        self.draft = self.filter_text
        self._filter_before_edit = self.filter_text
        self.caret_index = len(self.draft)
        reset_caret_blink(self)

    def commit_edit(self) -> None:
        """Stop editing and go back to the list, keeping the search shown."""
        if not self.editing:
            return
        self.editing = False
        self.focus = BrowserFocus.LIST
        self.set_filter(self.draft)

    def cancel_edit(self) -> None:
        """Stop editing and put back the search from before the edit."""
        if not self.editing:
            return
        self.editing = False
        self.draft = self._filter_before_edit
        self.set_filter(self._filter_before_edit)

    def type_text(self, text: str) -> None:
        """Insert typed characters at the caret; the list follows at once."""
        if not self.editing:
            return
        printable = "".join(ch for ch in text if ch.isprintable())
        if printable:
            insert_text_at_caret(self, printable)
            self.set_filter(self.draft)

    def edit_key(self, key: int) -> None:
        """Backspace or a caret move inside the field (pygame key codes)."""
        if self.editing:
            apply_text_edit_key(self, key)
            self.set_filter(self.draft)

    def caret_home(self, *, end: bool) -> None:
        if self.editing:
            self.caret_index = len(self.draft) if end else 0
            reset_caret_blink(self)

    def tick(self, dt_sec: float) -> None:
        self.caret_blink_sec += dt_sec
