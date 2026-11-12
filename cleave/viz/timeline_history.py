"""Undo and redo for bulk timeline commands.

Each entry holds the timeline before and after one command. Undo runs only
while the timeline still matches what that command left behind, so a later
hand edit is never thrown away. Layer changes count, since lanes are keyed by
slot.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from cleave.timeline import TimelineLane, copy_lane
from cleave.viz.session import TuningSession

_MAX_ENTRIES = 20


@dataclass(frozen=True)
class _Snapshot:
    lanes: dict[str, TimelineLane]
    timeline_enabled: bool
    preset_lists: dict[str, list[str]]
    pattern_mask: tuple[bool, str, int, float]


@dataclass(frozen=True)
class _Entry:
    label: str
    before: _Snapshot
    after: _Snapshot


class TimelineHistory:
    """Bounded undo and redo stacks of timeline snapshots."""

    def __init__(
        self,
        session: TuningSession,
        *,
        on_preset_list_change: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._on_preset_list_change = on_preset_list_change
        self._undo: list[_Entry] = []
        self._redo: list[_Entry] = []

    @contextmanager
    def recording(self, label: str) -> Iterator[None]:
        """Record the command in this block. One that changes nothing is skipped."""
        before = self._capture()
        yield
        after = self._capture()
        if after == before:
            return
        self._undo.append(_Entry(label, before, after))
        del self._undo[:-_MAX_ENTRIES]
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo) and self._matches(self._undo[-1].after)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo) and self._matches(self._redo[-1].before)

    @property
    def undo_label(self) -> str | None:
        """Label of the command Undo would reverse, or None when it cannot."""
        return self._undo[-1].label if self.can_undo else None

    @property
    def redo_label(self) -> str | None:
        """Label of the command Redo would repeat, or None when it cannot."""
        return self._redo[-1].label if self.can_redo else None

    def undo(self) -> str | None:
        """Restore the state before the last command. Returns its label."""
        if not self.can_undo:
            return None
        entry = self._undo.pop()
        self._restore(entry.before)
        self._redo.append(entry)
        return entry.label

    def redo(self) -> str | None:
        """Restore the state after the last undone command. Returns its label."""
        if not self.can_redo:
            return None
        entry = self._redo.pop()
        self._restore(entry.after)
        self._undo.append(entry)
        return entry.label

    def _matches(self, snapshot: _Snapshot) -> bool:
        """Compare in place. Menus read this every frame, so nothing is copied."""
        session = self.session
        mask = session.pattern_mask
        return (
            session.timeline.lanes == snapshot.lanes
            and bool(session.timeline.enabled) == snapshot.timeline_enabled
            and (mask.enabled, mask.type, mask.feather_pct, mask.transition)
            == snapshot.pattern_mask
            and len(session.layers) == len(snapshot.preset_lists)
            and all(
                layer.preset_list == snapshot.preset_lists.get(slot)
                for slot, layer in session.layers.items()
            )
        )

    def _capture(self) -> _Snapshot:
        session = self.session
        mask = session.pattern_mask
        return _Snapshot(
            lanes={slot: copy_lane(lane) for slot, lane in session.timeline.lanes.items()},
            timeline_enabled=bool(session.timeline.enabled),
            preset_lists={
                slot: list(layer.preset_list)
                for slot, layer in session.layers.items()
            },
            pattern_mask=(mask.enabled, mask.type, mask.feather_pct, mask.transition),
        )

    def _restore(self, snapshot: _Snapshot) -> None:
        session = self.session
        session.timeline.lanes = {
            slot: copy_lane(lane) for slot, lane in snapshot.lanes.items()
        }
        session.timeline.enabled = snapshot.timeline_enabled
        mask = session.pattern_mask
        mask.enabled, mask.type, mask.feather_pct, mask.transition = (
            snapshot.pattern_mask
        )
        for slot, preset_list in snapshot.preset_lists.items():
            layer = session.layers[slot]
            if layer.preset_list == preset_list:
                continue
            layer.preset_list[:] = preset_list
            if self._on_preset_list_change is not None:
                self._on_preset_list_change(slot)
