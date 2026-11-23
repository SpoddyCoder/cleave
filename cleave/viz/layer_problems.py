"""Layer problems and notices, and bad preset files.

A layer problem stops the layer doing what it is set to do; a layer notice is
something the user should know that does not stop it working. A problem
lights the layer's red warning icon on its navigator row and its pages' title
line; with only notices the icon is amber. With one issue the tooltip names
it; with more it says there are several, and the layer's right-click menu
lists them all (problems, then notices), each going to its own row. A missing
preset folder is a problem whether or not switching is on, and marks the
directory row. A preset file problem marks
that file's row (the preset row, or a preset list entry). It lights the layer
icon too while the layer would play that file: the preset while switching is
off, or any preset list entry while switching is on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.projectm import preset_failure_key
from cleave.viz.row_kinds import RowKind
from cleave.stems import stem_control_label

if TYPE_CHECKING:
    from cleave.viz.session import LayerRuntime, TuningSession

PRESET_FILE_MISSING = "File not found"
PRESET_FILE_FAILED = "Failed to load"
PRESET_DIR_MISSING = "Folder not found"


@dataclass
class PresetHealth:
    """Which preset files and folders are missing, and memoized per-entry problems.

    The disk is read only when a project loads (:meth:`check_on_disk`); a
    preset that goes missing later shows once libprojectM fails to load it.
    Presets added while editing were picked from disk, so they count as
    present. The panel asks every frame, so a layer's list answer is kept
    until its entries or its load failures change.
    """

    missing: frozenset[str] = frozenset()
    missing_dirs: frozenset[str] = frozenset()
    _lists: dict[str, tuple[object, tuple[str | None, ...]]] = field(
        default_factory=dict, repr=False
    )

    def check_on_disk(self, session: TuningSession) -> None:
        """Look for every layer's preset folder, preset, and preset list entries on disk."""
        paths: set[str] = set()
        dirs: set[str] = set()
        for layer in session.layers.values():
            dirs.add(os.fspath(layer.playlist.current_dir))
            current = layer.playlist.current
            if current is not None:
                paths.add(os.fspath(current))
            paths.update(entry.path for entry in layer.preset_list)
        self.missing = frozenset(
            preset_failure_key(path) for path in paths if not os.path.isfile(path)
        )
        self.missing_dirs = frozenset(
            preset_failure_key(path) for path in dirs if not os.path.isdir(path)
        )
        self._lists.clear()

    def dir_problem(self, path: Path | str) -> str | None:
        """Why the preset folder at *path* cannot be browsed, or None."""
        if preset_failure_key(path) in self.missing_dirs:
            return PRESET_DIR_MISSING
        return None

    def file_problem(self, layer: LayerRuntime, path: Path | str) -> str | None:
        """Why the preset at *path* cannot play on *layer*, or None."""
        key = preset_failure_key(path)
        if key in self.missing:
            return PRESET_FILE_MISSING
        reason = layer.failed_presets.get(key)
        if reason is None:
            return None
        reason = reason.strip()
        return f"{PRESET_FILE_FAILED}: {reason}" if reason else PRESET_FILE_FAILED

    def list_problems(self, slot: str, layer: LayerRuntime) -> tuple[str | None, ...]:
        """:meth:`file_problem` for each preset list entry, in list order."""
        key = (tuple(layer.preset_list), layer.failed_presets_revision)
        cached = self._lists.get(slot)
        if cached is not None and cached[0] == key:
            return cached[1]
        problems = tuple(
            self.file_problem(layer, entry.file) for entry in layer.preset_list
        )
        self._lists[slot] = (key, problems)
        return problems


class ProblemPage(Enum):
    """The layer page where a problem or notice is dealt with."""

    MILKDROP_PRESET = auto()
    PRESET_SWITCHING = auto()
    PRESET_LIST = auto()
    COMPOSITING = auto()


@dataclass(frozen=True)
class LayerProblem:
    """A problem, the page that fixes it, and the row on that page to focus."""

    message: str
    page: ProblemPage
    row: RowKind | None = None
    preset_index: int | None = None


@dataclass(frozen=True)
class LayerNotice:
    """A notice that does not stop the layer working, the page that deals
    with it, and the row on that page to focus."""

    message: str
    page: ProblemPage
    row: RowKind | None = None
    preset_index: int | None = None


def layer_problems(session: TuningSession, slot: str) -> tuple[LayerProblem, ...]:
    """Everything that stops the layer at *slot* doing what it is set to do."""
    layer = session.layers[slot]
    health = session.preset_health
    folder = _preset_dir_problem(layer, health)
    problems: list[LayerProblem] = [] if folder is None else [folder]
    each_clip = (
        layer.preset_switching == "on"
        and layer.preset_switching_trigger == "timeline"
    )
    if layer.preset_switching == "on":
        if not layer.preset_list:
            # Each-clip layers say which clips lack a preset instead.
            if not each_clip:
                problems.append(
                    LayerProblem(
                        "Preset switching is on, but the preset list is empty",
                        ProblemPage.PRESET_LIST,
                    )
                )
        else:
            entry_problems = health.list_problems(slot, layer)
            bad = sum(1 for problem in entry_problems if problem is not None)
            if bad == len(entry_problems):
                problems.append(
                    LayerProblem(
                        "None of the presets in the preset list can load",
                        ProblemPage.PRESET_LIST,
                        RowKind.TRACK_PRESET_LIST_ITEM,
                        0,
                    )
                )
            elif bad:
                noun = "preset" if bad == 1 else "presets"
                problems.append(
                    LayerProblem(
                        f"{bad} {noun} in the preset list can't load",
                        ProblemPage.PRESET_LIST,
                        RowKind.TRACK_PRESET_LIST_ITEM,
                        next(
                            index
                            for index, problem in enumerate(entry_problems)
                            if problem is not None
                        ),
                    )
                )
        if each_clip:
            from cleave.viz.preset_list_populate import (
                clips_missing_preset_count,
                on_segment_count,
            )

            missing = clips_missing_preset_count(session, slot)
            if not session.timeline.enabled:
                problems.append(
                    LayerProblem(
                        "Presets change on each clip, but the timeline is off",
                        ProblemPage.PRESET_SWITCHING,
                        RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
                    )
                )
            elif on_segment_count(session, slot) == 0:
                problems.append(
                    LayerProblem(
                        "Presets change on each clip, but this layer has no clips",
                        ProblemPage.PRESET_SWITCHING,
                        RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
                    )
                )
            elif missing:
                noun = "clip has" if missing == 1 else "clips have"
                problems.append(
                    LayerProblem(
                        f"{missing} {noun} no preset",
                        ProblemPage.PRESET_LIST,
                    )
                )
    elif folder is None:
        # A file inside a missing folder cannot be there: the folder is the problem.
        problem = _layer_preset_problem(layer, health)
        if problem is not None:
            problems.append(problem)
    if layer.stem in session.silent_stems:
        problems.append(
            LayerProblem(
                f"The {stem_control_label(layer.stem)} stem is silent, "
                "so this layer has no audio to react to",
                ProblemPage.COMPOSITING,
                RowKind.TRACK_STEM,
            )
        )
    return tuple(problems)


def _preset_dir_problem(layer: LayerRuntime, health: PresetHealth) -> LayerProblem | None:
    """The layer's preset folder is missing, whether or not switching is on:
    it is where the layer browses, and its preset while switching is off."""
    current_dir = layer.playlist.current_dir
    if health.dir_problem(current_dir) is None:
        return None
    return LayerProblem(
        f"Preset directory not found: {current_dir.name}",
        ProblemPage.MILKDROP_PRESET,
        RowKind.TRACK_PRESET_DIR,
    )


def _layer_preset_problem(layer: LayerRuntime, health: PresetHealth) -> LayerProblem | None:
    """The layer's own preset file, while switching is off and its folder is there."""
    current = layer.playlist.current
    if current is None:
        message = "Milkdrop preset not found"
    else:
        problem = health.file_problem(layer, current)
        if problem is None:
            return None
        if problem == PRESET_FILE_MISSING:
            message = f"Milkdrop preset not found: {current.name}"
        else:
            message = f"{current.name}: {problem}"
    return LayerProblem(message, ProblemPage.MILKDROP_PRESET, RowKind.TRACK_PRESET)


def layer_notices(session: TuningSession, slot: str) -> tuple[LayerNotice, ...]:
    """What the user should know about the layer at *slot* that does not stop it working."""
    layer = session.layers[slot]
    if (
        layer.preset_switching != "on"
        or layer.preset_switching_trigger != "timeline"
        or not session.timeline.enabled
    ):
        return ()
    from cleave.viz.preset_list_populate import (
        clips_missing_preset_count,
        on_segment_count,
    )

    clips = on_segment_count(session, slot)
    held = clips - clips_missing_preset_count(session, slot)
    spare = len(layer.preset_list) - held
    if clips == 0 or spare <= 0:
        return ()
    noun = "preset in the list has" if spare == 1 else "presets in the list have"
    return (
        LayerNotice(
            f"{spare} {noun} no clip",
            ProblemPage.PRESET_LIST,
            RowKind.TRACK_PRESET_LIST_ITEM,
            held,
        ),
    )


@dataclass(frozen=True)
class LayerIssues:
    """A layer's problems and notices, in the order the menu lists them."""

    problems: tuple[LayerProblem, ...] = ()
    notices: tuple[LayerNotice, ...] = ()

    @property
    def count(self) -> int:
        return len(self.problems) + len(self.notices)

    def items(self) -> tuple[LayerProblem | LayerNotice, ...]:
        """Every problem, then every notice."""
        return (*self.problems, *self.notices)


def layer_issues(session: TuningSession, slot: str) -> LayerIssues:
    """The layer's problems and notices."""
    return LayerIssues(layer_problems(session, slot), layer_notices(session, slot))


def is_problem(issue: LayerProblem | LayerNotice) -> bool:
    """True for a problem (red), False for a notice (amber)."""
    return isinstance(issue, LayerProblem)


def issue_menu_label(issue: LayerProblem | LayerNotice) -> str:
    """One menu line for *issue*: a message over several lines joins with ": "."""
    return ": ".join(line for line in issue.message.split("\n") if line)


def layer_issues_tooltip(issues: LayerIssues) -> str:
    """Hover text for the warning icon.

    One issue: its message, then the click. Several: say so, the click, and
    the right-click that lists them all.
    """
    noun = "problem" if issues.problems else "notice"
    click = f"Click to go to the first {noun}"
    if issues.count <= 1:
        return "\n".join((*(issue.message for issue in issues.items()), click))
    return "\n".join((f"Multiple {noun}s", click, "Right-click to view all"))
