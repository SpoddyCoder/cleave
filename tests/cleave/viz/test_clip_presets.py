"""Presets held on timeline clips: seeding, and keeping list and clips in step."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleave.timeline import SlotCue, TimelineLane, lane_clips
from cleave.viz.clip_presets import (
    clip_preset_list,
    clip_preset_view,
    deal_list_onto_clips,
    row_switching_clips,
    spare_preset_count,
)
from cleave.viz.preset_switching import clip_switch_at
from tests.support.preset_list import entries
from tests.support.viz import make_controls

A, B, C, D = entries("/p/a.milk", "/p/b.milk", "/p/c.milk", "/p/d.milk")


def _controls(*presets, spares=()):
    """One each-clip layer: a 10 s clip every 20 s, holding ``presets``."""
    controls = make_controls(("layer_1",), duration_sec=100.0)
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timeline"
    layer.preset_list = [*(p for p in presets if p is not None), *spares]
    session.timeline.enabled = True
    cues = []
    for index, preset in enumerate(presets):
        cues += [
            SlotCue(t=index * 20.0, level=1.0, preset=preset),
            SlotCue(t=index * 20.0 + 10.0, level=0.0),
        ]
    session.timeline.lanes["layer_1"] = TimelineLane(baseline=0.0, cues=cues)
    return controls


def _held(controls):
    return [
        clip.preset
        for clip in row_switching_clips(controls.session, "layer_1", 100.0)
    ]


def _list(controls):
    return controls.session.layers["layer_1"].preset_list


@pytest.mark.parametrize(
    ("index", "held"),
    [(0, [B, C, None]), (1, [A, C, None]), (2, [A, B, None])],
)
def test_removing_an_entry_moves_the_later_presets_up(index, held) -> None:
    controls = _controls(A, B, C)
    controls.preset_list.remove("layer_1", index)
    assert _held(controls) == held
    assert _list(controls) == [p for p in held if p is not None]
    controls.edit_history.undo()
    assert _held(controls) == _list(controls) == [A, B, C]
    controls.edit_history.redo()
    assert _held(controls) == held


def test_duplicating_mid_list_flows_and_leaves_a_spare() -> None:
    controls = _controls(A, B)
    controls.preset_list.duplicate("layer_1", 0)
    assert _held(controls) == [A, A]
    assert _list(controls) == [A, A, B]
    assert spare_preset_count(controls.session, "layer_1", 100.0) == 1


def test_duplicate_presets_each_keep_their_clip() -> None:
    controls = _controls(A, A, B)
    controls.preset_list.remove("layer_1", 0)
    assert _held(controls) == [A, B, None]


def test_reordering_changes_presets_in_place_and_keeps_empty_clips() -> None:
    controls = _controls(A, None, B)
    controls.preset_list.move_item("layer_1", 0, 1)
    assert _held(controls) == [B, None, A]


def test_appending_fills_the_empty_clip_and_moves_no_other() -> None:
    controls = _controls(A, None, B)
    with controls.edit_history.recording("Add"):
        _list(controls).append(C)
    assert _held(controls) == [A, C, B]
    assert _list(controls) == [A, C, B]


def test_removing_a_spare_changes_no_clip() -> None:
    controls = _controls(A, B, spares=(C, D))
    controls.preset_list.remove("layer_1", 2)
    assert _held(controls) == [A, B]
    assert _list(controls) == [A, B, D]


def test_clearing_empties_every_clip() -> None:
    controls = _controls(A, B)
    controls.preset_list.clear("layer_1")
    assert _held(controls) == [None, None]
    controls.edit_history.undo()
    assert _held(controls) == [A, B]


def test_deleting_a_clip_makes_its_preset_the_last_spare() -> None:
    controls = _controls(A, B, C, spares=(D,))
    controls.session.timeline.selected_clip_t["layer_1"] = 20.0
    controls.clip_editor.delete_selected("layer_1")
    assert _held(controls) == [A, C]
    assert _list(controls) == [A, C, D, B]
    controls.edit_history.undo()
    assert _held(controls) == [A, B, C]
    assert _list(controls) == [A, B, C, D]


def test_a_new_clip_takes_the_first_spare_else_stays_empty() -> None:
    controls = _controls(A, B, spares=(C,))
    assert controls.clip_editor.add_clip_at("layer_1", 12.0)
    assert _held(controls) == [A, C, B]
    assert _list(controls) == [A, C, B]
    assert controls.clip_editor.add_clip_at("layer_1", 40.0)
    assert _held(controls) == [A, C, B, None]
    view = clip_preset_view(
        controls.session, "layer_1", controls.clip_editor.selected("layer_1"), 100.0
    )
    assert view.empty and view.name == "b.milk"


def test_choosing_a_clip_preset_leaves_no_spare() -> None:
    controls = _controls(A, None, B)
    controls.session.timeline.selected_clip_t["layer_1"] = 0.0
    controls.clip_editor.set_preset("layer_1", C)
    assert _held(controls) == [C, None, B]
    assert _list(controls) == [C, B]
    controls.session.timeline.selected_clip_t["layer_1"] = 20.0
    controls.clip_editor.set_preset("layer_1", D)
    assert _held(controls) == [C, D, B]
    assert _list(controls) == [C, D, B]


def test_browsing_an_empty_clip_assigns_the_chosen_preset() -> None:
    controls = _controls(A, None)
    controls.session.timeline.selected_clip_t["layer_1"] = 20.0
    controls.preset_list.adopt = lambda _path: C  # type: ignore[method-assign]
    controls._choose_clip_preset("layer_1", Path("/p/c.milk"))
    assert _held(controls) == [A, C]


def test_an_empty_butted_clip_still_starts_a_preset() -> None:
    controls = _controls()
    session = controls.session
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=0.0, level=1.0, preset=A),
            SlotCue(t=10.0, level=1.0, recast=True, preset=B),
        ],
    )
    _list(controls)[:] = [A, B]
    controls.preset_list.remove("layer_1", 1)
    assert _held(controls) == [A, None]
    # Continuing on purpose is not empty, and starting again takes the spare.
    with controls.edit_history.recording("Add"):
        _list(controls).append(C)
    session.timeline.selected_clip_t["layer_1"] = 10.0
    controls.clip_editor.set_starts_preset("layer_1", False)
    assert _held(controls) == [A]
    assert _list(controls) == [A, C]
    controls.clip_editor.set_starts_preset("layer_1", True)
    assert _held(controls) == [A, C]
    assert _list(controls) == [A, C]


def test_empty_clips_play_the_preset_before_them_from_any_seek() -> None:
    session = _controls(None, A, None, B).session
    assert clip_switch_at(session, "layer_1", 5.0) == (0, A.file)
    assert clip_switch_at(session, "layer_1", 45.0) == (0, A.file)
    assert clip_switch_at(session, "layer_1", 65.0) == (1, B.file)
    assert clip_switch_at(session, "layer_1", 45.0) == (0, A.file)


def test_seeding_gives_whole_song_clips_and_keeps_the_timer() -> None:
    controls = make_controls(("layer_1", "layer_2"), duration_sec=100.0)
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = [A, B]
    session.layers["layer_2"].enabled = False
    session.timeline.enabled = False
    session.timeline.lanes = {}
    controls.set_timeline_enabled(True)
    assert layer.preset_switching_trigger == "timer"
    assert layer.preset_list == [A, B]
    assert session.timeline.lanes["layer_1"].baseline == 1.0
    assert session.timeline.lanes["layer_2"].baseline == 0.0


@pytest.mark.parametrize("previous", ["off", "projectm"])
def test_entering_each_clip_deals_the_list_onto_the_clips_there_are(previous) -> None:
    controls = _controls(D, None)
    layer = controls.session.layers["layer_1"]
    layer.preset_switching_trigger = previous
    layer.preset_list = [A, B, C]
    controls.layer_mutations.set_preset_switching_trigger("layer_1", "timeline")
    view = controls.modal_host.view_state()
    assert view is not None and view.body == (
        "This layer's clips are not cut.\n1 clip loses its earlier preset.\n"
        "1 preset in the list has no clip.\nUndo puts everything back."
    )
    controls.modal_host.activate_option(0)
    assert _held(controls) == [A, B]
    assert _list(controls) == [A, B, C]
    controls.edit_history.undo()
    assert layer.preset_switching_trigger == previous
    assert _held(controls) == [D, None]


def test_entering_each_clip_from_the_timer_cuts_the_row_in_one_undo_step() -> None:
    controls = _controls()
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching_trigger = "timer"
    layer.preset_duration = 30.0
    layer.preset_list = [A, B]
    session.timeline.lanes["layer_1"] = TimelineLane(baseline=1.0, cues=[])
    controls.convert_to_each_clip("layer_1")
    view = controls.modal_host.view_state()
    assert view is not None and view.body == (
        "1 clip on this layer is cut into 4, where the timer changes preset.\n"
        "Undo puts everything back."
    )
    # Asking changes nothing, and Cancel leaves the layer on its timer.
    assert layer.preset_switching_trigger == "timer"
    assert layer.preset_list == [A, B]
    assert session.timeline.lanes["layer_1"] == TimelineLane(baseline=1.0, cues=[])
    controls.modal_host.cancel()
    assert layer.preset_switching_trigger == "timer"
    controls.convert_to_each_clip("layer_1")
    controls.modal_host.activate_option(0)
    assert _held(controls) == _list(controls) == [A, B, A, B]
    clips = lane_clips(
        session.timeline.lanes["layer_1"], inherit=1.0, duration_sec=100.0
    )
    assert [clip.start for clip in clips] == [0.0, 30.0, 60.0, 90.0]
    controls.edit_history.undo()
    assert layer.preset_switching_trigger == "timer"
    assert layer.preset_list == [A, B]


def test_dealing_a_short_list_leaves_the_last_clips_empty() -> None:
    controls = _controls(A, B, C)
    _list(controls)[:] = [D]
    deal_list_onto_clips(controls.session, "layer_1", 100.0)
    assert _held(controls) == [D, None, None]
    assert clip_preset_list(controls.session, "layer_1", 100.0) == [D]


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


def test_entering_each_clip_asks_nothing_when_nothing_is_lost() -> None:
    controls = _controls(None, None)
    layer = controls.session.layers["layer_1"]
    layer.preset_switching_trigger = "projectm"
    layer.preset_list = [A, B]
    controls.layer_mutations.set_preset_switching_trigger("layer_1", "timeline")
    assert not controls.modal_host.active
    assert _held(controls) == [A, B]


def test_the_prompt_says_which_presets_and_timeline_state_change() -> None:
    controls = _controls()
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching_trigger = "timer"
    layer.preset_duration = 60.0
    layer.preset_list = [A, B, C]
    session.timeline.enabled = False
    session.timeline.lanes = {}
    controls.convert_to_each_clip("layer_1")
    view = controls.modal_host.view_state()
    assert view is not None and view.body == (
        "The timeline turns on and decides when every layer shows.\n"
        "1 clip on this layer is cut into 2, where the timer changes preset.\n"
        "1 preset the timer never shows leaves the preset list.\n"
        "Undo puts everything back."
    )
    assert session.timeline.lanes == {} and not session.timeline.enabled


def test_entering_from_an_empty_timer_list_clears_old_clip_presets() -> None:
    controls = _controls(A, B)
    layer = controls.session.layers["layer_1"]
    layer.preset_switching_trigger = "timer"
    layer.preset_list = []
    controls.convert_to_each_clip("layer_1")
    controls.modal_host.activate_option(0)
    assert _held(controls) == [None, None] and _list(controls) == []
