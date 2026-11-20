"""Problems that stop a layer doing what it is set to do, and bad preset files.

A layer problem lights the layer's warning icon on its navigator row and its
pages' title line; the tooltip lists every one. A preset file problem marks
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


@dataclass
class PresetHealth:
    """Which preset files are missing, and memoized per-entry problems.

    The disk is read only when a project loads (:meth:`check_on_disk`); a
    preset that goes missing later shows once libprojectM fails to load it.
    Presets added while editing were picked from disk, so they count as
    present. The panel asks every frame, so a layer's list answer is kept
    until its entries or its load failures change.
    """

    missing: frozenset[str] = frozenset()
    _lists: dict[str, tuple[object, tuple[str | None, ...]]] = field(
        default_factory=dict, repr=False
    )

    def check_on_disk(self, session: TuningSession) -> None:
        """Look for every layer's preset and preset list entries on disk."""
        paths: set[str] = set()
        for layer in session.layers.values():
            current = layer.playlist.current
            if current is not None:
                paths.add(os.fspath(current))
            paths.update(layer.preset_list)
        self.missing = frozenset(
            preset_failure_key(path) for path in paths if not os.path.isfile(path)
        )
        self._lists.clear()

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
        problems = tuple(self.file_problem(layer, path) for path in layer.preset_list)
        self._lists[slot] = (key, problems)
        return problems


class ProblemPage(Enum):
    """The layer page where a problem is fixed."""

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


def layer_problems(session: TuningSession, slot: str) -> tuple[LayerProblem, ...]:
    """Everything that stops the layer at *slot* doing what it is set to do."""
    layer = session.layers[slot]
    health = session.preset_health
    problems: list[LayerProblem] = []
    if layer.preset_switching == "on":
        if not layer.preset_list:
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
        if layer.preset_switching_trigger == "timeline":
            lane = session.timeline.lanes.get(slot)
            if not session.timeline.enabled:
                problems.append(
                    LayerProblem(
                        "Switching follows the timeline, but the timeline is off",
                        ProblemPage.PRESET_SWITCHING,
                        RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
                    )
                )
            elif lane is None or not lane.cues:
                problems.append(
                    LayerProblem(
                        "Switching follows the timeline, but this layer has no clips on it",
                        ProblemPage.PRESET_SWITCHING,
                        RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
                    )
                )
    else:
        current = layer.playlist.current
        if current is None:
            problems.append(
                LayerProblem(
                    "Milkdrop preset not found",
                    ProblemPage.MILKDROP_PRESET,
                    RowKind.TRACK_PRESET,
                )
            )
        else:
            problem = health.file_problem(layer, current)
            if problem is not None:
                problems.append(
                    LayerProblem(
                        f"{current.name}: {problem}",
                        ProblemPage.MILKDROP_PRESET,
                        RowKind.TRACK_PRESET,
                    )
                )
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


def layer_problems_tooltip(problems: tuple[LayerProblem, ...]) -> str:
    """Hover text for the warning icon: one problem per line, then the click."""
    lines = [problem.message for problem in problems]
    lines.append("Click to go to the first problem")
    return "\n".join(lines)
