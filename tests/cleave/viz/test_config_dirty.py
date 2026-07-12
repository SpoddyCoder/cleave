"""Config dirty tracking: persisted edits mark dirty; session-only edits do not."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import patch

from pathlib import Path

import pygame
import pytest

from cleave.viz.controls import TuningControls
from cleave.viz.timeline_controls import TimelineControls
from cleave.viz.row_semantics import RowDescriptor, RowKind
from tests.cleave.viz.test_controls import (
    _choose_save_as_new,
    _config_header_row,
    _desc,
    _expand_settings,
    _expand_settings_ui,
    _keydown,
    _make_controls,
    _row,
)
from tests.cleave.viz.test_timeline_controls import _make_timeline_controls
from tests.support.viz import keydown, stub_playback_state


def _expand_layer_1(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_HEADER))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _expand_render_overlay(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _expand_render_post_fx(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_layer_z_order(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_2", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_m))
    controls.handle_keydown(_keydown(pygame.K_UP))
    controls.handle_keydown(_keydown(pygame.K_m))


def _mutate_stem_enabled(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_HEADER))
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))


def _mutate_stem_opacity(controls: TuningControls) -> None:
    _expand_layer_1(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_OPACITY))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_stem_blend_mode(controls: TuningControls) -> None:
    _expand_layer_1(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_BLEND))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_stem_locked(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_HEADER))
    controls.handle_keydown(_keydown(pygame.K_l))


def _mutate_stem_beat_sensitivity(controls: TuningControls) -> None:
    _expand_layer_1(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_BEAT))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_stem_effects(controls: TuningControls) -> None:
    _expand_layer_1(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_EFFECTS_HEADER))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(
        view, "layer_1", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    ))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_preset_path(controls: TuningControls) -> None:
    _expand_layer_1(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_PRESET))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_preset_switching(controls: TuningControls) -> None:
    _expand_layer_1(controls)
    controls.session.layers["layer_1"].preset_switching_expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(
        _row(view, "layer_1", RowKind.TRACK_PRESET_SWITCHING_MODE)
    )
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_enabled(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_HEADER)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))


def _mutate_render_overlay_locked(controls: TuningControls) -> None:
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_HEADER)
    controls.handle_keydown(_keydown(pygame.K_l))


def _mutate_render_post_fx_locked(controls: TuningControls) -> None:
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    controls.handle_keydown(_keydown(pygame.K_l))


def _mutate_timeline_locked(controls: TuningControls) -> None:
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    controls.handle_keydown(_keydown(pygame.K_l))


def _mutate_render_overlay_position(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_POSITION)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_title_font_size(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    controls.session.render_overlay.title_expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_title_font(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    controls.session.render_overlay.title_expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_title_margin_bottom(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    controls.session.render_overlay.title_expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_body_font_size(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    controls.session.render_overlay.body_expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_BODY_FONT_SIZE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_body_font(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    controls.session.render_overlay.body_expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_BODY_FONT)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_opacity(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_border_width(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_BORDER_WIDTH)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_start_delay(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_START_DELAY)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_display_time(controls: TuningControls) -> None:
    _expand_render_overlay(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_DISPLAY_TIME)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_enabled(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))


def _mutate_render_post_fx_fade_in(controls: TuningControls) -> None:
    _expand_render_post_fx(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_fade_out(controls: TuningControls) -> None:
    _expand_render_post_fx(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_FADE_OUT)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _expand_render_post_fx_highlight_rolloff(controls: TuningControls) -> None:
    _expand_render_post_fx(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_highlight_rolloff_mode(controls: TuningControls) -> None:
    _expand_render_post_fx_highlight_rolloff(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_highlight_rolloff_curve(controls: TuningControls) -> None:
    _expand_render_post_fx_highlight_rolloff(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CURVE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_highlight_rolloff_threshold(controls: TuningControls) -> None:
    _expand_render_post_fx_highlight_rolloff(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_highlight_rolloff_ceiling(controls: TuningControls) -> None:
    _expand_render_post_fx_highlight_rolloff(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_highlight_rolloff_strength(controls: TuningControls) -> None:
    _expand_render_post_fx_highlight_rolloff(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_highlight_rolloff_softness(controls: TuningControls) -> None:
    _expand_render_post_fx_highlight_rolloff(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_highlight_rolloff_desaturation(controls: TuningControls) -> None:
    _expand_render_post_fx_highlight_rolloff(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _expand_render_post_fx_chroma_boost(controls: TuningControls) -> None:
    _expand_render_post_fx(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_chroma_boost_mode(controls: TuningControls) -> None:
    _expand_render_post_fx_chroma_boost(controls)
    controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_chroma_boost_variant(controls: TuningControls) -> None:
    _expand_render_post_fx_chroma_boost(controls)
    controls.session.render_post_fx.chroma_boost.mode = "composite"
    controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_CHROMA_BOOST_VARIANT)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_post_fx_chroma_boost_amount(controls: TuningControls) -> None:
    _expand_render_post_fx_chroma_boost(controls)
    controls.session.render_post_fx.chroma_boost.mode = "composite"
    controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_timeline_enabled(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))


def _mutate_timeline_cues_via_record() -> None:
    tuning = _make_controls(("layer_1",))
    tuning.session.timeline.enabled = True
    tuning.session.layers["layer_1"].enabled = True
    tuning.clear_config_dirty()
    assert not tuning.config_dirty
    playback = stub_playback_state()
    playback.player.seek(5.0)
    controls = TimelineControls(
        tuning.session,
        playback,
        120.0,
    )
    tuning.session.timeline.armed_slots = {"layer_1"}
    controls.handle_keydown(keydown(pygame.K_r))
    controls.handle_keydown(keydown(pygame.K_1))
    controls.handle_keydown(keydown(pygame.K_r))
    assert tuning.config_dirty


_PERSISTED_MUTATIONS: list[
    tuple[str, Callable[[TuningControls], None], tuple[str, ...], dict[str, object]]
] = [
    ("layer_z_order", _mutate_layer_z_order, ("layer_1", "layer_2", "layer_3"), {}),
    ("stem.enabled", _mutate_stem_enabled, ("layer_1",), {}),
    ("stem.opacity", _mutate_stem_opacity, ("layer_1",), {}),
    ("stem.blend_mode", _mutate_stem_blend_mode, ("layer_1",), {}),
    ("stem.locked", _mutate_stem_locked, ("layer_1",), {}),
    ("stem.beat_sensitivity", _mutate_stem_beat_sensitivity, ("layer_1",), {}),
    ("stem.effects", _mutate_stem_effects, ("layer_1",), {}),
    ("stem.preset", _mutate_preset_path, ("layer_1",), {}),
    ("stem.preset_switching", _mutate_preset_switching, ("layer_1",), {}),
    ("render_overlay.enabled", _mutate_render_overlay_enabled, ("layer_1",), {}),
    ("render_overlay.locked", _mutate_render_overlay_locked, ("layer_1",), {}),
    ("render_overlay.position", _mutate_render_overlay_position, ("layer_1",), {}),
    ("render_overlay.title_font_size", _mutate_render_overlay_title_font_size, ("layer_1",), {}),
    ("render_overlay.title_margin_bottom", _mutate_render_overlay_title_margin_bottom, ("layer_1",), {}),
    ("render_overlay.body_font_size", _mutate_render_overlay_body_font_size, ("layer_1",), {}),
    ("render_overlay.opacity_pct", _mutate_render_overlay_opacity, ("layer_1",), {}),
    ("render_overlay.border_width", _mutate_render_overlay_border_width, ("layer_1",), {}),
    ("render_overlay.start_delay", _mutate_render_overlay_start_delay, ("layer_1",), {}),
    ("render_overlay.display_time", _mutate_render_overlay_display_time, ("layer_1",), {}),
    ("render_post_fx.enabled", _mutate_render_post_fx_enabled, ("layer_1",), {}),
    ("render_post_fx.locked", _mutate_render_post_fx_locked, ("layer_1",), {}),
    ("render_post_fx.fade_in", _mutate_render_post_fx_fade_in, ("layer_1",), {}),
    ("render_post_fx.fade_out", _mutate_render_post_fx_fade_out, ("layer_1",), {}),
    ("render_post_fx.highlight_rolloff.mode", _mutate_render_post_fx_highlight_rolloff_mode, ("layer_1",), {}),
    ("render_post_fx.highlight_rolloff.curve", _mutate_render_post_fx_highlight_rolloff_curve, ("layer_1",), {}),
    ("render_post_fx.highlight_rolloff.threshold_pct", _mutate_render_post_fx_highlight_rolloff_threshold, ("layer_1",), {}),
    ("render_post_fx.highlight_rolloff.ceiling_pct", _mutate_render_post_fx_highlight_rolloff_ceiling, ("layer_1",), {}),
    ("render_post_fx.highlight_rolloff.strength_pct", _mutate_render_post_fx_highlight_rolloff_strength, ("layer_1",), {}),
    ("render_post_fx.highlight_rolloff.softness_pct", _mutate_render_post_fx_highlight_rolloff_softness, ("layer_1",), {}),
    ("render_post_fx.highlight_rolloff.desaturation_pct", _mutate_render_post_fx_highlight_rolloff_desaturation, ("layer_1",), {}),
    ("render_post_fx.chroma_boost.mode", _mutate_render_post_fx_chroma_boost_mode, ("layer_1",), {}),
    ("render_post_fx.chroma_boost.variant", _mutate_render_post_fx_chroma_boost_variant, ("layer_1",), {}),
    ("render_post_fx.chroma_boost.amount_pct", _mutate_render_post_fx_chroma_boost_amount, ("layer_1",), {}),
    ("timeline.enabled", _mutate_timeline_enabled, ("layer_1",), {"timeline_enabled": True}),
    ("timeline.locked", _mutate_timeline_locked, ("layer_1",), {}),
]


@pytest.mark.parametrize(
    "field_id,mutate,stems,make_kwargs",
    _PERSISTED_MUTATIONS,
    ids=[item[0] for item in _PERSISTED_MUTATIONS],
)
def test_persisted_mutation_marks_config_dirty(
    field_id: str,
    mutate: Callable[[TuningControls], None],
    stems: tuple[str, ...],
    make_kwargs: dict[str, object],
) -> None:
    del field_id
    controls = _make_controls(stems, **make_kwargs)
    assert not controls.config_dirty
    mutate(controls)
    assert controls.config_dirty


@patch("cleave.viz.fonts.render_overlay_system_fonts", return_value=["alpha", "bravo"])
@pytest.mark.parametrize(
    "mutate",
    [_mutate_render_overlay_title_font, _mutate_render_overlay_body_font],
    ids=["render_overlay.title_font", "render_overlay.body_font"],
)
def test_persisted_font_mutation_marks_config_dirty(
    _mock_fonts: object,
    mutate: Callable[[TuningControls], None],
) -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    mutate(controls)
    assert controls.config_dirty


def test_persisted_timeline_cue_record_marks_config_dirty() -> None:
    _mutate_timeline_cues_via_record()


def test_render_overlay_display_time_keyboard_regression() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _mutate_render_overlay_display_time(controls)
    assert controls.config_dirty
    assert controls.session.render_overlay.display_time > 0.0


def test_display_time_mutation_clears_dirty_after_save() -> None:
    saved_path = Path("/tmp/projects/my-track/unnamed-2.yaml")
    controls = _make_controls(("layer_1",))
    controls._config_save._on_save_new_config = lambda: saved_path
    _mutate_render_overlay_display_time(controls)
    assert controls.config_dirty

    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = _desc(view, _config_header_row(view))
    _choose_save_as_new(controls)
    assert not controls.config_dirty


def _mutate_track_expanded(controls: TuningControls) -> None:
    _expand_layer_1(controls)


def _mutate_effects_expanded(controls: TuningControls) -> None:
    _expand_layer_1(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_EFFECTS_HEADER))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_solo_slot(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_HEADER))
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))


def _mutate_timeline_panel_open(controls: TuningControls) -> None:
    controls.session.timeline.enabled = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_render_overlay_expanded(controls: TuningControls) -> None:
    _expand_render_overlay(controls)


def _mutate_render_overlay_solo(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAY_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))


def _mutate_render_post_fx_expanded(controls: TuningControls) -> None:
    _expand_render_post_fx(controls)


def _mutate_render_post_fx_solo(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))


def _mutate_move_mode_without_confirm(controls: TuningControls) -> None:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_2", RowKind.TRACK_HEADER))
    controls.handle_keydown(_keydown(pygame.K_m))
    controls.handle_keydown(_keydown(pygame.K_UP))


def _mutate_help_visible(controls: TuningControls) -> None:
    controls.session.help_visible = True


def _mutate_settings_preview_quality(controls: TuningControls) -> None:
    _expand_settings(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_settings_ui_fade(controls: TuningControls) -> None:
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_FADE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_settings_ui_width(controls: TuningControls) -> None:
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_settings_ui_width_mode(controls: TuningControls) -> None:
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH_MODE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _mutate_focus_navigation(controls: TuningControls) -> None:
    controls.handle_keydown(_keydown(pygame.K_DOWN))


def _mutate_timeline_arm(controls: TuningControls) -> None:
    del controls
    timeline_controls, session, _, _, _, _ = _make_timeline_controls(
        focus_row=0,
    )
    assert "layer_1" not in session.timeline.armed_slots
    timeline_controls.handle_keydown(keydown(pygame.K_a))
    assert "layer_1" in session.timeline.armed_slots


def _mutate_timeline_recording_start(controls: TuningControls) -> None:
    del controls
    timeline_controls, session, _, _, _, _ = _make_timeline_controls(
        focus_row=0,
        armed_slots={"layer_1"},
    )
    timeline_controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.recording is True


def _mutate_timeline_preview_pause(controls: TuningControls) -> None:
    del controls
    timeline_controls, session, _, _, _, _ = _make_timeline_controls()
    timeline_controls.handle_keydown(keydown(pygame.K_SPACE))
    assert session.timeline.preview_active is True


_SESSION_ONLY_MUTATIONS: list[tuple[str, Callable[[TuningControls], None], tuple[str, ...]]] = [
    ("track.expanded", _mutate_track_expanded, ("layer_1", "layer_2")),
    ("track.effects_expanded", _mutate_effects_expanded, ("layer_1",)),
    ("solo_slot", _mutate_solo_slot, ("layer_1",)),
    ("timeline.panel_open", _mutate_timeline_panel_open, ("layer_1",)),
    ("render_overlay.expanded", _mutate_render_overlay_expanded, ("layer_1",)),
    ("render_overlay.solo", _mutate_render_overlay_solo, ("layer_1",)),
    ("render_post_fx.expanded", _mutate_render_post_fx_expanded, ("layer_1",)),
    ("render_post_fx.solo", _mutate_render_post_fx_solo, ("layer_1",)),
    ("move_mode.swap", _mutate_move_mode_without_confirm, ("layer_1", "layer_2")),
    ("help_visible", _mutate_help_visible, ("layer_1",)),
    ("settings.preview_quality", _mutate_settings_preview_quality, ("layer_1",)),
    ("settings.ui_fade", _mutate_settings_ui_fade, ("layer_1",)),
    ("settings.ui_width", _mutate_settings_ui_width, ("layer_1",)),
    ("settings.ui_width_mode", _mutate_settings_ui_width_mode, ("layer_1",)),
    ("focus_navigation", _mutate_focus_navigation, ("layer_1",)),
    ("timeline.armed", _mutate_timeline_arm, ("layer_1",)),
    ("timeline.recording", _mutate_timeline_recording_start, ("layer_1",)),
    ("timeline.preview", _mutate_timeline_preview_pause, ("layer_1",)),
]


@pytest.mark.parametrize(
    "field_id,mutate,stems",
    _SESSION_ONLY_MUTATIONS,
    ids=[item[0] for item in _SESSION_ONLY_MUTATIONS],
)
def test_session_only_mutation_does_not_mark_config_dirty(
    field_id: str,
    mutate: Callable[[TuningControls], None],
    stems: tuple[str, ...],
) -> None:
    del field_id
    controls = _make_controls(stems, timeline_enabled=True)
    assert not controls.config_dirty
    mutate(controls)
    assert not controls.config_dirty
