"""Undo and redo of bulk timeline commands."""

from __future__ import annotations

from types import SimpleNamespace

from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.timeline_history import TimelineHistory


def _lane(*times: float) -> TimelineLane:
    return TimelineLane(
        baseline=None, cues=[SlotCue(t=t, level=1.0) for t in times]
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        timeline=SimpleNamespace(lanes={"layer_1": _lane(1.0)}, enabled=True),
        layers={"layer_1": SimpleNamespace(preset_list=["a.milk"])},
        pattern_mask=SimpleNamespace(
            enabled=False, type="stripes", feather_pct=5, transition=2.0
        ),
    )


def test_undo_and_redo_restore_lanes() -> None:
    session = _session()
    history = TimelineHistory(session)
    with history.recording("Snap cues"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    assert history.can_undo is True
    assert history.undo() == "Snap cues"
    assert session.timeline.lanes["layer_1"].cues[0].t == 1.0
    assert history.can_undo is False
    assert history.redo() == "Snap cues"
    assert session.timeline.lanes["layer_1"].cues[0].t == 2.0


def test_a_command_that_changes_nothing_is_not_recorded() -> None:
    session = _session()
    history = TimelineHistory(session)
    with history.recording("Snap cues"):
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
        session.layers["layer_1"].preset_list[:] = ["b.milk"]
        session.pattern_mask.enabled = True
        session.pattern_mask.type = "strips"
        session.pattern_mask.feather_pct = 0
        session.pattern_mask.transition = 1.0
    history.undo()
    assert session.timeline.enabled is True
    assert session.layers["layer_1"].preset_list == ["a.milk"]
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
    with history.recording("Snap cues"):
        session.timeline.lanes["layer_1"] = _lane(2.0)
    history.undo()
    with history.recording("Set cut type"):
        session.timeline.lanes["layer_1"] = _lane(4.0)
    assert history.can_redo is False


def test_history_is_bounded() -> None:
    session = _session()
    history = TimelineHistory(session)
    for index in range(30):
        with history.recording("Snap cues"):
            session.timeline.lanes["layer_1"] = _lane(float(index + 2))
    undone = 0
    while history.undo() is not None:
        undone += 1
    assert undone == 20
