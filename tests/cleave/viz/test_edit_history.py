"""Undo and redo of timeline and preset list edits."""

from __future__ import annotations

from types import SimpleNamespace

from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.edit_history import TIMELINE_SCOPE, EditHistory, preset_list_scope
from tests.support.preset_list import entries


def _lane(*times: float) -> TimelineLane:
    return TimelineLane(
        baseline=None, cues=[SlotCue(t=t, level=1.0) for t in times]
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        timeline=SimpleNamespace(
            lanes={"layer_1": _lane(1.0)},
            enabled=True,
            bar_phase_offset=0,
            selected_clip_t={},
        ),
        layers={
            "layer_1": SimpleNamespace(
                preset_list=entries("a.milk"),
                preset_switching_trigger="off",
                layer_preset=None,
                browse_snapshot=lambda: None,
            )
        },
        pattern_mask=SimpleNamespace(
            enabled=False, type="stripes", feather_pct=5, transition=2.0
        ),
    )


def test_undo_and_redo_restore_lanes() -> None:
    session = _session()
    history = EditHistory(session)
    with history.recording("Snap clips"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    assert history.can_undo is True
    assert history.undo() == "Snap clips"
    assert session.timeline.lanes["layer_1"].cues[0].t == 1.0
    assert history.can_undo is False
    assert history.redo() == "Snap clips"
    assert session.timeline.lanes["layer_1"].cues[0].t == 2.0


def test_a_command_that_changes_nothing_is_not_recorded() -> None:
    session = _session()
    history = EditHistory(session)
    with history.recording("Snap clips"):
        pass
    assert history.can_undo is False


def test_a_hand_edit_after_the_command_blocks_undo() -> None:
    session = _session()
    history = EditHistory(session)
    with history.recording("Generate timeline"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    session.timeline.lanes["layer_1"] = _lane(3.0)
    assert history.can_undo is False
    assert history.undo() is None
    assert session.timeline.lanes["layer_1"].cues[0].t == 3.0


def test_adding_a_layer_blocks_undo() -> None:
    session = _session()
    history = EditHistory(session)
    with history.recording("Reset timeline"):
        session.timeline.lanes["layer_1"] = _lane()
    session.timeline.lanes["layer_2"] = _lane()
    assert history.can_undo is False


def test_undo_restores_everything_generate_touches() -> None:
    session = _session()
    changed: list[str] = []
    history = EditHistory(session, on_preset_list_change=changed.append)
    with history.recording("Generate timeline"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
        session.timeline.enabled = False
        session.layers["layer_1"].preset_list[:] = entries("b.milk")
        session.pattern_mask.enabled = True
        session.pattern_mask.type = "strips"
        session.pattern_mask.feather_pct = 0
        session.pattern_mask.transition = 1.0
    history.undo()
    assert session.timeline.enabled is True
    assert session.layers["layer_1"].preset_list == entries("a.milk")
    assert changed == ["layer_1"]
    mask = session.pattern_mask
    assert (mask.enabled, mask.type, mask.feather_pct, mask.transition) == (
        False,
        "stripes",
        5,
        2.0,
    )


def test_a_new_command_clears_redo() -> None:
    session = _session()
    history = EditHistory(session)
    with history.recording("Snap clips"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    history.undo()
    with history.recording("Set cut type"):
        session.timeline.lanes["layer_1"] = _lane(4.0)
    assert history.can_redo is False


def test_history_is_bounded() -> None:
    session = _session()
    history = EditHistory(session)
    for index in range(30):
        with history.recording("Snap clips"):
            session.timeline.lanes["layer_1"] = _lane(float(index + 2))
    undone = 0
    while history.undo() is not None:
        undone += 1
    assert undone == 20


def test_undo_and_redo_labels_name_the_command() -> None:
    session = _session()
    history = EditHistory(session)
    assert history.undo_label is None
    assert history.redo_label is None
    with history.recording("Generate timeline"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    assert history.undo_label == "Generate timeline"
    assert history.redo_label is None
    history.undo()
    assert history.undo_label is None
    assert history.redo_label == "Generate timeline"


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_edits_with_one_merge_key_fold_into_one_entry() -> None:
    session = _session()
    clock = _Clock()
    history = EditHistory(session, clock=clock)
    for t in (2.0, 3.0, 4.0):
        clock.now += 0.2
        with history.recording("Cue level", merge_key=("level", "layer_1", 1.0)):
            session.timeline.lanes["layer_1"] = _lane(t)
    assert history.undo() == "Cue level"
    assert session.timeline.lanes["layer_1"].cues[0].t == 1.0
    assert history.can_undo is False


def test_edits_past_the_merge_window_stay_separate() -> None:
    session = _session()
    clock = _Clock()
    history = EditHistory(session, clock=clock)
    key = ("level", "layer_1", 1.0)
    with history.recording("Cue level", merge_key=key):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    clock.now += 5.0
    with history.recording("Cue level", merge_key=key):
        session.timeline.lanes["layer_1"] = _lane(3.0)
    history.undo()
    assert session.timeline.lanes["layer_1"].cues[0].t == 2.0


def test_a_different_merge_key_starts_a_new_entry() -> None:
    session = _session()
    history = EditHistory(session, clock=_Clock())
    with history.recording("Cue level", merge_key=("level", "layer_1", 1.0)):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    with history.recording("Cue cut", merge_key=("cut", "layer_1", 1.0)):
        session.timeline.lanes["layer_1"] = _lane(3.0)
    assert history.undo() == "Cue cut"
    assert history.undo() == "Cue level"


def test_an_edit_outside_the_history_breaks_a_merge() -> None:
    session = _session()
    history = EditHistory(session, clock=_Clock())
    key = ("level", "layer_1", 1.0)
    with history.recording("Cue level", merge_key=key):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    session.timeline.lanes["layer_1"] = _lane(5.0)
    with history.recording("Cue level", merge_key=key):
        session.timeline.lanes["layer_1"] = _lane(6.0)
    assert history.undo() == "Cue level"
    assert session.timeline.lanes["layer_1"].cues[0].t == 5.0
    assert history.can_undo is False


def test_begin_and_commit_span_frames_and_block_undo_meanwhile() -> None:
    session = _session()
    history = EditHistory(session)
    with history.recording("Snap clips"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    history.begin("Record take")
    session.timeline.lanes["layer_1"] = _lane(3.0)
    assert history.pending is True
    assert history.can_undo is False
    history.commit()
    assert history.undo() == "Record take"
    assert session.timeline.lanes["layer_1"].cues[0].t == 2.0


def test_cancel_drops_the_pending_edit() -> None:
    session = _session()
    history = EditHistory(session)
    history.begin("Move cue")
    history.cancel()
    assert history.pending is False
    assert history.can_undo is False


def test_undo_restores_the_selection_but_selection_alone_is_no_edit() -> None:
    session = _session()
    history = EditHistory(session)
    session.timeline.selected_clip_t = {"layer_1": 1.0}
    with history.recording("Move cue"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
        session.timeline.selected_clip_t = {"layer_1": 2.0}
    with history.recording("Select"):
        session.timeline.selected_clip_t = {}
    assert history.undo() == "Move cue"
    assert session.timeline.selected_clip_t == {"layer_1": 1.0}
    assert history.redo() == "Move cue"
    assert session.timeline.selected_clip_t == {"layer_1": 2.0}


def test_preset_list_edits_carry_their_layer_scope() -> None:
    session = _session()
    history = EditHistory(session)
    with history.recording("Remove preset", scope=preset_list_scope("layer_1")):
        session.layers["layer_1"].preset_list = []
    assert history.undo_scopes == {preset_list_scope("layer_1")}
    assert history.undo() == "Remove preset"
    assert session.layers["layer_1"].preset_list == entries("a.milk")
    assert history.redo_scopes == {preset_list_scope("layer_1")}


def test_a_locked_scope_blocks_only_its_own_entries() -> None:
    session = _session()
    locked: set[tuple[str, ...]] = {preset_list_scope("layer_1")}
    history = EditHistory(session, scope_locked=lambda scope: scope in locked)
    with history.recording("Remove preset", scope=preset_list_scope("layer_1")):
        session.layers["layer_1"].preset_list = []
    assert history.undo_locked is True
    with history.recording("Snap clips"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    assert history.undo_scopes == {TIMELINE_SCOPE}
    assert history.undo_locked is False


def test_edits_in_different_scopes_do_not_merge() -> None:
    session = _session()
    history = EditHistory(session, clock=lambda: 0.0)
    with history.recording("Move", merge_key="k", scope=preset_list_scope("layer_1")):
        session.layers["layer_1"].preset_list = entries("b.milk")
    with history.recording("Move", merge_key="k"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    history.undo()
    assert session.layers["layer_1"].preset_list == entries("b.milk")


def test_an_edit_in_two_sections_waits_on_either_lock() -> None:
    session = _session()
    locked: set[tuple[str, ...]] = set()
    history = EditHistory(session, scope_locked=lambda scope: scope in locked)
    with history.recording("Delete clip"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
        session.layers["layer_1"].preset_list = entries("b.milk")
    assert not history.undo_locked
    for scope in (TIMELINE_SCOPE, preset_list_scope("layer_1")):
        locked.clear()
        locked.add(scope)
        assert history.undo_locks == {scope}


def test_a_refused_edit_is_put_back_and_not_recorded() -> None:
    session = _session()
    said: list[str] = []
    history = EditHistory(
        session, refuse=lambda _before: "Unlock it", on_refused=said.append
    )
    with history.recording("Move cue") as edit:
        session.timeline.lanes["layer_1"] = _lane(2.0)
    assert edit.refused == "Unlock it" and said == ["Unlock it"]
    assert session.timeline.lanes["layer_1"] == _lane(1.0)
    assert not history.can_undo


def test_a_merged_run_that_ends_where_it_began_is_dropped() -> None:
    session = _session()
    history = EditHistory(session, clock=lambda: 0.0)
    for t in (2.0, 1.0):
        with history.recording("Trim clip", merge_key="k"):
            session.timeline.lanes["layer_1"] = _lane(t)
    assert not history.can_undo
