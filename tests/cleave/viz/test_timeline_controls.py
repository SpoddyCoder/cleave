"""Unit tests for timeline panel keyboard controls."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue
from cleave.viz.controls import LayerRuntime, SEEK_LONG, TuningSession
from cleave.viz.timeline_controls import TimelineControls
from tests.support.viz import keydown, make_playlist, stub_playback_state


def _make_timeline_controls(
    *,
    stems: tuple[str, ...] = tuple(STEM_NAMES),
    cues: list[TimelineCue] | None = None,
    focus_row: int = 0,
    armed_stems: set[str] | None = None,
    panel_open: bool = True,
    enabled: bool = True,
    position_sec: float = 0.0,
    recording: bool = False,
) -> tuple[
    TimelineControls,
    TuningSession,
    list[bool],
    list[bool],
    list[float],
    list[str],
]:
    preset_root = Path("/tmp/presets")
    session = TuningSession(
        layer_z_order=list(stems),
        layers={
            stem: LayerRuntime(
                playlist=make_playlist(stem),
                browse_floor=preset_root / stem,
            )
            for stem in stems
        },
    )
    tl = session.timeline
    tl.enabled = enabled
    tl.panel_open = panel_open
    tl.cues = list(cues or [])
    tl.focus_row = focus_row
    tl.armed_stems = set(armed_stems or ())
    tl.recording = recording

    playback = stub_playback_state()
    playback.player.seek(position_sec)

    visibility_calls: list[bool] = []
    close_calls: list[bool] = []
    seeks: list[float] = []
    toasts: list[str] = []

    controls = TimelineControls(
        session,
        playback,
        120.0,
        on_visibility_change=lambda: visibility_calls.append(True),
        on_close=lambda: (close_calls.append(True), setattr(tl, "panel_open", False)),
        on_seek=lambda delta: seeks.append(delta),
        on_toast=toasts.append,
    )
    return controls, session, visibility_calls, close_calls, seeks, toasts


def test_enter_toggles_arm_on_focused_stem() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(focus_row=1)
    assert session.timeline.armed_stems == set()

    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert session.timeline.armed_stems == {"bass"}

    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert session.timeline.armed_stems == set()


def test_up_down_change_focus_row() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(focus_row=1)

    controls.handle_keydown(keydown(pygame.K_UP))
    assert session.timeline.focus_row == 2

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 1

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 0

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 0


def test_left_right_navigate_cues_by_time() -> None:
    cues = [
        TimelineCue(t=30.0, layers={"drums": False}),
        TimelineCue(t=10.0, layers={"bass": False}),
        TimelineCue(t=50.0, layers={"vocals": False}),
    ]
    controls, _, _, _, _, _ = _make_timeline_controls(cues=cues)

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert controls.focused_cue_index == 0
    assert controls._sorted_cues()[0].t == 10.0

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert controls.focused_cue_index == 1
    assert controls._sorted_cues()[1].t == 30.0

    controls.handle_keydown(keydown(pygame.K_LEFT))
    assert controls.focused_cue_index == 0


def test_backspace_deletes_focused_cue() -> None:
    cue_a = TimelineCue(t=10.0, layers={"drums": False})
    cue_b = TimelineCue(t=30.0, layers={"bass": False})
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        cues=[cue_a, cue_b]
    )

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert controls.focused_cue_index == 1

    controls.handle_keydown(keydown(pygame.K_BACKSPACE))
    assert session.timeline.cues == [cue_a]
    assert controls.focused_cue_index == 0
    assert visibility_calls == [True]


def test_backspace_without_focus_deletes_nearest_cue() -> None:
    cue_near = TimelineCue(t=10.0, layers={"drums": False})
    cue_far = TimelineCue(t=80.0, layers={"bass": False})
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        cues=[cue_near, cue_far],
        position_sec=12.0,
    )

    controls.handle_keydown(keydown(pygame.K_BACKSPACE))
    assert session.timeline.cues == [cue_far]
    assert visibility_calls == [True]


def test_esc_and_t_close_panel() -> None:
    controls, session, _, close_calls, _, _ = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_ESCAPE))
    assert close_calls == [True]
    assert session.timeline.panel_open is False

    session.timeline.panel_open = True
    controls.handle_keydown(keydown(pygame.K_t))
    assert len(close_calls) == 2
    assert session.timeline.panel_open is False


def test_space_toggles_pause() -> None:
    controls, _, _, _, _, _ = _make_timeline_controls()
    playback = controls.playback

    assert playback.paused is False
    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert playback.paused is True
    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert playback.paused is False


def test_ctrl_seek_when_not_recording() -> None:
    controls, _, _, _, seeks, _ = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert seeks == [SEEK_LONG]

    controls.handle_keydown(keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert seeks == [SEEK_LONG, -SEEK_LONG]


def test_backspace_toast_when_no_cues() -> None:
    controls, _, _, _, _, toasts = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_BACKSPACE))
    assert toasts == ["No cues"]


def test_ctrl_enter_writes_visibility_cue_at_playhead() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=0,
        position_sec=5.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert len(session.timeline.cues) == 1
    assert session.timeline.cues[0].t == 5.0
    assert session.timeline.cues[0].layers == {"drums": False}
    assert visibility_calls == [True]


def test_r_without_armed_layers_shows_toast() -> None:
    controls, session, _, _, _, toasts = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_r))
    assert toasts == ["Arm at least one layer to record"]
    assert session.timeline.recording is False


def test_r_starts_recording_and_unpauses() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=3.0,
    )
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.recording is True
    assert session.timeline.record_start_sec == 3.0
    assert controls.playback.paused is False
    assert visibility_calls == [True]


def test_record_start_appends_snapshot_cue() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums", "bass"},
        position_sec=7.5,
    )
    session.layers["drums"].enabled = True
    session.layers["bass"].enabled = False

    controls.handle_keydown(keydown(pygame.K_r))
    assert len(session.timeline.record_buffer) == 1
    snapshot = session.timeline.record_buffer[0]
    assert snapshot.t == 7.5
    assert snapshot.layers == {"drums": True, "bass": False}


def test_layer_keys_only_affect_armed_stems() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=2.0,
    )
    session.layers["drums"].enabled = True
    session.layers["bass"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    assert len(session.timeline.record_buffer) == 1

    controls.handle_keydown(keydown(pygame.K_2))
    assert len(session.timeline.record_buffer) == 1

    controls.handle_keydown(keydown(pygame.K_1))
    assert len(session.timeline.record_buffer) == 2
    assert session.timeline.record_buffer[1] == TimelineCue(
        t=2.0, layers={"drums": False}
    )


def test_layer_key_debounce_ignores_rapid_press() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=4.0,
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_1))
    assert len(session.timeline.record_buffer) == 2


def test_ctrl_seek_blocked_while_recording() -> None:
    controls, session, _, _, seeks, _ = _make_timeline_controls(
        armed_stems={"drums"},
    )

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.recording is True

    controls.handle_keydown(keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    controls.handle_keydown(keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert seeks == []


def test_r_stop_punches_cues_and_clears_record_state() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=10.0,
        cues=[TimelineCue(t=5.0, layers={"bass": False})],
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(15.0)
    controls.handle_keydown(keydown(pygame.K_r))

    assert session.timeline.recording is False
    assert session.timeline.record_buffer == []
    assert session.timeline.record_start_sec is None
    assert TimelineCue(t=5.0, layers={"bass": False}) in session.timeline.cues
    assert any(
        cue.t == 10.0 and cue.layers.get("drums") is False
        for cue in session.timeline.cues
    )
    assert visibility_calls[-1] is True


def test_stop_record_preserves_unarmed_cues_in_punch_range() -> None:
    bass_cue = TimelineCue(t=12.0, layers={"bass": False})
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=10.0,
        cues=[bass_cue, TimelineCue(t=11.0, layers={"drums": True})],
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.playback.player.seek(14.0)
    controls.handle_keydown(keydown(pygame.K_r))

    assert bass_cue in session.timeline.cues
    assert not any(
        cue.t == 11.0 and "drums" in cue.layers for cue in session.timeline.cues
    )
