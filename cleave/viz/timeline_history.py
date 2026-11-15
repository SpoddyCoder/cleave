"""Undo and redo for timeline edits.

Each entry holds the timeline before and after one edit: a bulk command, a
hand edit to a clip, or a recorded take. Undo runs only while the timeline
still matches what that edit left behind, so a change made outside the
history is never thrown away. Layer changes count, since lanes are keyed by
slot.

Edits that share a merge key and follow each other closely fold into one
entry, so a held nudge key or a whole drag undoes as one step. The clip
selection is restored with the lanes but does not count as a change.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace

from cleave.timeline import TimelineLane, copy_lane
from cleave.viz.session import TuningSession

_MAX_ENTRIES = 20
_MERGE_WINDOW_SEC = 1.0


@dataclass(frozen=True)
class _Snapshot:
    lanes: dict[str, TimelineLane]
    timeline_enabled: bool
    preset_lists: dict[str, list[str]]
    pattern_mask: tuple[bool, str, int, float]
    # Restored with the rest, but never counts as a change.
    selected_clip_t: dict[str, float]

    def same_content(self, other: _Snapshot) -> bool:
        return (
            self.lanes == other.lanes
            and self.timeline_enabled == other.timeline_enabled
            and self.preset_lists == other.preset_lists
            and self.pattern_mask == other.pattern_mask
        )


@dataclass(frozen=True)
class _Entry:
    label: str
    before: _Snapshot
    after: _Snapshot
    merge_key: Hashable | None
    committed_at: float


@dataclass(frozen=True)
class _Pending:
    label: str
    before: _Snapshot
    merge_key: Hashable | None


class TimelineHistory:
    """Bounded undo and redo stacks of timeline snapshots."""

    def __init__(
        self,
        session: TuningSession,
        *,
        on_preset_list_change: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.session = session
        self._on_preset_list_change = on_preset_list_change
        self._clock = clock
        self._undo: list[_Entry] = []
        self._redo: list[_Entry] = []
        self._pending: _Pending | None = None

    @contextmanager
    def recording(
        self, label: str, *, merge_key: Hashable | None = None
    ) -> Iterator[None]:
        """Record the edit in this block. One that changes nothing is skipped."""
        self.begin(label, merge_key=merge_key)
        try:
            yield
        finally:
            self.commit()

    @property
    def pending(self) -> bool:
        """True between ``begin`` and ``commit`` or ``cancel``."""
        return self._pending is not None

    def begin(self, label: str, *, merge_key: Hashable | None = None) -> None:
        """Start an edit that may span frames, such as a drag or a take.

        A ``begin`` while another edit is pending commits that one first.
        """
        if self._pending is not None:
            self.commit()
        self._pending = _Pending(label, self._capture(), merge_key)

    def commit(self) -> None:
        """Record the pending edit, folding it into the last one when it merges."""
        pending = self._pending
        if pending is None:
            return
        self._pending = None
        after = self._capture()
        if after.same_content(pending.before):
            return
        now = self._clock()
        top = self._undo[-1] if self._undo else None
        if (
            top is not None
            and pending.merge_key is not None
            and top.merge_key == pending.merge_key
            and now - top.committed_at <= _MERGE_WINDOW_SEC
            and top.after.same_content(pending.before)
        ):
            self._undo[-1] = replace(top, after=after, committed_at=now)
        else:
            self._undo.append(
                _Entry(pending.label, pending.before, after, pending.merge_key, now)
            )
            del self._undo[:-_MAX_ENTRIES]
        self._redo.clear()

    def cancel(self) -> None:
        """Drop the pending edit without recording it. The caller restores state."""
        self._pending = None

    @property
    def can_undo(self) -> bool:
        """False while an edit is pending, such as a drag or a take."""
        return (
            self._pending is None
            and bool(self._undo)
            and self._matches(self._undo[-1].after)
        )

    @property
    def can_redo(self) -> bool:
        return (
            self._pending is None
            and bool(self._redo)
            and self._matches(self._redo[-1].before)
        )

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
            selected_clip_t=dict(session.timeline.selected_clip_t),
        )

    def _restore(self, snapshot: _Snapshot) -> None:
        session = self.session
        session.timeline.lanes = {
            slot: copy_lane(lane) for slot, lane in snapshot.lanes.items()
        }
        session.timeline.enabled = snapshot.timeline_enabled
        session.timeline.selected_clip_t = dict(snapshot.selected_clip_t)
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
