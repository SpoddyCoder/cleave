"""Unit tests for layer visibility and timeline integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pygame
import pytest

from cleave.extract import STEM_NAMES
from cleave.preset_playlist import PresetPlaylist
from cleave.stem_pcm import StemPcmBank
from cleave.timeline import TimelineCue
from cleave.viz.session import LayerRuntime, TimelineRuntime, TuningSession
from cleave.viz.row_semantics import RowKind
from cleave.viz.overlay import find_row_by_kind
from cleave.viz.layer import (
    StemLayer,
    _build_timeline_view_state,
    _warmup_layers,
    apply_layer_visibility,
    armed_recording_visible,
    build_record_punch_cues,
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


def _session(
    *,
    layer_enabled: dict[str, bool] | None = None,
    timeline_enabled: bool = False,
    cues: list[TimelineCue] | None = None,
    solo_stem: str | None = None,
) -> TuningSession:
    enabled = layer_enabled or {name: True for name in STEM_NAMES}
    return TuningSession(
        layer_z_order=list(STEM_NAMES),
        solo_stem=solo_stem,
        timeline=TimelineRuntime(
            enabled=timeline_enabled,
            cues=list(cues or []),
        ),
        layers={
            name: LayerRuntime(
                playlist=_playlist(name),
                browse_floor=Path(f"/tmp/presets/{name}"),
                enabled=enabled[name],
            )
            for name in STEM_NAMES
        },
    )


def _stem_layer(name: str) -> StemLayer:
    return StemLayer(
        name=name,
        pm=MagicMock(),
        fbo=MagicMock(enabled=True),
        playlist=_playlist(name),
    )


def test_timeline_defaults_from_layer_runtime() -> None:
    session = _session(layer_enabled={"drums": False, "bass": True, "vocals": True, "other": False})
    assert timeline_defaults(session) == {
        "drums": False,
        "bass": True,
        "vocals": True,
        "other": False,
    }


def test_effective_layer_enabled_uses_layer_when_timeline_off() -> None:
    session = _session(layer_enabled={"drums": False, "bass": True, "vocals": True, "other": True})
    assert effective_layer_enabled(session, "drums", 0.0) is False
    assert effective_layer_enabled(session, "bass", 99.0) is True


def test_effective_layer_enabled_uses_cues_when_timeline_on() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=5.0, layers={"drums": False})],
    )
    assert effective_layer_enabled(session, "drums", 4.9) is True
    assert effective_layer_enabled(session, "drums", 5.0) is False
    assert effective_layer_enabled(session, "bass", 5.0) is True


def test_effective_layer_enabled_defaults_before_first_cue() -> None:
    session = _session(
        layer_enabled={"drums": False, "bass": True, "vocals": False, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=10.0, layers={"drums": True})],
    )
    assert effective_layer_enabled(session, "drums", 0.0) is False
    assert effective_layer_enabled(session, "bass", 9.9) is True


def test_effective_layer_enabled_override_manual_override() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False, "bass": False})],
    )
    session.timeline.override_stems = {"bass"}
    session.timeline.override_visible = {"bass": True}
    assert effective_layer_enabled(session, "drums", 0.0) is False
    assert effective_layer_enabled(session, "bass", 0.0) is True


def test_effective_layer_enabled_override_when_paused() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"bass": False})],
    )
    session.timeline.override_stems = {"bass"}
    session.timeline.override_visible = {"bass": True}
    assert effective_layer_enabled(session, "bass", 0.0) is True


def test_effective_layer_enabled_override_ignored_when_preview_active() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"bass": False})],
    )
    session.timeline.preview_active = True
    session.timeline.monitor = {"bass": False}
    session.timeline.override_stems = {"bass"}
    session.timeline.override_visible = {"bass": True}
    assert effective_layer_enabled(session, "bass", 0.0) is False


def test_effective_layer_enabled_multiple_override_stems() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False, "bass": False, "vocals": False})],
    )
    session.timeline.override_stems = {"drums", "bass"}
    session.timeline.override_visible = {"drums": True, "bass": False}
    assert effective_layer_enabled(session, "drums", 0.0) is True
    assert effective_layer_enabled(session, "bass", 0.0) is False
    assert effective_layer_enabled(session, "vocals", 0.0) is False


def test_effective_layer_enabled_solo_overrides_timeline() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False, "bass": False})],
        solo_stem="drums",
    )
    assert effective_layer_enabled(session, "drums", 0.0) is True
    assert effective_layer_enabled(session, "bass", 0.0) is False


def test_effective_layer_enabled_uses_record_buffer_while_recording() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
    )
    session.timeline.recording = True
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_buffer = [TimelineCue(t=1.0, layers={"drums": False})]
    assert effective_layer_enabled(session, "drums", 1.0) is False
    assert effective_layer_enabled(session, "bass", 1.0) is True


def test_effective_layer_enabled_override_persists_for_unarmed_while_recording() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"bass": True, "vocals": True})],
    )
    session.timeline.recording = True
    session.timeline.armed_stems = {"drums"}
    session.timeline.override_stems = {"bass", "vocals"}
    session.timeline.override_visible = {"bass": False, "vocals": False}
    assert effective_layer_enabled(session, "bass", 1.0) is False
    assert effective_layer_enabled(session, "vocals", 1.0) is False


def test_timeline_cues_for_eval_merges_buffer_while_recording() -> None:
    session = _session(timeline_enabled=True, cues=[TimelineCue(t=0.0, layers={"drums": False})])
    session.timeline.recording = True
    session.timeline.record_buffer = [TimelineCue(t=1.0, layers={"bass": False})]
    tl = session.timeline
    merged = tl.cues + tl.record_buffer if tl.recording else tl.cues
    assert len(merged) == 2
    assert merged[0].t == 0.0
    assert merged[1].t == 1.0


def test_build_timeline_view_state_uses_record_buffer_while_recording() -> None:
    session = _session(
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False})],
    )
    session.timeline.recording = True
    session.timeline.record_buffer = [TimelineCue(t=1.0, layers={"bass": False})]
    state = _build_timeline_view_state(session, position_sec=1.0, duration_sec=60.0)
    assert len(state.cues) == 1
    assert state.cues[0].t == 0.0
    assert len(state.record_buffer) == 1
    assert state.record_buffer[0].layers == {"bass": False}


def test_apply_layer_visibility_sets_fbo_enabled_from_timeline() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=3.0, layers={"vocals": False})],
    )
    layers_by_name = {name: _stem_layer(name) for name in STEM_NAMES}

    apply_layer_visibility(session, layers_by_name, 2.0)
    assert layers_by_name["vocals"].fbo.enabled is True

    apply_layer_visibility(session, layers_by_name, 3.0)
    assert layers_by_name["vocals"].fbo.enabled is False
    assert layers_by_name["drums"].fbo.enabled is True


def test_header_toggle_blocked_when_timeline_enabled() -> None:
    controls = make_controls(("drums",))
    controls.session.timeline.enabled = True
    view = controls.build_view_state(paused=False)
    controls.focus_index = find_row_by_kind(view, RowKind.TRACK_HEADER)
    assert controls.session.layers["drums"].enabled is True

    controls.handle_keydown(keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))

    assert controls.session.layers["drums"].enabled is True
    view = controls.build_view_state(paused=False)
    assert view.toast_message == "Timeline controls layer visibility"


def test_effective_layer_enabled_preview_active_uses_monitor() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False, "bass": True})],
    )
    session.timeline.preview_active = True
    session.timeline.monitor = {
        "drums": True,
        "bass": False,
        "vocals": True,
        "other": False,
    }
    assert effective_layer_enabled(session, "drums", 0.0) is True
    assert effective_layer_enabled(session, "bass", 0.0) is False
    assert effective_layer_enabled(session, "vocals", 0.0) is True
    assert effective_layer_enabled(session, "other", 0.0) is False


def test_build_record_punch_cues_writes_baseline_only_when_it_differs() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False})],
    )
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_baseline = {"drums": True}
    session.timeline.record_buffer = [TimelineCue(t=12.0, layers={"drums": False})]

    punch = build_record_punch_cues(session, record_start=10.0, record_stop=20.0)
    assert TimelineCue(t=10.0, layers={"drums": True}, show_tick=False) in punch
    assert TimelineCue(t=12.0, layers={"drums": False}) in punch

    session.timeline.record_baseline = {"drums": False}
    session.timeline.record_buffer = []
    assert build_record_punch_cues(session, record_start=10.0, record_stop=20.0) == []


def test_effective_layer_enabled_recording_armed_ignores_committed_cues() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"drums": False}),
            TimelineCue(t=11.0, layers={"drums": False}),
        ],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_baseline = {"drums": True}
    session.timeline.record_buffer = []

    assert effective_layer_enabled(session, "drums", 11.5) is True
    assert armed_recording_visible(session, "drums", 11.5) is True
    assert timeline_committed_visible(session, "drums", 11.5) is False


def test_build_timeline_view_state_recording_baseline_not_in_cue_ticks() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False})],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_baseline = {"drums": True}
    session.timeline.record_buffer = []

    state = _build_timeline_view_state(session, position_sec=10.0, duration_sec=60.0)
    assert bar_tick_times_for_row(state, "drums") == [0.0]


def test_build_timeline_view_state_armed_recording_monitor_ignores_committed() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"drums": False}),
            TimelineCue(t=11.0, layers={"drums": False}),
        ],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_baseline = {"drums": True}
    session.timeline.record_buffer = []

    state = _build_timeline_view_state(session, position_sec=11.5, duration_sec=60.0)
    assert state.monitor_visible["drums"] is True
    assert state.timeline_visible["drums"] is False


def test_effective_layer_enabled_recording_armed_vs_unarmed() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": True, "bass": False})],
    )
    session.timeline.recording = True
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_buffer = [
        TimelineCue(t=1.0, layers={"drums": False, "bass": True}),
    ]
    assert effective_layer_enabled(session, "drums", 1.0) is False
    assert effective_layer_enabled(session, "bass", 1.0) is False


def test_timeline_committed_visible_ignores_record_buffer() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": True, "bass": False})],
    )
    session.timeline.recording = True
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_buffer = [
        TimelineCue(t=1.0, layers={"drums": False, "bass": True}),
    ]
    assert timeline_committed_visible(session, "drums", 1.0) is True
    assert timeline_committed_visible(session, "bass", 1.0) is False


def test_build_timeline_view_state_populates_visibility_playing() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=5.0, layers={"drums": False})],
    )
    session.timeline.override_stems = {"bass"}
    session.timeline.override_visible = {"bass": True}
    state = _build_timeline_view_state(session, position_sec=5.0, duration_sec=60.0)
    assert state.monitor_visible["drums"] is False
    assert state.monitor_visible["bass"] is True
    assert state.timeline_visible["drums"] is False
    assert state.timeline_visible["bass"] is True
    assert state.override_stems == {"bass"}


def test_build_timeline_view_state_monitor_preview_active() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False, "bass": True})],
    )
    session.timeline.preview_active = True
    session.timeline.monitor = {
        "drums": True,
        "bass": False,
        "vocals": True,
        "other": False,
    }
    state = _build_timeline_view_state(session, position_sec=0.0, duration_sec=60.0)
    assert state.monitor_visible == session.timeline.monitor
    assert state.timeline_visible["drums"] is False
    assert state.timeline_visible["bass"] is True


def test_snapshot_monitor_from_timeline_populates_from_committed() -> None:
    session = _session(
        layer_enabled={"drums": False, "bass": True, "vocals": True, "other": False},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=2.0, layers={"drums": True, "vocals": False}),
        ],
    )
    monitor = snapshot_monitor_from_timeline(session, 2.5)
    assert monitor == {
        "drums": True,
        "bass": True,
        "vocals": False,
        "other": False,
    }


def test_armed_recording_bar_blends_committed_and_live() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"drums": False}),
            TimelineCue(t=11.0, layers={"drums": False}),
            TimelineCue(t=30.0, layers={"drums": True}),
        ],
    )
    session.timeline.recording = True
    session.timeline.record_start_sec = 10.0
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_baseline = {"drums": True}
    session.timeline.record_buffer = [TimelineCue(t=12.0, layers={"drums": False})]

    state = _build_timeline_view_state(session, position_sec=12.0, duration_sec=60.0)
    segments = bar_segments_for_row(state, "drums")
    assert segments == [
        (0.0, 10.0, False),
        (10.0, 12.0, True),
        (12.0, 30.0, False),
        (30.0, 60.0, True),
    ]


def test_build_record_punch_cues_restores_committed_at_stop() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=0.0, layers={"drums": False}),
            TimelineCue(t=30.0, layers={"drums": True}),
        ],
    )
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_baseline = {"drums": False}
    session.timeline.record_buffer = [TimelineCue(t=15.0, layers={"drums": True})]

    punch = build_record_punch_cues(session, record_start=10.0, record_stop=20.0)
    assert TimelineCue(t=15.0, layers={"drums": True}) in punch
    assert TimelineCue(t=20.0, layers={"drums": False}, show_tick=False) in punch
    assert timeline_committed_visible(session, "drums", 20.0) is False


def test_build_record_punch_cues_restores_when_disable_only_inside_punch() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[
            TimelineCue(t=15.0, layers={"drums": False}),
            TimelineCue(t=25.0, layers={"drums": True}),
        ],
    )
    session.timeline.armed_stems = {"drums"}
    session.timeline.record_baseline = {"drums": True}
    session.timeline.record_buffer = [TimelineCue(t=18.0, layers={"drums": True})]

    punch = build_record_punch_cues(session, record_start=10.0, record_stop=22.0)
    assert TimelineCue(t=22.0, layers={"drums": False}, show_tick=False) in punch
    assert committed_visible_outside_punch(session, "drums", 10.0, 22.0) is True
    assert timeline_committed_visible(session, "drums", 22.0) is False


def _pcm_bank() -> StemPcmBank:
    pcm = {name: np.zeros(44100, dtype=np.float32) for name in STEM_NAMES}
    return StemPcmBank(project_dir=Path("/tmp/project"), duration_sec=1.0, _pcm=pcm)


def test_warmup_layers_feeds_pcm_and_frame_times() -> None:
    session = _session()
    drums = _stem_layer("drums")
    bass = _stem_layer("bass")
    layers = [drums, bass]
    pcm_bank = _pcm_bank()
    start_sec = 2.0
    frames = 3
    fps = 30
    n_pcm = 1470

    with patch("cleave.viz.layer._render_layer_fbo") as render_mock:
        _warmup_layers(
            layers,
            pcm_bank,
            start_sec,
            frames,
            fps,
            n_pcm,
            session=session,
        )

    expected_times = [
        start_sec - (frames - i) / fps for i in range(frames)
    ]
    assert drums.pm.set_frame_time.call_args_list == [
        ((t,),) for t in expected_times
    ]
    assert bass.pm.set_frame_time.call_args_list == [
        ((t,),) for t in expected_times
    ]
    assert drums.pm.feed_pcm.call_count == frames
    assert bass.pm.feed_pcm.call_count == frames
    assert render_mock.call_count == frames * 2


def test_warmup_layers_skips_disabled_layers() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": False, "vocals": True, "other": True},
    )
    drums = _stem_layer("drums")
    bass = _stem_layer("bass")
    pcm_bank = _pcm_bank()

    with patch("cleave.viz.layer._render_layer_fbo") as render_mock:
        _warmup_layers(
            [drums, bass],
            pcm_bank,
            start_sec=1.0,
            frames=2,
            fps=30,
            n_pcm=1470,
            session=session,
        )

    assert drums.pm.feed_pcm.call_count == 2
    assert bass.pm.feed_pcm.call_count == 0
    assert render_mock.call_count == 2


def test_warmup_layers_advances_frame_time_into_start() -> None:
    session = _session()
    drums = _stem_layer("drums")
    pcm_bank = _pcm_bank()
    fps = 30
    frames = 30

    with patch("cleave.viz.layer._render_layer_fbo"):
        _warmup_layers(
            [drums],
            pcm_bank,
            start_sec=0.0,
            frames=frames,
            fps=fps,
            n_pcm=1470,
            session=session,
        )

    times = [call.args[0] for call in drums.pm.set_frame_time.call_args_list]
    assert times == sorted(times)
    assert all(b - a == pytest.approx(1.0 / fps) for a, b in zip(times, times[1:]))
    assert any(t < 0.0 for t in times)
    assert times[-1] == pytest.approx(-1.0 / fps)


def test_warmup_layers_ends_one_frame_before_partial_start() -> None:
    session = _session()
    drums = _stem_layer("drums")
    pcm_bank = _pcm_bank()
    fps = 30

    with patch("cleave.viz.layer._render_layer_fbo"):
        _warmup_layers(
            [drums],
            pcm_bank,
            start_sec=10.0,
            frames=4,
            fps=fps,
            n_pcm=1470,
            session=session,
        )

    times = [call.args[0] for call in drums.pm.set_frame_time.call_args_list]
    assert times[-1] == pytest.approx(10.0 - 1.0 / fps)
    assert times[0] == pytest.approx(10.0 - 4.0 / fps)


def test_warmup_layers_respects_timeline_visibility() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=1.0, layers={"drums": False})],
    )
    drums = _stem_layer("drums")
    bass = _stem_layer("bass")
    pcm_bank = _pcm_bank()

    with patch("cleave.viz.layer._render_layer_fbo") as render_mock:
        _warmup_layers(
            [drums, bass],
            pcm_bank,
            start_sec=1.5,
            frames=2,
            fps=30,
            n_pcm=1470,
            session=session,
        )

    assert drums.pm.feed_pcm.call_count == 0
    assert bass.pm.feed_pcm.call_count == 2
    assert render_mock.call_count == 2
