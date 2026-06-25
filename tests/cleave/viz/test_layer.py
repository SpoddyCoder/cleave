"""Unit tests for layer visibility and timeline integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pygame

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import TimelineCue
from cleave.viz.session import LayerRuntime, TimelineRuntime, TuningSession
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.layer import StemLayer
from cleave.viz.layer_visibility import (
    apply_layer_visibility,
    armed_recording_visible,
    build_record_punch_cues,
    build_timeline_view_state,
    committed_visible_outside_punch,
    effective_layer_enabled,
    snapshot_monitor_from_timeline,
    timeline_committed_visible,
    timeline_defaults,
)
from cleave.viz.timeline_overlay import (
    bar_segments_for_row,
    bar_tick_times_for_row,
    cue_times_for_stem,
)
from tests.support.viz import keydown, make_controls


def _playlist(name: str) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{name}")
    paths = tuple(current_dir / f"preset-{i}.milk" for i in range(2))
    return PresetPlaylist(current_dir=current_dir, paths=paths, index=0)


DEFAULT_LAYER_SLOTS_LIST = list(DEFAULT_LAYER_SLOTS)


def _session(
    *,
    layer_enabled: dict[str, bool] | None = None,
    timeline_enabled: bool = False,
    cues: list[TimelineCue] | None = None,
    solo_slot: str | None = None,
) -> TuningSession:
    enabled = layer_enabled or {slot: True for slot in DEFAULT_LAYER_SLOTS}
    return TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        solo_slot=solo_slot,
        timeline=TimelineRuntime(
            enabled=timeline_enabled,
            cues=list(cues or []),
        ),
        layers={
            slot: LayerRuntime(
                playlist=_playlist(slot),
                browse_floor=Path(f"/tmp/presets/{slot}"),
                stem=TEST_LAYER_STEMS[slot],
                enabled=enabled[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
    )


def _stem_layer(slot: str) -> StemLayer:
    return StemLayer(
        slot=slot,
        pm=MagicMock(),
        fbo=MagicMock(enabled=True),
        playlist=_playlist(slot),
    )


def test_timeline_defaults_from_layer_runtime() -> None:
    session = _session(layer_enabled={"layer_1": False, "layer_2": True, "layer_3": True, "layer_4": False})
    assert timeline_defaults(session) == {
        "layer_1": False,
        "layer_2": True,
        "layer_3": True,
        "layer_4": False,
    }


def test_effective_layer_enabled_uses_layer_when_timeline_off() -> None:
    session = _session(layer_enabled={"layer_1": False, "layer_2": True, "layer_3": True, "layer_4": True})
    assert effective_layer_enabled(session, "layer_1", 0.0) is False
    assert effective_layer_enabled(session, "layer_2", 99.0) is True


def test_effective_layer_enabled_uses_cues_when_timeline_on() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=5.0, layers={"layer_1": False})],
    )
    assert effective_layer_enabled(session, "layer_1", 4.9) is True
    assert effective_layer_enabled(session, "layer_1", 5.0) is False
    assert effective_layer_enabled(session, "layer_2", 5.0) is True


def test_effective_layer_enabled_defaults_before_first_cue() -> None:
    session = _session(
        layer_enabled={"layer_1": False, "layer_2": True, "layer_3": False, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=10.0, layers={"layer_1": True})],
    )
    assert effective_layer_enabled(session, "layer_1", 0.0) is False
    assert effective_layer_enabled(session, "layer_2", 9.9) is True


def test_effective_layer_enabled_override_manual_override() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False, "layer_2": False})],
    )
    session.timeline.override_slots = {"layer_2"}
    session.timeline.override_visible = {"layer_2": True}
    assert effective_layer_enabled(session, "layer_1", 0.0) is False
    assert effective_layer_enabled(session, "layer_2", 0.0) is True


def test_effective_layer_enabled_override_when_paused() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_2": False})],
    )
    session.timeline.override_slots = {"layer_2"}
    session.timeline.override_visible = {"layer_2": True}
    assert effective_layer_enabled(session, "layer_2", 0.0) is True


def test_effective_layer_enabled_override_ignored_when_preview_active() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_2": False})],
    )
    session.timeline.preview_active = True
    session.timeline.monitor = {"layer_2": False}
    session.timeline.override_slots = {"layer_2"}
    session.timeline.override_visible = {"layer_2": True}
    assert effective_layer_enabled(session, "layer_2", 0.0) is False


def test_effective_layer_enabled_multiple_override_slots() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False, "layer_2": False, "layer_3": False})],
    )
    session.timeline.override_slots = {"layer_1", "layer_2"}
    session.timeline.override_visible = {"layer_1": True, "layer_2": False}
    assert effective_layer_enabled(session, "layer_1", 0.0) is True
    assert effective_layer_enabled(session, "layer_2", 0.0) is False
    assert effective_layer_enabled(session, "layer_3", 0.0) is False


def test_effective_layer_enabled_solo_overrides_timeline() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False, "layer_2": False})],
        solo_slot="layer_1",
    )
    assert effective_layer_enabled(session, "layer_1", 0.0) is True
    assert effective_layer_enabled(session, "layer_2", 0.0) is False


def test_effective_layer_enabled_uses_record_buffer_while_recording() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
    )
    session.timeline.recording = True
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = [TimelineCue(t=1.0, layers={"layer_1": False})]
    assert effective_layer_enabled(session, "layer_1", 1.0) is False
    assert effective_layer_enabled(session, "layer_2", 1.0) is True


def test_effective_layer_enabled_override_persists_for_unarmed_while_recording() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_2": True, "layer_3": True})],
    )
    session.timeline.recording = True
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.override_slots = {"layer_2", "layer_3"}
    session.timeline.override_visible = {"layer_2": False, "layer_3": False}
    assert effective_layer_enabled(session, "layer_2", 1.0) is False
    assert effective_layer_enabled(session, "layer_3", 1.0) is False


def test_timeline_cues_for_eval_merges_buffer_while_recording() -> None:
    session = _session(timeline_enabled=True, cues=[TimelineCue(t=0.0, layers={"layer_1": False})])
    session.timeline.recording = True
    session.timeline.record_buffer = [TimelineCue(t=1.0, layers={"layer_2": False})]
    tl = session.timeline
    merged = tl.cues + tl.record_buffer if tl.recording else tl.cues
    assert len(merged) == 2
    assert merged[0].t == 0.0
    assert merged[1].t == 1.0


def test_build_timeline_view_state_uses_record_buffer_while_recording() -> None:
    session = _session(
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False})],
    )
    session.timeline.recording = True
    session.timeline.record_buffer = [TimelineCue(t=1.0, layers={"layer_2": False})]
    state = build_timeline_view_state(session, position_sec=1.0, duration_sec=60.0)
    assert len(state.cues) == 1
    assert state.cues[0].t == 0.0
    assert len(state.record_buffer) == 1
    assert state.record_buffer[0].layers == {"layer_2": False}


def test_apply_layer_visibility_sets_fbo_enabled_from_timeline() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=3.0, layers={"layer_3": False})],
    )
    layers_by_slot = {slot: _stem_layer(slot) for slot in DEFAULT_LAYER_SLOTS}

    apply_layer_visibility(session, layers_by_slot, 2.0)
    assert layers_by_slot["layer_3"].fbo.enabled is True

    apply_layer_visibility(session, layers_by_slot, 3.0)
    assert layers_by_slot["layer_3"].fbo.enabled is False
    assert layers_by_slot["layer_1"].fbo.enabled is True


def test_header_toggle_blocked_when_timeline_enabled() -> None:
    controls = make_controls(("layer_1",))
    controls.session.timeline.enabled = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    assert controls.session.layers["layer_1"].enabled is True

    controls.handle_keydown(keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))

    assert controls.session.layers["layer_1"].enabled is True
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Timeline controls layer visibility"


def test_effective_layer_enabled_preview_active_uses_monitor() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False, "layer_2": True})],
    )
    session.timeline.preview_active = True
    session.timeline.monitor = {
        "layer_1": True,
        "layer_2": False,
        "layer_3": True,
        "layer_4": False,
    }
    assert effective_layer_enabled(session, "layer_1", 0.0) is True
    assert effective_layer_enabled(session, "layer_2", 0.0) is False
    assert effective_layer_enabled(session, "layer_3", 0.0) is True
    assert effective_layer_enabled(session, "layer_4", 0.0) is False


def test_build_record_punch_cues_writes_baseline_only_when_it_differs() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False})],
    )
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = [TimelineCue(t=12.0, layers={"layer_1": False})]

    punch = build_record_punch_cues(session, record_start=10.0, record_stop=20.0)
    assert TimelineCue(t=10.0, layers={"layer_1": True}, show_tick=False) in punch
    assert TimelineCue(t=12.0, layers={"layer_1": False}) in punch

    session.timeline.record_baseline = {"layer_1": False}
    session.timeline.record_buffer = []
    assert build_record_punch_cues(session, record_start=10.0, record_stop=20.0) == []


def test_effective_layer_enabled_recording_armed_ignores_committed_cues() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"layer_1": False}),
            TimelineCue(t=11.0, layers={"layer_1": False}),
        ],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = []

    assert effective_layer_enabled(session, "layer_1", 11.5) is True
    assert armed_recording_visible(session, "layer_1", 11.5) is True
    assert timeline_committed_visible(session, "layer_1", 11.5) is False


def test_build_timeline_view_state_recording_baseline_not_in_cue_ticks() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False})],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = []

    state = build_timeline_view_state(session, position_sec=10.0, duration_sec=60.0)
    assert bar_tick_times_for_row(state, "layer_1") == [0.0]


def test_build_timeline_view_state_armed_recording_monitor_ignores_committed() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"layer_1": False}),
            TimelineCue(t=11.0, layers={"layer_1": False}),
        ],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = []

    state = build_timeline_view_state(session, position_sec=11.5, duration_sec=60.0)
    assert state.monitor_visible["layer_1"] is True
    assert state.timeline_visible["layer_1"] is False


def test_effective_layer_enabled_recording_armed_vs_unarmed() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": True, "layer_2": False})],
    )
    session.timeline.recording = True
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = [
        TimelineCue(t=1.0, layers={"layer_1": False, "layer_2": True}),
    ]
    assert effective_layer_enabled(session, "layer_1", 1.0) is False
    assert effective_layer_enabled(session, "layer_2", 1.0) is False


def test_timeline_committed_visible_ignores_record_buffer() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": True, "layer_2": False})],
    )
    session.timeline.recording = True
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_buffer = [
        TimelineCue(t=1.0, layers={"layer_1": False, "layer_2": True}),
    ]
    assert timeline_committed_visible(session, "layer_1", 1.0) is True
    assert timeline_committed_visible(session, "layer_2", 1.0) is False


def test_build_timeline_view_state_populates_visibility_playing() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=5.0, layers={"layer_1": False})],
    )
    session.timeline.override_slots = {"layer_2"}
    session.timeline.override_visible = {"layer_2": True}
    state = build_timeline_view_state(session, position_sec=5.0, duration_sec=60.0)
    assert state.monitor_visible["layer_1"] is False
    assert state.monitor_visible["layer_2"] is True
    assert state.timeline_visible["layer_1"] is False
    assert state.timeline_visible["layer_2"] is True
    assert state.override_slots == {"layer_2"}


def test_build_timeline_view_state_monitor_preview_active() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False, "layer_2": True})],
    )
    session.timeline.preview_active = True
    session.timeline.monitor = {
        "layer_1": True,
        "layer_2": False,
        "layer_3": True,
        "layer_4": False,
    }
    state = build_timeline_view_state(session, position_sec=0.0, duration_sec=60.0)
    assert state.monitor_visible == session.timeline.monitor
    assert state.timeline_visible["layer_1"] is False
    assert state.timeline_visible["layer_2"] is True


def test_snapshot_monitor_from_timeline_populates_from_committed() -> None:
    session = _session(
        layer_enabled={"layer_1": False, "layer_2": True, "layer_3": True, "layer_4": False},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=2.0, layers={"layer_1": True, "layer_3": False}),
        ],
    )
    monitor = snapshot_monitor_from_timeline(session, 2.5)
    assert monitor == {
        "layer_1": True,
        "layer_2": True,
        "layer_3": False,
        "layer_4": False,
    }


def test_armed_recording_bar_blends_committed_and_live() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"layer_1": False}),
            TimelineCue(t=11.0, layers={"layer_1": False}),
            TimelineCue(t=30.0, layers={"layer_1": True}),
        ],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = [TimelineCue(t=12.0, layers={"layer_1": False})]

    state = build_timeline_view_state(session, position_sec=12.0, duration_sec=60.0)
    segments = bar_segments_for_row(state, "layer_1")
    assert segments == [
        (0.0, 10.0, False),
        (10.0, 12.0, True),
        (12.0, 30.0, False),
        (30.0, 60.0, True),
    ]


def test_armed_recording_bar_uses_committed_timeline_after_disarm() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"layer_1": False}),
            TimelineCue(t=10.0, layers={"layer_1": True}),
            TimelineCue(t=12.0, layers={"layer_1": False}),
        ],
    )
    session.timeline.recording = False
    session.timeline.armed_slots = set()
    session.timeline.record_baseline = {}
    session.timeline.record_buffer = []

    state = build_timeline_view_state(session, position_sec=12.0, duration_sec=60.0)
    segments = bar_segments_for_row(state, "layer_1")
    assert segments == [
        (0.0, 10.0, False),
        (10.0, 12.0, True),
        (12.0, 60.0, False),
    ]
    assert effective_layer_enabled(session, "layer_1", 12.0) is False


def test_build_record_punch_cues_uses_record_baseline_when_disarmed() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False})],
    )
    session.timeline.recording = True
    session.timeline.armed_slots = set()
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = [TimelineCue(t=12.0, layers={"layer_1": False})]

    punch = build_record_punch_cues(session, record_start=10.0, record_stop=15.0)
    assert TimelineCue(t=12.0, layers={"layer_1": False}) in punch


def test_build_record_punch_cues_restores_committed_at_stop() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"layer_1": False}),
            TimelineCue(t=30.0, layers={"layer_1": True}),
        ],
    )
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": False}
    session.timeline.record_buffer = [TimelineCue(t=15.0, layers={"layer_1": True})]

    punch = build_record_punch_cues(session, record_start=10.0, record_stop=20.0)
    assert TimelineCue(t=15.0, layers={"layer_1": True}) in punch
    assert TimelineCue(t=20.0, layers={"layer_1": False}, show_tick=False) in punch
    assert timeline_committed_visible(session, "layer_1", 20.0) is False


def test_build_record_punch_cues_restores_when_disable_only_inside_punch() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=15.0, layers={"layer_1": False}),
            TimelineCue(t=25.0, layers={"layer_1": True}),
        ],
    )
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": True}
    session.timeline.record_buffer = [TimelineCue(t=18.0, layers={"layer_1": True})]

    punch = build_record_punch_cues(session, record_start=10.0, record_stop=22.0)
    assert TimelineCue(t=22.0, layers={"layer_1": False}, show_tick=False) in punch
    assert committed_visible_outside_punch(session, "layer_1", 10.0, 22.0) is True
    assert timeline_committed_visible(session, "layer_1", 22.0) is False


def test_timeline_defaults_tracks_layer_enabled_before_first_record() -> None:
    session = _session(
        layer_enabled={"layer_1": False, "layer_2": True, "layer_3": True, "layer_4": True},
    )
    assert timeline_defaults(session)["layer_1"] is False
    session.layers["layer_1"].enabled = True
    assert timeline_defaults(session)["layer_1"] is True


def test_timeline_defaults_stable_after_layer_toggle_when_slot_has_cues() -> None:
    session = _session(
        layer_enabled={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=5.0, layers={"layer_1": True}),
            TimelineCue(t=10.0, layers={"layer_1": False}),
            TimelineCue(t=15.0, layers={"layer_1": True}),
        ],
    )
    assert timeline_defaults(session)["layer_1"] is False
    session.layers["layer_1"].enabled = False
    assert timeline_defaults(session)["layer_1"] is False
    assert timeline_committed_visible(session, "layer_1", 2.0) is False
    assert timeline_committed_visible(session, "layer_1", 7.0) is True


def test_build_record_punch_cues_adds_t0_anchor_on_first_record() -> None:
    session = _session(
        layer_enabled={"layer_1": False, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[],
    )
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_baseline = {"layer_1": False}
    session.timeline.record_buffer = [
        TimelineCue(t=5.0, layers={"layer_1": True}),
        TimelineCue(t=10.0, layers={"layer_1": False}),
        TimelineCue(t=15.0, layers={"layer_1": True}),
    ]

    punch = build_record_punch_cues(session, record_start=2.0, record_stop=20.0)
    assert TimelineCue(t=0.0, layers={"layer_1": False}, show_tick=False) in punch


def test_timeline_bar_preserves_pre_first_cue_after_layer_toggle() -> None:
    session = _session(
        layer_enabled={"layer_1": False, "layer_2": True, "layer_3": True, "layer_4": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=5.0, layers={"layer_1": True}),
            TimelineCue(t=10.0, layers={"layer_1": False}),
            TimelineCue(t=15.0, layers={"layer_1": True}),
        ],
    )
    state = build_timeline_view_state(session, position_sec=0.0, duration_sec=60.0)
    assert bar_segments_for_row(state, "layer_1") == [
        (0.0, 5.0, False),
        (5.0, 10.0, True),
        (10.0, 15.0, False),
        (15.0, 60.0, True),
    ]

    session.layers["layer_1"].enabled = True
    state = build_timeline_view_state(session, position_sec=0.0, duration_sec=60.0)
    assert bar_segments_for_row(state, "layer_1") == [
        (0.0, 5.0, False),
        (5.0, 10.0, True),
        (10.0, 15.0, False),
        (15.0, 60.0, True),
    ]