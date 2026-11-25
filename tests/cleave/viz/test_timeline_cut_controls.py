"""Setting cut types on clip edges."""

from __future__ import annotations

from cleave.preset_list_entry import PresetListEntry
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.timeline_cut_controls import apply_cut_to_lanes


def test_setting_a_cut_keeps_presets_and_preset_changes() -> None:
    preset = PresetListEntry("/tmp/presets/a.milk")
    cues = [
        SlotCue(0.0, 1.0, role="lead", blend="black-key", preset=preset),
        SlotCue(10.0, 1.0, role="lead", blend="black-key", recast=True),
        SlotCue(20.0, 0.5, anchor=True),
        SlotCue(30.0, 0.0),
    ]
    lanes = {"layer_1": TimelineLane(baseline=0.0, cues=list(cues))}
    assert apply_cut_to_lanes(lanes, "soft", song_marker_times=(), scope="all") == 4
    after = lanes["layer_1"].cues
    assert [cue.cut for cue in after] == ["soft"] * 4
    assert after[0].preset == preset
    assert after[1].recast
    assert after[2].anchor
