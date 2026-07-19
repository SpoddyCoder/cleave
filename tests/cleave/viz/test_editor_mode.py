"""Tests for preset curation editor mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame

from cleave.config_schema import persisted_session_payload
from cleave.viz.focus_nav import MainFocus
from cleave.viz.modal import ModalKind
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.tuning_view_state import SettingsBlock, TrackBlock, TuningViewState, view_state_structure_signature
from tests.cleave.viz.test_controls import _make_controls, _mutate_dirty
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.viz import keydown, make_playlist, make_test_cfg


def _curation_view_state(**kwargs: object) -> TuningViewState:
    defaults: dict[str, object] = {
        "settings": SettingsBlock(expanded=True, editor_mode="preset_curation"),
        "layer_z_order": ("layer_1", "layer_2"),
        "tracks": {
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=True,
            ),
            "layer_2": TrackBlock(
                stem="bass",
                preset_dir_label="dir2",
                preset_label="preset2.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=True,
            ),
        },
    }
    defaults.update(kwargs)
    return _minimal_view_state(**defaults)


def test_structure_signature_invalidates_on_editor_mode() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.settings.editor_mode = "preset_curation"
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_curation_layout_allowlist() -> None:
    state = _curation_view_state()
    kinds = [row.kind for row in state.layout.rows]
    slots = [row.slot for row in state.layout.rows if row.slot is not None]

    assert RowKind.SETTINGS_HEADER in kinds
    assert RowKind.SETTINGS_EDITOR_MODE in kinds
    assert RowKind.TRANSPORT in kinds
    assert RowKind.CONFIG_HEADER not in kinds
    assert RowKind.RENDER_SECTION_GAP not in kinds
    assert RowKind.RENDER_OVERLAY_HEADER not in kinds
    assert RowKind.RENDER_TIMELINE_HEADER not in kinds
    assert RowKind.LAYER_MANAGEMENT_ADD not in kinds

    track_headers = [
        row for row in state.layout.rows if row.kind == RowKind.TRACK_HEADER
    ]
    assert len(track_headers) == 1
    assert track_headers[0].slot == "layer_1"
    assert "layer_2" not in slots

    layer_1_kinds = {
        row.kind
        for row in state.layout.rows
        if row.slot == "layer_1" and row.kind != RowKind.TRACK_HEADER
    }
    assert layer_1_kinds == {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
    }


def test_curation_ignores_non_allowlisted_keys() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.settings.editor_mode = "preset_curation"
    layer = controls.session.layers["layer_1"]
    layer.expanded = True
    controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    )

    before_opacity = layer.opacity_pct
    was_enabled = layer.enabled

    controls.handle_keydown(keydown(pygame.K_l))
    assert layer.locked is False

    controls.handle_keydown(keydown(pygame.K_m))
    assert controls.move_mode_slot is None

    controls.handle_keydown(keydown(pygame.K_DELETE))
    assert "layer_1" in controls.session.layers

    controls.handle_keydown(keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
    assert controls.session.solo_slot is None

    controls.handle_keydown(keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert layer.enabled is was_enabled

    controls.handle_keydown(keydown(pygame.K_t))
    assert controls.session.timeline.panel_open is False

    controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    )
    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert layer.opacity_pct == before_opacity


def test_curation_ignores_timeline_for_layer_visibility() -> None:
    from cleave.viz.layer_visibility import effective_layer_enabled

    controls = _make_controls(("layer_1", "layer_2"))
    session = controls.session
    session.settings.editor_mode = "preset_curation"
    session.timeline.enabled = True
    session.layers["layer_1"].enabled = True
    session.layers["layer_2"].enabled = False
    assert effective_layer_enabled(session, "layer_1", 0.0) is True
    assert effective_layer_enabled(session, "layer_2", 0.0) is False


def test_enter_curation_expands_layer_one() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.layers["layer_1"].expanded = False
    controls.session.settings.expanded = True
    controls.focus_cursor = MainFocus(RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert controls.session.settings.editor_mode == "visualizer"
    assert controls.session.settings.editor_mode_selection == "preset_curation"

    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert not controls.modal_host.active
    assert controls.session.settings.editor_mode == "preset_curation"
    assert controls.session.layers["layer_1"].expanded is True


def test_curation_allowlisted_keys_still_work() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.settings.editor_mode = "preset_curation"
    controls.session.settings.editor_mode_selection = "preset_curation"
    controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    )
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation
    controls.handle_keydown(keydown(pygame.K_f))
    mock_curation.prompt_favourite.assert_called_once()

    was_paused = controls.playback.paused
    controls.handle_keydown(keydown(pygame.K_SPACE))
    assert controls.playback.paused != was_paused


def test_curation_ignores_layer_lock() -> None:
    from cleave.viz.row_layout import row_navigable
    from cleave.viz.row_semantics import section_locked
    from cleave.viz.theme import VALUE
    from cleave.viz.tuning_panel_draw import _row_value_color

    controls = _make_controls(("layer_1",))
    controls.session.settings.editor_mode = "preset_curation"
    controls.session.settings.editor_mode_selection = "preset_curation"
    layer = controls.session.layers["layer_1"]
    layer.locked = True
    layer.expanded = True

    view = controls.build_view_state(paused=True)
    header = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert section_locked(view, header) is False
    assert section_locked(controls.session, preset) is False
    assert view.tracks["layer_1"].locked is True
    assert row_navigable(view, preset) is True
    preset_index = view.layout.find_descriptor(preset)
    assert _row_value_color(view, preset_index) == VALUE

    controls.focus_cursor = MainFocus(preset)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation
    controls.handle_keydown(keydown(pygame.K_f))
    mock_curation.prompt_favourite.assert_called_once()


def test_dirty_enter_modal_cancel_stays_visualizer() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    controls.session.settings.expanded = True
    controls.focus_cursor = MainFocus(RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert controls.session.settings.editor_mode == "visualizer"
    controls.handle_keydown(keydown(pygame.K_RETURN))
    assert controls.modal_host.active
    view = controls.modal_host.view_state()
    assert view.kind == ModalKind.CHOICE
    assert list(view.options) == ["Yes", "Discard Changes", "Cancel"]

    controls.handle_keydown(keydown(pygame.K_ESCAPE))
    assert not controls.modal_host.active
    assert controls.session.settings.editor_mode == "visualizer"
    assert controls.session.settings.editor_mode_selection == "visualizer"


def test_exit_curation_reloads_and_clears_dirty() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.settings.editor_mode = "preset_curation"
    session.settings.editor_mode_selection = "preset_curation"
    session.layers["layer_1"].opacity_pct = 12
    controls._config_save.clear_config_dirty()
    session.layers["layer_1"].opacity_pct = 99
    assert controls.config_dirty

    reloaded_cfg = make_test_cfg(("layer_1",))
    fresh_playlists = {
        slot: (
            session.layers[slot].playlist
            if slot in session.layers
            else make_playlist(slot)
        )
        for slot in reloaded_cfg.layers
    }

    with (
        patch("cleave.viz.editor_mode_controls.load_config", return_value=reloaded_cfg),
        patch(
            "cleave.viz.editor_mode_controls.scan_all_layers",
            return_value=fresh_playlists,
        ),
        patch(
            "cleave.viz.editor_mode_controls.load_manifest",
            return_value=MagicMock(song_markers=[]),
        ),
    ):
        controls.session.settings.expanded = True
        controls.focus_cursor = MainFocus(RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))
        controls.handle_keydown(keydown(pygame.K_LEFT))
        assert controls.session.settings.editor_mode == "preset_curation"
        assert controls.session.settings.editor_mode_selection == "visualizer"
        controls.handle_keydown(keydown(pygame.K_RETURN))
        assert not controls.modal_host.active

    assert controls.session.settings.editor_mode == "visualizer"
    assert not controls.config_dirty


def test_horizontal_only_stages_editor_mode() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.settings.expanded = True
    controls.focus_cursor = MainFocus(RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert controls.session.settings.editor_mode == "visualizer"
    assert controls.session.settings.editor_mode_selection == "preset_curation"
    assert not controls.modal_host.active
    state = controls.build_view_state(paused=True)
    assert state.settings.editor_mode_selection == "preset_curation"
    from cleave.viz.row_fields import editor_mode_confirm_pending, format_row_value

    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))
        == "preset curation"
    )
    assert editor_mode_confirm_pending(state) is True

    controls.handle_keydown(keydown(pygame.K_LEFT))
    assert controls.session.settings.editor_mode_selection == "visualizer"
    state = controls.build_view_state(paused=True)
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))
        == "visualizer"
    )


def test_navigate_away_reverts_editor_mode_selection() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.settings.expanded = True
    controls.focus_cursor = MainFocus(RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))

    controls.handle_keydown(keydown(pygame.K_RIGHT))
    assert controls.session.settings.editor_mode_selection == "preset_curation"

    controls.handle_keydown(keydown(pygame.K_DOWN))
    assert controls.session.settings.editor_mode == "visualizer"
    assert controls.session.settings.editor_mode_selection == "visualizer"
    assert controls.focus_descriptor.kind != RowKind.SETTINGS_EDITOR_MODE


def test_flexible_mode_expands_for_editor_mode_confirm_suffix() -> None:
    """Staged confirm icon must widen the editor-mode row (and flexible panels)."""
    import pygame
    from cleave.viz.material_icons import action_enter_icon_suffix_width
    from cleave.viz.theme import panel_content_max_width_px
    from cleave.viz.tuning_panel_draw import TuningOverlay, fit_row_text
    from cleave.viz.tuning_view_state import SettingsBlock, TrackBlock
    from tests.cleave.viz.test_overlay import _minimal_view_state

    pygame.init()
    long_preset = (
        "very/long/path/to/presets/cream-of-the-crop/"
        "Some Extremely Long Preset Name That Forces Max Width.milk"
    )
    tracks = {
        "layer_1": TrackBlock(
            stem="drums",
            preset_dir_label="dir",
            preset_label=long_preset,
            blend_mode="black-key",
            opacity_pct=50,
            beat_sensitivity=1.0,
            effects={},
            expanded=True,
        )
    }

    def _compose(
        *,
        ui_width_mode: str,
        editor_mode: str,
        selection: str,
    ) -> tuple[int, str, int, int]:
        state = _minimal_view_state(
            settings=SettingsBlock(
                expanded=True,
                editor_mode=editor_mode,
                editor_mode_selection=selection,
                ui_width_mode=ui_width_mode,
                ui_width=100,
            ),
            tracks=tracks,
            layer_z_order=["layer_1"],
        )
        state.focus_cursor = MainFocus(RowDescriptor(RowKind.SETTINGS_EDITOR_MODE))
        overlay = TuningOverlay()
        overlay.notify_input()
        composed = overlay.compose_panel(
            state, viewport_width=1280, viewport_height=720
        )
        assert composed is not None
        font = overlay._font_get()
        line_h = font.get_linesize()
        idx = state.layout.find_by_kind(RowKind.SETTINGS_EDITOR_MODE)
        text = fit_row_text(
            font,
            state,
            idx,
            max_content_width=panel_content_max_width_px(100),
        )
        _, _, row_w = overlay._build_row_at_index(
            font,
            state,
            idx,
            max_content_width=panel_content_max_width_px(100),
            line_h=line_h,
        )
        return composed.panel_size[0], text, row_w, line_h

    max_panel_w = panel_content_max_width_px(100) + 2 * TuningOverlay()._padding
    pending_w, pending_text, pending_row_w, line_h = _compose(
        ui_width_mode="flexible",
        editor_mode="visualizer",
        selection="preset_curation",
    )
    _, confirmed_text, confirmed_row_w, _ = _compose(
        ui_width_mode="flexible",
        editor_mode="preset_curation",
        selection="preset_curation",
    )
    assert "[Enter to confirm]" not in pending_text
    assert "preset curation" in pending_text
    assert "preset curation" in confirmed_text
    assert pending_row_w == confirmed_row_w + action_enter_icon_suffix_width(line_h)
    assert pending_w > max_panel_w

    fixed_w, fixed_text, _, _ = _compose(
        ui_width_mode="fixed",
        editor_mode="visualizer",
        selection="preset_curation",
    )
    assert fixed_w == max_panel_w
    assert "[Enter to confirm]" not in fixed_text


def test_editor_mode_absent_from_persisted_payload() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.settings.editor_mode = "preset_curation"
    controls.session.settings.editor_mode_selection = "preset_curation"
    payload = persisted_session_payload(controls.cfg, controls.session)
    assert "editor_mode" not in payload
    settings_blob = payload.get("settings")
    if settings_blob is not None:
        assert "editor_mode" not in settings_blob
