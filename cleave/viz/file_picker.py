"""Keyboard file browser state for opening a wav or a Cleave project.

Pure state and view state: no pygame import, not even key constants. The host
maps real key events onto :class:`PickerAction` and the payload-carrying
methods, then draws :meth:`FilePicker.view_state`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from cleave.open_target import (
    AUDIO_SUFFIX,
    OpenTarget,
    classify_open_target,
    is_project_target,
    open_target_rejection,
)
from cleave.paths import (
    drive_roots,
    is_frozen,
    projects_dir,
    windows_documents_dir,
)

TITLE = "Open a Cleave project or a wav"
LEGEND: tuple[tuple[str, str], ...] = (
    ("Enter", "open"),
    ("Right", "enter folder"),
    ("Left/Backspace", "parent"),
    ("Tab", "shortcuts"),
    ("Esc", "quit"),
)
DRIVES_LABEL = "Drives"
PARENT_LABEL = ".."
MAX_ROWS = 512
PAGE_SIZE = 12


class PickerAction(Enum):
    """Payload-free picker commands the host can issue."""

    MOVE_UP = "move-up"
    MOVE_DOWN = "move-down"
    PAGE_UP = "page-up"
    PAGE_DOWN = "page-down"
    PARENT = "parent"
    ENTER = "enter"
    ACCEPT = "accept"
    CANCEL = "cancel"
    TOGGLE_FOCUS = "toggle-focus"


class PickerRowKind(Enum):
    """What a listed row points at."""

    PARENT = "parent"
    DIRECTORY = "directory"
    PROJECT = "project"
    AUDIO = "audio"
    DRIVE = "drive"
    NOTE = "note"


class PickerFocus(Enum):
    """Which list the highlight is in."""

    LIST = "list"
    SHORTCUTS = "shortcuts"


@dataclass(frozen=True)
class PickerRow:
    """One row in the current listing."""

    label: str
    kind: PickerRowKind
    target: Path | None = None
    drives: bool = False


@dataclass(frozen=True)
class PickerShortcut:
    """One entry in the shortcut header."""

    label: str
    target: Path | None = None
    drives: bool = False


@dataclass(frozen=True)
class PickerViewState:
    """Everything the overlay needs to draw the picker."""

    title: str
    location: str
    rows: tuple[PickerRow, ...]
    selected_index: int
    shortcuts: tuple[PickerShortcut, ...]
    selected_shortcut: int
    active_shortcut: int | None
    focus: PickerFocus
    status: str
    legend: tuple[tuple[str, str], ...]
    truncated: bool


def picker_shortcuts() -> tuple[PickerShortcut, ...]:
    """Return the shortcut header, skipping entries that do not apply.

    Never includes the install directory: on Windows that is read-only Program
    Files, and user data lives under Documents.
    """
    shortcuts = [
        PickerShortcut(label="Projects", target=projects_dir()),
        PickerShortcut(label="Home", target=Path.home()),
        PickerShortcut(label=DRIVES_LABEL, drives=True),
    ]
    if is_frozen() and sys.platform == "win32":
        shortcuts.append(
            PickerShortcut(label="Documents", target=windows_documents_dir())
        )
    windows_users = Path("/mnt/c/Users")
    if windows_users.is_dir():
        shortcuts.append(
            PickerShortcut(label="Windows files", target=windows_users)
        )
    return tuple(shortcuts)


def _is_volume_root(path: Path) -> bool:
    """True when *path* has no meaningful parent inside its own filesystem."""
    if path.parent == path:
        return True
    return path.parent == Path("/mnt") and len(path.name) == 1


def _sort_key(path: Path) -> str:
    return path.name.casefold()


def _list_directory(path: Path) -> tuple[tuple[PickerRow, ...], bool]:
    """Return rows for *path*, and whether the listing was truncated."""
    try:
        entries = list(path.iterdir())
    except OSError:
        return (), False

    directories: list[Path] = []
    audio: list[Path] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        try:
            if entry.is_dir():
                directories.append(entry)
            elif entry.suffix.lower() == AUDIO_SUFFIX and entry.is_file():
                audio.append(entry)
        except OSError:
            continue

    rows: list[PickerRow] = []
    for entry in sorted(directories, key=_sort_key):
        kind = (
            PickerRowKind.PROJECT
            if is_project_target(entry)
            else PickerRowKind.DIRECTORY
        )
        rows.append(PickerRow(label=entry.name, kind=kind, target=entry))
    for entry in sorted(audio, key=_sort_key):
        rows.append(
            PickerRow(label=entry.name, kind=PickerRowKind.AUDIO, target=entry)
        )

    truncated = len(rows) > MAX_ROWS
    return tuple(rows[:MAX_ROWS]), truncated


def _drive_rows() -> tuple[PickerRow, ...]:
    return tuple(
        PickerRow(label=str(root), kind=PickerRowKind.DRIVE, target=root)
        for root in drive_roots()
    )


@dataclass
class FilePicker:
    """Browse the filesystem and return a wav or project path.

    ``current`` is the directory being listed, or None while showing the
    drives listing.
    """

    current: Path | None = None
    shortcuts: tuple[PickerShortcut, ...] = field(default_factory=picker_shortcuts)
    selected_index: int = 0
    selected_shortcut: int = 0
    focus: PickerFocus = PickerFocus.LIST
    status: str = ""
    cancelled: bool = False
    _rows: tuple[PickerRow, ...] = field(default_factory=tuple, repr=False)
    _truncated: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        # A None at construction means "start where the user data lives"; a
        # None later means the drives listing.
        if self.current is None:
            start = projects_dir()
            try:
                start.mkdir(parents=True, exist_ok=True)
            except OSError:
                start = Path.home()
            self.current = start
        self._refresh()

    # -- listing -----------------------------------------------------------

    def _refresh(self, *, keep: Path | None = None) -> None:
        if self.current is None:
            rows = _drive_rows()
            truncated = False
        else:
            listing, truncated = _list_directory(self.current)
            # Always offer "..": at a volume root it leads to the drives
            # listing rather than nowhere.
            rows = (
                PickerRow(label=PARENT_LABEL, kind=PickerRowKind.PARENT),
            ) + listing
        if truncated:
            rows = rows + (
                PickerRow(
                    label=f"... more than {MAX_ROWS} entries, not shown",
                    kind=PickerRowKind.NOTE,
                ),
            )
        self._rows = rows
        self._truncated = truncated
        self.selected_index = 0
        if keep is not None:
            for index, row in enumerate(rows):
                if row.target == keep:
                    self.selected_index = index
                    break

    @property
    def rows(self) -> tuple[PickerRow, ...]:
        """Return the current listing."""
        return self._rows

    @property
    def selected_row(self) -> PickerRow | None:
        """Return the highlighted row, or None when the listing is empty."""
        if not self._rows:
            return None
        return self._rows[self.selected_index]

    def _active_shortcut_index(self) -> int | None:
        """Return the shortcut that matches the directory being listed."""
        for index, shortcut in enumerate(self.shortcuts):
            if shortcut.drives:
                if self.current is None:
                    return index
                continue
            if shortcut.target is not None and self.current == shortcut.target:
                return index
        return None

    def view_state(self) -> PickerViewState:
        """Return the immutable snapshot the overlay draws."""
        return PickerViewState(
            title=TITLE,
            location=DRIVES_LABEL if self.current is None else str(self.current),
            rows=self._rows,
            selected_index=self.selected_index,
            shortcuts=self.shortcuts,
            selected_shortcut=self.selected_shortcut,
            active_shortcut=self._active_shortcut_index(),
            focus=self.focus,
            status=self.status,
            legend=LEGEND,
            truncated=self._truncated,
        )

    # -- actions -----------------------------------------------------------

    def handle(self, action: PickerAction) -> OpenTarget | None:
        """Apply *action*. Returns a target only when the user accepted one."""
        if action is PickerAction.MOVE_UP:
            self._move(-1)
        elif action is PickerAction.MOVE_DOWN:
            self._move(1)
        elif action is PickerAction.PAGE_UP:
            self._move(-PAGE_SIZE)
        elif action is PickerAction.PAGE_DOWN:
            self._move(PAGE_SIZE)
        elif action is PickerAction.TOGGLE_FOCUS:
            self._toggle_focus()
        elif action is PickerAction.PARENT:
            if self.focus is PickerFocus.SHORTCUTS:
                self._move(-1)
            else:
                self.go_parent()
        elif action is PickerAction.ENTER:
            if self.focus is PickerFocus.SHORTCUTS:
                self._move(1)
            else:
                self._enter()
        elif action is PickerAction.ACCEPT:
            return self._accept()
        elif action is PickerAction.CANCEL:
            self.cancelled = True
        return None

    def _move(self, delta: int) -> None:
        self.status = ""
        if self.focus is PickerFocus.SHORTCUTS:
            count = len(self.shortcuts)
            if count:
                self.selected_shortcut = max(
                    0, min(count - 1, self.selected_shortcut + delta)
                )
            return
        if not self._rows:
            return
        self.selected_index = max(
            0, min(len(self._rows) - 1, self.selected_index + delta)
        )

    def _toggle_focus(self) -> None:
        self.status = ""
        self.focus = (
            PickerFocus.LIST
            if self.focus is PickerFocus.SHORTCUTS
            else PickerFocus.SHORTCUTS
        )

    def go_parent(self) -> None:
        """Move to the parent directory, or to the drives listing at a root."""
        self.status = ""
        self.focus = PickerFocus.LIST
        if self.current is None:
            return
        if _is_volume_root(self.current):
            child = self.current
            self.current = None
            self._refresh(keep=child)
            return
        child = self.current
        self.current = self.current.parent
        self._refresh(keep=child)

    def navigate_to(self, path: Path) -> None:
        """List *path*, keeping the highlight at the top."""
        self.status = ""
        self.focus = PickerFocus.LIST
        self.current = path
        self._refresh()

    def show_drives(self) -> None:
        """Switch to the drives listing."""
        self.status = ""
        self.focus = PickerFocus.LIST
        self.current = None
        self._refresh()

    def goto_shortcut(self, index: int) -> None:
        """Follow the shortcut at *index* in the header."""
        if not 0 <= index < len(self.shortcuts):
            return
        shortcut = self.shortcuts[index]
        self.selected_shortcut = index
        if shortcut.drives:
            self.show_drives()
        elif shortcut.target is not None:
            self.navigate_to(shortcut.target)

    def _enter(self) -> None:
        if self.focus is PickerFocus.SHORTCUTS:
            self.goto_shortcut(self.selected_shortcut)
            return
        row = self.selected_row
        if row is None or row.kind is PickerRowKind.NOTE:
            return
        if row.kind is PickerRowKind.PARENT:
            self.go_parent()
            return
        if row.target is not None and row.kind is not PickerRowKind.AUDIO:
            self.navigate_to(row.target)

    def _accept(self) -> OpenTarget | None:
        if self.focus is PickerFocus.SHORTCUTS:
            self.goto_shortcut(self.selected_shortcut)
            return None
        row = self.selected_row
        if row is None or row.kind is PickerRowKind.NOTE:
            return None
        if row.kind in (PickerRowKind.PARENT, PickerRowKind.DRIVE):
            self._enter()
            return None
        if row.target is None:
            return None
        target = classify_open_target(row.target)
        if target is None:
            if row.kind is PickerRowKind.DIRECTORY:
                self.navigate_to(row.target)
                return None
            self.status = open_target_rejection(row.target)
            return None
        return target
