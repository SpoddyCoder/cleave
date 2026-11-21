"""Undo and redo of timeline edits."""

from __future__ import annotations

from types import SimpleNamespace

from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.timeline_history import TimelineHistory
from tests.support.preset_list import entries


def _lane(*times: float) -> TimelineLane:
    return TimelineLane(
        baseline=None, cues=[SlotCue(t=t, level=1.0) for t in times]
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        timeline=SimpleNamespace(
            lanes={"layer_1": _lane(1.0)}, enabled=True, selected_clip_t={}
        ),
        layers={"layer_1": SimpleNamespace(preset_list=entries("a.milk"))},
        pattern_mask=SimpleNamespace(
            enabled=False, type="stripes", feather_pct=5, transition=2.0
        ),
    )


def test_undo_and_redo_restore_lanes() -> None:
    session = _session()
    history = TimelineHistory(session)
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
    history = TimelineHistory(session)
    with history.recording("Snap clips"):
        pass
    assert history.can_undo is False


def test_a_hand_edit_after_the_command_blocks_undo() -> None:
    session = _session()
    history = TimelineHistory(session)
    with history.recording("Generate timeline"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    session.timeline.lanes["layer_1"] = _lane(3.0)
    assert history.can_undo is False
    assert history.undo() is None
    assert session.timeline.lanes["layer_1"].cues[0].t == 3.0


def test_adding_a_layer_blocks_undo() -> None:
    session = _session()
    history = TimelineHistory(session)
    with history.recording("Reset timeline"):
        session.timeline.lanes["layer_1"] = _lane()
    session.timeline.lanes["layer_2"] = _lane()
    assert history.can_undo is False


def test_undo_restores_everything_generate_touches() -> None:
    session = _session()
    changed: list[str] = []
    history = TimelineHistory(session, on_preset_list_change=changed.append)
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
    history = TimelineHistory(session)
    with history.recording("Snap clips"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    history.undo()
    with history.recording("Set cut type"):
        session.timeline.lanes["layer_1"] = _lane(4.0)
    assert history.can_redo is False


def test_history_is_bounded() -> None:
    session = _session()
    history = TimelineHistory(session)
    for index in range(30):
        with history.recording("Snap clips"):
            session.timeline.lanes["layer_1"] = _lane(float(index + 2))
    undone = 0
    while history.undo() is not None:
        undone += 1
    assert undone == 20


def test_undo_and_redo_labels_name_the_command() -> None:
    session = _session()
    history = TimelineHistory(session)
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
    history = TimelineHistory(session, clock=clock)
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
    history = TimelineHistory(session, clock=clock)
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
    history = TimelineHistory(session, clock=_Clock())
    with history.recording("Cue level", merge_key=("level", "layer_1", 1.0)):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    with history.recording("Cue cut", merge_key=("cut", "layer_1", 1.0)):
        session.timeline.lanes["layer_1"] = _lane(3.0)
    assert history.undo() == "Cue cut"
    assert history.undo() == "Cue level"


def test_an_edit_outside_the_history_breaks_a_merge() -> None:
    session = _session()
    history = TimelineHistory(session, clock=_Clock())
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
    history = TimelineHistory(session)
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
    history = TimelineHistory(session)
    history.begin("Move cue")
    history.cancel()
    assert history.pending is False
    assert history.can_undo is False


def test_undo_restores_the_selection_but_selection_alone_is_no_edit() -> None:
    session = _session()
    history = TimelineHistory(session)
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
