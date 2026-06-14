"""Unit tests for timeline panel keyboard controls."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue
from cleave.viz.controls import LayerRuntime, SEEK_LONG, SEEK_SHORT, TuningSession
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
    assert session.timeline.focus_row == 0

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 1

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 2

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 3

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 3


def test_left_right_seek_short_when_not_recording() -> None:
    controls, _, _, _, seeks, _ = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert seeks == [SEEK_SHORT]

    controls.handle_keydown(keydown(pygame.K_LEFT))
    assert seeks == [SEEK_SHORT, -SEEK_SHORT]


def test_backspace_deletes_focused_cue() -> None:
    cue_a = TimelineCue(t=10.0, layers={"drums": False})
    cue_b = TimelineCue(t=30.0, layers={"bass": False})
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        cues=[cue_a, cue_b]
    )

    controls.focused_cue_index = 1

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


def test_pause_snapshots_monitor_and_sets_preview_active() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        position_sec=5.0,
        cues=[TimelineCue(t=0.0, layers={"drums": False})],
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.preview_active is True
    assert session.timeline.monitor == {
        "drums": False,
        "bass": True,
        "vocals": True,
        "other": True,
    }
    assert visibility_calls == [True]


def test_resume_clears_preview() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls()
    session.timeline.preview_active = True
    session.timeline.monitor = {"drums": False}
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert visibility_calls == [True]


def test_num_keys_toggle_monitor_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        position_sec=3.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.monitor["drums"] is True

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.monitor["drums"] is False
    assert session.timeline.cues == []
    assert session.timeline.record_buffer == []
    assert visibility_calls == [True, True]


def test_num_keys_ignored_when_playing_not_in_override() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls()
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert session.timeline.cues == []
    assert session.timeline.override_stems == set()
    assert visibility_calls == []


def test_num_keys_toggle_override_visible_when_playing() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        cues=[TimelineCue(t=0.0, layers={"drums": True})],
    )
    session.timeline.override_stems = {"drums"}
    session.timeline.override_visible = {"drums": True}

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.override_visible["drums"] is False
    assert visibility_calls == [True]


def test_record_from_pause_stores_wysiwyg_baseline_when_monitor_differs() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=7.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_r))

    assert session.timeline.recording is True
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert session.timeline.record_buffer == []
    assert session.timeline.record_baseline == {"drums": False}


def test_record_clears_override() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
    )
    session.timeline.override_stems = {"bass"}
    session.timeline.override_visible = {"bass": True}
    session.solo_stem = "bass"

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.override_stems == set()
    assert session.timeline.override_visible == {}
    assert session.solo_stem == "bass"
    assert visibility_calls == [True]


def test_shift_enter_override_when_playing() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        cues=[TimelineCue(t=0.0, layers={"bass": False})],
    )

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.solo_stem is None
    assert session.timeline.override_stems == {"bass"}
    assert session.timeline.override_visible == {"bass": False}
    assert visibility_calls == [True]


def test_shift_enter_clears_override_on_same_focused_row() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(focus_row=1)
    session.timeline.override_stems = {"bass"}
    session.timeline.override_visible = {"bass": True}

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_stems == set()
    assert session.timeline.override_visible == {}
    assert visibility_calls == [True]


def test_shift_enter_override_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        cues=[TimelineCue(t=0.0, layers={"bass": False})],
    )
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_stems == {"bass"}
    assert session.timeline.override_visible == {"bass": False}
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert visibility_calls == [True]


def test_shift_enter_override_clears_preview_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        cues=[TimelineCue(t=0.0, layers={"bass": False})],
    )
    controls.playback.paused = True
    session.timeline.preview_active = True
    session.timeline.monitor = {"bass": True}

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert session.timeline.override_stems == {"bass"}
    assert session.timeline.override_visible == {"bass": True}
    assert visibility_calls == [True]


def test_num_keys_toggle_override_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        cues=[TimelineCue(t=0.0, layers={"drums": True})],
    )
    controls.playback.paused = True
    session.timeline.override_stems = {"drums"}
    session.timeline.override_visible = {"drums": True}

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.override_visible["drums"] is False
    assert visibility_calls == [True]


def test_shift_enter_ignored_when_recording() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        armed_stems={"drums"},
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_stems == set()
    assert visibility_calls == [True]


def test_shift_enter_does_not_set_session_solo_stem() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(focus_row=1)

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.solo_stem is None
    assert session.timeline.override_stems == {"bass"}


def test_multiple_override_stems() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=0,
        cues=[TimelineCue(t=0.0, layers={"drums": False, "bass": False})],
    )

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    session.timeline.focus_row = 1
    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))

    assert session.timeline.override_stems == {"drums", "bass"}
    assert session.timeline.override_visible == {"drums": False, "bass": False}
    assert visibility_calls == [True, True]


def test_shift_enter_does_not_arm_focused_row() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(focus_row=1)

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_stems == {"bass"}
    assert session.timeline.armed_stems == set()


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


def test_ctrl_enter_writes_to_record_buffer_when_recording() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=0,
        armed_stems={"drums"},
        position_sec=5.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert session.timeline.cues == []
    assert len(session.timeline.record_buffer) == 1
    assert session.timeline.record_buffer[0] == TimelineCue(
        t=5.0, layers={"drums": False}
    )
    assert visibility_calls[-1] is True


def test_ctrl_enter_ignored_when_not_recording() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=0,
        armed_stems={"drums"},
        position_sec=5.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert session.timeline.cues == []
    assert session.timeline.record_buffer == []
    assert visibility_calls == []


def test_ctrl_enter_only_affects_armed_focused_stem() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        focus_row=1,
        armed_stems={"drums"},
        position_sec=5.0,
    )
    session.layers["bass"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert session.timeline.record_buffer == []
    assert session.timeline.record_baseline == {"drums": True}


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


def test_record_start_stores_baseline_not_buffer() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums", "bass"},
        position_sec=7.5,
    )
    session.layers["drums"].enabled = True
    session.layers["bass"].enabled = False

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.record_buffer == []
    assert session.timeline.record_baseline == {"drums": True, "bass": False}


def test_layer_keys_only_affect_armed_stems() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=2.0,
    )
    session.layers["drums"].enabled = True
    session.layers["bass"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    assert len(session.timeline.record_buffer) == 0

    controls.handle_keydown(keydown(pygame.K_2))
    assert len(session.timeline.record_buffer) == 0

    controls.handle_keydown(keydown(pygame.K_1))
    assert len(session.timeline.record_buffer) == 1
    assert session.timeline.record_buffer[0] == TimelineCue(
        t=2.0, layers={"drums": False}
    )


def test_numpad_layer_keys_work_while_recording() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=6.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_KP1))

    assert len(session.timeline.record_buffer) == 1
    assert session.timeline.record_buffer[0] == TimelineCue(
        t=6.0, layers={"drums": False}
    )


def test_layer_key_debounce_ignores_rapid_press() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=4.0,
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_1))
    assert len(session.timeline.record_buffer) == 1


def test_seek_blocked_while_recording() -> None:
    controls, session, _, _, seeks, _ = _make_timeline_controls(
        armed_stems={"drums"},
    )

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.recording is True

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    controls.handle_keydown(keydown(pygame.K_LEFT))
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


def test_stop_record_restores_committed_after_punch_range() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=10.0,
        cues=[
            TimelineCue(t=0.0, layers={"drums": False}),
            TimelineCue(t=30.0, layers={"drums": True}),
        ],
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(20.0)
    controls.handle_keydown(keydown(pygame.K_r))

    from cleave.timeline import layer_visible_at
    from cleave.viz.layer import timeline_defaults

    defaults = timeline_defaults(session)
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 14.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 15.0) is True
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 19.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 20.0) is False
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 29.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 30.0) is True
    restore_cues = [
        cue for cue in session.timeline.cues if cue.t == 20.0 and "drums" in cue.layers
    ]
    assert len(restore_cues) == 1
    assert restore_cues[0].show_tick is False


def test_stop_record_restores_disabled_tail_when_disable_inside_punch() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=10.0,
        cues=[
            TimelineCue(t=15.0, layers={"drums": False}),
            TimelineCue(t=25.0, layers={"drums": True}),
        ],
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(12.0)
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(22.0)
    controls.handle_keydown(keydown(pygame.K_r))

    from cleave.timeline import layer_visible_at
    from cleave.viz.layer import timeline_defaults

    defaults = timeline_defaults(session)
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 11.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 12.0) is True
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 21.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 22.0) is False
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 24.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 25.0) is True


def test_stop_record_restores_enabled_tail_when_injecting_disabled_section() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=10.0,
        cues=[TimelineCue(t=5.0, layers={"drums": True})],
    )
    session.layers["drums"].enabled = False

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(22.0)
    controls.handle_keydown(keydown(pygame.K_r))

    from cleave.timeline import layer_visible_at
    from cleave.viz.layer import timeline_defaults

    defaults = timeline_defaults(session)
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 9.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 10.0) is False
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 21.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 22.0) is True
    assert layer_visible_at(session.timeline.cues, defaults, "drums", 40.0) is True


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


def test_ctrl_space_starts_record_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=3.0,
    )
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))
    assert session.timeline.recording is True
    assert controls.playback.paused is False
    assert visibility_calls == [True]


def test_ctrl_space_starts_record_when_playing() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"bass"},
        position_sec=2.0,
    )

    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))
    assert session.timeline.recording is True
    assert controls.playback.paused is False
    assert visibility_calls == [True]


def test_ctrl_space_stops_record_and_pauses() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=10.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(15.0)
    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))

    assert session.timeline.recording is False
    assert controls.playback.paused is True
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert visibility_calls == [True, True, True]


def test_ctrl_space_stop_stays_paused_if_already_paused() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=8.0,
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))
    assert session.timeline.recording is False
    assert controls.playback.paused is True
    assert session.timeline.preview_active is False


def test_space_resumes_when_recording_and_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=8.0,
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.recording is True
    assert controls.playback.paused is False
    assert visibility_calls == [True, True]


def test_space_stops_record_and_pauses_while_playing() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_stems={"drums"},
        position_sec=10.0,
    )
    session.layers["drums"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(15.0)
    controls.handle_keydown(keydown(pygame.K_SPACE))

    assert session.timeline.recording is False
    assert controls.playback.paused is True
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert visibility_calls == [True, True, True]


def test_ctrl_space_without_armed_stems_toasts() -> None:
    controls, session, visibility_calls, _, _, toasts = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))
    assert session.timeline.recording is False
    assert toasts == ["Arm at least one layer to record"]
    assert visibility_calls == []
