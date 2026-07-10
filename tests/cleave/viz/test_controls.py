"""Unit-style tests for live tuning controls (no Milkdrop window)."""

from __future__ import annotations

import io
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pygame
import pytest

_MOVE_MODE_KEY = pygame.K_m

from cleave.config_schema import DEFAULT_LAYER_SLOTS, MAX_LAYER_COUNT
from tests.support.config import TEST_LAYER_STEMS
from cleave.preset_playlist import (
    PresetPlaylist,
    directory_display,
    playlist_at_dir,
    preset_browse_floor,
    preset_filename_display,
    scan_preset_playlist,
)
from cleave.timeline import TimelineCue
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.key_repeat import mod_shift
from cleave.viz.playback import format_mmss
from tests.support.viz import make_test_cfg, noop_layer_bindings, stub_playback_state
from cleave.viz.controls import (
    NOTIFICATION_TIMELINE_DISABLED_TEXT,
    NOTIFICATION_TIMELINE_ENABLED_TEXT,
    SEEK_LONG,
    SEEK_SHORT,
    TuningControls,
)
from cleave.viz.panel_notification import NOTIFICATION_DURATION_SEC
from cleave.viz.modal import ModalKind
from cleave.viz.session import (
    LayerRuntime,
    TimelineRuntime,
    TuningSession,
    allow_overwrite_for_path,
    config_path_display,
)
from cleave.viz.row_semantics import REPEAT_ROW_KINDS
from cleave.viz.theme import (
    DISABLED,
    HIGHLIGHT,
    LOCKED,
    MOVE_MODE,
    SOLO_BG,
    VALUE,
)
from cleave.viz.material_icons import (
    FILE_GLYPH,
    FOLDER_GLYPH,
    LOCK_GLYPH,
    VISIBILITY_GLYPH,
    VISIBILITY_OFF_GLYPH,
    render_glyph,
    render_transport_icons,
    row_icon_prefix_width,
    track_header_lock_suffix_width,
    visibility_icon_prefix_width,
)
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.tuning_panel_draw import (
    TREE_INDENT,
    _row_bg_color,
    _row_indent,
    _row_text,
    _row_value_color,
    fit_row_text,
    preset_row_prefix_width,
    render_visibility_icon,
    track_header_prefix_width,
)
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState
from tests.support.viz import baseline_tuning_ui_metrics


def _keydown(key: int, *, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def _overlay_font() -> pygame.font.Font:
    pygame.font.init()
    return pygame.font.SysFont("monospace", baseline_tuning_ui_metrics().font_size)


def _make_playlist(name: str, count: int = 3) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{name}")
    paths = tuple(current_dir / f"preset-{i}.milk" for i in range(count))
    return PresetPlaylist(current_dir=current_dir, paths=paths, index=0)


_REPO_ROOT_EXAMPLE = Path("/tmp/cleave-viz.yaml")
_DEFAULT_ACTIVE_CONFIG = Path("/tmp/projects/my-track/active.yaml")


def _mutate_dirty(controls: TuningControls) -> None:
    controls.session.layers["layer_1"].opacity_pct = 60


def _make_controls(
    slots: tuple[str, ...] = ("layer_1", "layer_2"),
    *,
    timeline_enabled: bool = False,
    launch_config_path: Path | None = _DEFAULT_ACTIVE_CONFIG,
    repo_root_example: Path = _REPO_ROOT_EXAMPLE,
) -> TuningControls:
    preset_root = Path("/tmp/presets")
    cfg = make_test_cfg(slots, preset_root=preset_root, config_path=launch_config_path or _DEFAULT_ACTIVE_CONFIG)
    session = TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=_make_playlist(slot),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
                opacity_pct=50,
                expanded=True,
            )
            for slot in slots
        },
        timeline=TimelineRuntime(enabled=timeline_enabled),
    )
    return TuningControls(
        session,
        cfg,
        preset_root=preset_root,
        playback=stub_playback_state(),
        duration_sec=120.0,
        launch_config_path=launch_config_path,
        repo_root_example=repo_root_example,
    )


def _make_controls_with_manager(
    slots: tuple[str, ...] = ("layer_1",),
    *,
    can_add: bool = True,
    can_remove: bool = True,
    launch_config_path: Path | None = _DEFAULT_ACTIVE_CONFIG,
    repo_root_example: Path = _REPO_ROOT_EXAMPLE,
) -> tuple[TuningControls, MagicMock]:
    preset_root = Path("/tmp/presets")
    cfg = make_test_cfg(slots, preset_root=preset_root, config_path=launch_config_path or _DEFAULT_ACTIVE_CONFIG)
    session = TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=_make_playlist(slot),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
                opacity_pct=50,
                expanded=True,
            )
            for slot in slots
        },
    )
    layer_manager = MagicMock()
    layer_manager.can_add.return_value = can_add
    layer_manager.can_remove.return_value = can_remove
    controls = TuningControls(
        session,
        cfg,
        preset_root=preset_root,
        playback=stub_playback_state(),
        duration_sec=120.0,
        launch_config_path=launch_config_path,
        repo_root_example=repo_root_example,
        layer_manager=layer_manager,
    )
    return controls, layer_manager


def _confirm_modal_yes(controls: TuningControls) -> None:
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    controls.handle_keydown(_keydown(pygame.K_RETURN))


def _config_header_row(view: TuningViewState) -> int:
    return next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.CONFIG_HEADER
    )


def _choose_save_as_new(controls: TuningControls) -> None:
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    target = modal_view.options.index("SAVE AS NEW")
    while controls.modal_host.view_state().focus_index != target:
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_keydown(_keydown(pygame.K_RETURN))


def _choose_overwrite(controls: TuningControls) -> None:
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    controls.handle_keydown(_keydown(pygame.K_RETURN))


def test_build_view_state_passes_fps() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False, fps=42.0)
    assert view.fps == 42.0


def test_add_layer_row_omitted_at_max() -> None:
    controls, manager = _make_controls_with_manager(("layer_1",), can_add=False)
    with patch("cleave.viz.row_layout.MAX_LAYER_COUNT", 1):
        view = controls.build_view_state(paused=False)
        with pytest.raises(ValueError, match="no row for kind"):
            view.layout.find_by_kind(RowKind.LAYER_MANAGEMENT_ADD)
    controls.focus_descriptor = RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD)

    controls.handle_keydown(_keydown(pygame.K_RETURN))

    manager.add_layer.assert_not_called()
    assert controls.modal_host.view_state() is None


def test_delete_layer_at_min_shows_toast() -> None:
    controls, manager = _make_controls_with_manager(("layer_1",), can_remove=False)
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(view.layout.find(
        "layer_1", RowKind.LAYER_MANAGEMENT_DELETE
    ))

    controls.handle_keydown(_keydown(pygame.K_RETURN))

    manager.remove_layer.assert_not_called()
    assert controls.modal_host.view_state() is None
    assert (
        controls.build_view_state(paused=False).notification_message
        == "Must have at least 1 layer"
    )


def test_add_layer_confirm_calls_manager() -> None:
    controls, manager = _make_controls_with_manager(("layer_1",))

    def add_layer() -> None:
        controls.session.layer_z_order.append("layer_2")
        controls.session.layers["layer_2"] = LayerRuntime(
            playlist=_make_playlist("layer_2"),
            browse_floor=Path("/tmp/presets/layer_2"),
            stem="bass",
            opacity_pct=50,
        )

    manager.add_layer.side_effect = add_layer
    view = controls.build_view_state(paused=False)
    before_count = len(view.layout)
    controls.focus_descriptor = RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD)

    _confirm_modal_yes(controls)

    manager.add_layer.assert_called_once()
    view = controls.build_view_state(paused=False)
    assert len(view.layout) > before_count
    assert "layer_2" in controls.session.layer_z_order


@pytest.mark.parametrize("confirm_key", (pygame.K_RETURN, pygame.K_DELETE))
def test_delete_layer_confirm_calls_manager(confirm_key: int) -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))
    controls.session.layers["layer_2"].expanded = True

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(view.layout.find(
        "layer_2", RowKind.LAYER_MANAGEMENT_DELETE
    ))

    controls.handle_keydown(_keydown(confirm_key))
    controls.handle_keydown(_keydown(pygame.K_RETURN))

    manager.remove_layer.assert_called_once_with("layer_2")
    assert "layer_2" not in controls.session.layer_z_order


def test_delete_layer_from_header_with_delete_key() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(view.layout.find( "layer_2", RowKind.TRACK_HEADER))

    controls.handle_keydown(_keydown(pygame.K_DELETE))
    controls.handle_keydown(_keydown(pygame.K_RETURN))

    manager.remove_layer.assert_called_once_with("layer_2")
    assert "layer_2" not in controls.session.layer_z_order


def test_delete_layer_clamps_timeline_focus_row() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    controls, manager = _make_controls_with_manager(slots)
    controls.session.timeline.enabled = True
    controls.session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(3)

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    controls._confirm_delete_layer("layer_4")

    manager.remove_layer.assert_called_once_with("layer_4")
    assert len(controls.session.layer_z_order) == 3
    assert controls.session.timeline.focus_row == 2


def test_delete_layer_exits_move_mode() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))
    controls.session.layers["layer_2"].expanded = True

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_HEADER))
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    assert controls.move_mode_slot == "layer_1"

    controls._delete_layer("layer_2")
    controls.handle_keydown(_keydown(pygame.K_RETURN))

    assert controls.move_mode_slot is None
    manager.remove_layer.assert_called_once_with("layer_2")


def _row(
    view: TuningViewState,
    stem: str,
    kind: RowKind,
    *,
    effect_id: str | None = None,
    driver_slug: str | None = None,
) -> int:
    return view.layout.find(stem, kind, effect_id=effect_id, driver_slug=driver_slug)


def _desc(view: TuningViewState, index: int) -> RowDescriptor:
    return view.layout.descriptor(index)


def _expand_settings(controls: TuningControls) -> None:
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _expand_settings_ui(controls: TuningControls) -> None:
    _expand_settings(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))


def _focus_index(controls: TuningControls, *, paused: bool = False) -> int:
    view = controls.build_view_state(paused=paused)
    return view.layout.find_descriptor(controls.focus_descriptor)


def test_allow_overwrite_for_path_hides_repo_root_template_only() -> None:
    root = Path("/repo/cleave-viz.yaml")
    assert allow_overwrite_for_path(root, repo_root_example=root) is False
    assert (
        allow_overwrite_for_path(
            Path("/repo/projects/my-track/foo.yaml"),
            repo_root_example=root,
        )
        is True
    )
    assert allow_overwrite_for_path(None, repo_root_example=root) is False


def test_focus_navigation_wraps() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    navigable = view.layout.navigable_indices(view)
    transport_row = view.layout.find_by_kind(RowKind.TRANSPORT)
    start_pos = navigable.index(transport_row)
    assert controls.focus_descriptor == _desc(view, transport_row)

    for step in range(1, len(navigable)):
        assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
        assert controls.focus_descriptor == _desc(view, navigable[(start_pos + step) % len(navigable)])

    assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
    assert controls.focus_descriptor == _desc(view, transport_row)

    assert controls.handle_keydown(_keydown(pygame.K_UP)) is True
    assert controls.focus_descriptor == _desc(view, navigable[start_pos - 1])


def test_opacity_clamps() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    opacity_row = _row(view, "layer_1", RowKind.TRACK_OPACITY)
    controls.focus_descriptor = _desc(view, opacity_row)
    for _ in range(60):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].opacity_pct == 100

    for _ in range(120):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].opacity_pct == 0


def test_header_toggles_enabled() -> None:
    enabled_events: list[tuple[str, bool]] = []
    controls = _make_controls(("layer_1",))
    controls._layer_bindings = noop_layer_bindings(
        on_layer_enabled_change=lambda stem, on: enabled_events.append((stem, on))
    )

    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.session.layers["layer_1"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].enabled is False
    assert enabled_events == [("layer_1", False)]
    assert controls.session.layers["layer_1"].opacity_pct == 50

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].enabled is True
    assert enabled_events == [("layer_1", False), ("layer_1", True)]
    assert controls.session.layers["layer_1"].opacity_pct == 50


def test_navigation_skips_sub_rows_when_collapsed() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.layers["layer_1"].enabled = False
    controls.session.layers["layer_1"].expanded = False
    view = controls.build_view_state(paused=False)

    drums_header = next(
        i
        for i in range(len(view.layout))
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_1"
    )
    bass_header = next(
        i
        for i in range(len(view.layout))
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_2"
    )
    navigable = view.layout.navigable_indices(view)
    assert drums_header in navigable
    assert bass_header in navigable
    for i in navigable:
        stem = view.layout.slot( i)
        if stem == "layer_1":
            assert view.layout.kind(i) == RowKind.TRACK_HEADER

    controls.focus_descriptor = _desc(view, drums_header)
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, bass_header)


def test_re_enable_without_expanding() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].enabled = False
    controls.session.layers["layer_1"].expanded = False
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    add_layer_row = view.layout.find_by_kind(RowKind.LAYER_MANAGEMENT_ADD)
    render_overlay_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_HEADER)
    transport_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.TRANSPORT
    )
    controls.focus_descriptor = _desc(view, header_row)
    render_post_fx_row = view.layout.find_by_kind(RowKind.RENDER_POST_FX_HEADER)
    render_timeline_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, add_layer_row)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, render_overlay_row)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, render_post_fx_row)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, render_timeline_row)

    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].enabled is True
    assert controls.session.layers["layer_1"].expanded is False

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, add_layer_row)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, render_overlay_row)


def test_header_collapses_and_expands_sub_rows() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = False
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    preset_dir_desc = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.session.layers["layer_1"].expanded is False
    assert not view.layout.contains_descriptor(preset_dir_desc)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].expanded is True

    view = controls.build_view_state(paused=False)
    preset_dir_row = _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)
    assert preset_dir_row in view.layout.navigable_indices(view)
    assert preset_dir_row in view.layout.visible_indices(view)


def test_disable_auto_collapses_sub_rows() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    preset_dir_row = _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)
    assert controls.focus_descriptor == _desc(view, preset_dir_row)

    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].enabled is False
    assert controls.session.layers["layer_1"].expanded is False
    assert controls.focus_descriptor == _desc(view, header_row)

    view = controls.build_view_state(paused=False)
    preset_dir_desc = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    assert not view.layout.contains_descriptor(preset_dir_desc)


def test_disabled_track_can_expand_sub_rows() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].enabled is False
    assert controls.session.layers["layer_1"].expanded is False

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].enabled is False
    assert controls.session.layers["layer_1"].expanded is True

    view = controls.build_view_state(paused=False)
    preset_dir_row = _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)
    assert preset_dir_row in view.layout.visible_indices(view)
    assert preset_dir_row in view.layout.navigable_indices(view)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, preset_dir_row)


def test_beat_sensitivity_clamps() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    beat_row = _row(view, "layer_1", RowKind.TRACK_BEAT)
    controls.focus_descriptor = _desc(view, beat_row)
    for _ in range(400):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].beat_sensitivity == pytest.approx(5.0)

    for _ in range(500):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].beat_sensitivity == pytest.approx(0.0)


def test_opacity_ctrl_step_is_ten_percent() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    opacity_row = _row(view, "layer_1", RowKind.TRACK_OPACITY)
    controls.focus_descriptor = _desc(view, opacity_row)
    controls.session.layers["layer_1"].opacity_pct = 50

    controls.handle_keydown(
        _keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL),
    )
    assert controls.session.layers["layer_1"].opacity_pct == 60

    controls.handle_keydown(
        _keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL),
    )
    assert controls.session.layers["layer_1"].opacity_pct == 50


def test_move_mode_swaps_z_order() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))

    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(15)
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_2"
    )
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.handle_keydown(_keydown(_MOVE_MODE_KEY)) is True
    assert controls.move_mode_slot == "layer_2"

    assert controls.handle_keydown(_keydown(pygame.K_UP)) is True
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]

    assert controls.handle_keydown(_keydown(_MOVE_MODE_KEY)) is True
    assert controls.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]
    assert controls.config_dirty


def test_move_mode_esc_cancels_without_applying() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))

    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(15)
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_2"
    )
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    controls.handle_keydown(_keydown(pygame.K_UP))
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]

    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_1", "layer_2", "layer_3"]
    assert not controls.config_dirty


def test_move_mode_backspace_cancels_without_applying() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))

    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(15)
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_2"
    )
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.session.layer_z_order == ["layer_1", "layer_3", "layer_2"]

    assert controls.handle_keydown(_keydown(pygame.K_BACKSPACE)) is True
    assert controls.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_1", "layer_2", "layer_3"]
    assert not controls.config_dirty


def test_save_as_new_triggers_notification_without_blocking_input() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    config_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, config_row)
    stderr = io.StringIO()
    with patch.object(time, "monotonic", return_value=1000.0):
        with patch("sys.stderr", stderr):
            controls.handle_keydown(_keydown(pygame.K_RETURN))
            modal_view = controls.modal_host.view_state()
            assert modal_view is not None
            assert modal_view.kind == ModalKind.SAVE_CHOICE
            controls.handle_keydown(_keydown(pygame.K_RIGHT))
            controls.handle_keydown(_keydown(pygame.K_RETURN))

        assert "Config saved to unnamed-1.yaml" in stderr.getvalue()
        state = controls.build_view_state(paused=False)
        assert state.notification_message == "Config saved to unnamed-1.yaml"
        assert state.notification_remaining_sec == NOTIFICATION_DURATION_SEC

        before = controls.focus_descriptor
        assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
        assert controls.focus_descriptor != before


def test_config_header_shows_active_path() -> None:
    launch_path = Path("/tmp/projects/my-track/my-track.yaml")
    controls = _make_controls(("layer_1",))
    controls._config_save._active_config_path = launch_path
    view = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.CONFIG_HEADER
    )
    assert _row_text(view, header_row) == config_path_display(launch_path)
    assert header_row in view.layout.navigable_indices(view)


def test_config_header_shows_asterisk_when_dirty() -> None:
    launch_path = Path("/tmp/projects/my-track/my-track.yaml")
    controls = _make_controls(("layer_1",))
    controls._config_save._active_config_path = launch_path
    _mutate_dirty(controls)
    view = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.CONFIG_HEADER
    )
    assert _row_text(view, header_row) == config_path_display(launch_path)
    assert view.config_dirty
    assert header_row in view.layout.navigable_indices(view)


def test_blend_and_opacity_change_sets_dirty_save_clears() -> None:
    saved_path = Path("/tmp/projects/my-track/unnamed-2.yaml")
    controls = _make_controls(("layer_1",))
    controls._config_save._on_save_new_config = lambda: saved_path
    assert not controls.config_dirty

    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_BLEND))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.config_dirty

    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_OPACITY))
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.config_dirty

    save_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, save_row)
    _choose_save_as_new(controls)
    assert not controls.config_dirty


def test_config_header_truncates_long_paths() -> None:
    long_path = Path(
        "/very/long/root/projects/my-track/nested/deep/unnamed-99.yaml"
    )
    controls = _make_controls(("layer_1",))
    controls._config_save._active_config_path = long_path
    view = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.CONFIG_HEADER
    )
    font = _overlay_font()
    panel_w = baseline_tuning_ui_metrics().panel_content_max_width
    label = fit_row_text(font, view, header_row, max_content_width=panel_w)
    icon_budget = row_icon_prefix_width(font.get_linesize())
    assert font.size(label)[0] + icon_budget <= panel_w
    assert label.startswith("…")
    assert "…/" not in label


def test_preset_row_truncates_long_filenames() -> None:
    long_name = (
        "Phat_Zylot_Eo.S. rainbow bubble_mid3-starpoints_spirals_VE "
        "- Bitcore Tweak.milk (1/50)"
    )
    view = TuningViewState(
        layer_z_order=("layer_1",),
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="short (1/1)",
                preset_label=long_name,
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                enabled=True,
                expanded=True,
                preset_empty=False,
            )
        },
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
        move_mode_slot=None,
        notification_message=None,
        notification_remaining_sec=0.0,
    )
    preset_row = _row(view, "layer_1", RowKind.TRACK_PRESET)
    font = _overlay_font()
    panel_w = baseline_tuning_ui_metrics().panel_content_max_width
    label = fit_row_text(font, view, preset_row, max_content_width=panel_w)
    prefix_w = preset_row_prefix_width(font, font.get_linesize())
    assert font.size(label)[0] <= panel_w - TREE_INDENT - prefix_w
    assert label.endswith("(1/50)")
    assert label.startswith("…")
    assert "…/" not in label


def test_fit_row_text_config_and_preset_share_panel_width() -> None:
    long_path = Path(
        "/very/long/root/projects/my-track/nested/deep/unnamed-99.yaml"
    )
    long_name = (
        "Phat_Zylot_Eo.S. rainbow bubble_mid3-starpoints_spirals_VE "
        "- Bitcore Tweak.milk (1/50)"
    )
    controls = _make_controls(("layer_1",))
    controls._config_save._active_config_path = long_path
    view = controls.build_view_state(paused=False)
    view.tracks["layer_1"] = TrackBlock(
        stem="layer_1",
        preset_dir_label="short (1/1)",
        preset_label=long_name,
        blend_mode="black-key",
        opacity_pct=50,
        beat_sensitivity=1.0,
        effects={},
        enabled=True,
        preset_empty=False,
    )
    header_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.CONFIG_HEADER
    )
    preset_row = _row(view, "layer_1", RowKind.TRACK_PRESET)
    font = _overlay_font()
    panel_w = baseline_tuning_ui_metrics().panel_content_max_width
    config_label = fit_row_text(font, view, header_row, max_content_width=panel_w)
    preset_label = fit_row_text(font, view, preset_row, max_content_width=panel_w)
    icon_budget = row_icon_prefix_width(font.get_linesize())
    preset_prefix_w = preset_row_prefix_width(font, font.get_linesize())
    assert font.size(config_label)[0] + icon_budget <= panel_w
    assert font.size(preset_label)[0] + TREE_INDENT + preset_prefix_w <= panel_w


def test_save_as_new_updates_active_config_path() -> None:
    saved_path = Path("/tmp/projects/my-track/unnamed-2.yaml")
    controls = _make_controls(("layer_1",))
    controls._config_save._on_save_new_config = lambda: saved_path

    view = controls.build_view_state(paused=False)
    save_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, save_row)
    _choose_save_as_new(controls)

    assert controls._config_save._active_config_path == saved_path
    state = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(len(state.layout)) if state.layout.kind( i) == RowKind.CONFIG_HEADER
    )
    assert _row_text(state, header_row) == config_path_display(saved_path)


def test_save_as_new_enables_overwrite_from_root_template() -> None:
    saved_path = Path("/tmp/projects/my-track/unnamed-2.yaml")
    controls = _make_controls(
        ("layer_1",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    assert controls.build_view_state(paused=False).allow_overwrite is False

    controls._config_save._on_save_new_config = lambda: saved_path
    view = controls.build_view_state(paused=False)
    save_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, save_row)
    _choose_save_as_new(controls)

    state = controls.build_view_state(paused=False)
    assert state.allow_overwrite is True
    kinds = {state.layout.kind( i) for i in range(len(state.layout))}
    assert RowKind.CONFIG_HEADER in kinds


def test_repo_root_save_shows_save_as_new_only_modal() -> None:
    controls = _make_controls(
        ("layer_1",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = _desc(view, _config_header_row(view))

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.SAVE_CHOICE
    assert modal_view.options == ("SAVE AS NEW", "CANCEL")

    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert not controls.modal_host.active
    assert controls._config_save._active_config_path == _REPO_ROOT_EXAMPLE

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert not controls.modal_host.active
    assert controls._config_save._active_config_path == _REPO_ROOT_EXAMPLE


def test_repo_root_save_as_new_requires_confirmation() -> None:
    saved_path = Path("/tmp/projects/my-track/unnamed-1.yaml")
    controls = _make_controls(
        ("layer_1",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    controls._config_save._on_save_new_config = lambda: saved_path
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = _desc(view, _config_header_row(view))

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls._config_save._active_config_path == _REPO_ROOT_EXAMPLE

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls._config_save._active_config_path == saved_path


def test_overwrite_after_save_uses_new_active_path() -> None:
    saved_path = Path("/tmp/projects/my-track/unnamed-1.yaml")
    writes: list[Path] = []
    controls = _make_controls(
        ("layer_1",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    controls._config_save._on_save_new_config = lambda: saved_path
    controls._config_save._on_overwrite_config = lambda path: writes.append(path) or path.name

    view = controls.build_view_state(paused=False)
    save_row = _config_header_row(view)

    with patch.object(time, "monotonic", return_value=3000.0):
        controls.focus_descriptor = _desc(view, save_row)
        controls.handle_keydown(_keydown(pygame.K_RETURN))
        controls.handle_keydown(_keydown(pygame.K_RETURN))

    with patch.object(time, "monotonic", return_value=3000.0 + NOTIFICATION_DURATION_SEC + 1):
        state = controls.build_view_state(paused=False)
        save_row = _config_header_row(state)
        controls.focus_descriptor = _desc(view, save_row)
        _choose_overwrite(controls)
        controls.handle_keydown(_keydown(pygame.K_RETURN))

    assert writes == [saved_path]


def test_navigable_rows_without_overwrite() -> None:
    controls = _make_controls(
        ("layer_1",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    view = controls.build_view_state(paused=False)
    assert view.allow_overwrite is False
    assert len(view.layout) == 18
    assert RowDescriptor(RowKind.TIMELINE_PRESETS) not in view.layout.rows

    kinds = {view.layout.kind(i) for i in range(len(view.layout))}
    assert RowKind.CONFIG_HEADER in kinds

    navigable = view.layout.navigable_indices(view)
    assert any(view.layout.kind(i) == RowKind.CONFIG_HEADER for i in navigable)

    transport_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.TRANSPORT
    )
    config_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, config_row)
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, transport_row)


def test_navigable_rows_with_overwrite() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    assert view.allow_overwrite is True
    assert len(view.layout) == 18
    assert RowDescriptor(RowKind.TIMELINE_PRESETS) not in view.layout.rows

    config_row = _config_header_row(view)
    assert config_row in view.layout.navigable_indices(view)


def test_save_choice_with_overwrite_includes_cancel() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = _desc(view, _config_header_row(view))
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.SAVE_CHOICE
    assert modal_view.options == ("OVERWRITE", "SAVE AS NEW", "CANCEL")

    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    assert controls.modal_host.view_state().focus_index == 2
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert not controls.modal_host.active


def test_overwrite_shows_confirm_before_write() -> None:
    launch_path = Path("/tmp/custom/cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("layer_1",), launch_config_path=launch_path)
    controls._config_save._on_overwrite_config = lambda path: (
        writes.append(path) or path.name
    )

    view = controls.build_view_state(paused=False)
    save_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, save_row)
    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.SAVE_CHOICE
    assert writes == []

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.YES_NO
    assert modal_view.message == "Overwrite cleave.config.yaml?"
    assert modal_view.options == ("Yes", "CANCEL")
    assert writes == []

    assert controls.handle_keydown(_keydown(pygame.K_n)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.YES_NO
    assert modal_view.message == "Overwrite cleave.config.yaml?"
    assert modal_view.focus_index == 1
    assert writes == []

    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    assert not controls.modal_host.active
    assert writes == []


def test_overwrite_confirm_yes_writes_launch_path() -> None:
    launch_path = Path("/tmp/my-launch.cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("layer_1",))
    controls._config_save._active_config_path = launch_path
    controls._config_save._on_overwrite_config = lambda path: (
        writes.append(path) or path.name
    )

    view = controls.build_view_state(paused=False)
    save_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, save_row)
    stderr = io.StringIO()
    with patch.object(time, "monotonic", return_value=2000.0):
        with patch("sys.stderr", stderr):
            _choose_overwrite(controls)
            controls.handle_keydown(_keydown(pygame.K_RETURN))

        assert writes == [launch_path]
        assert not controls.modal_host.active
        state = controls.build_view_state(paused=False)
        assert state.notification_message == "Config overwritten: my-launch.cleave.config.yaml"
        assert "Config overwritten: my-launch.cleave.config.yaml" in stderr.getvalue()


def test_overwrite_confirm_esc_dismisses() -> None:
    launch_path = Path("/tmp/custom/cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("layer_1",), launch_config_path=launch_path)
    controls._config_save._on_overwrite_config = lambda path: (
        writes.append(path) or path.name
    )

    view = controls.build_view_state(paused=False)
    save_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, save_row)
    _choose_overwrite(controls)
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert not controls.modal_host.active
    assert writes == []


def test_esc_during_confirm_does_not_quit() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    save_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, save_row)
    _choose_overwrite(controls)
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.consume_hide_overlay() is False


def test_esc_requests_overlay_hide() -> None:
    controls = _make_controls()
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.consume_hide_overlay() is True
    assert controls.consume_hide_overlay() is False


def test_esc_hide_preserves_focus_when_not_in_timeline_submenu() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    preset_row = _row(view, "layer_1", RowKind.TRACK_PRESET)
    controls.focus_descriptor = _desc(view, preset_row)
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.consume_hide_overlay() is True
    controls.exit_timeline_submenu()
    assert controls.focus_descriptor.kind == RowKind.TRACK_PRESET


def test_exit_timeline_submenu_only_when_submenu_focused() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    preset_row = _row(view, "layer_1", RowKind.TRACK_PRESET)
    controls.focus_descriptor = _desc(view, preset_row)
    controls.exit_timeline_submenu()
    assert controls.focus_descriptor.kind == RowKind.TRACK_PRESET

    controls.focus_cursor = TimelineFocus(0)
    controls.exit_timeline_submenu()
    assert controls.focus_descriptor.kind == RowKind.RENDER_TIMELINE_HEADER


def test_esc_in_move_mode_does_not_request_overlay_hide() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    assert controls.move_mode_slot == "layer_1"
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.move_mode_slot is None
    assert controls.consume_hide_overlay() is False


def test_ctrl_q_not_handled_by_main_controls() -> None:
    controls = _make_controls()
    assert controls.handle_keydown(
        _keydown(pygame.K_q, mod=pygame.KMOD_CTRL)
    ) is True


def test_q_alone_does_not_quit() -> None:
    controls = _make_controls()
    assert controls.handle_keydown(_keydown(pygame.K_q)) is True


def test_row_icons_render() -> None:
    line_height = 17
    color = (255, 255, 255)
    for glyph in (FOLDER_GLYPH, FILE_GLYPH, VISIBILITY_GLYPH, VISIBILITY_OFF_GLYPH):
        surf = render_glyph(glyph, color=color, line_height=line_height)
        assert surf.get_width() > 0
        assert surf.get_height() == line_height
        assert pygame.mask.from_surface(surf).count() > 0


def test_track_header_icons_render() -> None:
    line_height = 17
    header_color = (170, 210, 255)
    lock_color = (235, 90, 90)
    for glyph in (VISIBILITY_GLYPH, VISIBILITY_OFF_GLYPH):
        surf = render_glyph(glyph, color=header_color, line_height=line_height)
        assert surf.get_width() > 0
        assert surf.get_height() == line_height
        assert pygame.mask.from_surface(surf).count() > 0

    lock = render_glyph(LOCK_GLYPH, color=lock_color, line_height=line_height)
    assert lock.get_width() > 0
    assert visibility_icon_prefix_width(line_height) > lock.get_width()
    assert track_header_lock_suffix_width(line_height) > lock.get_width()


def test_track_header_text_omits_enabled_status() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    text = _row_text(view, header_row)
    assert text.startswith("Layer ")
    assert "enabled" not in text.lower()
    assert "disabled" not in text.lower()


def test_track_header_expand_arrow() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = False
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    assert _row_text(view, header_row).endswith(" ▶")

    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    assert _row_text(view, header_row).endswith(" ▼")


def test_render_overlay_header_label_spacing() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_HEADER)
    assert _row_text(view, header_row) == "Render: OVERLAY ▶"


def test_render_overlay_title_header_expand_arrow() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    view = controls.build_view_state(paused=False)
    title_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    assert _row_text(view, title_header) == "└─ title ▶"

    controls.session.render_overlay.title_expanded = True
    view = controls.build_view_state(paused=False)
    title_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    assert _row_text(view, title_header) == "└─ title ▼"


def test_render_overlay_body_header_expand_arrow() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    view = controls.build_view_state(paused=False)
    body_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_BODY_HEADER)
    assert _row_text(view, body_header) == "└─ body ▶"

    controls.session.render_overlay.body_expanded = True
    view = controls.build_view_state(paused=False)
    body_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_BODY_HEADER)
    assert _row_text(view, body_header) == "└─ body ▼"


_OVERLAY_TEST_FONTS = ("alpha", "bravo", "charlie")


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=_OVERLAY_TEST_FONTS,
)
def test_render_overlay_title_font_row(_mock_fonts) -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.title_expanded = True
    controls.session.render_overlay.title_font = "alpha"
    view = controls.build_view_state(paused=False)
    font_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_FONT)
    assert _row_text(view, font_row) == "  └─ font: alpha (1/3)"

    controls.focus_descriptor = _desc(view, font_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.render_overlay.title_font == "bravo"


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=_OVERLAY_TEST_FONTS,
)
def test_render_overlay_body_font_row(_mock_fonts) -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.body_expanded = True
    controls.session.render_overlay.body_font = "bravo"
    view = controls.build_view_state(paused=False)
    font_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_BODY_FONT)
    assert _row_text(view, font_row) == "  └─ font: bravo (2/3)"

    controls.focus_descriptor = _desc(view, font_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.render_overlay.body_font == "alpha"


def test_render_overlay_title_font_size_row() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.title_expanded = True
    controls.session.render_overlay.title_font_size = 12
    view = controls.build_view_state(paused=False)
    font_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE)
    assert _row_text(view, font_row) == "  └─ font size: 12px"

    controls.focus_descriptor = _desc(view, font_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.render_overlay.title_font_size == 13


def test_render_overlay_title_margin_bottom_row() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.title_expanded = True
    controls.session.render_overlay.title_margin_bottom = 10
    view = controls.build_view_state(paused=False)
    margin_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM)
    assert _row_text(view, margin_row) == "  └─ margin bottom: 10px"

    controls.focus_descriptor = _desc(view, margin_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.render_overlay.title_margin_bottom == 11


def test_render_overlay_body_font_size_row() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.body_expanded = True
    controls.session.render_overlay.body_font_size = 18
    view = controls.build_view_state(paused=False)
    font_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_BODY_FONT_SIZE)
    assert _row_text(view, font_row) == "  └─ font size: 18px"

    controls.focus_descriptor = _desc(view, font_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.render_overlay.body_font_size == 17


def test_render_overlay_font_rows_nested_indent() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.title_expanded = True
    controls.session.render_overlay.body_expanded = True
    view = controls.build_view_state(paused=False)
    title_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    title_font_size = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE)
    title_font = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_FONT)
    body_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_BODY_HEADER)
    body_font_size = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_BODY_FONT_SIZE)
    body_font = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_BODY_FONT)
    assert _row_indent(view, title_header) == TREE_INDENT
    assert _row_indent(view, title_font_size) == TREE_INDENT * 2
    assert _row_indent(view, title_font) == TREE_INDENT * 2
    assert _row_indent(view, body_header) == TREE_INDENT
    assert _row_indent(view, body_font_size) == TREE_INDENT * 2
    assert _row_indent(view, body_font) == TREE_INDENT * 2


def test_render_overlay_title_header_toggles_expansion() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    view = controls.build_view_state(paused=False)
    title_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    controls.focus_descriptor = _desc(view, title_header)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.render_overlay.title_expanded is True

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.render_overlay.title_expanded is False


def test_render_overlay_collapse_refocuses_from_title_font_row() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.title_expanded = True
    view = controls.build_view_state(paused=False)
    font_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE)
    font_desc = _desc(view, font_row)
    controls.focus_descriptor = font_desc
    controls._render_overlay.set_expanded(False)
    assert controls.focus_descriptor == font_desc
    view = controls.build_view_state(paused=False)
    assert view.layout.resolve_navigable(
        controls.focus_descriptor, view
    ) == RowDescriptor(RowKind.TRANSPORT)


def test_render_overlay_title_collapse_refocuses_from_font_row() -> None:
    controls = _make_controls()
    controls.session.render_overlay.expanded = True
    controls.session.render_overlay.title_expanded = True
    view = controls.build_view_state(paused=False)
    title_header = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    font_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE)
    controls.focus_descriptor = _desc(view, font_row)
    controls._render_overlay.set_title_expanded(False)
    view = controls.build_view_state(paused=False)
    assert view.layout.resolve_navigable(
        controls.focus_descriptor, view
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_HEADER)


def test_track_header_visibility_icon_color() -> None:
    line_height = 17
    enabled = render_glyph(
        VISIBILITY_GLYPH, color=VALUE, line_height=line_height
    )
    disabled = render_glyph(
        VISIBILITY_OFF_GLYPH, color=DISABLED, line_height=line_height
    )
    assert enabled.get_width() > 0
    assert disabled.get_width() > 0
    assert enabled.get_at((enabled.get_width() // 2, line_height // 2))[:3] != (
        0,
        0,
        0,
    )
    assert disabled.get_at((disabled.get_width() // 2, line_height // 2))[:3] != (
        0,
        0,
        0,
    )


def test_transport_icons_render() -> None:
    s = render_transport_icons(color=(255, 255, 255), line_height=17, paused=False)
    assert s.get_width() > 0
    assert s.get_height() == 17
    assert pygame.mask.from_surface(s).count() > 50


def test_transport_icons_play_vs_pause() -> None:
    playing = render_transport_icons(color=(255, 255, 255), line_height=17, paused=False)
    paused = render_transport_icons(color=(255, 255, 255), line_height=17, paused=True)
    assert playing.get_width() == paused.get_width()

    w, h = playing.get_size()
    x0 = w // 3
    x1 = 2 * w // 3
    region_w = x1 - x0
    play_middle = pygame.Surface((region_w, h), pygame.SRCALPHA)
    pause_middle = pygame.Surface((region_w, h), pygame.SRCALPHA)
    play_middle.blit(playing, (0, 0), (x0, 0, region_w, h))
    pause_middle.blit(paused, (0, 0), (x0, 0, region_w, h))
    play_mask = pygame.mask.from_surface(play_middle)
    pause_mask = pygame.mask.from_surface(pause_middle)
    assert play_mask.count() > 0
    assert pause_mask.count() > 0
    overlap_px = play_mask.overlap_area(pause_mask, (0, 0))
    assert overlap_px < play_mask.count() or overlap_px < pause_mask.count()


def test_render_post_fx_highlight_rolloff_mode_off_keeps_section_expanded() -> None:
    controls = _make_controls()
    controls.session.render_post_fx.expanded = True
    controls._render_post_fx.set_highlight_rolloff_expanded(True)
    controls.session.render_post_fx.highlight_rolloff.mode = "composite"

    controls._render_post_fx.cycle_highlight_rolloff_mode(forward=True)

    assert controls.session.render_post_fx.highlight_rolloff.mode == "off"
    assert controls.session.render_post_fx.highlight_rolloff_expanded is True


def test_render_timeline_header_after_post_fx() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    post_fx_row = view.layout.find_by_kind(RowKind.RENDER_POST_FX_HEADER)
    timeline_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    transport_row = view.layout.find_by_kind(RowKind.TRANSPORT)
    assert transport_row < post_fx_row < timeline_row


def _focus_timeline_presets(controls: TuningControls) -> None:
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    presets_row = view.layout.find_by_kind(RowKind.TIMELINE_PRESETS)
    controls.focus_descriptor = _desc(view, presets_row)


def _choose_modal_option(controls: TuningControls, label: str) -> None:
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    target = modal_view.options.index(label)
    while controls.modal_host.view_state().focus_index != target:
        controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))


def test_timeline_presets_enter_opens_choice_modal() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3", "layer_4"))
    _focus_timeline_presets(controls)
    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.CHOICE
    assert modal_view.options == ("Slow Build", "Random", "Cancel")
    assert "timeline preset" in modal_view.message.lower()


def test_timeline_presets_slow_build_clears_and_applies() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3", "layer_4"))
    prior = [
        TimelineCue(t=1.0, layers={"layer_1": False}),
        TimelineCue(t=2.0, layers={"layer_2": True}),
    ]
    controls.session.timeline.cues = list(prior)
    controls.session.timeline.enabled = False
    controls.session.timeline.recording = True
    controls.session.timeline.armed_slots.add("layer_1")
    _focus_timeline_presets(controls)
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Slow Build")
    assert not controls.modal_host.active
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.recording is False
    assert not controls.session.timeline.armed_slots
    cues = controls.session.timeline.cues
    assert cues
    assert cues != prior
    assert cues[0].t == 0.0
    assert set(cues[0].layers) == set(controls.session.layer_z_order)


def test_timeline_presets_random_clears_and_applies() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.timeline.cues = [TimelineCue(t=5.0, layers={"layer_1": False})]
    controls.session.timeline.enabled = False
    _focus_timeline_presets(controls)
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Random")
    assert not controls.modal_host.active
    assert controls.session.timeline.enabled is True
    cues = controls.session.timeline.cues
    assert cues
    assert cues[0].t == 0.0
    assert set(cues[0].layers) == {"layer_1", "layer_2"}


def test_timeline_presets_cancel_and_escape_leave_unchanged() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    prior = [TimelineCue(t=3.0, layers={"layer_1": True, "layer_2": False})]
    controls.session.timeline.cues = list(prior)
    controls.session.timeline.enabled = False

    _focus_timeline_presets(controls)
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Cancel")
    assert not controls.modal_host.active
    assert controls.session.timeline.cues == prior
    assert controls.session.timeline.enabled is False

    _focus_timeline_presets(controls)
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert not controls.modal_host.active
    assert controls.session.timeline.cues == prior
    assert controls.session.timeline.enabled is False


def test_render_timeline_header_label_spacing() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_text(view, header_row) == "Render: TIMELINE ▶"


def test_render_timeline_header_expand_arrow() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_text(view, header_row).endswith(" ▶")

    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_text(view, header_row).endswith(" ▼")


def test_render_timeline_ctrl_right_toggles_enabled() -> None:
    controls = _make_controls(timeline_enabled=True)
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.session.timeline.enabled is True

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.timeline.enabled is True

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.timeline.enabled is False

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.panel_open is True
    assert not isinstance(controls.focus_cursor, TimelineFocus)


def test_timeline_enabled_startup_shows_notification() -> None:
    with patch.object(time, "monotonic", return_value=1000.0):
        controls = _make_controls(timeline_enabled=True)
        view = controls.build_view_state(paused=False)
    assert view.notification_message == NOTIFICATION_TIMELINE_ENABLED_TEXT
    assert view.notification_remaining_sec == pytest.approx(
        NOTIFICATION_DURATION_SEC, abs=0.01
    )
    assert RowKind.PANEL_NOTIFICATION in [row.kind for row in view.layout.rows]


def test_render_timeline_toggle_shows_notification() -> None:
    with patch.object(time, "monotonic", return_value=1000.0):
        controls = _make_controls(timeline_enabled=True)
        view = controls.build_view_state(paused=False)
        header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
        controls.focus_descriptor = _desc(view, header_row)
        controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
        view = controls.build_view_state(paused=False)
        assert view.notification_message == NOTIFICATION_TIMELINE_DISABLED_TEXT

        controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
        view = controls.build_view_state(paused=False)
        assert view.notification_message == NOTIFICATION_TIMELINE_ENABLED_TEXT


def test_panel_notification_expires_after_duration() -> None:
    with patch.object(time, "monotonic", return_value=5000.0):
        controls = _make_controls(timeline_enabled=True)
        view = controls.build_view_state(paused=False)
        assert view.notification_message == NOTIFICATION_TIMELINE_ENABLED_TEXT

    with patch.object(
        time,
        "monotonic",
        return_value=5000.0 + NOTIFICATION_DURATION_SEC + 0.1,
    ):
        controls.tick(0.0)
        view = controls.build_view_state(paused=False)
        assert view.notification_message is None
        assert view.notification_remaining_sec == 0.0


def test_render_timeline_enable_opens_panel() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is False

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.panel_open is True
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_text(view, header_row).endswith(" ▼")


def test_render_timeline_right_opens_panel() -> None:
    controls = _make_controls(timeline_enabled=True)
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.session.timeline.focus_row = 2
    assert controls.session.timeline.panel_open is False
    assert not isinstance(controls.focus_cursor, TimelineFocus)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.timeline.panel_open is True
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.session.timeline.focus_row == 2
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_text(view, header_row).endswith(" ▼")

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.timeline.panel_open is False
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_text(view, header_row).endswith(" ▶")


def test_render_timeline_down_enters_submenu() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    presets_row = view.layout.find_by_kind(RowKind.TIMELINE_PRESETS)
    controls.focus_descriptor = _desc(view, header_row)
    controls.session.timeline.focus_row = 2

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, presets_row)
    assert not isinstance(controls.focus_cursor, TimelineFocus)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.session.timeline.focus_row == 0
    assert controls.focus_descriptor == _desc(view, header_row)


def test_render_timeline_down_enters_submenu_and_routes_keys() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.session.timeline.focus_row = 2

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.session.timeline.focus_row == 0

    tl = controls.session.timeline
    timeline_controls = MagicMock()
    main_controls = MagicMock()

    def key_handler_for(key: int):
        if (
            tl.panel_open
            and tl.enabled
            and isinstance(controls.focus_cursor, TimelineFocus)
            and key not in (pygame.K_UP, pygame.K_DOWN)
        ):
            return timeline_controls
        return main_controls

    assert key_handler_for(pygame.K_UP) is main_controls
    assert key_handler_for(pygame.K_DOWN) is main_controls
    assert key_handler_for(pygame.K_RETURN) is timeline_controls

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.session.timeline.focus_row == 1


def test_vertical_navigation_repeats_on_hold() -> None:
    from cleave.viz.key_repeat import INITIAL_DELAY_SEC, SLOW_INTERVAL_SEC

    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    transport = view.layout.find_by_kind(RowKind.TRANSPORT)
    controls.focus_descriptor = _desc(view, transport)
    navigable = view.layout.navigable_indices(view)
    start_pos = navigable.index(transport)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert navigable.index(_focus_index(controls)) == (start_pos + 1) % len(navigable)

    controls.tick(INITIAL_DELAY_SEC)
    assert navigable.index(_focus_index(controls)) == (start_pos + 2) % len(navigable)

    controls.tick(SLOW_INTERVAL_SEC)
    assert navigable.index(_focus_index(controls)) == (start_pos + 3) % len(navigable)


def test_timeline_submenu_vertical_navigation_repeats() -> None:
    from cleave.viz.key_repeat import INITIAL_DELAY_SEC, SLOW_INTERVAL_SEC

    controls = _make_controls(
        timeline_enabled=True,
        slots=("layer_1", "layer_2", "layer_3", "layer_4"),
    )
    controls.session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(0)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.session.timeline.focus_row == 1

    controls.tick(INITIAL_DELAY_SEC)
    assert controls.session.timeline.focus_row == 2

    controls.tick(SLOW_INTERVAL_SEC)
    assert controls.session.timeline.focus_row == 3


def test_vertical_navigation_stops_on_keyup() -> None:
    from cleave.viz.key_repeat import INITIAL_DELAY_SEC

    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    transport = view.layout.find_by_kind(RowKind.TRANSPORT)
    controls.focus_descriptor = _desc(view, transport)
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    focus_after_keydown = controls.focus_descriptor

    controls.handle_keyup(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))
    controls.tick(INITIAL_DELAY_SEC + 1.0)
    assert controls.focus_descriptor == focus_after_keydown


def test_key_repeat_armed_while_navigation_key_held() -> None:
    controls = _make_controls()
    assert controls.key_repeat_armed is False

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.key_repeat_armed is True

    controls.handle_keyup(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))
    assert controls.key_repeat_armed is False


def test_held_key_repeat_keeps_overlay_visible() -> None:
    from cleave.config_schema import DEFAULT_UI_FADE_SEC
    from cleave.viz.tuning_panel_draw import TuningOverlay
    from cleave.viz.theme import FADE_DURATION_SEC

    controls = _make_controls()
    overlay = TuningOverlay()
    overlay.notify_input()

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    dt = 0.05
    for _ in range(int(DEFAULT_UI_FADE_SEC / dt) + 5):
        controls.tick(dt)
        if controls.key_repeat_armed:
            overlay.notify_input()
        overlay.update(dt)

    assert overlay.is_visible() is True

    controls.handle_keyup(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))
    overlay.update(DEFAULT_UI_FADE_SEC + FADE_DURATION_SEC + 0.1)
    assert overlay.is_visible() is False


def test_render_timeline_submenu_up_returns_to_header() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.focus_cursor = TimelineFocus(0)

    controls.handle_keydown(_keydown(pygame.K_UP))

    assert not isinstance(controls.focus_cursor, TimelineFocus)
    view = controls.build_view_state(paused=False)
    assert controls.focus_descriptor == RowDescriptor(RowKind.TIMELINE_PRESETS)


def test_render_timeline_submenu_entry_stops_repeat_on_keyup() -> None:
    from cleave.viz.key_repeat import INITIAL_DELAY_SEC

    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    presets_row = view.layout.find_by_kind(RowKind.TIMELINE_PRESETS)
    controls.focus_descriptor = _desc(view, presets_row)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.session.timeline.focus_row == 0
    assert controls.key_repeat_armed is True

    controls.handle_keyup(pygame.event.Event(pygame.KEYUP, key=pygame.K_DOWN))
    assert controls.key_repeat_armed is False
    controls.tick(INITIAL_DELAY_SEC + 1.0)
    assert controls.session.timeline.focus_row == 0


def test_render_timeline_submenu_down_from_last_row_wraps_to_settings() -> None:
    stems = ("layer_1", "layer_2", "layer_3", "layer_4")
    controls = _make_controls(stems, timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    settings_row = view.layout.find_by_kind(RowKind.SETTINGS_HEADER)
    controls.focus_cursor = TimelineFocus(len(stems) - 1)

    controls.handle_keydown(_keydown(pygame.K_DOWN))

    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, settings_row)


def test_render_timeline_submenu_up_from_transport_wraps_to_config_header() -> None:
    stems = ("layer_1", "layer_2", "layer_3", "layer_4")
    controls = _make_controls(stems, timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    transport_row = view.layout.find_by_kind(RowKind.TRANSPORT)
    config_row = view.layout.find_by_kind(RowKind.CONFIG_HEADER)
    controls.focus_descriptor = _desc(view, transport_row)

    controls.handle_keydown(_keydown(pygame.K_UP))

    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, config_row)


def test_render_timeline_panel_closed_wrap_unchanged() -> None:
    controls = _make_controls(("layer_1", "layer_2"), timeline_enabled=True)
    controls.session.timeline.panel_open = False
    view = controls.build_view_state(paused=False)
    navigable = view.layout.navigable_indices(view)
    settings_row = view.layout.find_by_kind(RowKind.SETTINGS_HEADER)
    transport_row = view.layout.find_by_kind(RowKind.TRANSPORT)
    timeline_header = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert RowDescriptor(RowKind.TIMELINE_PRESETS) not in view.layout.rows
    controls.focus_descriptor = _desc(view, timeline_header)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, settings_row)

    controls.focus_descriptor = _desc(view, transport_row)
    controls.handle_keydown(_keydown(pygame.K_UP))
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, navigable[navigable.index(transport_row) - 1])


def test_render_timeline_disable_closes_panel() -> None:
    controls = _make_controls()
    controls.session.timeline.enabled = True
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is False


def test_render_timeline_header_eye_color_when_disabled() -> None:
    controls = _make_controls(timeline_enabled=True)
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_value_color(view, header_row) == VALUE

    controls.session.timeline.enabled = False
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_value_color(view, header_row) == DISABLED


def test_track_header_visible_follows_timeline_at_position() -> None:
    controls = _make_controls(("layer_1", "layer_2"), timeline_enabled=True)
    controls.session.timeline.cues = [
        TimelineCue(t=5.0, layers={"layer_1": False}),
    ]
    before = controls.build_view_state(paused=False, position_sec=4.9)
    after = controls.build_view_state(paused=False, position_sec=5.0)
    assert before.tracks["layer_1"].visible is True
    assert after.tracks["layer_1"].visible is False
    assert before.tracks["layer_2"].visible is True
    assert after.tracks["layer_2"].visible is True


def test_track_header_visible_uses_layer_enabled_when_timeline_off() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].enabled = False
    view = controls.build_view_state(paused=False, position_sec=10.0)
    assert view.tracks["layer_1"].visible is False
    assert view.tracks["layer_1"].enabled is False


def test_solo_marks_non_solo_tracks_not_visible_when_timeline_off() -> None:
    controls = _make_controls(("layer_1", "layer_2"), timeline_enabled=False)
    controls.session.solo_slot = "layer_1"
    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].visible is True
    assert view.tracks["layer_2"].visible is False


def test_render_timeline_enabled_change_callback() -> None:
    controls = _make_controls(timeline_enabled=True)
    events: list[bool] = []
    controls._layer_bindings = noop_layer_bindings(
        on_timeline_enabled_change=lambda: events.append(
            controls.session.timeline.enabled
        )
    )
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert events == []

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert events == [False]

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert events == [False, True]


def test_t_opens_timeline_panel_when_enabled() -> None:
    controls = _make_controls()
    controls.session.timeline.enabled = True
    controls.session.timeline.focus_row = 2
    assert controls.session.timeline.panel_open is False

    controls.handle_keydown(_keydown(pygame.K_t))
    assert controls.session.timeline.panel_open is True
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.session.timeline.focus_row == 0


def test_t_closes_timeline_panel_and_focuses_header_when_open() -> None:
    controls = _make_controls(timeline_enabled=True)
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.session.timeline.panel_open = True
    
    controls.focus_descriptor = RowDescriptor(RowKind.TRANSPORT)

    controls.handle_keydown(_keydown(pygame.K_t))
    assert controls.session.timeline.panel_open is False
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, header_row)


def test_t_from_submenu_closes_and_focuses_render_timeline_header() -> None:
    controls = _make_controls(timeline_enabled=True)
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(0)

    from cleave.viz.timeline_controls import TimelineControls

    timeline_controls = TimelineControls(
        controls.session,
        controls.playback,
        controls.duration_sec,
        on_close=controls.close_timeline_panel,
    )
    timeline_controls.handle_keydown(_keydown(pygame.K_t))

    assert controls.session.timeline.panel_open is False
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, header_row)


def test_t_notification_when_timeline_disabled() -> None:
    controls = _make_controls()
    controls.session.timeline.enabled = False

    controls.handle_keydown(_keydown(pygame.K_t))
    assert controls.session.timeline.panel_open is False
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Enable timeline first"


def test_t_ignored_during_move_mode() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.enabled = True
    view = controls.build_view_state(paused=False)
    header_row = view.layout.find_by_kind(RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    assert controls.move_mode_slot == "layer_1"

    controls.handle_keydown(_keydown(pygame.K_t))
    assert controls.session.timeline.panel_open is False


def test_transport_enter_toggles_pause() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    transport_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.TRANSPORT
    )
    controls.focus_descriptor = _desc(view, transport_row)
    assert controls.playback.paused is False

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.playback.paused is True

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.playback.paused is False


def test_space_toggles_pause_from_any_focus() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    assert controls.playback.paused is False
    assert controls.focus_descriptor == RowDescriptor(RowKind.TRANSPORT)

    controls.handle_keydown(_keydown(pygame.K_SPACE))
    assert controls.playback.paused is True

    controls.handle_keydown(_keydown(pygame.K_SPACE))
    assert controls.playback.paused is False


def test_quick_nav_row_indices_headers_and_transport_only() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.layers["layer_1"].enabled = False
    view = controls.build_view_state(paused=False)

    quick = view.layout.quick_nav_indices()
    assert len(quick) == 7
    for index in quick:
        kind = view.layout.kind( index)
        assert kind in (
            RowKind.SETTINGS_HEADER,
            RowKind.TRACK_HEADER,
            RowKind.RENDER_OVERLAY_HEADER,
            RowKind.RENDER_POST_FX_HEADER,
            RowKind.RENDER_TIMELINE_HEADER,
            RowKind.TRANSPORT,
        )

    settings_row = view.layout.find_by_kind(RowKind.SETTINGS_HEADER)
    drums_header = next(
        i
        for i in range(len(view.layout))
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_1"
    )
    bass_header = next(
        i
        for i in range(len(view.layout))
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_2"
    )
    render_overlay_row = view.layout.find_by_kind(RowKind.RENDER_OVERLAY_HEADER)
    render_post_fx_row = view.layout.find_by_kind(RowKind.RENDER_POST_FX_HEADER)
    render_timeline_row = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    transport_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.TRANSPORT
    )
    assert quick == [
        settings_row,
        transport_row,
        drums_header,
        bass_header,
        render_overlay_row,
        render_post_fx_row,
        render_timeline_row,
    ]


def test_ctrl_quick_nav_cycles_headers_and_transport() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    quick = view.layout.quick_nav_indices()

    controls.focus_descriptor = _desc(view, quick[0])
    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[1])

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[2])

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[3])

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[4])

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[5])

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[6])

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[0])

    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[6])


def test_ctrl_quick_nav_from_sub_row_jumps_forward() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    quick = view.layout.quick_nav_indices()
    preset_row = next(
        i for i in range(12) if view.layout.kind(i) == RowKind.TRACK_PRESET
    )

    controls.focus_descriptor = _desc(view, preset_row)
    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[3])

    controls.focus_descriptor = _desc(view, preset_row)
    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[2])


def test_ctrl_quick_nav_from_config_header_row() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    quick = view.layout.quick_nav_indices()
    config_row = _config_header_row(view)

    controls.focus_descriptor = _desc(view, config_row)
    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[0])

    controls.focus_descriptor = _desc(view, config_row)
    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_descriptor == _desc(view, quick[1])


def test_ctrl_quick_nav_does_not_affect_normal_up_down() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_descriptor == _desc(view, preset_dir_row)


def test_ctrl_quick_nav_from_timeline_submenu_jumps_sections() -> None:
    controls = _make_controls(("layer_1", "layer_2"), timeline_enabled=True)
    view = controls.build_view_state(paused=False)
    quick = view.layout.quick_nav_indices()
    timeline_header = view.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
    settings_row = view.layout.find_by_kind(RowKind.SETTINGS_HEADER)

    controls.session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(1)

    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, timeline_header)

    controls.focus_cursor = TimelineFocus(2)
    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor == _desc(view, settings_row)
    assert timeline_header in quick


def _write_milk(path: Path) -> None:
    path.write_text("milk")


def _make_sibling_dir_tree(
    count: int,
    *,
    child_name: str = "child",
    child_preset_count: int = 1,
) -> tuple[Path, tuple[Path, ...]]:
    """Return (preset_root, sibling_dirs) each with at least one .milk file."""
    tmp = tempfile.mkdtemp()
    root = Path(tmp)
    siblings: list[Path] = []
    for i in range(count):
        sibling = root / f"dir-{i:02d}"
        sibling.mkdir()
        for j in range(child_preset_count):
            _write_milk(sibling / f"preset-{j}.milk")
        siblings.append(sibling)
    if child_name:
        child = siblings[0] / child_name
        child.mkdir()
        _write_milk(child / "nested.milk")
    return root, tuple(siblings)


def _controls_with_playlist(
    root: Path,
    current_dir: Path,
    *,
    index: int = 0,
    browse_floor: Path | None = None,
) -> TuningControls:
    anchor = current_dir / "preset-0.milk"
    floor = browse_floor if browse_floor is not None else preset_browse_floor(
        anchor, root
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist_at_dir(current_dir, index=index),
                browse_floor=floor,
                stem="layer_1",
                opacity_pct=50,
                expanded=True,
            )
        },
    )
    cfg = make_test_cfg(("layer_1",), preset_root=root)
    return TuningControls(
        session,
        cfg,
        preset_root=root,
        playback=stub_playback_state(),
        duration_sec=120.0,
    )


def _preset_dir_row(controls: TuningControls) -> int:
    view = controls.build_view_state(paused=False)
    return _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)


def _preset_row(controls: TuningControls) -> int:
    view = controls.build_view_state(paused=False)
    return _row(view, "layer_1", RowKind.TRACK_PRESET)


def test_directory_row_lr_changes_current_dir() -> None:
    root, siblings = _make_sibling_dir_tree(3)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert playlist.current_dir.resolve() == siblings[1].resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_enter_descends_backspace_goes_parent() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_ctrl_arrows_descend_and_ascend() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_ctrl_left_at_preset_root_is_noop() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == root.resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == root.resolve()


def test_directory_ctrl_arrows_do_not_repeat_parent_climb() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == siblings[0].resolve()

    for _ in range(20):
        controls.tick(0.5)
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_backspace_at_preset_root_is_noop() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()


def test_directory_parent_round_trip_reaches_preset_root() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    child = siblings[0] / "child"
    controls = _controls_with_playlist(root, child)
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist

    for _ in range(3):
        controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() != root.resolve()

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()


def test_preset_lr_noop_when_paths_empty() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    empty_dir = root / "empty"
    empty_dir.mkdir()
    controls = _controls_with_playlist(root, empty_dir)
    changed: list[tuple[str, int]] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_change=lambda stem, pl: changed.append((stem, pl.index))
    )
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_row(controls))
    playlist = controls.session.layers["layer_1"].playlist
    assert playlist.paths == ()

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert changed == []
    assert playlist.index == 0


def test_track_preset_dir_in_repeat_row_kinds() -> None:
    assert RowKind.TRACK_PRESET_DIR in REPEAT_ROW_KINDS


def test_ctrl_preset_steps_by_ten_wrapping() -> None:
    changed: list[tuple[str, int]] = []
    controls = _make_controls(("layer_1",))
    current_dir = Path("/tmp/presets/drums")
    paths = tuple(current_dir / f"preset-{i:02d}.milk" for i in range(12))
    controls.session.layers["layer_1"].playlist = PresetPlaylist(
        current_dir=current_dir, paths=paths, index=5
    )
    controls._layer_bindings = noop_layer_bindings(
        on_preset_change=lambda stem, pl: changed.append((stem, pl.index))
    )

    view = controls.build_view_state(paused=False)
    preset_row = _row(view, "layer_1", RowKind.TRACK_PRESET)
    controls.focus_descriptor = _desc(view, preset_row)
    playlist = controls.session.layers["layer_1"].playlist

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert playlist.index == 3
    assert changed == [("layer_1", 3)]

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.index == 5
    assert changed[-1] == ("layer_1", 5)


def test_empty_playlist_view_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty_dir = root / "empty"
        empty_dir.mkdir()
        controls = _controls_with_playlist(root, empty_dir)
        view = controls.build_view_state(paused=False)
        block = view.tracks["layer_1"]
        assert block.preset_label == "NO PRESETS FOUND"
        assert block.preset_empty is True


def test_move_mode_colors_focused_track_header() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(len(view.layout))
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_2"
    )
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.handle_keydown(_keydown(_MOVE_MODE_KEY)) is True

    view = controls.build_view_state(paused=False)
    child_row = header_row + 1
    assert _row_value_color(view, header_row) == MOVE_MODE
    assert _row_bg_color(view, header_row) == MOVE_MODE
    assert _row_value_color(view, child_row) == MOVE_MODE
    assert _row_bg_color(view, child_row) == MOVE_MODE


def test_row_value_color_dim_for_focused_empty_preset() -> None:
    state = TuningViewState(
        layer_z_order=("layer_1",),
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="empty (1/1)",
                preset_label="NO PRESETS FOUND",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                preset_empty=True,
                expanded=True,
            )
        },
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
        move_mode_slot=None,
        notification_message=None,
        notification_remaining_sec=0.0,
    )
    preset_row = _row(state, "layer_1", RowKind.TRACK_PRESET)
    state = TuningViewState(
        layer_z_order=state.layer_z_order,
        tracks=state.tracks,
        paused=state.paused,
        position_sec=state.position_sec,
        focus_cursor=MainFocus(state.layout.descriptor(preset_row)),
        move_mode_slot=state.move_mode_slot,
        notification_message=state.notification_message,
        notification_remaining_sec=state.notification_remaining_sec,
    )
    assert _row_value_color(state, preset_row) == DISABLED
    assert _row_bg_color(state, preset_row) == HIGHLIGHT


def test_preset_overlay_shows_directory_and_position() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    block = view.tracks["layer_1"]
    assert block.preset_dir_label == "layer_1/ (1/1)"
    assert block.preset_label == "preset-0.milk (1/3)"

    controls.session.layers["layer_1"].playlist.index = 1
    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].preset_label == "preset-1.milk (2/3)"


def test_scan_file_anchor_builds_parent_directory_playlist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack" / "Aurora"
        preset_dir.mkdir(parents=True)
        first = preset_dir / "alpha.milk"
        second = preset_dir / "beta.milk"
        first.write_text("milk")
        second.write_text("milk")

        playlist = scan_preset_playlist(second)
        assert playlist.current_dir == preset_dir.resolve()
        assert playlist.paths == (first.resolve(), second.resolve())
        assert playlist.index == 1
        assert preset_filename_display(playlist) == "beta.milk (2/2)"
        assert directory_display(playlist, root) == "pack/Aurora/ (1/1)"


def _header_row(
    controls: TuningControls,
    stem: str,
    *,
    paused: bool = False,
) -> int:
    view = controls.build_view_state(paused=paused)
    return next(
        i
        for i in range(len(view.layout))
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == stem
    )


def _sub_rows_for_stem(view: TuningViewState, stem: str) -> list[int]:
    sub_kinds = (
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.TRACK_EFFECT,
    )
    return [
        i
        for i in range(len(view.layout))
        if view.layout.slot( i) == stem and view.layout.kind(i) in sub_kinds
    ]


def test_ctrl_enter_toggles_lock() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.session.layers["layer_1"].locked is False

    controls.handle_keydown(_keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].locked is True

    controls.handle_keydown(_keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].locked is False


def test_locked_expanded_skips_sub_rows_in_nav() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)

    sub_rows = _sub_rows_for_stem(view, "layer_1")
    assert sub_rows
    visible = view.layout.visible_indices(view)
    navigable = view.layout.navigable_indices(view)
    effects_header = _row(view, "layer_1", RowKind.TRACK_EFFECTS_HEADER)
    stem_row = _row(view, "layer_1", RowKind.TRACK_STEM)
    assert effects_header in navigable
    assert stem_row not in navigable
    for row in sub_rows:
        assert row in visible
        if row == effects_header:
            continue
        assert row not in navigable


def test_locked_blocks_enable_disable() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.session.layers["layer_1"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].enabled is True


def test_locked_blocks_move_mode() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    assert controls.move_mode_slot is None


def test_locked_header_still_expands() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    controls.session.layers["layer_1"].expanded = False
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    assert controls.session.layers["layer_1"].expanded is False

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].expanded is True

    view = controls.build_view_state(paused=False)
    preset_dir_row = _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)
    assert preset_dir_row in view.layout.visible_indices(view)

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].expanded is False

    view = controls.build_view_state(paused=False)
    preset_dir_desc = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    assert not view.layout.contains_descriptor(preset_dir_desc)


def test_locked_sub_rows_use_locked_color() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)
    unfocused = TuningViewState(
        layer_z_order=view.layer_z_order,
        tracks=view.tracks,
        paused=view.paused,
        position_sec=view.position_sec,
        focus_cursor=MainFocus(view.layout.descriptor(len(view.layout) - 1)),
        move_mode_slot=view.move_mode_slot,
        notification_message=view.notification_message,
        notification_remaining_sec=view.notification_remaining_sec,
        active_config_label=view.active_config_label,
        allow_overwrite=view.allow_overwrite,
    )
    assert _row_value_color(unfocused, header_row) == VALUE
    assert _row_value_color(unfocused, preset_dir_row) == LOCKED

    focused_header = TuningViewState(
        layer_z_order=view.layer_z_order,
        tracks=view.tracks,
        paused=view.paused,
        position_sec=view.position_sec,
        focus_cursor=MainFocus(view.layout.descriptor(header_row)),
        move_mode_slot=view.move_mode_slot,
        notification_message=view.notification_message,
        notification_remaining_sec=view.notification_remaining_sec,
        active_config_label=view.active_config_label,
        allow_overwrite=view.allow_overwrite,
    )
    assert _row_value_color(focused_header, header_row) == HIGHLIGHT
    assert _row_value_color(focused_header, preset_dir_row) == LOCKED


def test_locked_not_toggleable_during_move_mode() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    bass_header = _header_row(controls, "layer_2")
    controls.focus_descriptor = _desc(view, bass_header)
    assert controls.session.layers["layer_2"].locked is False

    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    assert controls.move_mode_slot == "layer_2"

    controls.handle_keydown(_keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_2"].locked is False


def test_ctrl_quick_nav_blocked_during_move_mode() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))
    view = controls.build_view_state(paused=False)
    bass_header = next(
        i
        for i in range(15)
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot( i) == "layer_2"
    )
    controls.focus_descriptor = _desc(view, bass_header)
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    assert controls.move_mode_slot == "layer_2"

    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]
    assert controls.focus_descriptor == _desc(view, bass_header)


def test_transport_seek_constants() -> None:
    seeks: list[float] = []
    controls = _make_controls(("layer_1",))
    controls._layer_bindings = noop_layer_bindings(
        on_seek=lambda delta: seeks.append(delta)
    )

    view = controls.build_view_state(paused=False)
    transport_row = next(
        i for i in range(len(view.layout)) if view.layout.kind(i) == RowKind.TRANSPORT
    )
    controls.focus_descriptor = _desc(view, transport_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))

    assert seeks == [SEEK_SHORT, -SEEK_SHORT, SEEK_LONG, -SEEK_LONG]


def test_effect_pulse_clamps() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.layers["layer_1"].effects_expanded = True
    controls.session.layers["layer_2"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    pulse_row = _row(
        view, "layer_1", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    )
    bass_pulse_row = _row(
        view, "layer_2", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="sub_bass"
    )
    controls.focus_descriptor = _desc(view, pulse_row)
    for _ in range(120):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].effects["pulse"]["onset"] == 100

    for _ in range(120):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert "pulse" not in controls.session.layers["layer_1"].effects

    controls.focus_descriptor = _desc(view, bass_pulse_row)
    for _ in range(20):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_2"].effects["pulse"]["sub_bass"] == 20


def test_effect_pulse_row_label() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].effects = {"pulse": {"onset": 35}}
    controls.session.layers["layer_1"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    pulse_row = _row(
        view, "layer_1", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    )
    assert _row_text(view, pulse_row) == "  └─ pulse (onset): 35%"


def test_effects_header_expand_arrow() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_EFFECTS_HEADER)
    assert _row_text(view, header_row) == "└─ cleave effects ▶"

    controls.session.layers["layer_1"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_EFFECTS_HEADER)
    assert _row_text(view, header_row) == "└─ cleave effects ▼"


def test_effect_row_nested_indent() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    effects_header = _row(view, "layer_1", RowKind.TRACK_EFFECTS_HEADER)
    pulse_row = _row(
        view, "layer_1", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    )
    assert _row_indent(view, effects_header) == TREE_INDENT
    assert _row_indent(view, pulse_row) == TREE_INDENT * 2


def test_stem_row_indent() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    blend_row = _row(view, "layer_1", RowKind.TRACK_BLEND)
    stem_row = _row(view, "layer_1", RowKind.TRACK_STEM)
    assert _row_indent(view, stem_row) == TREE_INDENT
    assert _row_indent(view, blend_row) == TREE_INDENT


def test_format_mmss() -> None:
    assert format_mmss(0) == "00:00"
    assert format_mmss(42.7) == "00:42"
    assert format_mmss(222) == "03:42"
    assert format_mmss(-5) == "00:00"


def test_mod_shift_detects_shift_modifier() -> None:
    assert mod_shift(pygame.KMOD_SHIFT)
    assert mod_shift(pygame.KMOD_LSHIFT)
    assert not mod_shift(0)
    assert not mod_shift(pygame.KMOD_CTRL)


def test_shift_right_enters_solo() -> None:
    solo_calls: list[str | None] = []
    controls = _make_controls(("layer_1", "layer_2"))
    controls._layer_bindings = noop_layer_bindings(
        on_solo_change=lambda: solo_calls.append(controls.session.solo_slot)
    )

    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
    assert controls.session.solo_slot == "layer_1"
    assert solo_calls == ["layer_1"]
    state = controls.build_view_state(paused=False)
    assert state.solo_active is True
    assert state.solo_slot == "layer_1"


def test_shift_right_switches_solo_target() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    drums_header = _row(view, "layer_1", RowKind.TRACK_HEADER)
    bass_header = _row(view, "layer_2", RowKind.TRACK_HEADER)

    controls.focus_descriptor = _desc(view, drums_header)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
    assert controls.session.solo_slot == "layer_1"

    controls.focus_descriptor = _desc(view, bass_header)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
    assert controls.session.solo_slot == "layer_2"


def test_shift_left_exits_solo_only_for_active_target() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    drums_header = _row(view, "layer_1", RowKind.TRACK_HEADER)
    bass_header = _row(view, "layer_2", RowKind.TRACK_HEADER)

    controls.focus_descriptor = _desc(view, drums_header)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
    assert controls.session.solo_slot == "layer_1"

    controls.focus_descriptor = _desc(view, bass_header)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_SHIFT))
    assert controls.session.solo_slot == "layer_1"

    controls.focus_descriptor = _desc(view, drums_header)
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_SHIFT))
    assert controls.session.solo_slot is None


def test_save_blocked_while_solo_active() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "layer_1", RowKind.TRACK_HEADER)
    config_row = _config_header_row(view)
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))

    controls.focus_descriptor = _desc(view, config_row)
    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert stderr.getvalue() == ""
    assert controls.build_view_state(paused=False).solo_active is True


def test_config_header_greyed_while_solo_active() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.solo_slot = "layer_1"
    view = controls.build_view_state(paused=False)
    config_row = _config_header_row(view)
    assert _row_value_color(view, config_row) == DISABLED


def test_solo_visibility_icon_same_width_as_normal() -> None:
    line_h = 17
    soloed = render_visibility_icon(enabled=True, solo=True, line_height=line_h)
    normal = render_visibility_icon(enabled=True, solo=False, line_height=line_h)
    assert soloed.get_width() == normal.get_width()
    assert soloed.get_at((1, line_h // 2))[:3] == SOLO_BG


def test_track_header_prefix_width_matches_visibility_icon() -> None:
    font = _overlay_font()
    line_h = font.get_linesize()
    assert track_header_prefix_width(font) == visibility_icon_prefix_width(line_h)
    soloed = render_visibility_icon(enabled=True, solo=True, line_height=line_h)
    normal = render_visibility_icon(enabled=True, solo=False, line_height=line_h)
    assert soloed.get_width() == normal.get_width()


def test_try_quit_clean_session_returns_true_immediately() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.try_quit() is True


def test_try_quit_dirty_opens_dialog_and_blocks_exit() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    assert controls.try_quit() is False
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.UNSAVED_QUIT
    assert modal_view.focus_index == 0


def test_try_quit_dont_save_sets_pending_exit() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    controls.try_quit()
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert controls.consume_pending_exit() is True
    assert controls.consume_pending_exit() is False
    assert not controls.modal_host.active


def test_try_quit_cancel_and_escape_stay() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    controls.try_quit()

    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert controls._config_save._pending_exit is False
    assert controls.config_dirty
    assert not controls.modal_host.active

    controls.try_quit()
    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert controls._config_save._pending_exit is False
    assert controls.config_dirty
    assert not controls.modal_host.active


def test_try_quit_save_chains_through_save_as_new() -> None:
    saved_path = Path("/tmp/projects/my-track/unnamed-2.yaml")
    controls = _make_controls(("layer_1",))
    controls._config_save._on_save_new_config = lambda: saved_path
    _mutate_dirty(controls)

    controls.try_quit()
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.SAVE_CHOICE

    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert controls.try_quit() is True
    assert not controls.config_dirty


def test_try_quit_save_choice_esc_clears_quit_after_save() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    controls.try_quit()
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert controls._config_save._quit_after_save is True

    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert controls._config_save._quit_after_save is False
    assert controls._config_save._pending_exit is False
    assert controls.config_dirty
    assert not controls.modal_host.active


def test_stem_row_cycles_sources() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    stem_row = _row(view, "layer_1", RowKind.TRACK_STEM)
    controls.focus_descriptor = _desc(view, stem_row)
    assert controls.session.layers["layer_1"].stem == "drums"

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].stem == "bass"

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].stem == "drums"


def test_stem_change_clears_effects() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = True
    controls.session.layers["layer_1"].effects = {"pulse": {"onset": 50}}
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_STEM))

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].effects == {}


def test_locked_blocks_stem_change() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = True
    controls.session.layers["layer_1"].locked = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_STEM))
    assert controls.session.layers["layer_1"].stem == "drums"

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].stem == "drums"


def test_locked_blocks_preset_dir_enter_and_backspace() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.session.layers["layer_1"].expanded = True
    controls.focus_descriptor = _desc(controls.build_view_state(paused=False), _preset_dir_row(controls))
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.session.layers["layer_1"].locked = True

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.session.layers["layer_1"].locked = False
    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()

    controls.session.layers["layer_1"].locked = True
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_cycle_stem_to_full_mix() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = True
    controls.session.layers["layer_1"].stem = "other"
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(_row(view, "layer_1", RowKind.TRACK_STEM))

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].stem == "full_mix"

    view = controls.build_view_state(paused=False)
    assert _row_text(view, _focus_index(controls)) == "└─ driving stem: full-mix"


def test_try_quit_overwrite_confirm_esc_clears_quit_after_save() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    controls.try_quit()
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert controls._config_save._quit_after_save is True

    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert controls._config_save._quit_after_save is False
    assert controls._config_save._pending_exit is False
    assert controls.config_dirty
    assert not controls.modal_host.active


def test_settings_header_is_first_row() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    assert view.layout.kind( 0) == RowKind.SETTINGS_HEADER
    assert view.layout.kind( 1) == RowKind.CONFIG_HEADER
    assert view.layout.kind( 2) == RowKind.TRANSPORT


def test_settings_expand_collapse_and_sub_row_visibility() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    settings_row = view.layout.find_by_kind(RowKind.SETTINGS_HEADER)
    assert RowKind.SETTINGS_PREVIEW_QUALITY not in {
        view.layout.kind(i) for i in range(len(view.layout))
    }

    controls.focus_descriptor = _desc(view, settings_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.settings.expanded is True
    view = controls.build_view_state(paused=False)
    preview_quality_row = view.layout.find_by_kind(RowKind.SETTINGS_PREVIEW_QUALITY)
    assert preview_quality_row == 1
    assert preview_quality_row in view.layout.navigable_indices(view)
    assert view.layout.header_row_count() == 5

    controls.focus_descriptor = _desc(view, preview_quality_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    controls.focus_descriptor = _desc(view, settings_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.settings.expanded is False
    view = controls.build_view_state(paused=False)
    assert RowKind.SETTINGS_PREVIEW_QUALITY not in {
        view.layout.kind(i) for i in range(len(view.layout))
    }
    assert view.layout.header_row_count() == 3


def test_settings_ui_expand_collapse_and_sub_row_visibility() -> None:
    controls = _make_controls(("layer_1",))
    _expand_settings(controls)
    view = controls.build_view_state(paused=False)
    assert RowKind.SETTINGS_UI_FADE not in {
        view.layout.kind(i) for i in range(len(view.layout))
    }

    ui_header = view.layout.find_by_kind(RowKind.SETTINGS_UI_HEADER)
    controls.focus_descriptor = _desc(view, ui_header)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.settings.ui_expanded is True
    view = controls.build_view_state(paused=False)
    ui_fade_row = view.layout.find_by_kind(RowKind.SETTINGS_UI_FADE)
    assert ui_fade_row in view.layout.navigable_indices(view)
    assert view.layout.header_row_count() == 8

    controls.focus_descriptor = _desc(view, ui_fade_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    controls.focus_descriptor = _desc(view, ui_header)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.settings.ui_expanded is False
    view = controls.build_view_state(paused=False)
    assert RowKind.SETTINGS_UI_FADE not in {
        view.layout.kind(i) for i in range(len(view.layout))
    }
    assert view.layout.header_row_count() == 5


def test_settings_collapse_from_sub_row_refocuses_header() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    controls._settings.set_expanded(False)
    view = controls.build_view_state(paused=False)
    assert view.layout.resolve_navigable(
        controls.focus_descriptor, view
    ) == RowDescriptor(RowKind.SETTINGS_HEADER)


def test_settings_cycle_preview_quality() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.preview_quality == "balanced"
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "performance"
    view = controls.build_view_state(paused=False)
    assert _row_text(view, _focus_index(controls)) == "└─ preview quality: performance"

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "ultra-performance"
    view = controls.build_view_state(paused=False)
    assert _row_text(view, _focus_index(controls)) == "└─ preview quality: ultra-performance"

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "full-quality"
    view = controls.build_view_state(paused=False)
    assert _row_text(view, _focus_index(controls)) == "└─ preview quality: full-quality"

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "balanced"

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.cfg.editor.preview_quality == "full-quality"


def test_settings_preview_quality_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_cycle_preview_quality_calls_apply_preview_resolutions() -> None:
    controls, layer_manager = _make_controls_with_manager(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))

    layer_manager.apply_preview_resolutions.assert_called_once()


def test_settings_adjust_ui_fade() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.ui_fade == 10.0
    _expand_settings_ui(controls)
    view = controls.build_view_state(paused=False)
    ui_fade_row = view.layout.find_by_kind(RowKind.SETTINGS_UI_FADE)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_FADE)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_fade == 11.0
    view = controls.build_view_state(paused=False)
    assert _row_text(view, ui_fade_row) == "  └─ auto-fade: 11s"

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.cfg.editor.ui_fade == 6.0

    for _ in range(6):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_fade == 0.0
    view = controls.build_view_state(paused=False)
    assert _row_text(view, ui_fade_row) == "  └─ auto-fade: disabled"


def test_settings_ui_fade_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_FADE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_settings_adjust_ui_width() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.ui_width == 110
    _expand_settings_ui(controls)
    view = controls.build_view_state(paused=False)
    ui_width_row = view.layout.find_by_kind(RowKind.SETTINGS_UI_WIDTH)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_width == 111
    view = controls.build_view_state(paused=False)
    assert _row_text(view, ui_width_row) == "  └─ max width: 111"

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.cfg.editor.ui_width == 106

    for _ in range(86):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_width == 20


def test_settings_ui_width_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_settings_cycle_ui_width_mode() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.ui_width_mode == "flexible"
    _expand_settings_ui(controls)
    view = controls.build_view_state(paused=False)
    mode_row = view.layout.find_by_kind(RowKind.SETTINGS_UI_WIDTH_MODE)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH_MODE)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_width_mode == "fixed"
    view = controls.build_view_state(paused=False)
    assert _row_text(view, mode_row) == "  └─ width mode: fixed"

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_width_mode == "flexible"


def test_settings_ui_width_mode_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH_MODE)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_move_mode_swap_calls_apply_preview_resolutions() -> None:
    controls, layer_manager = _make_controls_with_manager(("layer_1", "layer_2", "layer_3"))
    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(15)
        if view.layout.kind(i) == RowKind.TRACK_HEADER and view.layout.slot(i) == "layer_2"
    )
    controls.focus_descriptor = _desc(view, header_row)
    controls.handle_keydown(_keydown(_MOVE_MODE_KEY))
    layer_manager.apply_preview_resolutions.reset_mock()

    controls.handle_keydown(_keydown(pygame.K_UP))

    layer_manager.apply_preview_resolutions.assert_called_once()


def test_default_focus_stays_on_transport() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    assert controls.focus_descriptor == RowDescriptor(RowKind.TRANSPORT)


def test_preset_switching_row_cycles_none_and_projectm() -> None:
    controls = _make_controls(("layer_1",))
    switched: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_switching_change=lambda slot: switched.append(slot)
    )
    controls.session.layers["layer_1"].expanded = True
    controls.session.layers["layer_1"].preset_switching_expanded = True
    view = controls.build_view_state(paused=False)
    row = _row(view, "layer_1", RowKind.TRACK_PRESET_SWITCHING_MODE)
    controls.focus_descriptor = view.layout.descriptor(row)
    assert controls.session.layers["layer_1"].preset_switching == "none"

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].preset_switching == "projectm"
    assert switched == ["layer_1"]

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].preset_switching == "none"


def test_projectm_mode_allows_preset_browse() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    controls.session.layers["layer_1"].expanded = True
    changed: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_change=lambda slot, _pl: changed.append(slot)
    )
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(
        _row(view, "layer_1", RowKind.TRACK_PRESET)
    )
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert changed == ["layer_1"]

    root, siblings = _make_sibling_dir_tree(3)
    dir_controls = _controls_with_playlist(root, siblings[0])
    dir_controls.session.layers["layer_1"].preset_switching = "projectm"
    dir_controls.session.layers["layer_1"].expanded = True
    dir_controls.focus_descriptor = _desc(
        dir_controls.build_view_state(paused=False), _preset_dir_row(dir_controls)
    )
    playlist = dir_controls.session.layers["layer_1"].playlist
    dir_controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert playlist.current_dir.resolve() == siblings[1].resolve()


def test_user_defined_mode_allows_preset_browse() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "user_defined"
    controls.session.layers["layer_1"].expanded = True
    changed: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_change=lambda slot, _pl: changed.append(slot)
    )
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(
        _row(view, "layer_1", RowKind.TRACK_PRESET)
    )
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert changed == ["layer_1"]

    root, siblings = _make_sibling_dir_tree(3)
    dir_controls = _controls_with_playlist(root, siblings[0])
    dir_controls.session.layers["layer_1"].preset_switching = "user_defined"
    dir_controls.session.layers["layer_1"].expanded = True
    dir_controls.focus_descriptor = _desc(
        dir_controls.build_view_state(paused=False), _preset_dir_row(dir_controls)
    )
    playlist = dir_controls.session.layers["layer_1"].playlist
    dir_controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert playlist.current_dir.resolve() == siblings[1].resolve()


def test_scope_row_hidden_when_mode_none() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    with pytest.raises(ValueError, match="TRACK_PRESET_SWITCHING_SCOPE"):
        _row(view, "layer_1", RowKind.TRACK_PRESET_SWITCHING_SCOPE)


def test_scope_row_visible_when_mode_projectm() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    controls.session.layers["layer_1"].preset_switching_expanded = True
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    _row(view, "layer_1", RowKind.TRACK_PRESET_SWITCHING_SCOPE)


def test_preset_duration_ctrl_step_is_ten_seconds() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    controls.session.layers["layer_1"].preset_switching_expanded = True
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    row = _row(view, "layer_1", RowKind.TRACK_PRESET_DURATION)
    controls.focus_descriptor = view.layout.descriptor(row)
    controls.session.layers["layer_1"].preset_duration = 30.0

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].preset_duration == 31.0

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].preset_duration == 41.0


def test_hard_cut_enabled_cycles_and_hides_child_rows() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    controls.session.layers["layer_1"].preset_switching_expanded = True
    controls.session.layers["layer_1"].expanded = True
    switched: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_switching_change=lambda slot: switched.append(slot)
    )
    view = controls.build_view_state(paused=False)
    _row(view, "layer_1", RowKind.TRACK_HARD_CUT_DURATION)
    _row(view, "layer_1", RowKind.TRACK_HARD_CUT_SENSITIVITY)

    row = _row(view, "layer_1", RowKind.TRACK_HARD_CUT_ENABLED)
    controls.focus_descriptor = view.layout.descriptor(row)
    assert controls.session.layers["layer_1"].hard_cut_enabled is True

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].hard_cut_enabled is False
    assert switched == ["layer_1"]

    view = controls.build_view_state(paused=False)
    with pytest.raises(ValueError, match="TRACK_HARD_CUT_DURATION"):
        _row(view, "layer_1", RowKind.TRACK_HARD_CUT_DURATION)

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].hard_cut_enabled is True
    view = controls.build_view_state(paused=False)
    _row(view, "layer_1", RowKind.TRACK_HARD_CUT_DURATION)


def test_easter_egg_steps_with_standard_and_large_increments() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    controls.session.layers["layer_1"].preset_switching_expanded = True
    controls.session.layers["layer_1"].expanded = True
    switched: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_switching_change=lambda slot: switched.append(slot)
    )
    view = controls.build_view_state(paused=False)
    row = _row(view, "layer_1", RowKind.TRACK_EASTER_EGG)
    controls.focus_descriptor = view.layout.descriptor(row)
    controls.session.layers["layer_1"].easter_egg = 1.0

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].easter_egg == pytest.approx(1.01)
    assert switched == ["layer_1"]

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].easter_egg == pytest.approx(1.11)


def test_preset_start_clean_cycles_yes_no() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    controls.session.layers["layer_1"].preset_switching_expanded = True
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    row = _row(view, "layer_1", RowKind.TRACK_PRESET_START_CLEAN)
    controls.focus_descriptor = view.layout.descriptor(row)
    assert controls.session.layers["layer_1"].preset_start_clean is False

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].preset_start_clean is True

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].preset_start_clean is False


def test_preset_switching_shuffle_cycles_off_on() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "user_defined"
    controls.session.layers["layer_1"].preset_switching_expanded = True
    controls.session.layers["layer_1"].expanded = True
    switched: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_switching_change=lambda slot: switched.append(slot)
    )
    view = controls.build_view_state(paused=False)
    row = _row(view, "layer_1", RowKind.TRACK_PRESET_SWITCHING_SHUFFLE)
    controls.focus_descriptor = view.layout.descriptor(row)
    assert controls.session.layers["layer_1"].preset_switching_shuffle is False

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].preset_switching_shuffle is True
    assert switched == ["layer_1"]

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].preset_switching_shuffle is False


def test_hard_cut_sensitivity_steps_like_beat_sensitivity() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    controls.session.layers["layer_1"].preset_switching_expanded = True
    controls.session.layers["layer_1"].expanded = True
    controls.session.layers["layer_1"].hard_cut_enabled = True
    view = controls.build_view_state(paused=False)
    row = _row(view, "layer_1", RowKind.TRACK_HARD_CUT_SENSITIVITY)
    controls.focus_descriptor = view.layout.descriptor(row)
    controls.session.layers["layer_1"].hard_cut_sensitivity = 1.5

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].hard_cut_sensitivity == pytest.approx(
        1.51
    )

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["layer_1"].hard_cut_sensitivity == pytest.approx(
        1.61
    )


def _focus_preset_file_row(controls: TuningControls) -> Path:
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(
        _row(view, "layer_1", RowKind.TRACK_PRESET)
    )
    current = controls.session.layers["layer_1"].playlist.current
    assert current is not None
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text("milk", encoding="utf-8")
    return current


def _focus_user_preset_item_row(
    controls: TuningControls,
    *,
    preset_path: Path | None = None,
) -> tuple[RowDescriptor, Path]:
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "user_defined"
    layer.preset_switching_expanded = True
    layer.user_presets_expanded = True
    layer.expanded = True
    path = preset_path or Path("/tmp/projects/my-track/user-preset-0.milk")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("milk", encoding="utf-8")
    layer.user_presets = [str(path)]
    desc = RowDescriptor(
        RowKind.TRACK_USER_PRESET_ITEM,
        slot="layer_1",
        preset_index=0,
    )
    controls.focus_descriptor = desc
    return desc, path


def test_ctrl_f_on_preset_file_prompts_favourite() -> None:
    controls = _make_controls(("layer_1",))
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert controls.handle_keydown(_keydown(pygame.K_f, mod=pygame.KMOD_CTRL)) is True

    mock_curation.prompt_favourite.assert_called_once_with("layer_1", current)


def test_ctrl_b_on_preset_file_prompts_blacklist() -> None:
    controls = _make_controls(("layer_1",))
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert controls.handle_keydown(_keydown(pygame.K_b, mod=pygame.KMOD_CTRL)) is True

    mock_curation.prompt_blacklist.assert_called_once_with(
        "layer_1",
        current,
        from_user_preset=False,
        user_preset_index=None,
    )


def test_ctrl_f_on_user_preset_item_prompts_favourite() -> None:
    controls = _make_controls(("layer_1",))
    _desc_row, path = _focus_user_preset_item_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert controls.handle_keydown(_keydown(pygame.K_f, mod=pygame.KMOD_CTRL)) is True

    mock_curation.prompt_favourite.assert_called_once_with("layer_1", path)


def test_ctrl_b_on_user_preset_item_prompts_blacklist() -> None:
    controls = _make_controls(("layer_1",))
    desc, path = _focus_user_preset_item_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert controls.handle_keydown(_keydown(pygame.K_b, mod=pygame.KMOD_CTRL)) is True

    mock_curation.prompt_blacklist.assert_called_once_with(
        "layer_1",
        path,
        from_user_preset=True,
        user_preset_index=desc.preset_index,
    )


def test_ctrl_f_b_not_on_preset_dir() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].expanded = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.descriptor(
        _row(view, "layer_1", RowKind.TRACK_PRESET_DIR)
    )
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    controls.handle_keydown(_keydown(pygame.K_f, mod=pygame.KMOD_CTRL))
    controls.handle_keydown(_keydown(pygame.K_b, mod=pygame.KMOD_CTRL))
    mock_curation.prompt_favourite.assert_not_called()
    mock_curation.prompt_blacklist.assert_not_called()


def test_ctrl_f_b_blocked_when_layer_locked() -> None:
    controls = _make_controls(("layer_1",))
    _focus_preset_file_row(controls)
    controls.session.layers["layer_1"].locked = True
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert controls.handle_keydown(_keydown(pygame.K_f, mod=pygame.KMOD_CTRL)) is True
    assert controls.handle_keydown(_keydown(pygame.K_b, mod=pygame.KMOD_CTRL)) is True
    mock_curation.prompt_favourite.assert_not_called()
    mock_curation.prompt_blacklist.assert_not_called()


def test_ctrl_f_b_allowed_in_projectm_mode() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "projectm"
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert controls.handle_keydown(_keydown(pygame.K_f, mod=pygame.KMOD_CTRL)) is True

    mock_curation.prompt_favourite.assert_called_once_with("layer_1", current)


def test_ctrl_f_b_ignored_on_non_preset_rows() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.TRANSPORT)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    controls.handle_keydown(_keydown(pygame.K_f, mod=pygame.KMOD_CTRL))
    controls.handle_keydown(_keydown(pygame.K_b, mod=pygame.KMOD_CTRL))
    mock_curation.prompt_favourite.assert_not_called()
    mock_curation.prompt_blacklist.assert_not_called()