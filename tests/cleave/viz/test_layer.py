"""Unit tests for layer visibility and timeline integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pygame

from cleave.extract import STEM_NAMES
from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import TimelineCue
from cleave.viz.controls import LayerRuntime, TimelineRuntime, TuningSession
from cleave.viz.layer import (
    StemLayer,
    _build_timeline_view_state,
    apply_layer_visibility,
    effective_layer_enabled,
    snapshot_monitor_from_timeline,
    timeline_committed_visible,
    timeline_cues_for_eval,
    timeline_defaults,
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
    assert effective_layer_enabled(session, "drums", 0.0, playing=True) is False
    assert effective_layer_enabled(session, "bass", 0.0, playing=True) is True


def test_effective_layer_enabled_override_ignored_when_paused() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"bass": False})],
    )
    session.timeline.override_stems = {"bass"}
    session.timeline.override_visible = {"bass": True}
    assert effective_layer_enabled(session, "bass", 0.0, playing=False) is False


def test_effective_layer_enabled_multiple_override_stems() -> None:
    session = _session(
        layer_enabled={"drums": True, "bass": True, "vocals": True, "other": True},
        timeline_enabled=True,
        cues=[TimelineCue(t=0.0, layers={"drums": False, "bass": False, "vocals": False})],
    )
    session.timeline.override_stems = {"drums", "bass"}
    session.timeline.override_visible = {"drums": True, "bass": False}
    assert effective_layer_enabled(session, "drums", 0.0, playing=True) is True
    assert effective_layer_enabled(session, "bass", 0.0, playing=True) is False
    assert effective_layer_enabled(session, "vocals", 0.0, playing=True) is False


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


def test_timeline_cues_for_eval_merges_buffer_while_recording() -> None:
    session = _session(timeline_enabled=True, cues=[TimelineCue(t=0.0, layers={"drums": False})])
    session.timeline.recording = True
    session.timeline.record_buffer = [TimelineCue(t=1.0, layers={"bass": False})]
    merged = timeline_cues_for_eval(session)
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
    assert len(state.cues) == 2
    assert state.cues[1].layers == {"bass": False}


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
    controls.focus_index = 0
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
