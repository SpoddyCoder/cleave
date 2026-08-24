"""Explicit pattern-mask wipe commands.

Compose emits slot-set changes (on/off) and optional recasts. A recast is a
preset switch on a continuing slot, not a wipe. ``LayerFramePipeline`` turns a
slot-set change into a ``MaskTransition``; the masked compositor applies that
command and does not infer wipes from slot diffs.

Add-then-remove overlap is a compose concern: the overlap set is kept only when
it spans at least ``transition_duration`` plus one beat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HARD_LAYOUT_MASK_TYPES = frozenset({"strips", "radial"})

MaskTransitionKind = Literal["hard_layout", "weight_field", "clear"]


def uses_hard_layout_morph(mask_type: str) -> bool:
    """Strips/radial lerp 1D cuts; checker/plasma dissolve via weight fields."""
    return mask_type in HARD_LAYOUT_MASK_TYPES


def mask_transition_kind(mask_type: str) -> Literal["hard_layout", "weight_field"]:
    if uses_hard_layout_morph(mask_type):
        return "hard_layout"
    return "weight_field"


@dataclass(frozen=True)
class MaskTransition:
    """Wipe issued by the layer pipeline; compositor does not infer from diffs.

    ``kind`` is ``hard_layout`` (strips/radial 1D cut lerp), ``weight_field``
    (checker/plasma dissolve), or ``clear`` (slot-set changed with duration 0).
    ``from_slots`` is the active set before this change (departing morph source).
    """

    kind: MaskTransitionKind
    start_sec: float
    duration: float
    from_slots: tuple[bool, ...]


class PatternMaskTransitionTracker:
    """Holds the previous active set and emits ``MaskTransition`` commands."""

    def __init__(self) -> None:
        self._last_active_slots: tuple[bool, ...] | None = None

    @property
    def last_active_slots(self) -> tuple[bool, ...] | None:
        return self._last_active_slots

    def peek(
        self,
        active_slots: tuple[bool, ...],
        *,
        song_time_sec: float,
        duration: float,
        mask_type: str,
    ) -> MaskTransition | None:
        """Return a wipe command when the active set changed. Does not mutate."""
        last = self._last_active_slots
        if last is None or active_slots == last:
            return None
        duration = max(0.0, float(duration))
        if duration <= 0.0:
            return MaskTransition(
                kind="clear",
                start_sec=float(song_time_sec),
                duration=0.0,
                from_slots=last,
            )
        return MaskTransition(
            kind=mask_transition_kind(mask_type),
            start_sec=float(song_time_sec),
            duration=duration,
            from_slots=last,
        )

    def commit(self, active_slots: tuple[bool, ...]) -> None:
        self._last_active_slots = tuple(bool(flag) for flag in active_slots)

    def reset(self) -> None:
        self._last_active_slots = None
