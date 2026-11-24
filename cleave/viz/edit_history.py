"""Undo and redo for timeline and preset list edits.

Each entry holds the timeline and every layer's preset list and switching
trigger before and after one edit: a bulk command, a hand edit to a clip, a
recorded take, a preset list edit, or a change of when presets change. Undo runs only while that state still matches what the edit left
behind, so a change made outside the history is never thrown away. Layer
changes count, since lanes and preset lists are keyed by slot.

Each entry names its scopes, so the Undo command can refuse one that changes
a locked section: :data:`TIMELINE_SCOPE`, and :func:`preset_list_scope` for
each layer. They are the scope the edit was begun with plus whatever it
changed. An edit a lock forbids is put back as it finishes, unrecorded.

Edits that share a merge key and follow each other closely fold into one
entry, so a held nudge key or a whole drag undoes as one step. The clip
selection is restored with the lanes but does not count as a change.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from cleave.config_schema.layers import preset_switching_mode_for_trigger
from cleave.preset_list_entry import PresetListEntry
from cleave.timeline import TimelineLane, copy_lane
from cleave.viz.session import BrowseSnapshot, TuningSession

_MAX_ENTRIES = 20
_MERGE_WINDOW_SEC = 1.0

EditScope = tuple[str, ...]
TIMELINE_SCOPE: EditScope = ("timeline",)


def preset_list_scope(slot: str) -> EditScope:
    """Scope of an edit to *slot*'s preset list."""
    return ("preset_list", slot)


def preset_list_scope_slot(scope: EditScope) -> str | None:
    """The layer a preset list scope names, or None for any other scope."""
    if len(scope) == 2 and scope[0] == "preset_list":
        return scope[1]
    return None


@dataclass(frozen=True)
class EditSnapshot:
    """What undo restores: the state on one side of an edit."""

    lanes: dict[str, TimelineLane]
    timeline_enabled: bool
    preset_lists: dict[str, list[PresetListEntry]]
    # Each layer's switching trigger: entering or leaving "each clip" moves
    # presets between the list and the clips in the same step.
    triggers: dict[str, str]
    pattern_mask: tuple[bool, str, int, float]
    # Restored with the rest, but never counts as a change.
    selected_clip_t: dict[str, float]
    # Each layer's own preset and browse position. Restored for a layer whose
    # switching the step turns on or off, but never count as a change.
    browse: dict[str, tuple[Path | None, BrowseSnapshot]]

    def same_content(self, other: EditSnapshot) -> bool:
        return (
            self.lanes == other.lanes
            and self.timeline_enabled == other.timeline_enabled
            and self.preset_lists == other.preset_lists
            and self.triggers == other.triggers
            and self.pattern_mask == other.pattern_mask
        )


@dataclass
class EditOutcome:
    """How a recorded edit ended, filled in as its block finishes.

    ``refused`` says which lock forbade it, when one did: the edit has been
    put back. ``before`` is the state from before the edit.
    """

    before: EditSnapshot
    refused: str | None = None


@dataclass(frozen=True)
class _Entry:
    label: str
    before: EditSnapshot
    after: EditSnapshot
    merge_key: Hashable | None
    committed_at: float
    scope: EditScope
    scopes: frozenset[EditScope]


@dataclass(frozen=True)
class _Pending:
    label: str
    before: EditSnapshot
    merge_key: Hashable | None
    scope: EditScope


class EditHistory:
    """Bounded undo and redo stacks of timeline and preset list snapshots."""

    def __init__(
        self,
        session: TuningSession,
        *,
        on_preset_list_change: Callable[[str], None] | None = None,
        on_trigger_restored: Callable[[str], None] | None = None,
        scope_locked: Callable[[EditScope], bool] | None = None,
        before_commit: Callable[[EditSnapshot], None] | None = None,
        refuse: Callable[[EditSnapshot], str | None] | None = None,
        on_refused: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """``before_commit`` runs as each edit finishes, before it is recorded,
        with the state from before the edit. Changes it makes join the
        same undo step (each-clip layers keep their clips and list in step).
        ``refuse`` then says why a lock forbids the edit, if one does: the
        edit is put back and ``on_refused`` told. Undo and redo call
        ``on_trigger_restored`` for a layer whose switching trigger they
        change, else ``on_preset_list_change`` for one whose list they do.
        """
        self.session = session
        self._on_preset_list_change = on_preset_list_change
        self._on_trigger_restored = on_trigger_restored
        self._before_commit = before_commit
        self._refuse = refuse
        self._on_refused = on_refused
        self._scope_locked = scope_locked
        self._clock = clock
        self._undo: list[_Entry] = []
        self._redo: list[_Entry] = []
        self._pending: _Pending | None = None

    @contextmanager
    def recording(
        self,
        label: str,
        *,
        merge_key: Hashable | None = None,
        scope: EditScope = TIMELINE_SCOPE,
    ) -> Iterator[EditOutcome]:
        """Record the edit in this block. One that changes nothing is skipped.

        The outcome it gives says, after the block, whether a lock refused it.
        """
        outcome = EditOutcome(self.begin(label, merge_key=merge_key, scope=scope))
        try:
            yield outcome
        finally:
            outcome.refused = self.commit()

    @property
    def pending(self) -> bool:
        """True between ``begin`` and ``commit`` or ``cancel``."""
        return self._pending is not None

    def begin(
        self,
        label: str,
        *,
        merge_key: Hashable | None = None,
        scope: EditScope = TIMELINE_SCOPE,
    ) -> EditSnapshot:
        """Start an edit that may span frames, such as a drag or a take.

        A ``begin`` while another edit is pending commits that one first.
        Returns the state the edit starts from.
        """
        if self._pending is not None:
            self.commit()
        before = self._capture()
        self._pending = _Pending(label, before, merge_key, scope)
        return before

    def commit(self) -> str | None:
        """Record the pending edit, folding it into the last one when it merges.

        Returns why a lock refused the edit, which is then put back, or None.
        """
        pending = self._pending
        if pending is None:
            return None
        self._pending = None
        if self._before_commit is not None:
            self._before_commit(pending.before)
        after = self._capture()
        if after.same_content(pending.before):
            return None
        refused = None if self._refuse is None else self._refuse(pending.before)
        if refused is not None:
            self._restore(pending.before)
            self.report_refused(refused)
            return refused
        scopes = _changed_scopes(pending.before, after) | {pending.scope}
        now = self._clock()
        top = self._undo[-1] if self._undo else None
        if (
            top is not None
            and pending.merge_key is not None
            and top.merge_key == pending.merge_key
            and top.scope == pending.scope
            and now - top.committed_at <= _MERGE_WINDOW_SEC
            and top.after.same_content(pending.before)
        ):
            if after.same_content(top.before):
                # The run of edits ended where it began.
                self._undo.pop()
            else:
                self._undo[-1] = replace(
                    top,
                    label=pending.label,
                    after=after,
                    committed_at=now,
                    scopes=top.scopes | scopes,
                )
        else:
            self._undo.append(
                _Entry(
                    pending.label,
                    pending.before,
                    after,
                    pending.merge_key,
                    now,
                    pending.scope,
                    scopes,
                )
            )
            del self._undo[:-_MAX_ENTRIES]
        self._redo.clear()
        return None

    def report_refused(self, reason: str) -> None:
        """Say which lock forbids an edit, as a refused ``commit`` does."""
        if self._on_refused is not None:
            self._on_refused(reason)

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
    def undo_scopes(self) -> frozenset[EditScope]:
        """Scopes of the command Undo would reverse; empty when it cannot."""
        return self._undo[-1].scopes if self.can_undo else frozenset()

    @property
    def redo_scopes(self) -> frozenset[EditScope]:
        """Scopes of the command Redo would repeat; empty when it cannot."""
        return self._redo[-1].scopes if self.can_redo else frozenset()

    @property
    def undo_locked(self) -> bool:
        """True when a section the next Undo would change is locked."""
        return bool(self.undo_locks)

    @property
    def redo_locked(self) -> bool:
        """True when a section the next Redo would change is locked."""
        return bool(self.redo_locks)

    @property
    def undo_locks(self) -> frozenset[EditScope]:
        """The locked scopes the next Undo waits on."""
        return frozenset(s for s in self.undo_scopes if self._is_locked(s))

    @property
    def redo_locks(self) -> frozenset[EditScope]:
        """The locked scopes the next Redo waits on."""
        return frozenset(s for s in self.redo_scopes if self._is_locked(s))

    def _is_locked(self, scope: EditScope) -> bool:
        if self._scope_locked is not None:
            return self._scope_locked(scope)
        if scope == TIMELINE_SCOPE:
            return bool(self.session.timeline.locked)
        return False

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

    def _matches(self, snapshot: EditSnapshot) -> bool:
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
                and layer.preset_switching_trigger == snapshot.triggers.get(slot)
                for slot, layer in session.layers.items()
            )
        )

    def _capture(self) -> EditSnapshot:
        session = self.session
        mask = session.pattern_mask
        return EditSnapshot(
            lanes={slot: copy_lane(lane) for slot, lane in session.timeline.lanes.items()},
            timeline_enabled=bool(session.timeline.enabled),
            preset_lists={
                slot: list(layer.preset_list)
                for slot, layer in session.layers.items()
            },
            triggers={
                slot: layer.preset_switching_trigger
                for slot, layer in session.layers.items()
            },
            pattern_mask=(mask.enabled, mask.type, mask.feather_pct, mask.transition),
            selected_clip_t=dict(session.timeline.selected_clip_t),
            browse={
                slot: (layer.layer_preset, layer.browse_snapshot())
                for slot, layer in session.layers.items()
            },
        )

    def _restore(self, snapshot: EditSnapshot) -> None:
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
            trigger = snapshot.triggers.get(slot, layer.preset_switching_trigger)
            if (
                layer.preset_list == preset_list
                and layer.preset_switching_trigger == trigger
            ):
                continue
            previous = layer.preset_switching_trigger
            layer.preset_list[:] = preset_list
            layer.preset_switching_trigger = trigger  # type: ignore[assignment]
            layer.preset_switching = preset_switching_mode_for_trigger(
                layer.preset_switching_trigger
            )
            if trigger != previous:
                if "off" in (trigger, previous):
                    layer.layer_preset, browse = snapshot.browse[slot]
                    layer.restore_browse(browse)
                if self._on_trigger_restored is not None:
                    self._on_trigger_restored(slot)
            elif self._on_preset_list_change is not None:
                self._on_preset_list_change(slot)


def _changed_scopes(
    before: EditSnapshot, after: EditSnapshot
) -> frozenset[EditScope]:
    scopes: set[EditScope] = set()
    if (
        before.lanes != after.lanes
        or before.timeline_enabled != after.timeline_enabled
    ):
        scopes.add(TIMELINE_SCOPE)
    for slot, preset_list in after.preset_lists.items():
        if preset_list != before.preset_lists.get(slot) or after.triggers.get(
            slot
        ) != before.triggers.get(slot):
            scopes.add(preset_list_scope(slot))
    return frozenset(scopes)
