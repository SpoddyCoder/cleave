"""Bulk apply hard/soft cut types to timeline cues."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal

from cleave.cut_types import CutType
from cleave.timeline import (
    SONG_MARKER_CUT_MATCH_EPS,
    SlotCue,
    TimelineLane,
    canonicalize,
    matches_song_marker,
)
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

ApplyCutScope = Literal["all", "except_markers", "markers_only"]

_ALL_LABEL = "All cues"
_EXCEPT_MARKERS_LABEL = "All cues except song marker cues"
_MARKERS_ONLY_LABEL = "Song marker cues only"
_CANCEL_LABEL = "Cancel"


def apply_cut_to_lanes(
    lanes: dict[str, TimelineLane],
    cut: CutType,
    *,
    song_marker_times: Sequence[float],
    scope: ApplyCutScope,
) -> int:
    """Set ``cut`` on matching cues (on and off) across lanes.

    Returns the number of cues updated.
    """
    markers = tuple(float(t) for t in song_marker_times)
    updated = 0
    for slot, lane in list(lanes.items()):
        new_cues: list[SlotCue] = []
        changed = False
        for cue in lane.cues:
            at_marker = matches_song_marker(
                cue.t,
                markers,
                eps=SONG_MARKER_CUT_MATCH_EPS,
            )
            if scope == "all":
                apply = True
            elif scope == "except_markers":
                apply = not at_marker
            else:
                apply = at_marker
            if apply and cue.cut != cut:
                new_cues.append(
                    SlotCue(
                        t=cue.t,
                        level=cue.level,
                        blend=cue.blend,
                        role=cue.role,
                        cut=cut,
                    )
                )
                changed = True
                updated += 1
            else:
                new_cues.append(cue)
        if changed:
            lanes[slot] = TimelineLane(
                baseline=lane.baseline,
                cues=canonicalize(lane.baseline, new_cues),
            )
    return updated


class TimelineCutController:
    """Prompt for and apply hard/soft cut types to committed cues."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._on_notification = on_notification

    def prompt_soft(self) -> None:
        self._prompt("soft")

    def prompt_hard(self) -> None:
        self._prompt("hard")

    def _prompt(self, cut: CutType) -> None:
        tl = self.session.timeline
        if tl.locked:
            return
        if tl.recording:
            return
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to update")
            return
        label = "soft" if cut == "soft" else "hard"
        dismiss = lambda: None
        options = [
            ModalOption(
                _ALL_LABEL,
                lambda: self._apply(cut, "all"),
            ),
            ModalOption(
                _EXCEPT_MARKERS_LABEL,
                lambda: self._apply(cut, "except_markers"),
            ),
            ModalOption(
                _MARKERS_ONLY_LABEL,
                lambda: self._apply(cut, "markers_only"),
            ),
            ModalOption(_CANCEL_LABEL, dismiss),
        ]
        self._modal.prompt_choice(
            f"Apply {label} cuts to cues?",
            options,
            on_dismiss=dismiss,
        )

    def _apply(self, cut: CutType, scope: ApplyCutScope) -> None:
        tl = self.session.timeline
        if tl.locked or tl.recording:
            return
        count = apply_cut_to_lanes(
            tl.lanes,
            cut,
            song_marker_times=self.session.song_markers.times,
            scope=scope,
        )
        if count == 0:
            self._notify("No matching cues to update")
            return
        label = "soft" if cut == "soft" else "hard"
        noun = "cue" if count == 1 else "cues"
        self._notify(f"Applied {label} cuts to {count} {noun}")

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
