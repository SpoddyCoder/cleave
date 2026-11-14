"""File browser state for opening an audio file or a Cleave project.

Pure state and view state: no pygame import, not even key constants. The host
maps keys onto :class:`PickerAction` and pointer hits onto the row and
shortcut methods, then draws :meth:`FilePicker.view_state`. The list scrollbar
and the wheel live on the overlay.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from cleave.open_target import (
    AUDIO_SUFFIXES,
    OpenTarget,
    OpenTargetKind,
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

TITLE = "Open a Cleave project, or select an audio file to create a new project..."
OPEN_LABEL = "Open"
QUIT_LABEL = "Quit"
CANCEL_LABEL = "Cancel"


def picker_legend(cancel_label: str) -> tuple[tuple[str, str], ...]:
    """Key hints under the listing. Esc does what the cancel button says."""
    return (
        ("Enter", OPEN_LABEL.lower()),
        ("Right", "enter folder"),
        ("Left/Backspace", "parent"),
        ("Tab", "shortcuts"),
        ("Esc", cancel_label.lower()),
    )
DRIVES_LABEL = "Drives"
PARENT_LABEL = ".."
MAX_ROWS = 512
PAGE_SIZE = 12


class PickerMode(Enum):
    """Which open flow the picker is serving."""

    COLD_START = "cold-start"
    OPEN_PROJECT = "open-project"
    NEW_PROJECT = "new-project"


class PickerStart(Enum):
    """Where a mode lists first."""

    PROJECTS = "projects"
    HOME = "home"


@dataclass(frozen=True)
class PickerModeSpec:
    """Title, start directory, and accepted targets for one picker mode."""

    title: str
    start: PickerStart
    kinds: frozenset[OpenTargetKind]


PICKER_MODE_SPECS: dict[PickerMode, PickerModeSpec] = {
    PickerMode.COLD_START: PickerModeSpec(
        title=TITLE,
        start=PickerStart.PROJECTS,
        kinds=frozenset({OpenTargetKind.AUDIO, OpenTargetKind.PROJECT}),
    ),
    PickerMode.OPEN_PROJECT: PickerModeSpec(
        title="Open a Cleave project...",
        start=PickerStart.PROJECTS,
        kinds=frozenset({OpenTargetKind.PROJECT}),
    ),
    PickerMode.NEW_PROJECT: PickerModeSpec(
        title="Select an audio file to create a new project...",
        start=PickerStart.HOME,
        kinds=frozenset({OpenTargetKind.AUDIO}),
    ),
}


def picker_mode_rejection(mode: PickerMode, path: Path) -> str:
    """Return why *path* cannot be accepted in *mode*."""
    kinds = PICKER_MODE_SPECS[mode].kinds
    if kinds == frozenset({OpenTargetKind.PROJECT}):
        return f"select a Cleave project, not {path.name}"
    if kinds == frozenset({OpenTargetKind.AUDIO}):
        return f"select an audio file, not {path.name}"
    return f"cannot open {path.name}"


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
    """Which part of the picker the arrow keys move in."""

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
    cancel_label: str = QUIT_LABEL


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


def _list_directory(
    path: Path,
    accepted: frozenset[OpenTargetKind],
) -> tuple[tuple[PickerRow, ...], bool]:
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
            elif (
                OpenTargetKind.AUDIO in accepted
                and entry.suffix.lower() in AUDIO_SUFFIXES
                and entry.is_file()
            ):
                audio.append(entry)
        except OSError:
            continue

    rows: list[PickerRow] = []
    for entry in sorted(directories, key=_sort_key):
        kind = (
            PickerRowKind.PROJECT
            if OpenTargetKind.PROJECT in accepted and is_project_target(entry)
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
    """Browse the filesystem and return an audio file or project path.

    ``current`` is the directory being listed, or None while showing the
    drives listing. ``selected_index`` is the row Open acts on: arrow keys
    and a click move it. Pointer hover only washes a row; it never selects.
    """

    mode: PickerMode = PickerMode.COLD_START
    current: Path | None = None
    shortcuts: tuple[PickerShortcut, ...] = field(default_factory=picker_shortcuts)
    selected_index: int = 0
    selected_shortcut: int = 0
    focus: PickerFocus = PickerFocus.LIST
    status: str = ""
    cancelled: bool = False
    # Quit at launch, where closing the picker ends the app; Cancel in the
    # editor, where it only closes the picker.
    cancel_label: str = QUIT_LABEL
    _rows: tuple[PickerRow, ...] = field(default_factory=tuple, repr=False)
    _truncated: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        # A None at construction means "start in this mode's directory"; a
        # None later means the drives listing.
        if self.current is None:
            start = _start_directory(self.mode)
            self.current = start
            self.selected_shortcut = _shortcut_index(self.shortcuts, start)
        self._refresh()

    # -- listing -----------------------------------------------------------

    def _refresh(self, *, keep: Path | None = None) -> None:
        if self.current is None:
            rows = _drive_rows()
            truncated = False
        else:
            listing, truncated = _list_directory(
                self.current, PICKER_MODE_SPECS[self.mode].kinds
            )
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
            title=PICKER_MODE_SPECS[self.mode].title,
            location=DRIVES_LABEL if self.current is None else str(self.current),
            rows=self._rows,
            selected_index=self.selected_index,
            shortcuts=self.shortcuts,
            selected_shortcut=self.selected_shortcut,
            active_shortcut=self._active_shortcut_index(),
            focus=self.focus,
            status=self.status,
            legend=picker_legend(self.cancel_label),
            truncated=self._truncated,
            cancel_label=self.cancel_label,
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
                self._move_shortcut(-1)
            else:
                self.go_parent()
        elif action is PickerAction.ENTER:
            if self.focus is PickerFocus.SHORTCUTS:
                self._move_shortcut(1)
            else:
                self._enter()
        elif action is PickerAction.ACCEPT:
            return self._accept()
        elif action is PickerAction.CANCEL:
            self.cancel()
        return None

    def _move(self, delta: int) -> None:
        self.status = ""
        if self.focus is PickerFocus.SHORTCUTS:
            # Down returns to the listing. Up and paging stay put; Left/Right
            # move between shortcuts.
            if delta == 1:
                self.focus = PickerFocus.LIST
                self.selected_index = 0
            return
        if delta == -1 and self.selected_index <= 0:
            self.focus = PickerFocus.SHORTCUTS
            return
        if not self._rows:
            return
        self.selected_index = max(
            0, min(len(self._rows) - 1, self.selected_index + delta)
        )

    def _move_shortcut(self, delta: int) -> None:
        self.status = ""
        count = len(self.shortcuts)
        if not count:
            return
        self.selected_shortcut = max(
            0, min(count - 1, self.selected_shortcut + delta)
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

    def select_row(self, index: int) -> None:
        """Highlight a listing row. Does not open it."""
        self.focus = PickerFocus.LIST
        self.status = ""
        if 0 <= index < len(self._rows):
            self.selected_index = index

    def cancel(self) -> None:
        """Close the picker without a target. Same as Esc."""
        self.cancelled = True

    def open_row(self) -> OpenTarget | None:
        """Accept the highlighted listing row.

        Audio and projects return a target. Directories, the parent row, and
        drives navigate. A note does nothing.
        """
        self.focus = PickerFocus.LIST
        self.status = ""
        return self._accept()

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
        if target.kind not in PICKER_MODE_SPECS[self.mode].kinds:
            try:
                is_dir = row.target.is_dir()
            except OSError:
                is_dir = False
            if is_dir:
                self.navigate_to(row.target)
                return None
            self.status = picker_mode_rejection(self.mode, row.target)
            return None
        return target


def _start_directory(mode: PickerMode) -> Path:
    """Return the directory a new picker lists for *mode*."""
    if PICKER_MODE_SPECS[mode].start is PickerStart.HOME:
        return Path.home()
    start = projects_dir()
    try:
        start.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path.home()
    return start


def _shortcut_index(shortcuts: tuple[PickerShortcut, ...], target: Path) -> int:
    """Return the shortcut whose target is *target*, or 0 when none matches."""
    for index, shortcut in enumerate(shortcuts):
        if shortcut.target == target:
            return index
    return 0
