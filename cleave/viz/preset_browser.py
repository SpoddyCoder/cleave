"""Preset browser state: one layer's folders, collections, and presets.

Pure state and view state: no pygame or ImGui import. The controller maps keys
and typed text onto :class:`BrowserAction` and :meth:`PresetBrowser.type_text`,
previews :meth:`PresetBrowser.selected_preset` on the layer, and draws
:meth:`PresetBrowser.view_state`.

The list is MilkDrop style: ``..``, then (at the top level) the library
collections, then subfolders with their preset counts, then presets. Typing
filters every preset under the folder being shown, matched on its path below
that folder.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from cleave.preset_library import COLLECTION_LABEL, PresetCatalog, PresetCollection
from cleave.preset_playlist import list_navigable_dirs, milk_files_in_dir

ROOT_LABEL = "presets"
PARENT_LABEL = ".."
FILTER_PLACEHOLDER = "Type to filter"
MAX_ROWS = 512
PAGE_SIZE = 12


def browser_legend() -> tuple[tuple[str, str], ...]:
    """Key hints under the list."""
    return (
        ("Enter", "open / keep"),
        ("Left", "parent"),
        ("Type", "filter"),
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
class BrowserViewState:
    """Everything the surface needs to draw the browser."""

    title: str
    crumbs: tuple[BrowserCrumb, ...]
    filter_text: str
    rows: tuple[BrowserRow, ...]
    selected_index: int
    legend: tuple[tuple[str, str], ...]
    location_key: str


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


@dataclass
class PresetBrowser:
    """Browse one layer's presets from *preset_root* down.

    ``folder`` is the folder listed, or the folder a collection was entered
    from while ``collection`` is set. ``marker`` returns a preset's curation
    tags (``" [F] [L]"``), as on the preset row.
    """

    preset_root: Path
    catalog: PresetCatalog
    title: str = "Browse presets"
    folder: Path | None = None
    collection: PresetCollection | None = None
    select: Path | None = None
    marker: Callable[[Path], str] = field(default=lambda _path: "", repr=False)
    filter_text: str = ""
    selected_index: int = 0
    _rows: tuple[BrowserRow, ...] = field(default_factory=tuple, repr=False)

    def __post_init__(self) -> None:
        self.preset_root = self.preset_root.resolve()
        folder = (self.folder or self.preset_root).resolve()
        if not self._within_root(folder):
            folder = self.preset_root
        self.folder = folder
        self._refresh(keep=self.select)

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

    def _counts(self) -> dict[Path, int]:
        return self.catalog.preset_counts_by_dir()

    def _child_folders(self, folder: Path) -> tuple[tuple[Path, int], ...]:
        """Subfolders that hold visible presets, with how many, by name."""
        counts = self._counts()
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

    def _listing(self) -> tuple[BrowserRow, ...]:
        assert self.folder is not None
        rows: list[BrowserRow] = []
        if not self.at_top:
            rows.append(BrowserRow(BrowserRowKind.PARENT, PARENT_LABEL))
        if self.collection is not None:
            paths = self.catalog.collection_paths(self.collection)
            presets = tuple(
                self._preset_row(path, self._relative_label(path, self.preset_root))
                for path in paths
            )
            if not presets:
                rows.append(
                    BrowserRow(BrowserRowKind.NOTE, "No presets in this collection")
                )
            return (*rows, *presets)
        if self.at_top:
            for collection in self.catalog.collections():
                rows.append(
                    BrowserRow(
                        BrowserRowKind.COLLECTION,
                        COLLECTION_LABEL[collection],
                        collection=collection,
                    )
                )
        for child, count in self._child_folders(self.folder):
            rows.append(
                BrowserRow(
                    BrowserRowKind.FOLDER,
                    child.name,
                    detail=preset_count_text(count),
                    path=child,
                )
            )
        presets = self.catalog.visible(
            p.resolve() for p in milk_files_in_dir(self.folder)
        )
        rows.extend(self._preset_row(path, path.name) for path in presets)
        if all(row.kind is BrowserRowKind.PARENT for row in rows):
            rows.append(BrowserRow(BrowserRowKind.NOTE, "No presets here"))
        return tuple(rows)

    @staticmethod
    def _relative_label(path: Path, base: Path) -> str:
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            return path.name

    def _filtered(self) -> tuple[BrowserRow, ...]:
        assert self.folder is not None
        terms = filter_terms(self.filter_text)
        if self.collection is not None:
            base = self.preset_root
            candidates = self.catalog.collection_paths(self.collection)
        else:
            base = self.folder
            candidates = self._presets_below(self.folder)
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
        if self.collection is None:
            visible = set(self.catalog.visible(p for p, _label in matched))
            matched = [(p, label) for p, label in matched if p in visible]
        rows = [self._preset_row(p, label) for p, label in matched[:MAX_ROWS]]
        if not matched:
            return (BrowserRow(BrowserRowKind.NOTE, "No presets match"),)
        if len(matched) > MAX_ROWS:
            rows.append(
                BrowserRow(
                    BrowserRowKind.NOTE,
                    f"Showing the first {MAX_ROWS:,} of {len(matched):,} matches",
                )
            )
        return tuple(rows)

    def _refresh(self, *, keep: Path | None = None) -> None:
        rows = self._filtered() if self.filter_text.strip() else self._listing()
        self._rows = rows
        self.selected_index = _first_entry_index(rows)
        if keep is not None:
            for index, row in enumerate(rows):
                if row.path == keep:
                    self.selected_index = index
                    break

    def refresh(self) -> None:
        """Re-list after curation changes, keeping the selected row."""
        row = self.selected_row
        keep = row.path if row is not None else None
        self._refresh(keep=keep)

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
        """The preset row under the selection, or None on a folder or note."""
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
            legend=browser_legend(),
            location_key=f"{location}?{self.filter_text}",
        )

    # -- actions -----------------------------------------------------------

    def handle(self, action: BrowserAction) -> BrowserOutcome:
        """Apply *action*. COMMIT keeps the selected preset; CANCEL reverts."""
        if action is BrowserAction.MOVE_UP:
            self._move(-1)
        elif action is BrowserAction.MOVE_DOWN:
            self._move(1)
        elif action is BrowserAction.PAGE_UP:
            self._move(-PAGE_SIZE)
        elif action is BrowserAction.PAGE_DOWN:
            self._move(PAGE_SIZE)
        elif action is BrowserAction.HOME:
            self._move(-len(self._rows))
        elif action is BrowserAction.END:
            self._move(len(self._rows))
        elif action is BrowserAction.OPEN:
            return self.open_selected()
        elif action is BrowserAction.ENTER_FOLDER:
            row = self.selected_row
            if row is not None and row.kind is not BrowserRowKind.PRESET:
                self.open_selected()
        elif action is BrowserAction.PARENT:
            self.go_parent()
        elif action is BrowserAction.BACKSPACE:
            if self.filter_text:
                self.set_filter(self.filter_text[:-1])
            else:
                self.go_parent()
        elif action is BrowserAction.CANCEL:
            if self.filter_text:
                self.set_filter("")
            else:
                return BrowserOutcome.CANCEL
        return BrowserOutcome.NONE

    def _move(self, delta: int) -> None:
        if not self._rows:
            return
        self.selected_index = max(
            0, min(len(self._rows) - 1, self.selected_index + delta)
        )

    def select_row(self, index: int) -> None:
        """Highlight a row. Does not open it."""
        if 0 <= index < len(self._rows):
            self.selected_index = index

    def open_selected(self) -> BrowserOutcome:
        """Open a folder, collection, or ``..``; COMMIT on a preset."""
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
            left = self.collection
            self._show(folder=self.preset_root)
            for index, row in enumerate(self._rows):
                if row.collection == left:
                    self.selected_index = index
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
        keep = crumbs[index + 1].path
        self._show(folder=target, keep=keep)

    def _show(
        self,
        *,
        folder: Path | None = None,
        collection: PresetCollection | None = None,
        keep: Path | None = None,
    ) -> None:
        self.filter_text = ""
        self.collection = collection
        if folder is not None:
            self.folder = folder.resolve()
        self._refresh(keep=keep)

    def set_filter(self, text: str) -> None:
        if text == self.filter_text:
            return
        keep = self.selected_preset()
        self.filter_text = text
        self._refresh(keep=keep)

    def type_text(self, text: str) -> None:
        """Append typed characters to the filter. A leading space is dropped."""
        printable = "".join(ch for ch in text if ch.isprintable())
        if not self.filter_text:
            printable = printable.lstrip()
        if printable:
            self.set_filter(self.filter_text + printable)
