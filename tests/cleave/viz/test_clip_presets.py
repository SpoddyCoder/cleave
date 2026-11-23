"""Presets held on timeline clips: seeding, laying out, and keeping list and clips in step."""

from __future__ import annotations

import math

from cleave.timeline import SlotCue, TimelineLane, lane_clips
from cleave.viz.clip_presets import (
    clip_preset_list,
    clip_preset_view,
    fill_missing_clip_presets,
    lay_out_list_as_clips,
    seed_timeline_from_switching,
    sync_each_clip_layers,
    timeline_is_empty,
)
from cleave.viz.preset_switching import clip_switch_at
from tests.support.preset_list import entries
from tests.support.viz import make_controls

A, B, C = entries("/p/a.milk", "/p/b.milk", "/p/c.milk")


def _timer_controls(duration_sec: float = 100.0):
    controls = make_controls(("layer_1", "layer_2"), duration_sec=duration_sec)
    timer = controls.session.layers["layer_1"]
    timer.preset_switching = "on"
    timer.preset_switching_trigger = "timer"
    timer.preset_duration = 30.0
    timer.preset_list = [A, B]
    controls.session.timeline.enabled = False
    controls.session.timeline.lanes = {}
    return controls


def test_seeding_keeps_the_timer_schedule_exactly() -> None:
    controls = _timer_controls()
    session = controls.session
    timer = session.layers["layer_1"]
    before = {
        t: timer.preset_list[math.floor(t / 30.0) % 2].file
        for t in (0.0, 29.9, 30.0, 59.0, 61.0, 99.0)
    }
    converted = seed_timeline_from_switching(session, 100.0)
    assert converted == ["layer_1"]
    assert timer.preset_switching_trigger == "timeline"
    lane = session.timeline.lanes["layer_1"]
    assert [cue.t for cue in lane.cues] == [0.0, 30.0, 60.0, 90.0]
    assert all(cue.cut == "none" for cue in lane.cues)
    session.timeline.enabled = True
    for t, path in before.items():
        assert clip_switch_at(session, "layer_1", t)[1] == path, t
    # The other layer is one whole-song clip and keeps its switching.
    other = session.timeline.lanes["layer_2"]
    assert other.baseline == 1.0 and other.cues == []
    assert not timeline_is_empty(session)


def test_seeding_leaves_a_disabled_layer_off() -> None:
    controls = _timer_controls()
    controls.session.layers["layer_1"].enabled = False
    assert seed_timeline_from_switching(controls.session, 100.0) == []
    assert controls.session.timeline.lanes["layer_1"].baseline == 0.0


def test_turning_the_timeline_on_seeds_once_and_undo_restores_the_timer() -> None:
    controls = _timer_controls()
    controls.set_timeline_enabled(True)
    layer = controls.session.layers["layer_1"]
    assert layer.preset_switching_trigger == "timeline"
    assert [entry.file for entry in layer.preset_list] == [
        A.file, B.file, A.file, B.file,
    ]
    assert controls.build_view_state(paused=True).notification_message == (
        "Timeline controls layer visibility. Layer 1 now changes preset on "
        "each clip, at the same times"
    )
    controls.edit_history.undo()
    assert layer.preset_switching_trigger == "timer"
    assert layer.preset_list == [A, B]
    assert not controls.session.timeline.enabled


def test_lay_out_runs_the_last_clip_to_the_song_end() -> None:
    controls = _timer_controls(duration_sec=45.0)
    assert lay_out_list_as_clips(controls.session, "layer_1", 45.0, [A, B, C]) == 2
    clips = lane_clips(
        controls.session.timeline.lanes["layer_1"], inherit=1.0, duration_sec=45.0
    )
    assert [(clip.start, clip.end) for clip in clips] == [(0.0, 30.0), (30.0, 45.0)]
    assert clip_preset_list(controls.session, "layer_1", 45.0) == [A, B]


def _each_clip_session(*cues: SlotCue):
    controls = make_controls(("layer_1",), duration_sec=100.0)
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timeline"
    session.timeline.enabled = True
    session.timeline.lanes["layer_1"] = TimelineLane(baseline=0.0, cues=list(cues))
    return session


def test_fill_missing_takes_list_presets_in_order_then_picks() -> None:
    session = _each_clip_session(
        SlotCue(t=0.0, level=1.0, preset=A),
        SlotCue(t=10.0, level=0.0),
        SlotCue(t=20.0, level=1.0),
        SlotCue(t=30.0, level=0.0),
        SlotCue(t=40.0, level=1.0),
    )
    picked: list[str] = []

    def pick(slot, role):
        picked.append(slot)
        return C

    filled = fill_missing_clip_presets(
        session, "layer_1", 100.0, pick, from_entries=[B]
    )
    assert filled == 2
    assert picked == ["layer_1"]
    assert clip_preset_list(session, "layer_1", 100.0) == [A, B, C]


def test_sync_pushes_a_list_edit_onto_the_clips() -> None:
    session = _each_clip_session(
        SlotCue(t=0.0, level=1.0, preset=A),
        SlotCue(t=10.0, level=1.0, recast=True, preset=B),
    )
    layer = session.layers["layer_1"]
    layer.preset_list = [A, B]
    before = {"layer_1": [A, B]}
    layer.preset_list[1] = C
    assert sync_each_clip_layers(session, 100.0, before, None) == ["layer_1"]
    assert clip_preset_list(session, "layer_1", 100.0) == [A, C]


def test_sync_gives_a_new_clip_a_preset_and_mirrors_the_list() -> None:
    session = _each_clip_session(
        SlotCue(t=0.0, level=1.0, preset=A),
        SlotCue(t=10.0, level=0.0),
        SlotCue(t=20.0, level=1.0),
    )
    layer = session.layers["layer_1"]
    layer.preset_list = [A]
    changed = sync_each_clip_layers(
        session, 100.0, {"layer_1": [A]}, lambda _slot, _role: B
    )
    assert changed == ["layer_1"]
    assert layer.preset_list == [A, B]


def test_split_continues_and_the_view_says_so() -> None:
    controls = make_controls(("layer_1",), duration_sec=100.0)
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timeline"
    session.timeline.enabled = True
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0, cues=[SlotCue(t=0.0, level=1.0, preset=A)]
    )
    assert controls.clip_editor.split_at("layer_1", 50.0)
    second = controls.clip_editor.selected("layer_1")
    assert second is not None and second.start == 50.0
    view = clip_preset_view(session, "layer_1", second, 100.0)
    assert view.starts is False and view.butted is True and view.name == "a.milk"
    assert clip_switch_at(session, "layer_1", 60.0)[1] == A.file


def test_a_new_clip_against_another_starts_its_own_preset() -> None:
    controls = make_controls(("layer_1",), duration_sec=100.0)
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timeline"
    session.timeline.enabled = True
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0,
        cues=[SlotCue(t=0.0, level=1.0, preset=A), SlotCue(t=10.0, level=0.0)],
    )
    controls._clip_preset_pick = lambda _slot, _role: B  # type: ignore[assignment]
    controls.clip_editor._pick_preset = controls._clip_preset_pick
    assert controls.clip_editor.add_clip_at("layer_1", 10.0)
    added = controls.clip_editor.selected("layer_1")
    assert added is not None
    assert clip_preset_view(session, "layer_1", added, 100.0).starts is True
    assert clip_preset_list(session, "layer_1", 100.0) == [A, B]
    assert layer.preset_list == [A, B]
