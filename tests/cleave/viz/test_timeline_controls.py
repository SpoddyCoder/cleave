"""Unit tests for timeline panel keyboard controls."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue
from cleave.viz.controls import SEEK_LONG, SEEK_SHORT, TuningControls
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.timeline_controls import TimelineControls
from tests.support.viz import keydown, make_playlist, stub_playback_state


def _make_timeline_controls(
    *,
    slots: tuple[str, ...] = tuple(DEFAULT_LAYER_SLOTS),
    cues: list[TimelineCue] | None = None,
    focus_row: int = 0,
    armed_slots: set[str] | None = None,
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
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=make_playlist(slot),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
            )
            for slot in slots
        },
    )
    tl = session.timeline
    tl.enabled = enabled
    tl.panel_open = panel_open
    tl.cues = list(cues or [])
    tl.focus_row = focus_row
    tl.armed_slots = set(armed_slots or ())
    tl.recording = recording

    playback = stub_playback_state()
    playback.player.seek(position_sec)

    visibility_calls: list[bool] = []
    close_calls: list[bool] = []
    seeks: list[float] = []
    notifications: list[str] = []

    controls = TimelineControls(
        session,
        playback,
        120.0,
        on_visibility_change=lambda: visibility_calls.append(True),
        on_close=lambda: (
            close_calls.append(True),
            setattr(tl, "panel_open", False),
        ),
        on_seek=lambda delta: seeks.append(delta),
        on_notification=notifications.append,
    )
    return controls, session, visibility_calls, close_calls, seeks, notifications


def test_enter_toggles_arm_on_focused_stem() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(focus_row=1)
    assert session.timeline.armed_slots == set()

    before = pygame.time.get_ticks()
    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert session.timeline.armed_slots == {"layer_2"}
    assert session.timeline.arm_flash_start_ms["layer_2"] >= before

    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert session.timeline.armed_slots == set()
    assert session.timeline.arm_flash_start_ms["layer_2"] >= before


def test_left_right_seek_short_when_not_recording() -> None:
    controls, _, _, _, seeks, _ = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert seeks == [SEEK_SHORT]

    controls.handle_keydown(keydown(pygame.K_LEFT))
    assert seeks == [SEEK_SHORT, -SEEK_SHORT]


def test_esc_and_t_close_panel_when_not_recording() -> None:
    controls, session, _, close_calls, _, _ = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_ESCAPE))
    assert close_calls == [True]
    assert session.timeline.panel_open is False

    session.timeline.panel_open = True
    controls.handle_keydown(keydown(pygame.K_t))
    assert len(close_calls) == 2
    assert session.timeline.panel_open is False


def test_esc_and_t_while_recording_do_not_close_panel() -> None:
    controls, session, _, close_calls, _, _ = _make_timeline_controls(
        recording=True,
    )
    session.timeline.armed_slots = {"layer_1"}
    session.timeline.record_start_sec = 0.0

    controls.handle_keydown(keydown(pygame.K_ESCAPE))
    controls.handle_keydown(keydown(pygame.K_t))
    assert close_calls == []
    assert session.timeline.panel_open is True


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
        cues=[TimelineCue(t=0.0, layers={"layer_1": False})],
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.preview_active is True
    assert session.timeline.monitor == {
        "layer_1": False,
        "layer_2": True,
        "layer_3": True,
        "layer_4": True,
    }
    assert visibility_calls == [True]


def test_resume_clears_preview() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls()
    session.timeline.preview_active = True
    session.timeline.monitor = {"layer_1": False}
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert visibility_calls == [True]


def test_num_keys_toggle_monitor_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        position_sec=3.0,
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.monitor["layer_1"] is True

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.monitor["layer_1"] is False
    assert session.timeline.cues == []
    assert session.timeline.record_buffer == []
    assert visibility_calls == [True, True]


def test_num_key_5_toggles_fifth_layer_when_paused() -> None:
    slots = tuple(f"layer_{i}" for i in range(1, 6))
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        slots=slots,
        position_sec=3.0,
    )
    controls.playback.paused = True
    session.timeline.preview_active = True
    session.timeline.monitor = {slot: True for slot in slots}

    controls.handle_keydown(keydown(pygame.K_5))
    assert session.timeline.monitor["layer_5"] is False
    assert session.timeline.monitor["layer_4"] is True
    assert visibility_calls == [True]


def test_num_keys_beyond_layer_count_are_noop() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls()
    controls.playback.paused = True
    session.timeline.preview_active = True
    session.timeline.monitor = {slot: True for slot in DEFAULT_LAYER_SLOTS}

    controls.handle_keydown(keydown(pygame.K_5))
    assert session.timeline.monitor == {
        "layer_1": True,
        "layer_2": True,
        "layer_3": True,
        "layer_4": True,
    }
    assert visibility_calls == []


def test_num_keys_ignored_when_playing_not_in_override() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls()
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert session.timeline.cues == []
    assert session.timeline.override_slots == set()
    assert visibility_calls == []


def test_num_keys_toggle_override_visible_when_playing() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        cues=[TimelineCue(t=0.0, layers={"layer_1": True})],
    )
    session.timeline.override_slots = {"layer_1"}
    session.timeline.override_visible = {"layer_1": True}

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.override_visible["layer_1"] is False
    assert visibility_calls == [True]


def test_record_from_pause_stores_wysiwyg_baseline_when_monitor_differs() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=7.0,
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_SPACE))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_r))

    assert session.timeline.recording is True
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert session.timeline.record_buffer == []
    assert session.timeline.record_baseline == {"layer_1": False}


def test_record_preserves_override() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
    )
    session.timeline.override_slots = {"layer_2", "layer_3"}
    session.timeline.override_visible = {"layer_2": False, "layer_3": False}
    session.solo_slot = "layer_2"

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.override_slots == {"layer_2", "layer_3"}
    assert session.timeline.override_visible == {"layer_2": False, "layer_3": False}
    assert session.solo_slot == "layer_2"
    assert visibility_calls == [True]


def test_shift_enter_override_when_playing() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        cues=[TimelineCue(t=0.0, layers={"layer_2": False})],
    )

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.solo_slot is None
    assert session.timeline.override_slots == {"layer_2"}
    assert session.timeline.override_visible == {"layer_2": False}
    assert visibility_calls == [True]


def test_shift_enter_clears_override_on_same_focused_row() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(focus_row=1)
    session.timeline.override_slots = {"layer_2"}
    session.timeline.override_visible = {"layer_2": True}

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_slots == set()
    assert session.timeline.override_visible == {}
    assert visibility_calls == [True]


def test_shift_enter_override_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        cues=[TimelineCue(t=0.0, layers={"layer_2": False})],
    )
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_slots == {"layer_2"}
    assert session.timeline.override_visible == {"layer_2": False}
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert visibility_calls == [True]


def test_shift_enter_override_clears_preview_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        cues=[TimelineCue(t=0.0, layers={"layer_2": False})],
    )
    controls.playback.paused = True
    session.timeline.preview_active = True
    session.timeline.monitor = {"layer_2": True}

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert session.timeline.override_slots == {"layer_2"}
    assert session.timeline.override_visible == {"layer_2": True}
    assert visibility_calls == [True]


def test_num_keys_toggle_override_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        cues=[TimelineCue(t=0.0, layers={"layer_1": True})],
    )
    controls.playback.paused = True
    session.timeline.override_slots = {"layer_1"}
    session.timeline.override_visible = {"layer_1": True}

    controls.handle_keydown(keydown(pygame.K_1))
    assert session.timeline.override_visible["layer_1"] is False
    assert visibility_calls == [True]


def test_shift_enter_ignored_when_recording() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=1,
        armed_slots={"layer_1"},
    )
    session.timeline.override_slots = {"layer_2"}
    session.timeline.override_visible = {"layer_2": False}

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_slots == {"layer_2"}
    assert session.timeline.override_visible == {"layer_2": False}
    assert visibility_calls == [True]


def test_shift_enter_does_not_set_session_solo_stem() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(focus_row=1)

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.solo_slot is None
    assert session.timeline.override_slots == {"layer_2"}


def test_multiple_override_stems() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        focus_row=0,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False, "layer_2": False})],
    )

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    session.timeline.focus_row = 1
    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))

    assert session.timeline.override_slots == {"layer_1", "layer_2"}
    assert session.timeline.override_visible == {"layer_1": False, "layer_2": False}
    assert visibility_calls == [True, True]


def test_shift_enter_does_not_arm_focused_row() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(focus_row=1)

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    assert session.timeline.override_slots == {"layer_2"}
    assert session.timeline.armed_slots == set()


def test_ctrl_seek_when_not_recording() -> None:
    controls, _, _, _, seeks, _ = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert seeks == [SEEK_LONG]

    controls.handle_keydown(keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert seeks == [SEEK_LONG, -SEEK_LONG]


def test_ctrl_enter_noop_while_recording() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        focus_row=0,
        armed_slots={"layer_1"},
        position_sec=5.0,
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.armed_slots == {"layer_1"}
    assert session.timeline.record_buffer == []

    controls.handle_keydown(keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))

    assert session.timeline.armed_slots == {"layer_1"}
    assert session.timeline.record_buffer == []


def test_r_without_armed_layers_shows_notification() -> None:
    controls, session, _, _, _, notifications = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_r))
    assert notifications == ["Arm at least one layer to record"]
    assert session.timeline.recording is False


def test_r_starts_recording_and_unpauses() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
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
        armed_slots={"layer_1", "layer_2"},
        position_sec=7.5,
    )
    session.layers["layer_1"].enabled = True
    session.layers["layer_2"].enabled = False

    controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.record_buffer == []
    assert session.timeline.record_baseline == {"layer_1": True, "layer_2": False}


def test_layer_keys_only_affect_armed_stems() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=2.0,
    )
    session.layers["layer_1"].enabled = True
    session.layers["layer_2"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    assert len(session.timeline.record_buffer) == 0

    controls.handle_keydown(keydown(pygame.K_2))
    assert len(session.timeline.record_buffer) == 0

    controls.handle_keydown(keydown(pygame.K_1))
    assert len(session.timeline.record_buffer) == 1
    assert session.timeline.record_buffer[0] == TimelineCue(
        t=2.0, layers={"layer_1": False}
    )


def test_numpad_layer_keys_work_while_recording() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=6.0,
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_KP1))

    assert len(session.timeline.record_buffer) == 1
    assert session.timeline.record_buffer[0] == TimelineCue(
        t=6.0, layers={"layer_1": False}
    )


def test_layer_key_debounce_ignores_rapid_press() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=4.0,
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_1))
    assert len(session.timeline.record_buffer) == 1


def test_disarm_during_recording_commits_slot_and_exits_recording() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=5.0,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False})],
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert session.timeline.armed_slots == set()
    assert session.timeline.recording is False
    assert session.timeline.record_baseline == {}
    assert session.timeline.record_buffer == []
    assert any(
        cue.t == 5.0 and cue.layers.get("layer_1") is False
        for cue in session.timeline.cues
    )
    assert visibility_calls


def test_disarm_one_slot_keeps_recording_on_remaining_armed() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1", "layer_2"},
        focus_row=0,
        position_sec=8.0,
        cues=[TimelineCue(t=0.0, layers={"layer_1": False, "layer_2": False})],
    )
    session.layers["layer_1"].enabled = True
    session.layers["layer_2"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert session.timeline.armed_slots == {"layer_2"}
    assert session.timeline.recording is True
    assert session.timeline.record_baseline == {"layer_2": False}
    assert "layer_1" not in session.timeline.record_baseline
    assert all("layer_1" not in cue.layers for cue in session.timeline.record_buffer)
    assert visibility_calls


def test_seek_blocked_while_recording() -> None:
    controls, session, _, _, seeks, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
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
        armed_slots={"layer_1"},
        position_sec=10.0,
        cues=[TimelineCue(t=5.0, layers={"layer_2": False})],
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(15.0)
    controls.handle_keydown(keydown(pygame.K_r))

    assert session.timeline.recording is False
    assert session.timeline.record_buffer == []
    assert session.timeline.record_start_sec is None
    assert TimelineCue(t=5.0, layers={"layer_2": False}) in session.timeline.cues
    assert any(
        cue.t == 10.0 and cue.layers.get("layer_1") is False
        for cue in session.timeline.cues
    )
    assert visibility_calls[-1] is True


def test_stop_record_restores_committed_after_punch_range() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=10.0,
        cues=[
            TimelineCue(t=0.0, layers={"layer_1": False}),
            TimelineCue(t=30.0, layers={"layer_1": True}),
        ],
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(20.0)
    controls.handle_keydown(keydown(pygame.K_r))

    from cleave.timeline import layer_visible_at
    from cleave.viz.layer_visibility import timeline_defaults

    defaults = timeline_defaults(session)
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 14.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 15.0) is True
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 19.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 20.0) is False
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 29.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 30.0) is True
    restore_cues = [
        cue for cue in session.timeline.cues if cue.t == 20.0 and "layer_1" in cue.layers
    ]
    assert len(restore_cues) == 1
    assert restore_cues[0].show_tick is False


def test_stop_record_restores_disabled_tail_when_disable_inside_punch() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=10.0,
        cues=[
            TimelineCue(t=15.0, layers={"layer_1": False}),
            TimelineCue(t=25.0, layers={"layer_1": True}),
        ],
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(12.0)
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(22.0)
    controls.handle_keydown(keydown(pygame.K_r))

    from cleave.timeline import layer_visible_at
    from cleave.viz.layer_visibility import timeline_defaults

    defaults = timeline_defaults(session)
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 11.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 12.0) is True
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 21.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 22.0) is False
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 24.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 25.0) is True


def test_stop_record_restores_enabled_tail_when_injecting_disabled_section() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=10.0,
        cues=[TimelineCue(t=5.0, layers={"layer_1": True})],
    )
    session.layers["layer_1"].enabled = False

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(22.0)
    controls.handle_keydown(keydown(pygame.K_r))

    from cleave.timeline import layer_visible_at
    from cleave.viz.layer_visibility import timeline_defaults

    defaults = timeline_defaults(session)
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 9.9) is True
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 10.0) is False
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 21.9) is False
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 22.0) is True
    assert layer_visible_at(session.timeline.cues, defaults, "layer_1", 40.0) is True


def test_stop_record_preserves_unarmed_cues_in_punch_range() -> None:
    bass_cue = TimelineCue(t=12.0, layers={"layer_2": False})
    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=10.0,
        cues=[bass_cue, TimelineCue(t=11.0, layers={"layer_1": True})],
    )

    controls.handle_keydown(keydown(pygame.K_r))
    controls.playback.player.seek(14.0)
    controls.handle_keydown(keydown(pygame.K_r))

    assert bass_cue in session.timeline.cues
    assert not any(
        cue.t == 11.0 and "layer_1" in cue.layers for cue in session.timeline.cues
    )


def test_ctrl_space_starts_record_when_paused() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=3.0,
    )
    controls.playback.paused = True

    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))
    assert session.timeline.recording is True
    assert controls.playback.paused is False
    assert visibility_calls == [True]


def test_ctrl_space_starts_record_when_playing() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_2"},
        position_sec=2.0,
    )

    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))
    assert session.timeline.recording is True
    assert controls.playback.paused is False
    assert visibility_calls == [True]


def test_ctrl_space_stops_record_and_pauses() -> None:
    controls, session, visibility_calls, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=10.0,
    )
    session.layers["layer_1"].enabled = True

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
        armed_slots={"layer_1"},
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
        armed_slots={"layer_1"},
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
        armed_slots={"layer_1"},
        position_sec=10.0,
    )
    session.layers["layer_1"].enabled = True

    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(15.0)
    controls.handle_keydown(keydown(pygame.K_SPACE))

    assert session.timeline.recording is False
    assert controls.playback.paused is True
    assert session.timeline.preview_active is False
    assert session.timeline.monitor == {}
    assert visibility_calls == [True, True, True]


def test_ctrl_space_without_armed_stems_notifies() -> None:
    controls, session, visibility_calls, _, _, notifications = _make_timeline_controls()

    controls.handle_keydown(keydown(pygame.K_SPACE, mod=pygame.KMOD_CTRL))
    assert session.timeline.recording is False
    assert notifications == ["Arm at least one layer to record"]
    assert visibility_calls == []


def test_recorded_timeline_bar_unchanged_after_disable_layer_toggle_reenable() -> None:
    from cleave.viz.layer_visibility import build_timeline_view_state
    from cleave.viz.timeline_overlay import bar_segments_for_row

    controls, session, _, _, _, _ = _make_timeline_controls(
        armed_slots={"layer_1"},
        position_sec=0.0,
    )
    session.layers["layer_1"].enabled = False

    controls.handle_keydown(keydown(pygame.K_r))
    for t_sec in (3.0, 6.0, 9.0, 12.0, 15.0):
        controls.playback.player.seek(t_sec)
        controls.handle_keydown(keydown(pygame.K_1))
    controls.playback.player.seek(18.0)
    controls.handle_keydown(keydown(pygame.K_r))

    def segments() -> list[tuple[float, float, bool]]:
        state = build_timeline_view_state(session, position_sec=0.0, duration_sec=60.0)
        return bar_segments_for_row(state, "layer_1")

    expected = segments()

    session.timeline.enabled = False
    session.layers["layer_1"].enabled = True
    session.timeline.enabled = True
    assert segments() == expected
    assert expected[0] == (0.0, 3.0, False)