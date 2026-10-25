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

from cleave.config_schema.editor import (
    DEFAULT_EDITOR_HEIGHT,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_EDITOR_UPSCALE,
    DEFAULT_EDITOR_WIDTH,
    DEFAULT_NOTIFICATION_DISPLAY_SEC,
    DEFAULT_SHELL_LAYOUT_MODE,
    DEFAULT_UI_MIN_WIDTH,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    MIN_COLUMN_WIDTH,
    editor_display_size,
)
from cleave.config_schema.layers import (
    DEFAULT_LAYER_SLOTS,
    MAX_LAYER_COUNT,
)
from tests.support.config import TEST_LAYER_STEMS
from cleave.preset_playlist import (
    PresetPlaylist,
    directory_display,
    playlist_at_dir,
    preset_browse_floor,
    preset_filename_display,
    scan_preset_playlist,
)
from cleave.timeline import SlotCue, TimelineLane, canonicalize, lane_level_at
from cleave.project import load_manifest, write_manifest
from cleave.song_markers import SongMarker
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.shell_focus import InspectorGroupKey, ShellRegion
from cleave.viz.navigator import layer_node_id, overlay_card_node_id
from cleave.viz.key_repeat import mod_shift
from cleave.viz.playback import format_mmss
from tests.support.viz import (
    press_layer_row,
    baseline_tuning_ui_metrics,
    make_test_cfg,
    make_track_block,
    noop_layer_bindings,
    overlay_font,
    stub_playback_state,
)
from cleave.user_config import load_user_config
from cleave.viz.controls import (
    NOTIFICATION_TIMELINE_DISABLED_TEXT,
    NOTIFICATION_TIMELINE_ENABLED_TEXT,
    SEEK_SHORT,
    TuningControls,
)
from cleave.viz.settings_controls import EDITOR_WINDOW_RESTART_TOAST
from cleave.viz.modal import ModalKind, ModalLabeledLine
from cleave.viz.theme import ERROR_NOTIFICATION, HIGHLIGHT
from cleave.viz.session import (
    LayerRuntime,
    TimelineRuntime,
    TuningSession,
)
from cleave.viz.row_hotkeys import handle_row_hotkey
from cleave.viz.row_spec import (
    REPEAT_ROW_KINDS,
    apply_field_action,
    apply_field_horizontal,
)
from cleave.viz.commands import command_by_id, command_context
from cleave.viz.theme import (
    ACTION,
    CONFIG_DIRTY,
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
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import (
    row_composite_header_display_text,
    row_expand_subheader_display_text,
    row_full_line_display_text,
    row_indent as _layout_row_indent,
    row_labeled_display_text,
    row_text as _layout_row_text,
    row_value_color as _layout_row_value_color,
    row_value_color_for,
)
from cleave.viz.row_sections import row_tree_indent_depth
from cleave.viz.row_spec import RowPresentStyle, row_spec
from cleave.viz.tuning_panel_draw import (
    TREE_INDENT,
    _row_bg_color,
    fit_row_text,
    preset_row_prefix_width,
    render_visibility_icon,
    track_header_prefix_width,
)
from cleave.viz.tuning_view_state import TuningViewState


def _keydown(key: int, *, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def _make_playlist(name: str, count: int = 3) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{name}")
    paths = tuple(current_dir / f"preset-{i}.milk" for i in range(count))
    return PresetPlaylist(current_dir=current_dir, paths=paths, index=0)


_DEFAULT_ACTIVE_CONFIG = Path("/tmp/projects/my-track/active.yaml")


def _mutate_dirty(controls: TuningControls) -> None:
    controls.session.layers["layer_1"].opacity_pct = 60


def _make_controls(
    slots: tuple[str, ...] = ("layer_1", "layer_2"),
    *,
    timeline_enabled: bool = False,
    launch_config_path: Path | None = _DEFAULT_ACTIVE_CONFIG,
    beat_times: tuple[float, ...] = (),
    bar_times: tuple[float, ...] = (),
    project_dir: Path | None = None,
    duration_sec: float = 120.0,
    signals=None,
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
        duration_sec=duration_sec,
        project_dir=project_dir,
        launch_config_path=launch_config_path,
        beat_times=beat_times,
        bar_times=bar_times,
        signals=signals,
    )


def _make_controls_with_manager(
    slots: tuple[str, ...] = ("layer_1",),
    *,
    can_add: bool = True,
    can_remove: bool = True,
    launch_config_path: Path | None = _DEFAULT_ACTIVE_CONFIG,
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
        layer_manager=layer_manager,
    )
    return controls, layer_manager


def _expand_project(controls: TuningControls) -> None:
    return None


def _expand_project_render(controls: TuningControls) -> None:
    return None


def _save_now(controls: TuningControls) -> None:
    command_by_id("file.save").run(controls)
    assert not controls.modal_host.active


def test_build_view_state_passes_fps() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False, fps=42.0)
    assert view.fps == 42.0


def test_add_layer_row_omitted_at_max() -> None:
    controls, manager = _make_controls_with_manager(("layer_1",), can_add=False)
    view = controls.build_view_state(paused=False)
    with pytest.raises(ValueError, match="no row for kind"):
        view.layout.find_by_kind(RowKind.LAYER_MANAGEMENT_ADD)
    controls.focus_descriptor = RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD)

    press_layer_row(controls, RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD), _keydown(pygame.K_RETURN))

    manager.add_layer.assert_not_called()
    assert controls.modal_host.view_state() is None


def test_delete_layer_at_min_shows_toast() -> None:
    controls, manager = _make_controls_with_manager(("layer_1",), can_remove=False)
    controls.shell_focus.selected_id = layer_node_id("layer_1")
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_DELETE))

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
    press_layer_row(
        controls,
        RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD),
        _keydown(pygame.K_RETURN),
    )
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))

    manager.add_layer.assert_called_once()
    assert "layer_2" in controls.session.layer_z_order


@pytest.mark.parametrize("confirm_key", (pygame.K_RETURN, pygame.K_DELETE))
def test_delete_layer_confirm_calls_manager(confirm_key: int) -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    controls.shell_focus.selected_id = layer_node_id("layer_2")
    controls.focus_descriptor = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_2")

    press_layer_row(controls, RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_2"), _keydown(confirm_key))
    press_layer_row(controls, RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_2"), _keydown(pygame.K_RETURN))

    manager.remove_layer.assert_called_once_with("layer_2")
    assert "layer_2" not in controls.session.layer_z_order


def test_delete_layer_from_header_with_delete_key() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(pygame.K_DELETE))
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(pygame.K_RETURN))

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
    controls.layer_lifecycle.confirm_delete("layer_4")

    manager.remove_layer.assert_called_once_with("layer_4")
    assert len(controls.session.layer_z_order) == 3
    assert controls.session.timeline.focus_row == 2


def test_delete_layer_exits_move_mode() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(_MOVE_MODE_KEY))
    assert controls.layer_lifecycle.move_mode_slot == "layer_1"

    controls.layer_lifecycle.prompt_delete("layer_2")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_RETURN))

    assert controls.layer_lifecycle.move_mode_slot is None
    manager.remove_layer.assert_called_once_with("layer_2")


def _mount_track_sections(view: TuningViewState) -> None:
    from cleave.viz.row_layout import RowLayout, build_layout_frame
    from cleave.viz.row_sections import TRACK_SECTION, append_expand_section_rows

    if any(row.kind.name.startswith("TRACK_") for row in view.layout.rows):
        return
    rows = list(view.layout.rows)
    for slot in view.layer_z_order:
        append_expand_section_rows(rows, TRACK_SECTION, view, slot)
    view.layout = RowLayout(
        rows=tuple(rows),
        descriptor_index={desc: index for index, desc in enumerate(rows)},
    )
    view.layout_frame = build_layout_frame(view.layout, view)


def _inspector_kinds(controls: TuningControls, slot: str) -> list[RowKind]:
    from cleave.viz.inspector import build_inspector_rows

    view = controls.build_view_state(paused=False)
    focus = controls.shell_focus
    rows = build_inspector_rows(
        view, layer_node_id(slot), focus.collapsed, focus.opened
    )
    return [
        row.descriptor.kind
        for row in rows
        if row.descriptor is not None
    ]


def _row(
    view: TuningViewState,
    stem: str,
    kind: RowKind,
    *,
    effect_id: str | None = None,
    driver_slug: str | None = None,
) -> int:
    try:
        return view.layout.find(stem, kind, effect_id=effect_id, driver_slug=driver_slug)
    except ValueError:
        if not kind.name.startswith("TRACK_") and not kind.name.startswith("LAYER_MANAGEMENT"):
            raise
        before = len(view.layout)
        _mount_track_sections(view)
        if len(view.layout) == before:
            raise
        return view.layout.find(stem, kind, effect_id=effect_id, driver_slug=driver_slug)


def _row_indent(state: TuningViewState, index: int | RowDescriptor) -> int:
    if isinstance(index, RowDescriptor):
        return TREE_INDENT * row_tree_indent_depth(index.kind)
    return _layout_row_indent(state, index)


def _row_value_color(
    state: TuningViewState, index: int | RowDescriptor
) -> tuple[int, int, int]:
    if isinstance(index, RowDescriptor):
        return row_value_color_for(state, index)
    return _layout_row_value_color(state, index)


def _page_kinds(state: TuningViewState, node_id: str) -> list[RowKind]:
    rows = build_inspector_rows(state, node_id, frozenset())
    return [
        row.descriptor.kind for row in rows if row.descriptor is not None
    ]


def _assert_card_order(state: TuningViewState, card: str, *kinds: RowKind) -> None:
    page = _page_kinds(state, overlay_card_node_id(card))
    indexes = [page.index(kind) for kind in kinds]
    assert indexes == sorted(indexes)
    assert len(set(indexes)) == len(indexes)


def _text_for_descriptor(state: TuningViewState, desc: RowDescriptor) -> str:
    spec = row_spec(desc.kind)
    style = spec.present_style
    if style == RowPresentStyle.LABELED_VALUE:
        return row_labeled_display_text(state, desc)
    if style == RowPresentStyle.EXPAND_SUBHEADER:
        return row_expand_subheader_display_text(state, desc)
    if style in (RowPresentStyle.COMPOSITE_HEADER, RowPresentStyle.TRACK_HEADER):
        return row_composite_header_display_text(state, desc)
    if style == RowPresentStyle.FULL_LINE:
        return row_full_line_display_text(state, desc)
    return ""


def _row_text(state: TuningViewState, index: int | RowDescriptor) -> str:
    if isinstance(index, RowDescriptor):
        return _text_for_descriptor(state, index)
    return _layout_row_text(state, index)


def _desc(view: TuningViewState, index: int | RowDescriptor) -> RowDescriptor:
    if isinstance(index, RowDescriptor):
        return index
    return view.layout.descriptor(index)


def _expand_settings(controls: TuningControls) -> None:
    return None


def _expand_settings_ui(controls: TuningControls) -> None:
    return None


def _expand_settings_editor_window(controls: TuningControls) -> None:
    return None


def _expand_settings_latency(controls: TuningControls) -> None:
    return None


def _focus_index(controls: TuningControls, *, paused: bool = False) -> int:
    view = controls.build_view_state(paused=paused)
    return view.layout.find_descriptor(controls.focus_descriptor)



_INSPECTOR_COMMANDS = {
    RowKind.TIMELINE_PRESETS: "timeline.apply_preset",
    RowKind.TIMELINE_RESET: "timeline.reset",
    RowKind.TIMELINE_SNAP_CUES: "timeline.snap_cues",
}
_BEAT_INSPECTOR_KINDS = {
    RowKind.TIMELINE_BAR_PHASE,
    RowKind.TIMELINE_BAR_GRID,
    RowKind.TIMELINE_PLACEMENT_SNAP,
    RowKind.TIMELINE_SNAP_CUES,
}
_CUT_INSPECTOR_KINDS = {
    RowKind.TIMELINE_HARD_CUTS,
    RowKind.TIMELINE_HARD_CUT_FADE_IN,
    RowKind.TIMELINE_HARD_CUT_FADE_OUT,
    RowKind.TIMELINE_HARD_CUT_CROSSFADE,
    RowKind.TIMELINE_SOFT_CUTS,
    RowKind.TIMELINE_SOFT_CUT_FADE_IN,
    RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
    RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
    RowKind.TIMELINE_APPLY_SOFT_CUTS,
    RowKind.TIMELINE_APPLY_HARD_CUTS,
    RowKind.TIMELINE_REMOVE_SOFT_CUTS,
    RowKind.TIMELINE_REMOVE_HARD_CUTS,
}
_SONG_INSPECTOR_KINDS = {
    RowKind.SONG_MARKERS_HEADER,
    RowKind.SONG_MARKER_ITEM,
    RowKind.TIMELINE_SNAP_TO_SONG_MARKERS,
}


def _focus_inspector_kind(
    controls: TuningControls,
    kind: RowKind,
    *,
    marker_index: int | None = None,
) -> None:
    focus = controls.shell_focus
    focus.region = ShellRegion.INSPECTOR
    focus.selected_id = (
        "song_markers" if kind in _SONG_INSPECTOR_KINDS else "render.timeline"
    )
    if kind in _BEAT_INSPECTOR_KINDS:
        focus.opened.add(InspectorGroupKey(RowKind.TIMELINE_BEAT_BAR_GRID_HEADER))
    if kind in _CUT_INSPECTOR_KINDS:
        focus.opened.add(InspectorGroupKey(RowKind.TIMELINE_CUTS_HEADER))
    command_id = _INSPECTOR_COMMANDS.get(kind)
    if command_id is not None:
        focus.inspector_command_id = command_id
        focus.inspector_cursor = None
        return
    focus.inspector_command_id = None
    focus.inspector_cursor = RowDescriptor(kind, marker_index=marker_index)


def _press_focused(controls: TuningControls, event: pygame.event.Event) -> bool:
    """Route a key the way the tests name their target.

    Inspector region uses the inspector. A main-list cursor still applies
    that descriptor's row action so field tests do not need the old tree.
    """
    if controls.modal_host.active:
        return TuningControls.handle_keydown(controls, event)
    if controls.shell_focus.region is ShellRegion.INSPECTOR:
        if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            return controls.inspector.handle_hotkey(event)
        if controls.inspector.handle_keydown(event):
            return True
    cursor = controls.focus_cursor
    if isinstance(cursor, MainFocus):
        desc = cursor.descriptor
        key = event.key
        if key in (
            pygame.K_LEFT,
            pygame.K_RIGHT,
            pygame.K_PAGEUP,
            pygame.K_PAGEDOWN,
        ):
            forward = key in (pygame.K_RIGHT, pygame.K_PAGEDOWN)
            large = key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN)
            if apply_field_horizontal(controls, desc, forward, large):
                return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if apply_field_action(controls, desc):
                return True
        if handle_row_hotkey(controls, desc, event):
            return True
    return TuningControls.handle_keydown(controls, event)


def _press_timeline_hotkey(controls: TuningControls, key: int) -> bool:
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    controls.shell_focus.selected_id = "render.timeline"
    return controls.navigator.handle_hotkey(_keydown(key))


def test_focus_navigation_does_not_walk_a_main_list() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    before = controls.focus_cursor
    assert _press_focused(controls, _keydown(pygame.K_DOWN)) is True
    assert controls.focus_cursor == before
    assert _press_focused(controls, _keydown(pygame.K_UP)) is True
    assert controls.focus_cursor == before
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.focus_cursor == before

def test_disabled_render_overlay_can_expand_sub_rows() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    controls.focus_descriptor = header_row
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_overlays.opening_card.enabled is False
    assert controls.session.render_overlays.closing_card.enabled is False

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.render_overlays.opening_card.enabled is False

    view = controls.build_view_state(paused=False)
    leftover = {row.kind for row in view.layout.rows}
    assert RowKind.RENDER_OVERLAYS_HEADER not in leftover
    assert RowKind.RENDER_OVERLAY_CARD_HEADER not in leftover
    page = _page_kinds(view, overlay_card_node_id("opening_card"))
    assert RowKind.RENDER_OVERLAY_CARD_POSITION in page


def test_disabled_render_post_fx_can_expand_sub_rows() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    header_row = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    controls.focus_descriptor = header_row
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_post_fx.enabled is False

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.render_post_fx.enabled is False

    view = controls.build_view_state(paused=False)
    leftover = {row.kind for row in view.layout.rows}
    assert RowKind.RENDER_POST_FX_HEADER not in leftover
    assert RowKind.RENDER_POST_FX_FADE_HEADER not in leftover
    page = _page_kinds(view, "render.post_fx")
    assert RowKind.RENDER_POST_FX_FADE_IN_START in page


def test_disabled_render_timeline_can_open_panel() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is False
    command_by_id("timeline.show_strip").run(controls)
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is True
    assert isinstance(controls.focus_cursor, TimelineFocus)
    view = controls.build_view_state(paused=False)
    kinds = {row.kind for row in view.layout.rows}
    assert RowKind.RENDER_TIMELINE_HEADER not in kinds
    assert RowKind.TIMELINE_BEAT_BAR_GRID_HEADER not in kinds
    assert RowKind.SONG_MARKERS_HEADER not in kinds
    assert RowKind.TIMELINE_PRESETS_HEADER not in kinds

def test_beat_sensitivity_clamps() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_BEAT, slot="layer_1")
    for _ in range(400):
        press_layer_row(controls, RowDescriptor(RowKind.TRACK_BEAT, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].beat_sensitivity == pytest.approx(5.0)

    for _ in range(500):
        press_layer_row(controls, RowDescriptor(RowKind.TRACK_BEAT, slot="layer_1"), _keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].beat_sensitivity == pytest.approx(0.0)


def test_opacity_ctrl_step_is_ten_percent() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    controls.session.layers["layer_1"].opacity_pct = 50

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1"), _keydown(pygame.K_PAGEDOWN),)
    assert controls.session.layers["layer_1"].opacity_pct == 60

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1"), _keydown(pygame.K_PAGEUP),)
    assert controls.session.layers["layer_1"].opacity_pct == 50


def test_move_mode_swaps_z_order() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))

    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")
    assert press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(_MOVE_MODE_KEY)) is True
    assert controls.layer_lifecycle.move_mode_slot == "layer_2"

    assert controls.handle_move_mode_keydown(_keydown(pygame.K_UP)) is True
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]

    assert controls.handle_move_mode_keydown(_keydown(_MOVE_MODE_KEY)) is True
    assert controls.layer_lifecycle.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]
    assert controls.config_dirty


def test_move_mode_esc_cancels_without_applying() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))

    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(_MOVE_MODE_KEY))
    controls.handle_move_mode_keydown(_keydown(pygame.K_UP))
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]

    assert controls.handle_move_mode_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.layer_lifecycle.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_1", "layer_2", "layer_3"]
    assert not controls.config_dirty


def test_move_mode_backspace_cancels_without_applying() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))

    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(_MOVE_MODE_KEY))
    controls.handle_move_mode_keydown(_keydown(pygame.K_DOWN))
    assert controls.session.layer_z_order == ["layer_1", "layer_3", "layer_2"]

    assert controls.handle_move_mode_keydown(_keydown(pygame.K_BACKSPACE)) is True
    assert controls.layer_lifecycle.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_1", "layer_2", "layer_3"]
    assert not controls.config_dirty


def test_save_triggers_notification_without_blocking_input() -> None:
    controls = _make_controls(("layer_1",))
    stderr = io.StringIO()
    with patch.object(time, "monotonic", return_value=1000.0):
        with patch("sys.stderr", stderr):
            _save_now(controls)

        assert "Saved" in stderr.getvalue()
        state = controls.build_view_state(paused=False)
        assert state.notification_message == "Saved"
        assert state.notification_remaining_sec == DEFAULT_NOTIFICATION_DISPLAY_SEC

        before = controls.focus_cursor
        assert _press_focused(controls, _keydown(pygame.K_DOWN)) is True
        assert controls.focus_cursor == before
        assert controls.playback.paused is False


def test_save_writes_immediately_no_modal() -> None:
    launch_path = Path("/tmp/projects/my-track/cleave-viz.yaml")
    writes: list[Path] = []
    controls = _make_controls(("layer_1",), launch_config_path=launch_path)
    controls._config_save._on_save_config = lambda path: writes.append(path) or path.name
    _mutate_dirty(controls)
    _save_now(controls)
    assert writes == [launch_path]
    assert not controls.config_dirty
    assert not controls.modal_host.active


def test_save_command_label() -> None:
    controls = _make_controls(("layer_1",))
    command = command_by_id("file.save")
    assert command.label == "Save"
    assert command.enabled(command_context(controls)) is True
    assert command.label_role(command_context(controls)) == ACTION


def test_save_command_label_role_when_dirty() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    assert controls.config_dirty
    assert command_by_id("file.save").label_role(command_context(controls)) == CONFIG_DIRTY


def test_blend_and_opacity_change_sets_dirty_save_clears() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty

    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.config_dirty

    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.config_dirty

    _save_now(controls)
    assert not controls.config_dirty


def test_preset_row_truncates_long_filenames() -> None:
    long_name = (
        "Phat_Zylot_Eo.S. rainbow bubble_mid3-starpoints_spirals_VE "
        "- Bitcore Tweak.milk (1/50)"
    )
    view = TuningViewState(
        layer_z_order=("layer_1",),
        tracks={
            "layer_1": make_track_block(
                stem="drums",
                preset_dir_label="short (1/1)",
                preset_label=long_name,
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                enabled=True,
                preset_empty=False,
            )
        },
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)),
        move_mode_slot=None,
        notification_message=None,
        notification_remaining_sec=0.0,
    )
    preset_row = _row(view, "layer_1", RowKind.TRACK_PRESET)
    font = overlay_font()
    panel_w = baseline_tuning_ui_metrics().panel_content_max_width
    label = fit_row_text(font, view, preset_row, max_content_width=panel_w)
    prefix_w = preset_row_prefix_width(font, font.get_linesize())
    assert font.size(label)[0] <= panel_w - prefix_w
    assert label.endswith("(1/50)")
    assert label.startswith("Phat_Zylot")
    assert "…" in label
    assert "…/" not in label


def test_fit_row_text_config_and_preset_share_panel_width() -> None:
    long_name = (
        "Phat_Zylot_Eo.S. rainbow bubble_mid3-starpoints_spirals_VE "
        "- Bitcore Tweak.milk (1/50)"
    )
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    view.tracks["layer_1"] = make_track_block(
        stem="drums",
        preset_dir_label="short (1/1)",
        preset_label=long_name,
        blend_mode="black-key",
        opacity_pct=50,
        beat_sensitivity=1.0,
        effects={},
        enabled=True,
        preset_empty=False,
    )
    preset_row = _row(view, "layer_1", RowKind.TRACK_PRESET)
    font = overlay_font()
    panel_w = baseline_tuning_ui_metrics().panel_content_max_width
    preset_label = fit_row_text(font, view, preset_row, max_content_width=panel_w)
    preset_prefix_w = preset_row_prefix_width(font, font.get_linesize())
    assert font.size(preset_label)[0] + preset_prefix_w <= panel_w



def test_save_writes_launch_path() -> None:
    launch_path = Path("/tmp/my-launch.cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("layer_1",))
    controls._config_save._active_config_path = launch_path
    controls._config_save._on_save_config = lambda path: (
        writes.append(path) or path.name
    )

    stderr = io.StringIO()
    with patch.object(time, "monotonic", return_value=2000.0):
        with patch("sys.stderr", stderr):
            _save_now(controls)

        assert writes == [launch_path]
        assert not controls.modal_host.active
        state = controls.build_view_state(paused=False)
        assert state.notification_message == "Saved"
        assert "Saved" in stderr.getvalue()


def test_esc_requests_overlay_hide() -> None:
    controls = _make_controls()
    assert _press_focused(controls, _keydown(pygame.K_ESCAPE)) is True
    assert controls.consume_hide_overlay() is True
    assert controls.consume_hide_overlay() is False


def test_esc_hide_preserves_focus_when_not_in_timeline_submenu() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert _press_focused(controls, _keydown(pygame.K_ESCAPE)) is True
    assert controls.consume_hide_overlay() is True
    controls.exit_timeline_submenu()
    assert controls.focus_descriptor.kind == RowKind.TRACK_PRESET


def test_exit_timeline_submenu_only_when_submenu_focused() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    controls.exit_timeline_submenu()
    assert controls.focus_descriptor.kind == RowKind.TRACK_PRESET

    controls.focus_cursor = TimelineFocus(0)
    controls.exit_timeline_submenu()
    assert controls.focus_descriptor.kind == RowKind.RENDER_TIMELINE_HEADER


def test_esc_in_move_mode_does_not_request_overlay_hide() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(_MOVE_MODE_KEY))
    assert controls.layer_lifecycle.move_mode_slot == "layer_1"
    assert controls.handle_move_mode_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.layer_lifecycle.move_mode_slot is None
    assert controls.consume_hide_overlay() is False


def test_ctrl_q_not_handled_by_main_controls() -> None:
    controls = _make_controls()
    assert _press_focused(controls, 
        _keydown(pygame.K_q, mod=pygame.KMOD_CTRL)
    ) is True


def test_q_alone_does_not_quit() -> None:
    controls = _make_controls()
    assert _press_focused(controls, _keydown(pygame.K_q)) is True


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






def test_render_overlay_header_label_spacing() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    header_row = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    assert _row_text(view, header_row) == "Render: OVERLAYS ▼"


def test_render_overlay_title_header_expand_arrow() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    title_header = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER, card="opening_card")
    assert _row_text(view, title_header) == "  └─ title ▼"

    view = controls.build_view_state(paused=False)
    title_header = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER, card="opening_card")
    assert _row_text(view, title_header) == "  └─ title ▼"


def test_render_overlay_body_header_expand_arrow() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    body_header = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_HEADER, card="opening_card")
    assert _row_text(view, body_header) == "  └─ body ▼"

    view = controls.build_view_state(paused=False)
    body_header = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_HEADER, card="opening_card")
    assert _row_text(view, body_header) == "  └─ body ▼"


_OVERLAY_TEST_FONTS = ("alpha", "bravo", "charlie")


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=_OVERLAY_TEST_FONTS,
)
def test_render_overlay_title_font_row(_mock_fonts) -> None:
    controls = _make_controls()
    controls.session.render_overlays.opening_card.title_font = "alpha"
    view = controls.build_view_state(paused=False)
    font_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT, card="opening_card")
    assert _row_text(view, font_row) == "    └─ font: alpha (1/3)"

    controls.focus_descriptor = _desc(view, font_row)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.render_overlays.opening_card.title_font == "bravo"


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=_OVERLAY_TEST_FONTS,
)
def test_render_overlay_body_font_row(_mock_fonts) -> None:
    controls = _make_controls()
    controls.session.render_overlays.opening_card.body_font = "bravo"
    view = controls.build_view_state(paused=False)
    font_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_FONT, card="opening_card")
    assert _row_text(view, font_row) == "    └─ font: bravo (2/3)"

    controls.focus_descriptor = _desc(view, font_row)
    _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.session.render_overlays.opening_card.body_font == "alpha"


def test_render_overlay_title_font_size_row() -> None:
    controls = _make_controls()
    controls.session.render_overlays.opening_card.title_font_size = 12
    view = controls.build_view_state(paused=False)
    font_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE, card="opening_card")
    assert _row_text(view, font_row) == "    └─ font size: 12px"

    controls.focus_descriptor = _desc(view, font_row)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.render_overlays.opening_card.title_font_size == 13


def test_render_overlay_title_margin_bottom_row() -> None:
    controls = _make_controls()
    controls.session.render_overlays.opening_card.title_margin_bottom = 10
    view = controls.build_view_state(paused=False)
    margin_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_MARGIN_BOTTOM, card="opening_card")
    assert _row_text(view, margin_row) == "    └─ margin bottom: 10px"

    controls.focus_descriptor = _desc(view, margin_row)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.render_overlays.opening_card.title_margin_bottom == 11


def test_render_overlay_body_font_size_row() -> None:
    controls = _make_controls()
    controls.session.render_overlays.opening_card.body_font_size = 18
    view = controls.build_view_state(paused=False)
    font_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_FONT_SIZE, card="opening_card")
    assert _row_text(view, font_row) == "    └─ font size: 18px"

    controls.focus_descriptor = _desc(view, font_row)
    _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.session.render_overlays.opening_card.body_font_size == 17


def test_render_overlay_font_rows_nested_indent() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    title_header = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER, card="opening_card")
    title_text = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="opening_card")
    title_colour = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="opening_card")
    title_background = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR, card="opening_card")
    title_font_size = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE, card="opening_card")
    title_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT, card="opening_card")
    body_header = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_HEADER, card="opening_card")
    body_text = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="opening_card")
    body_colour = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR, card="opening_card")
    body_background = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR, card="opening_card")
    body_font_size = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_FONT_SIZE, card="opening_card")
    body_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_FONT, card="opening_card")
    background_colour = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR, card="opening_card")
    border_colour = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR, card="opening_card")
    assert _row_indent(view, title_header) == TREE_INDENT * 2
    assert _row_indent(view, title_text) == TREE_INDENT * 3
    assert _row_indent(view, title_colour) == TREE_INDENT * 3
    assert _row_indent(view, title_background) == TREE_INDENT * 3
    assert _row_indent(view, title_font_size) == TREE_INDENT * 3
    assert _row_indent(view, title_font) == TREE_INDENT * 3
    assert _row_indent(view, body_header) == TREE_INDENT * 2
    assert _row_indent(view, body_text) == TREE_INDENT * 3
    assert _row_indent(view, body_colour) == TREE_INDENT * 3
    assert _row_indent(view, body_background) == TREE_INDENT * 3
    assert _row_indent(view, body_font_size) == TREE_INDENT * 3
    assert _row_indent(view, body_font) == TREE_INDENT * 3
    assert _row_indent(view, background_colour) == TREE_INDENT * 2
    assert _row_indent(view, border_colour) == TREE_INDENT * 2


def test_render_overlay_background_margin_and_padding_placement() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    colour = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR, card="opening_card")
    margin = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN, card="opening_card")
    padding = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_PADDING, card="opening_card")
    border_width = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH, card="opening_card")
    _assert_card_order(
        view,
        "opening_card",
        colour.kind,
        margin.kind,
        padding.kind,
        border_width.kind,
    )
    assert _row_indent(view, margin) == TREE_INDENT * 2
    assert _row_indent(view, padding) == TREE_INDENT * 2


def test_render_overlay_background_margin_row() -> None:
    controls = _make_controls()
    controls.session.render_overlays.opening_card.background_margin = 40
    view = controls.build_view_state(paused=False)
    margin_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN, card="opening_card")
    assert _row_text(view, margin_row) == "  └─ background margin: 40px"

    controls.focus_descriptor = _desc(view, margin_row)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.render_overlays.opening_card.background_margin == 41
    _press_focused(controls, _keydown(pygame.K_PAGEUP))
    assert controls.session.render_overlays.opening_card.background_margin == 31


def test_render_overlay_background_padding_row() -> None:
    controls = _make_controls()
    controls.session.render_overlays.opening_card.background_padding = 20
    view = controls.build_view_state(paused=False)
    padding_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_PADDING, card="opening_card")
    assert _row_text(view, padding_row) == "  └─ background padding: 20px"

    controls.focus_descriptor = _desc(view, padding_row)
    _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.session.render_overlays.opening_card.background_padding == 19
    _press_focused(controls, _keydown(pygame.K_PAGEDOWN))
    assert controls.session.render_overlays.opening_card.background_padding == 29


def _expand_overlay_card_title(controls: TuningControls, card: str) -> None:
    overlays = controls.session.render_overlays


def test_render_overlay_title_text_row_present_for_both_cards() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    _expand_overlay_card_title(controls, "closing_card")
    view = controls.build_view_state(paused=False)
    opening = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="opening_card")
    closing = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="closing_card")
    opening_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT, card="opening_card")
    closing_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT, card="closing_card")
    assert opening.card == "opening_card"
    assert closing.card == "closing_card"
    _assert_card_order(view, "opening_card", opening.kind, opening_font.kind)
    _assert_card_order(view, "closing_card", closing.kind, closing_font.kind)


def test_render_overlay_title_text_formats_newlines_as_spaces() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_content = "Line one\nLine two"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="opening_card")
    assert _row_text(view, row) == "    └─ title text: Line one Line two"


def test_render_overlay_title_text_enter_opens_single_line_modal() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_content = "Opening title"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.kind == ModalKind.TEXT
    assert modal.single_line is True
    assert modal.cta == "Change text..."
    assert modal.draft == "Opening title"
    assert modal.editing is True


def test_render_overlay_title_text_confirm_updates_session() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_content = "Opening title"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    controls.modal_host.handle_text_input(" edited")
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _press_focused(controls, _keydown(pygame.K_RETURN))
    assert controls.modal_host.view_state() is None
    assert (
        controls.session.render_overlays.opening_card.title_content
        == "Opening title edited"
    )


def test_render_overlay_title_text_cancel_keeps_session() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "closing_card")
    controls.session.render_overlays.closing_card.title_content = "Closing title"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="closing_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    controls.modal_host.handle_text_input(" edited")
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    assert controls.modal_host.view_state() is None
    assert controls.session.render_overlays.closing_card.title_content == (
        "Closing title"
    )


def test_render_overlay_title_text_lock_blocks_enter() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    controls.session.render_overlays.locked = True
    _press_focused(controls, _keydown(pygame.K_RETURN))
    assert controls.modal_host.view_state() is None


def _replace_text_modal_draft(controls: TuningControls, text: str) -> None:
    view = controls.modal_host.view_state()
    assert view is not None
    for _ in range(len(view.draft)):
        _press_focused(controls, _keydown(pygame.K_BACKSPACE))
    if text:
        controls.modal_host.handle_text_input(text)


def _confirm_text_modal(controls: TuningControls) -> None:
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _press_focused(controls, _keydown(pygame.K_RETURN))


def test_render_overlay_title_colour_row_present_for_both_cards() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    _expand_overlay_card_title(controls, "closing_card")
    view = controls.build_view_state(paused=False)
    opening_text = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="opening_card")
    opening_colour = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="opening_card")
    opening_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT, card="opening_card")
    closing_text = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT, card="closing_card")
    closing_colour = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="closing_card")
    closing_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT, card="closing_card")
    assert opening_colour.card == "opening_card"
    assert closing_colour.card == "closing_card"
    _assert_card_order(
        view, "opening_card", opening_text.kind, opening_colour.kind, opening_font.kind
    )
    _assert_card_order(
        view, "closing_card", closing_text.kind, closing_colour.kind, closing_font.kind
    )


def test_render_overlay_title_colour_formats_hex() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_colour = (255, 0, 0)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="opening_card")
    assert _row_text(view, row) == "    └─ title colour: #ff0000"


def test_render_overlay_title_colour_enter_opens_single_line_modal() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_colour = (255, 255, 255)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.kind == ModalKind.TEXT
    assert modal.single_line is True
    assert modal.cta == "Change colour (#rgb or #rrggbb)..."
    assert modal.draft == "#ffffff"
    assert modal.editing is True


def test_render_overlay_title_colour_confirm_updates_session() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_colour = (255, 255, 255)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _replace_text_modal_draft(controls, "#ff0000")
    _confirm_text_modal(controls)
    assert controls.modal_host.view_state() is None
    assert controls.session.render_overlays.opening_card.title_colour == (255, 0, 0)


def test_render_overlay_title_colour_confirm_invalid_stays_open() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_colour = (255, 255, 255)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _replace_text_modal_draft(controls, "bad")
    _confirm_text_modal(controls)
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.kind == ModalKind.TEXT
    assert modal.error == "invalid hex colour (use #rgb or #rrggbb)"
    assert controls.session.render_overlays.opening_card.title_colour == (
        255,
        255,
        255,
    )


def test_render_overlay_title_colour_cancel_keeps_session() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "closing_card")
    controls.session.render_overlays.closing_card.title_colour = (255, 255, 255)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="closing_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _replace_text_modal_draft(controls, "#ff0000")
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    assert controls.modal_host.view_state() is None
    assert controls.session.render_overlays.closing_card.title_colour == (
        255,
        255,
        255,
    )


def test_render_overlay_title_colour_lock_blocks_enter() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    controls.session.render_overlays.locked = True
    _press_focused(controls, _keydown(pygame.K_RETURN))
    assert controls.modal_host.view_state() is None


def _expand_overlay_card_body(controls: TuningControls, card: str) -> None:
    overlays = controls.session.render_overlays


def test_render_overlay_body_text_row_present_for_both_cards() -> None:
    controls = _make_controls()
    _expand_overlay_card_body(controls, "opening_card")
    _expand_overlay_card_body(controls, "closing_card")
    view = controls.build_view_state(paused=False)
    opening = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="opening_card")
    closing = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="closing_card")
    opening_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_FONT, card="opening_card")
    closing_font = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_FONT, card="closing_card")
    assert opening.card == "opening_card"
    assert closing.card == "closing_card"
    _assert_card_order(view, "opening_card", opening.kind, opening_font.kind)
    _assert_card_order(view, "closing_card", closing.kind, closing_font.kind)


def test_render_overlay_body_text_formats_newlines_as_spaces() -> None:
    controls = _make_controls()
    _expand_overlay_card_body(controls, "opening_card")
    controls.session.render_overlays.opening_card.body_content = "Line one\nLine two"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="opening_card")
    assert _row_text(view, row) == "    └─ body text: Line one Line two"


def test_render_overlay_body_text_enter_opens_multiline_modal() -> None:
    controls = _make_controls()
    _expand_overlay_card_body(controls, "opening_card")
    controls.session.render_overlays.opening_card.body_content = "Opening body"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.kind == ModalKind.TEXT
    assert modal.single_line is False
    assert modal.cta == "Change text..."
    assert modal.draft == "Opening body"
    assert modal.editing is True


def test_render_overlay_body_text_confirm_updates_session() -> None:
    controls = _make_controls()
    _expand_overlay_card_body(controls, "opening_card")
    controls.session.render_overlays.opening_card.body_content = "Opening body"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    controls.modal_host.handle_text_input(" edited")
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _press_focused(controls, _keydown(pygame.K_RETURN))
    assert controls.modal_host.view_state() is None
    assert (
        controls.session.render_overlays.opening_card.body_content
        == "Opening body edited"
    )


def test_render_overlay_body_text_cancel_keeps_session() -> None:
    controls = _make_controls()
    _expand_overlay_card_body(controls, "closing_card")
    controls.session.render_overlays.closing_card.body_content = "Closing body"
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="closing_card")
    controls.focus_descriptor = _desc(view, row)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    controls.modal_host.handle_text_input(" edited")
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    assert controls.modal_host.view_state() is None
    assert controls.session.render_overlays.closing_card.body_content == (
        "Closing body"
    )


def test_render_overlay_body_text_lock_blocks_enter() -> None:
    controls = _make_controls()
    _expand_overlay_card_body(controls, "opening_card")
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_TEXT, card="opening_card")
    controls.focus_descriptor = _desc(view, row)
    controls.session.render_overlays.locked = True
    _press_focused(controls, _keydown(pygame.K_RETURN))
    assert controls.modal_host.view_state() is None


def _expand_overlay_card(controls: TuningControls, card: str) -> None:
    overlays = controls.session.render_overlays


def _focus_overlay_colour_row(
    controls: TuningControls, kind: RowKind, card: str
):
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(kind, card=card)
    controls.focus_descriptor = row
    return view, row


def _assert_overlay_colour_row_present_confirm_cancel(
    *,
    kind: RowKind,
    field: str,
    expand: str,
    after_kind: RowKind,
    before_kind: RowKind,
    label: str,
    nested: bool,
) -> None:
    controls = _make_controls()
    if expand == "title":
        _expand_overlay_card_title(controls, "opening_card")
        _expand_overlay_card_title(controls, "closing_card")
    elif expand == "body":
        _expand_overlay_card_body(controls, "opening_card")
        _expand_overlay_card_body(controls, "closing_card")
    else:
        _expand_overlay_card(controls, "opening_card")
        _expand_overlay_card(controls, "closing_card")
    opening_card = controls.session.render_overlays.opening_card
    closing_card = controls.session.render_overlays.closing_card
    setattr(opening_card, field, (255, 255, 255))
    setattr(closing_card, field, (255, 255, 255))
    view = controls.build_view_state(paused=False)
    opening_colour = RowDescriptor(kind, card="opening_card")
    closing_colour = RowDescriptor(kind, card="closing_card")
    assert opening_colour.card == "opening_card"
    assert closing_colour.card == "closing_card"
    _assert_card_order(view, "opening_card", after_kind, kind, before_kind)
    _assert_card_order(view, "closing_card", after_kind, kind, before_kind)
    prefix = "    └─ " if nested else "  └─ "
    assert _row_text(view, opening_colour) == f"{prefix}{label}: #ffffff"

    controls.focus_descriptor = _desc(view, opening_colour)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.kind == ModalKind.TEXT
    assert modal.single_line is True
    assert modal.cta == "Change colour (#rgb or #rrggbb)..."
    assert modal.draft == "#ffffff"
    _replace_text_modal_draft(controls, "#ff0000")
    _confirm_text_modal(controls)
    assert controls.modal_host.view_state() is None
    assert getattr(opening_card, field) == (255, 0, 0)

    view = controls.build_view_state(paused=False)
    closing_colour = RowDescriptor(kind, card="closing_card")
    controls.focus_descriptor = closing_colour
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _replace_text_modal_draft(controls, "#00ff00")
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    _press_focused(controls, _keydown(pygame.K_ESCAPE))
    assert controls.modal_host.view_state() is None
    assert getattr(closing_card, field) == (255, 255, 255)


def test_render_overlay_title_background_colour_row_present_and_confirm_cancel() -> None:
    _assert_overlay_colour_row_present_confirm_cancel(
        kind=RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
        field="title_background_colour",
        expand="title",
        after_kind=RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR,
        before_kind=RowKind.RENDER_OVERLAY_CARD_TITLE_FONT,
        label="title background",
        nested=True,
    )


def test_render_overlay_body_colour_row_present_and_confirm_cancel() -> None:
    _assert_overlay_colour_row_present_confirm_cancel(
        kind=RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR,
        field="body_colour",
        expand="body",
        after_kind=RowKind.RENDER_OVERLAY_CARD_BODY_TEXT,
        before_kind=RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
        label="body colour",
        nested=True,
    )


def test_render_overlay_body_background_colour_row_present_and_confirm_cancel() -> None:
    _assert_overlay_colour_row_present_confirm_cancel(
        kind=RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
        field="body_background_colour",
        expand="body",
        after_kind=RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR,
        before_kind=RowKind.RENDER_OVERLAY_CARD_BODY_FONT,
        label="body background",
        nested=True,
    )


def test_render_overlay_background_colour_row_present_and_confirm_cancel() -> None:
    _assert_overlay_colour_row_present_confirm_cancel(
        kind=RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR,
        field="background_colour",
        expand="card",
        after_kind=RowKind.RENDER_OVERLAY_CARD_OPACITY,
        before_kind=RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN,
        label="background colour",
        nested=False,
    )


def test_render_overlay_border_colour_row_present_and_confirm_cancel() -> None:
    _assert_overlay_colour_row_present_confirm_cancel(
        kind=RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR,
        field="border_colour",
        expand="card",
        after_kind=RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH,
        before_kind=RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER,
        label="border colour",
        nested=False,
    )


def test_render_overlay_optional_colour_formats_none() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    _expand_overlay_card_body(controls, "opening_card")
    controls.session.render_overlays.opening_card.title_background_colour = None
    controls.session.render_overlays.opening_card.body_background_colour = None
    view = controls.build_view_state(paused=False)
    title_bg = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR, card="opening_card")
    body_bg = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR, card="opening_card")
    assert _row_text(view, title_bg) == "    └─ title background: none"
    assert _row_text(view, body_bg) == "    └─ body background: none"
    controls.focus_descriptor = _desc(view, title_bg)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.draft == ""


def test_render_overlay_optional_colour_empty_confirm_clears() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    _expand_overlay_card_body(controls, "opening_card")
    opening = controls.session.render_overlays.opening_card
    opening.title_background_colour = (10, 20, 30)
    opening.body_background_colour = (40, 50, 60)
    for kind, field in (
        (
            RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
            "title_background_colour",
        ),
        (
            RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
            "body_background_colour",
        ),
    ):
        view, _row = _focus_overlay_colour_row(controls, kind, "opening_card")
        _press_focused(controls, _keydown(pygame.K_RETURN))
        modal = controls.modal_host.view_state()
        assert modal is not None
        assert modal.draft != ""
        _replace_text_modal_draft(controls, "")
        _confirm_text_modal(controls)
        assert controls.modal_host.view_state() is None
        assert getattr(opening, field) is None


def test_render_overlay_remaining_colour_rows_invalid_hex_stays_open() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    _expand_overlay_card_body(controls, "opening_card")
    opening = controls.session.render_overlays.opening_card
    opening.title_background_colour = (255, 255, 255)
    opening.body_colour = (255, 255, 255)
    opening.body_background_colour = (255, 255, 255)
    opening.background_colour = (255, 255, 255)
    opening.border_colour = (255, 255, 255)
    for kind, field in (
        (
            RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
            "title_background_colour",
        ),
        (RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR, "body_colour"),
        (
            RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
            "body_background_colour",
        ),
        (RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR, "background_colour"),
        (RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR, "border_colour"),
    ):
        _focus_overlay_colour_row(controls, kind, "opening_card")
        _press_focused(controls, _keydown(pygame.K_RETURN))
        _replace_text_modal_draft(controls, "bad")
        _confirm_text_modal(controls)
        modal = controls.modal_host.view_state()
        assert modal is not None
        assert modal.kind == ModalKind.TEXT
        assert modal.error == "invalid hex colour (use #rgb or #rrggbb)"
        assert getattr(opening, field) == (255, 255, 255)
        _press_focused(controls, _keydown(pygame.K_ESCAPE))
        _press_focused(controls, _keydown(pygame.K_ESCAPE))
        assert controls.modal_host.view_state() is None


def test_render_overlay_remaining_colour_rows_lock_blocks_enter() -> None:
    controls = _make_controls()
    _expand_overlay_card_title(controls, "opening_card")
    _expand_overlay_card_body(controls, "opening_card")
    for kind in (
        RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR,
    ):
        _focus_overlay_colour_row(controls, kind, "opening_card")
        controls.session.render_overlays.locked = True
        _press_focused(controls, _keydown(pygame.K_RETURN))
        assert controls.modal_host.view_state() is None
        controls.session.render_overlays.locked = False


def test_render_overlay_title_header_toggles_expansion() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    title_header = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER, card="opening_card")
    controls.focus_descriptor = _desc(view, title_header)
    _press_focused(controls, _keydown(pygame.K_RIGHT))

    _press_focused(controls, _keydown(pygame.K_LEFT))


def test_render_overlay_collapse_refocuses_from_title_font_row() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    font_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE, card="opening_card")
    font_desc = _desc(view, font_row)
    controls.focus_descriptor = font_desc
    assert controls.focus_descriptor == font_desc
    view = controls.build_view_state(paused=False)
    assert view.layout.resolve_navigable(controls.focus_descriptor, view) == font_desc


def test_render_overlay_title_collapse_refocuses_from_font_row() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    font_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE, card="opening_card")
    controls.focus_descriptor = font_row
    view = controls.build_view_state(paused=False)
    assert view.layout.resolve_navigable(controls.focus_descriptor, view) == font_row


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


def test_render_post_fx_fade_rows_step_window_edges() -> None:
    controls = _make_controls(("layer_1",))
    pp = controls.session.render_post_fx
    view = controls.build_view_state(paused=False)

    fade_in_start = RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN_START)
    controls.focus_descriptor = _desc(view, fade_in_start)
    fin = pp.fade.fade_in
    start = fin.start
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert fin.start == start + 1.0
    view = controls.build_view_state(paused=False)
    assert view.render_post_fx.fade.fade_in.start == fin.start

    fade_in_end = RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN_END)
    controls.focus_descriptor = _desc(view, fade_in_end)
    end = fin.end
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert fin.end == end + 1.0
    view = controls.build_view_state(paused=False)
    assert view.render_post_fx.fade.fade_in.end == fin.end

    fade_out_start = RowDescriptor(RowKind.RENDER_POST_FX_FADE_OUT_START)
    controls.focus_descriptor = _desc(view, fade_out_start)
    fout = pp.fade.fade_out
    fout_start = fout.start
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert fout.start == fout_start + 1.0
    view = controls.build_view_state(paused=False)
    assert view.render_post_fx.fade.fade_out.start == fout.start


def test_render_post_fx_fade_setters_clamp_and_cycle() -> None:
    controls = _make_controls(("layer_1",))
    fade = controls.session.render_post_fx.fade
    controls.render_post_fx.set_fade_end("fade_in", 12.0)
    assert fade.fade_in.end == 12.0
    controls.render_post_fx.set_fade_start("fade_in", 20.0)
    assert fade.fade_in.start == 20.0
    assert fade.fade_in.end == 20.0
    controls.render_post_fx.set_fade_start("fade_in", -3.0)
    assert fade.fade_in.start == 0.0
    assert fade.fade_in.end == 20.0

    controls.render_post_fx.set_fade_end("fade_out", 5.0)
    assert fade.fade_out.end == 5.0
    assert fade.fade_out.start == 5.0
    controls.render_post_fx.set_fade_start("fade_out", 1.0)
    assert fade.fade_out.start == 5.0

    assert fade.fade_in.type == "smoothstep"
    controls.render_post_fx.cycle_fade_type("fade_in", forward=True)
    assert fade.fade_in.type == "ease_out_cubic"
    controls.render_post_fx.cycle_fade_type("fade_in", forward=False)
    assert fade.fade_in.type == "smoothstep"


def test_render_post_fx_highlight_rolloff_mode_off_keeps_section_expanded() -> None:
    controls = _make_controls()
    controls.session.render_post_fx.highlight_rolloff.mode = "composite"

    controls.render_post_fx.cycle_highlight_rolloff_mode(forward=True)

    assert controls.session.render_post_fx.highlight_rolloff.mode == "off"


def test_render_timeline_header_after_post_fx() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    kinds = {row.kind for row in view.layout.rows}
    assert RowKind.RENDER_TIMELINE_HEADER not in kinds
    assert RowKind.RENDER_OVERLAYS_HEADER not in kinds
    assert RowKind.RENDER_POST_FX_HEADER not in kinds
    assert RowKind.RENDER_PATTERN_MASK_HEADER not in kinds


def _focus_timeline_presets(controls: TuningControls) -> None:
    _focus_inspector_kind(controls, RowKind.TIMELINE_PRESETS)


def _focus_timeline_snap_cues(controls: TuningControls) -> None:
    _focus_inspector_kind(controls, RowKind.TIMELINE_SNAP_CUES)


def _focus_timeline_snap_song_markers(controls: TuningControls) -> None:
    _focus_inspector_kind(controls, RowKind.TIMELINE_SNAP_TO_SONG_MARKERS)


def _focus_timeline_apply_soft_cuts(controls: TuningControls) -> None:
    controls.session.timeline.soft_cut_fades.enabled = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_APPLY_SOFT_CUTS)


def _focus_timeline_apply_hard_cuts(controls: TuningControls) -> None:
    controls.session.timeline.hard_cut_fades.enabled = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_APPLY_HARD_CUTS)


def _focus_timeline_remove_soft_cuts(controls: TuningControls) -> None:
    controls.session.timeline.soft_cut_fades.enabled = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_REMOVE_SOFT_CUTS)


def _focus_timeline_remove_hard_cuts(controls: TuningControls) -> None:
    controls.session.timeline.hard_cut_fades.enabled = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_REMOVE_HARD_CUTS)


def _focus_timeline_bar_phase(controls: TuningControls) -> None:
    _focus_inspector_kind(controls, RowKind.TIMELINE_BAR_PHASE)


def _focus_timeline_bar_grid(controls: TuningControls) -> None:
    _focus_inspector_kind(controls, RowKind.TIMELINE_BAR_GRID)


def _confirm_snap_song_markers(
    controls: TuningControls,
    *,
    proximity_label: str = "5.0s",
    scope_label: str = "All Layers",
) -> None:
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, proximity_label)
    _choose_modal_option(controls, scope_label)


def _focus_timeline_bar_phase(controls: TuningControls) -> None:
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_BAR_PHASE)
    view = controls.build_view_state(paused=False)
    phase_row = RowDescriptor(RowKind.TIMELINE_BAR_PHASE)


def _focus_timeline_bar_grid(controls: TuningControls) -> None:
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_BAR_GRID)
    view = controls.build_view_state(paused=False)
    grid_row = RowDescriptor(RowKind.TIMELINE_BAR_GRID)


def _choose_modal_option(controls: TuningControls, label: str) -> None:
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    target = modal_view.options.index(label)
    while controls.modal_host.view_state().focus_index != target:
        controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))


def test_timeline_presets_enter_opens_yes_cancel_modal() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3", "layer_4"))
    controls.session.timeline.timeline_preset_kind = "arc"
    controls.session.timeline.timeline_preset_conductor = True
    _focus_timeline_presets(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.YES_NO
    assert modal_view.options == ("Yes", "Cancel")
    assert modal_view.message == "Apply timeline preset?"
    assert modal_view.labeled_lines == (
        ModalLabeledLine("character", "arc"),
        ModalLabeledLine("density", "normal"),
        ModalLabeledLine("cue snap", "none"),
        ModalLabeledLine("song marker snap", "none"),
        ModalLabeledLine("timeline cuts", "by marker"),
        ModalLabeledLine("re-populate preset lists", "no"),
        ModalLabeledLine("conductor", "on"),
        ModalLabeledLine("mode", "layers"),
    )


def test_timeline_preset_cue_snap_row_cycles() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_PRESET_CUE_SNAP)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.TIMELINE_PRESET_CUE_SNAP)
    assert controls.session.timeline.timeline_preset_cue_snap == "none"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.timeline_preset_cue_snap == "beats"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.timeline_preset_cue_snap == "bars"
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.session.timeline.timeline_preset_cue_snap == "beats"
    view = controls.build_view_state(paused=False)
    assert "beats" in _row_text(view, row)


def test_timeline_preset_song_marker_snap_row_cycles() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP)
    assert controls.session.timeline.timeline_preset_song_marker_snap is None
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.timeline_preset_song_marker_snap == 0.5
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.timeline_preset_song_marker_snap == 1.0
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.session.timeline.timeline_preset_song_marker_snap == 0.5
    view = controls.build_view_state(paused=False)
    assert "0.5s" in _row_text(view, row)


def test_timeline_preset_timeline_cuts_row_cycles() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_PRESET_TIMELINE_CUTS)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.TIMELINE_PRESET_TIMELINE_CUTS)
    assert controls.session.timeline.timeline_preset_timeline_cuts == "by marker"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.timeline_preset_timeline_cuts == "all soft"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.timeline_preset_timeline_cuts == "all hard"
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.session.timeline.timeline_preset_timeline_cuts == "all soft"
    view = controls.build_view_state(paused=False)
    assert "all soft" in _row_text(view, row)


def test_timeline_preset_repopulate_row_cycles() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_PRESET_REPOPULATE)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.TIMELINE_PRESET_REPOPULATE)
    assert controls.session.timeline.timeline_preset_repopulate == "no"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.timeline_preset_repopulate == "cue roles"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert (
        controls.session.timeline.timeline_preset_repopulate
        == "directory random"
    )
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.session.timeline.timeline_preset_repopulate == "cue roles"
    view = controls.build_view_state(paused=False)
    assert "cue roles" in _row_text(view, row)


def test_timeline_presets_cuts_none_keeps_cut_none() -> None:
    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=beats,
        bar_times=bars,
    )
    controls.session.timeline.timeline_preset_kind = "breathing"
    controls.session.timeline.timeline_preset_timeline_cuts = "none"
    _focus_timeline_presets(controls)
    _confirm_timeline_preset(controls)
    assert not controls.modal_host.active
    for lane in controls.session.timeline.lanes.values():
        assert all(cue.cut == "none" for cue in lane.cues)


def test_timeline_presets_by_marker_cuts_assign_soft_or_hard() -> None:
    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    controls = _make_controls(
        ("layer_1", "layer_2", "layer_3", "layer_4"),
        beat_times=beats,
        bar_times=bars,
        duration_sec=240.0,
    )
    controls.session.song_markers.times = [30.0, 90.0, 150.0]
    controls.session.timeline.timeline_preset_kind = "breathing"
    controls.session.timeline.timeline_preset_timeline_cuts = "by marker"
    _focus_timeline_presets(controls)
    _confirm_timeline_preset(controls)
    assert not controls.modal_host.active
    cuts = {
        cue.cut
        for lane in controls.session.timeline.lanes.values()
        for cue in lane.cues
    }
    assert cuts
    assert cuts <= {"soft", "hard"}
    assert "soft" in cuts


def _as_level(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def _lane(
    baseline,
    *transitions,
) -> TimelineLane:
    base = _as_level(baseline)
    cues = [SlotCue(t=t, level=float(_as_level(level))) for t, level in transitions]
    return TimelineLane(baseline=base, cues=canonicalize(base, cues))


def _confirm_timeline_preset(controls: TuningControls) -> None:
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Yes")


def test_timeline_presets_breathing_clears_and_applies() -> None:
    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    controls = _make_controls(
        ("layer_1", "layer_2", "layer_3", "layer_4"),
        beat_times=beats,
        bar_times=bars,
    )
    prior = {
        "layer_1": _lane(True, (1.0, False)),
        "layer_2": _lane(True, (2.0, True)),
    }
    controls.session.timeline.lanes = dict(prior)
    controls.session.timeline.enabled = False
    controls.session.timeline.recording = True
    controls.session.timeline.armed_slots.add("layer_1")
    controls.session.timeline.timeline_preset_kind = "breathing"
    _focus_timeline_presets(controls)
    _confirm_timeline_preset(controls)
    assert not controls.modal_host.active
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.recording is False
    assert not controls.session.timeline.armed_slots
    lanes = controls.session.timeline.lanes
    assert lanes
    assert lanes != prior
    assert set(lanes) == set(controls.session.layer_z_order)
    assert all(lane.baseline is not None for lane in lanes.values())
    assert any(
        lane_level_at(lane, 0.0, inherit=0.0) > 0.0 for lane in lanes.values()
    )


def test_timeline_presets_arc_clears_and_applies() -> None:
    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=beats,
        bar_times=bars,
    )
    controls.session.timeline.lanes = {"layer_1": _lane(True, (5.0, False))}
    controls.session.timeline.enabled = False
    controls.session.timeline.timeline_preset_kind = "arc"
    _focus_timeline_presets(controls)
    _confirm_timeline_preset(controls)
    assert not controls.modal_host.active
    assert controls.session.timeline.enabled is True
    lanes = controls.session.timeline.lanes
    assert lanes
    assert set(lanes) == {"layer_1", "layer_2"}
    assert all(lane.baseline is not None for lane in lanes.values())


def test_timeline_presets_crescendo_when_typed_marker() -> None:
    from cleave.song_markers import SongMarker

    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    controls = _make_controls(
        ("layer_1", "layer_2", "layer_3", "layer_4"),
        beat_times=beats,
        bar_times=bars,
        duration_sec=240.0,
    )
    controls.session.song_markers.markers = [
        SongMarker(30.0),
        SongMarker(90.0),
        SongMarker(150.0),
        SongMarker(200.0, "crescendo"),
    ]
    controls.session.timeline.timeline_preset_kind = "breathing"
    _focus_timeline_presets(controls)
    _confirm_timeline_preset(controls)
    assert not controls.modal_host.active
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Applied Breathing timeline preset (crescendo)"


def test_timeline_presets_skips_crescendo_without_typed_marker() -> None:
    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=beats,
        bar_times=bars,
        duration_sec=240.0,
    )
    controls.session.song_markers.times = [30.0, 90.0, 150.0, 200.0]
    controls.session.timeline.timeline_preset_kind = "pulse"
    _focus_timeline_presets(controls)
    _confirm_timeline_preset(controls)
    assert not controls.modal_host.active
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Applied Pulse timeline preset"


def _focus_timeline_reset(controls: TuningControls) -> None:
    _focus_inspector_kind(controls, RowKind.TIMELINE_RESET)


def test_timeline_reset_enter_opens_choice_modal() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    _focus_timeline_reset(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.CHOICE
    assert modal_view.options == ("All Off", "All On", "Cancel")
    assert "reset" in modal_view.message.lower()


def test_timeline_reset_all_off() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))
    controls.session.timeline.lanes = {
        "layer_1": _lane(True, (1.0, False)),
        "layer_2": _lane(False, (2.0, True)),
    }
    controls.session.timeline.enabled = False
    controls.session.timeline.recording = True
    controls.session.timeline.armed_slots.add("layer_1")
    _focus_timeline_reset(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "All Off")
    assert not controls.modal_host.active
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.recording is False
    assert not controls.session.timeline.armed_slots
    lanes = controls.session.timeline.lanes
    assert set(lanes) == {"layer_1", "layer_2", "layer_3"}
    assert all(lane.baseline == 0.0 and lane.cues == [] for lane in lanes.values())
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Reset timeline: all layers off"


def test_timeline_reset_all_on() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.timeline.lanes = {
        "layer_1": _lane(False, (3.0, True)),
    }
    controls.session.timeline.enabled = False
    _focus_timeline_reset(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "All On")
    assert not controls.modal_host.active
    assert controls.session.timeline.enabled is True
    lanes = controls.session.timeline.lanes
    assert set(lanes) == {"layer_1", "layer_2"}
    assert all(lane.baseline == 1.0 and lane.cues == [] for lane in lanes.values())
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Reset timeline: all layers on"


def test_timeline_presets_refuse_without_bars() -> None:
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=(0.0, 1.0),
        bar_times=(),
    )
    prior = {
        "layer_1": _lane(True, (3.0, True)),
        "layer_2": _lane(True, (3.0, False)),
    }
    controls.session.timeline.lanes = dict(prior)
    controls.session.timeline.timeline_preset_kind = "breathing"
    _focus_timeline_presets(controls)
    _confirm_timeline_preset(controls)
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes == prior
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No bars available; re-run separate"


def test_timeline_presets_conductor_passes_signals_to_builder() -> None:
    from cleave.signals import Signals
    import numpy as np

    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    n = 100
    ones = np.ones(n, dtype=np.float64)
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=1.0,
        path=Path("."),
        stems={
            "drums": {"onset_strength": ones},
            "bass": {"rms": ones, "sub_bass": ones, "mid_bass": ones},
            "vocals": {"rms": ones, "pitch_hz": ones},
            "other": {"spectral_centroid": ones, "rms": ones},
            "full_mix": {"onset_strength": ones, "rms": ones},
        },
    )
    controls = _make_controls(
        ("layer_1", "layer_2", "layer_3", "layer_4"),
        beat_times=beats,
        bar_times=bars,
        signals=signals,
    )
    controls.session.timeline.timeline_preset_kind = "breathing"
    controls.session.timeline.timeline_preset_conductor = True
    captured: dict = {}

    def _fake_builder(slots, duration_sec, rng, **kwargs):
        captured["kwargs"] = kwargs
        return {slot: TimelineLane(baseline=1.0, cues=[]) for slot in slots}

    with patch.dict(
        "cleave.viz.timeline_preset_controls._KIND_BUILDERS",
        {"breathing": (_fake_builder, "Applied Breathing timeline preset")},
    ):
        _focus_timeline_presets(controls)
        _confirm_timeline_preset(controls)
    assert captured["kwargs"]["signals"] is signals
    assert captured["kwargs"]["slot_stems"] == {
        "layer_1": "drums",
        "layer_2": "bass",
        "layer_3": "vocals",
        "layer_4": "other",
    }
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Applied Breathing timeline preset"




def test_timeline_presets_conductor_skips_without_signals() -> None:
    beats = tuple(float(i) for i in range(241))
    bars = tuple(float(i) for i in range(0, 241, 4))
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=beats,
        bar_times=bars,
        signals=None,
    )
    controls.session.timeline.timeline_preset_kind = "breathing"
    controls.session.timeline.timeline_preset_conductor = True
    captured: dict = {}

    def _fake_builder(slots, duration_sec, rng, **kwargs):
        captured["kwargs"] = kwargs
        return {slot: TimelineLane(baseline=1.0, cues=[]) for slot in slots}

    with patch.dict(
        "cleave.viz.timeline_preset_controls._KIND_BUILDERS",
        {"breathing": (_fake_builder, "Applied Breathing timeline preset")},
    ):
        _focus_timeline_presets(controls)
        _confirm_timeline_preset(controls)
    assert "signals" not in captured["kwargs"]
    assert "slot_stems" not in captured["kwargs"]
    assert controls.session.timeline.enabled is True
    assert set(controls.session.timeline.lanes) == {"layer_1", "layer_2"}
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No signals; conductor skipped"


def test_timeline_presets_cancel_and_escape_leave_unchanged() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    prior = {
        "layer_1": _lane(True, (3.0, True)),
        "layer_2": _lane(True, (3.0, False)),
    }
    controls.session.timeline.lanes = dict(prior)
    controls.session.timeline.enabled = False

    _focus_timeline_presets(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Cancel")
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes == prior
    assert controls.session.timeline.enabled is False

    _focus_timeline_presets(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes == prior
    assert controls.session.timeline.enabled is False


def test_timeline_snap_cues_enter_opens_beats_or_bars_modal() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0, 2.0),
        bar_times=(0.0, 4.0),
    )
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (0.4, True)),
    }
    _focus_timeline_snap_cues(controls)
    view = controls.build_view_state(paused=False)
    snap_row = RowDescriptor(RowKind.TIMELINE_SNAP_CUES)
    assert "Snap Cues" in _row_text(view, snap_row)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.CHOICE
    assert modal_view.options == ("Beats", "Bars", "Cancel")
    assert modal_view.message == "Snap timeline cues to?"


def test_timeline_snap_beats_mutates_cues() -> None:
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=(0.0, 1.0, 2.0),
    )
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (0.4, True)),
        "layer_2": _lane(None, (1.6, False)),
    }
    _focus_timeline_snap_cues(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Beats")
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=1.0),
    ]
    assert controls.session.timeline.lanes["layer_2"].cues == [
        SlotCue(t=2.0, level=0.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Snapped timeline cues to beats"


def test_timeline_snap_bars_mutates_cues() -> None:
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=(0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0),
        bar_times=(0.0, 4.0),
    )
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (0.4, True)),
        "layer_2": _lane(None, (3.6, False)),
    }
    _focus_timeline_snap_cues(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Bars")
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=1.0),
    ]
    assert controls.session.timeline.lanes["layer_2"].cues == [
        SlotCue(t=4.0, level=0.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Snapped timeline cues to bars"


def test_timeline_snap_beats_recording_blocks() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0),
    )
    prior = {"layer_1": _lane(None, (0.4, True))}
    controls.session.timeline.lanes = dict(prior)
    controls.session.timeline.recording = True
    _focus_timeline_snap_cues(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes == prior
    view = controls.build_view_state(paused=False)
    assert view.notification_message is None


def test_timeline_snap_beats_no_cues_notifies() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0),
    )
    controls.session.timeline.lanes = {}
    _focus_timeline_snap_cues(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    assert not controls.modal_host.active
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No timeline cues to snap"


def test_timeline_bar_phase_right_nudges_cues_and_offset() -> None:
    controls = _make_controls(
        ("layer_1", "layer_2"),
        beat_times=(0.0, 1.0, 2.0, 3.0, 4.0, 5.0),
        bar_times=(0.0, 4.0),
    )
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (0.0, True)),
        "layer_2": _lane(None, (4.0, False)),
    }
    assert controls.session.timeline.bar_phase_offset == 0
    _focus_timeline_bar_phase(controls)
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.bar_phase_offset == 1
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=1.0, level=1.0),
    ]
    assert controls.session.timeline.lanes["layer_2"].cues == [
        SlotCue(t=5.0, level=0.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Bar phase +1"
    phase_row = RowDescriptor(RowKind.TIMELINE_BAR_PHASE)
    assert "+1" in _row_text(view, phase_row)


def test_timeline_bar_grid_right_shows_left_hides() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.session.timeline.show_bar_grid is False
    _focus_timeline_bar_grid(controls)
    view = controls.build_view_state(paused=False)
    grid_row = RowDescriptor(RowKind.TIMELINE_BAR_GRID)
    assert "hide" in _row_text(view, grid_row)

    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.show_bar_grid is True
    view = controls.build_view_state(paused=False)
    grid_row = RowDescriptor(RowKind.TIMELINE_BAR_GRID)
    assert "show" in _row_text(view, grid_row)

    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.session.timeline.show_bar_grid is False
    view = controls.build_view_state(paused=False)
    grid_row = RowDescriptor(RowKind.TIMELINE_BAR_GRID)
    assert "hide" in _row_text(view, grid_row)


def test_timeline_bar_phase_left_wraps_offset() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0, 2.0, 3.0),
        bar_times=(0.0,),
    )
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (1.0, True)),
    }
    _focus_timeline_bar_phase(controls)
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.session.timeline.bar_phase_offset == 3
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=1.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Bar phase +3"


def test_timeline_bar_phase_recording_blocks() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0),
    )
    prior = {"layer_1": _lane(None, (0.0, True))}
    controls.session.timeline.lanes = dict(prior)
    controls.session.timeline.recording = True
    _focus_timeline_bar_phase(controls)
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.lanes == prior
    assert controls.session.timeline.bar_phase_offset == 0


def test_timeline_snap_bars_no_bars_notifies() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0),
        bar_times=(),
    )
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (0.4, True)),
    }
    _focus_timeline_snap_cues(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    _choose_modal_option(controls, "Bars")
    assert not controls.modal_host.active
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No bars available; re-run separate"


def test_timeline_snap_beats_no_beats_notifies() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(),
        bar_times=(0.0, 4.0),
    )
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (0.4, True)),
    }
    _focus_timeline_snap_cues(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    _choose_modal_option(controls, "Beats")
    assert not controls.modal_host.active
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No beats available; re-run separate"


def test_timeline_snap_song_markers_enter_opens_proximity_then_scope_modals() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.song_markers.times = [10.0, 40.0]
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (9.0, True)),
    }
    _focus_timeline_snap_song_markers(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.CHOICE
    assert modal_view.message == "Proximity of cues to pull onto song markers..."
    assert "5.0s" in modal_view.options
    assert modal_view.options[-1] == "Cancel"
    assert modal_view.options[modal_view.focus_index] == "5.0s"

    _choose_modal_option(controls, "5.0s")
    scope_view = controls.modal_host.view_state()
    assert scope_view is not None
    assert scope_view.kind == ModalKind.CHOICE
    assert scope_view.message == "Layer scope?"
    assert "All Layers" in scope_view.options
    assert "Closest Wins" in scope_view.options
    assert "Layer 1" in scope_view.options
    assert scope_view.options[-1] == "Cancel"
    assert scope_view.options[scope_view.focus_index] == "All Layers"


def test_timeline_snap_song_markers_layer_mutates_only_that_lane() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.song_markers.times = [5.0]
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (4.0, True)),
        "layer_2": _lane(None, (4.2, False)),
    }
    _focus_timeline_snap_song_markers(controls)
    _confirm_snap_song_markers(controls, scope_label="Layer 1")
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=5.0, level=1.0),
    ]
    assert controls.session.timeline.lanes["layer_2"].cues == [
        SlotCue(t=4.2, level=0.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Snapped 1 cue to song markers"


def test_timeline_snap_song_markers_each_layer_vs_closest_wins() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.song_markers.times = [5.0]
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (4.5, True)),
        "layer_2": _lane(None, (4.8, False)),
    }
    _focus_timeline_snap_song_markers(controls)
    _confirm_snap_song_markers(controls, scope_label="All Layers")
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=5.0, level=1.0),
    ]
    assert controls.session.timeline.lanes["layer_2"].cues == [
        SlotCue(t=5.0, level=0.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Snapped 2 cues to song markers"

    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (4.5, True)),
        "layer_2": _lane(None, (4.8, False)),
    }
    _focus_timeline_snap_song_markers(controls)
    _confirm_snap_song_markers(controls, scope_label="Closest Wins")
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=4.5, level=1.0),
    ]
    assert controls.session.timeline.lanes["layer_2"].cues == [
        SlotCue(t=5.0, level=0.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Snapped 1 cue to song markers"


def test_timeline_snap_song_markers_recording_blocks() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = [5.0]
    prior = {"layer_1": _lane(None, (4.0, True))}
    controls.session.timeline.lanes = dict(prior)
    controls.session.timeline.recording = True
    _focus_timeline_snap_song_markers(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes == prior
    view = controls.build_view_state(paused=False)
    assert view.notification_message is None


def test_timeline_snap_song_markers_no_markers_notifies() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = []
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (4.0, True)),
    }
    _focus_timeline_snap_song_markers(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    assert not controls.modal_host.active
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No song markers to snap to"


def test_timeline_snap_song_markers_no_cues_notifies() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = [5.0]
    controls.session.timeline.lanes = {}
    _focus_timeline_snap_song_markers(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    assert not controls.modal_host.active
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No timeline cues to snap"


def test_timeline_snap_song_markers_is_plain_action_row() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    snap_row = RowDescriptor(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS)
    text = _row_text(view, snap_row)
    assert "Snap Cues" in text
    assert "▶" not in text
    assert "▼" not in text
    _focus_inspector_kind(controls, RowKind.TIMELINE_SNAP_TO_SONG_MARKERS)
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    view_after = controls.build_view_state(paused=False)
    assert view_after.layout.rows == view.layout.rows


def test_timeline_snap_song_markers_uses_proximity() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = [5.0]
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (3.0, True)),
    }
    _focus_timeline_snap_song_markers(controls)
    _confirm_snap_song_markers(controls, proximity_label="1.0s")
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=3.0, level=1.0),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "No cues within snap proximity"


def test_timeline_apply_soft_cuts_enter_opens_scope_modal() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (4.0, True), (10.0, False)),
    }
    _focus_timeline_apply_soft_cuts(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.CHOICE
    assert modal_view.message == "Apply soft cuts to cues?"
    assert modal_view.options == (
        "All Cues",
        "All Cues Except Song Marker Cues",
        "Song Marker Cues Only",
        "Cancel",
    )


def test_timeline_apply_hard_cuts_markers_only() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = [10.0]
    controls.session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=None,
            cues=[
                SlotCue(t=4.0, level=1.0, cut="soft"),
                SlotCue(t=10.0, level=0.0, cut="soft"),
            ],
        ),
    }
    _focus_timeline_apply_hard_cuts(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Song Marker Cues Only")
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=4.0, level=1.0, cut="soft"),
        SlotCue(t=10.0, level=0.0, cut="hard"),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Applied hard cuts to 1 cue"


def test_timeline_apply_hard_cuts_all_updates_on_and_off() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=None,
            cues=[
                SlotCue(t=4.0, level=1.0, cut="soft"),
                SlotCue(t=10.0, level=0.0, cut="soft"),
            ],
        ),
    }
    _focus_timeline_apply_hard_cuts(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "All Cues")
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=4.0, level=1.0, cut="hard"),
        SlotCue(t=10.0, level=0.0, cut="hard"),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Applied hard cuts to 2 cues"


def test_timeline_apply_soft_cuts_except_markers() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = [10.0]
    controls.session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=None,
            cues=[
                SlotCue(t=4.0, level=1.0),
                SlotCue(t=10.0, level=0.0),
            ],
        ),
    }
    _focus_timeline_apply_soft_cuts(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "All Cues Except Song Marker Cues")
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=4.0, level=1.0, cut="soft"),
        SlotCue(t=10.0, level=0.0),
    ]


def test_timeline_remove_cuts_enter_opens_scope_modal() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.lanes = {
        "layer_1": _lane(None, (4.0, True), (10.0, False)),
    }
    _focus_timeline_remove_soft_cuts(controls)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.CHOICE
    assert modal_view.message == "Remove cuts from cues?"
    assert modal_view.options == (
        "All Cues",
        "All Cues Except Song Marker Cues",
        "Song Marker Cues Only",
        "Cancel",
    )


def test_timeline_remove_hard_cuts_markers_only() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = [10.0]
    controls.session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=None,
            cues=[
                SlotCue(t=4.0, level=1.0, cut="hard"),
                SlotCue(t=10.0, level=0.0, cut="soft"),
            ],
        ),
    }
    _focus_timeline_remove_hard_cuts(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Song Marker Cues Only")
    assert not controls.modal_host.active
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=4.0, level=1.0, cut="hard"),
        SlotCue(t=10.0, level=0.0, cut="none"),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Removed cuts from 1 cue"


def test_timeline_remove_soft_cuts_all_clears_on_and_off() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=None,
            cues=[
                SlotCue(t=4.0, level=1.0, cut="hard"),
                SlotCue(t=10.0, level=0.0, cut="soft"),
            ],
        ),
    }
    _focus_timeline_remove_soft_cuts(controls)
    _press_focused(controls, _keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "All Cues")
    assert controls.session.timeline.lanes["layer_1"].cues == [
        SlotCue(t=4.0, level=1.0, cut="none"),
        SlotCue(t=10.0, level=0.0, cut="none"),
    ]
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Removed cuts from 2 cues"


def test_render_timeline_header_is_not_a_layout_row() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    assert RowKind.RENDER_TIMELINE_HEADER not in {row.kind for row in view.layout.rows}
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    assert RowKind.RENDER_TIMELINE_HEADER not in {row.kind for row in view.layout.rows}


def test_render_timeline_e_toggles_enabled() -> None:
    controls = _make_controls(timeline_enabled=True)
    assert controls.session.timeline.enabled is True
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert controls.session.timeline.enabled is False
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.panel_open is True
    assert not isinstance(controls.focus_cursor, TimelineFocus)


def test_timeline_enabled_startup_shows_notification() -> None:
    with patch.object(time, "monotonic", return_value=1000.0):
        controls = _make_controls(timeline_enabled=True)
        view = controls.build_view_state(paused=False)
    assert view.notification_message == NOTIFICATION_TIMELINE_ENABLED_TEXT
    assert view.notification_remaining_sec == pytest.approx(
        DEFAULT_NOTIFICATION_DISPLAY_SEC, abs=0.01
    )
    assert RowKind.PANEL_NOTIFICATION in [row.kind for row in view.layout.rows]


def test_render_timeline_toggle_shows_notification() -> None:
    with patch.object(time, "monotonic", return_value=1000.0):
        controls = _make_controls(timeline_enabled=True)
        assert _press_timeline_hotkey(controls, pygame.K_e) is True
        view = controls.build_view_state(paused=False)
        assert view.notification_message == NOTIFICATION_TIMELINE_DISABLED_TEXT
        assert _press_timeline_hotkey(controls, pygame.K_e) is True
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
        return_value=5000.0 + DEFAULT_NOTIFICATION_DISPLAY_SEC + 0.1,
    ):
        controls.tick(0.0)
        view = controls.build_view_state(paused=False)
        assert view.notification_message is None
        assert view.notification_remaining_sec == 0.0


def test_panel_notification_until_dismissed_stays_until_enter() -> None:
    controls = _make_controls(("layer_1",))
    for _ in range(DEFAULT_NOTIFICATION_DISPLAY_SEC):
        controls.settings.adjust_notification_display_sec(forward=False, large=False)
    assert controls.cfg.editor.notification_display_sec == 0

    with patch.object(time, "monotonic", return_value=8000.0):
        controls.show_notification("Saved")
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"

    with patch.object(time, "monotonic", return_value=8000.0 + 10_000.0):
        controls.tick(0.0)
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"
        toast = RowDescriptor(RowKind.PANEL_NOTIFICATION, marker_index=1)
        assert toast in view.layout.rows
        assert toast not in view.layout.navigable_descriptors(view)
        assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"


def test_panel_notification_expires_after_adjusted_duration(tmp_path: Path) -> None:
    controls = _make_controls(("layer_1",))
    controls.cfg.user_config_path = tmp_path / "config.yaml"
    for _ in range(DEFAULT_NOTIFICATION_DISPLAY_SEC - 1):
        controls.settings.adjust_notification_display_sec(forward=False, large=False)
    assert controls.cfg.editor.notification_display_sec == 1

    with patch.object(time, "monotonic", return_value=200.0):
        controls.show_notification("Saved")
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"

    with patch.object(time, "monotonic", return_value=200.5):
        controls.tick(0.0)
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"

    with patch.object(time, "monotonic", return_value=201.1):
        controls.tick(0.0)
        view = controls.build_view_state(paused=False)
        assert view.notification_message is None
        assert view.notification_remaining_sec == 0.0


def test_panel_notification_retargets_when_display_sec_changes(tmp_path: Path) -> None:
    controls = _make_controls(("layer_1",))
    controls.cfg.user_config_path = tmp_path / "config.yaml"
    for _ in range(DEFAULT_NOTIFICATION_DISPLAY_SEC):
        controls.settings.adjust_notification_display_sec(forward=False, large=False)
    assert controls.cfg.editor.notification_display_sec == 0

    with patch.object(time, "monotonic", return_value=100.0):
        controls.show_notification("Saved")
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"

    with patch.object(time, "monotonic", return_value=110.0):
        controls.tick(0.0)
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"
        controls.settings.adjust_notification_display_sec(forward=True, large=False)
        assert controls.cfg.editor.notification_display_sec == 1
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"
        assert view.notification_remaining_sec == pytest.approx(1.0)

    with patch.object(time, "monotonic", return_value=111.1):
        controls.tick(0.0)
        view = controls.build_view_state(paused=False)
        assert view.notification_message is None


def test_panel_notification_enter_dismisses_before_timeout() -> None:
    with patch.object(time, "monotonic", return_value=9000.0):
        controls = _make_controls(("layer_1",))
        controls.show_notification("Saved")
        view = controls.build_view_state(paused=False)
        toast = RowDescriptor(RowKind.PANEL_NOTIFICATION, marker_index=1)
        assert toast in view.layout.rows
        assert toast not in view.layout.navigable_descriptors(view)
        assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"


def test_panel_notification_enter_dismisses_without_focusing_toast() -> None:
    with patch.object(time, "monotonic", return_value=9000.0):
        controls = _make_controls(("layer_1",))
        controls.focus_descriptor = RowDescriptor(RowKind.RENDER_SECTION_GAP)
        controls.show_notification("Saved")
        assert controls.playback.paused is False
        before = controls.focus_cursor
        assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"
        assert controls.playback.paused is False
        assert controls.focus_cursor == before

    with patch.object(time, "monotonic", return_value=9100.0):
        controls = _make_controls(("layer_1",))
        _expand_settings_ui(controls)
        controls.focus_descriptor = RowDescriptor(
            RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY
        )
        controls.show_notification("Saved")
        before = controls.focus_cursor
        assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
        view = controls.build_view_state(paused=False)
        assert view.notification_message == "Saved"
        assert controls.focus_cursor == before


def test_render_timeline_enable_opens_panel() -> None:
    controls = _make_controls()
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is False
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.panel_open is True
    assert not isinstance(controls.focus_cursor, TimelineFocus)


def test_render_timeline_right_does_not_open_the_strip() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.shell_focus.selected_id = "render.timeline"
    controls.session.timeline.focus_row = 2
    controls.navigator.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.timeline.panel_open is False
    assert controls.session.timeline.focus_row == 2


def test_render_timeline_disable_closes_panel() -> None:
    controls = _make_controls()
    controls.session.timeline.enabled = True
    controls.session.timeline.panel_open = True
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is False


def test_render_timeline_header_eye_color_when_disabled() -> None:
    controls = _make_controls(timeline_enabled=True)
    view = controls.build_view_state(paused=False)
    header = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    assert _row_value_color(view, header) == VALUE
    controls.session.timeline.enabled = False
    view = controls.build_view_state(paused=False)
    assert _row_value_color(view, header) == DISABLED


def test_render_timeline_sub_rows_dim_when_disabled() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    controls.session.timeline.hard_cut_fades.enabled = True
    controls.session.timeline.soft_cut_fades.enabled = True
    controls.session.timeline.enabled = False
    view = controls.build_view_state(paused=False)
    for kind in (
        RowKind.RENDER_TIMELINE_HEADER,
        RowKind.SONG_MARKERS_HEADER,
        RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
        RowKind.TIMELINE_BAR_PHASE,
        RowKind.TIMELINE_BAR_GRID,
        RowKind.TIMELINE_PLACEMENT_SNAP,
        RowKind.TIMELINE_SNAP_CUES,
        RowKind.TIMELINE_SNAP_TO_SONG_MARKERS,
        RowKind.TIMELINE_CUTS_HEADER,
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
        RowKind.TIMELINE_APPLY_SOFT_CUTS,
        RowKind.TIMELINE_APPLY_HARD_CUTS,
        RowKind.TIMELINE_REMOVE_SOFT_CUTS,
        RowKind.TIMELINE_REMOVE_HARD_CUTS,
        RowKind.TIMELINE_PRESETS_HEADER,
        RowKind.TIMELINE_PRESET_CHARACTER,
        RowKind.TIMELINE_PRESET_DENSITY,
        RowKind.TIMELINE_PRESET_CUE_SNAP,
        RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP,
        RowKind.TIMELINE_PRESET_TIMELINE_CUTS,
        RowKind.TIMELINE_PRESET_REPOPULATE,
        RowKind.TIMELINE_PRESET_CONDUCTOR,
        RowKind.TIMELINE_PRESET_MODE,
        RowKind.TIMELINE_PRESETS,
        RowKind.TIMELINE_RESET,
    ):
        assert _row_value_color(view, RowDescriptor(kind)) == DISABLED, kind


def test_render_timeline_enabled_change_callback() -> None:
    controls = _make_controls(timeline_enabled=True)
    events: list[bool] = []
    controls._layer_bindings = noop_layer_bindings(
        on_timeline_enabled_change=lambda: events.append(
            controls.session.timeline.enabled
        )
    )
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert events == [False]
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert events == [False, True]


def test_track_header_visible_follows_timeline_at_position() -> None:
    controls = _make_controls(("layer_1", "layer_2"), timeline_enabled=True)
    controls.session.timeline.lanes = {
        "layer_1": _lane(True, (5.0, False)),
    }
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
    assert view.tracks["layer_1"].runtime.enabled is False


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
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert events == [False]
    assert _press_timeline_hotkey(controls, pygame.K_e) is True
    assert events == [False, True]


def test_t_opens_timeline_panel_when_enabled() -> None:
    controls = _make_controls()
    controls.session.timeline.enabled = True
    controls.session.timeline.focus_row = 2
    assert controls.session.timeline.panel_open is False

    command_by_id("timeline.show_strip").run(controls)
    assert controls.session.timeline.panel_open is True
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.session.timeline.focus_row == 0


def test_t_closes_timeline_panel_without_moving_a_main_cursor() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    command_by_id("timeline.show_strip").run(controls)
    assert controls.session.timeline.panel_open is False
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_descriptor.kind == RowKind.RENDER_OVERLAYS_HEADER


def test_t_from_submenu_closes_and_leaves_the_strip_cursor() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(0)
    command_by_id("timeline.show_strip").run(controls)
    assert controls.session.timeline.panel_open is False
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR


def test_t_opens_timeline_panel_when_disabled() -> None:
    controls = _make_controls()
    controls.session.timeline.enabled = False
    controls.session.timeline.focus_row = 2
    assert controls.session.timeline.panel_open is False

    command_by_id("timeline.show_strip").run(controls)
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is True
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.session.timeline.focus_row == 0


def test_t_ignored_during_move_mode() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.enabled = True
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(_MOVE_MODE_KEY))
    assert controls.layer_lifecycle.move_mode_slot == "layer_1"

    _press_focused(controls, _keydown(pygame.K_t))
    assert controls.session.timeline.panel_open is False



def test_space_toggles_pause_from_any_focus() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.playback.paused is False
    assert controls.focus_descriptor == RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)

    _press_focused(controls, _keydown(pygame.K_SPACE))
    assert controls.playback.paused is True

    _press_focused(controls, _keydown(pygame.K_SPACE))
    assert controls.playback.paused is False









def test_timeline_focus_change_clears_selected_cue_flash() -> None:
    controls = _make_controls(("layer_1", "layer_2"), timeline_enabled=True)
    controls.session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(0)
    controls.session.timeline.selected_cue_t = {"layer_1": 10.0, "layer_2": 20.0}
    controls.session.timeline.selected_cue_flash_start_ms = 1234

    controls.focus_cursor = TimelineFocus(1)
    assert controls.session.timeline.focus_row == 1
    assert controls.session.timeline.selected_cue_t == {
        "layer_1": 10.0,
        "layer_2": 20.0,
    }
    assert controls.session.timeline.selected_cue_flash_start_ms is None

    controls.session.timeline.selected_cue_flash_start_ms = 5678
    controls.focus_cursor = TimelineFocus(1)
    assert controls.session.timeline.selected_cue_flash_start_ms == 5678




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
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    layer = controls.session.layers["layer_1"]

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert playlist.current_dir.resolve() == siblings[1].resolve()
    assert layer.browse_floor.resolve() == siblings[1].resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_LEFT))
    assert playlist.current_dir.resolve() == siblings[0].resolve()
    assert layer.browse_floor.resolve() == siblings[0].resolve()


def test_directory_pack_hop_then_enter_ctrl_left_still_ascends() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    other = siblings[1]
    child = other / "nested"
    child.mkdir()
    _write_milk(child / "nested.milk")
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert playlist.current_dir.resolve() == other.resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()
    view = controls.build_view_state(paused=False)
    assert "[..]" in view.tracks["layer_1"].preset_dir_label

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == other.resolve()


def test_directory_enter_then_ctrl_left_ascends_within_pack() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()
    view = controls.build_view_state(paused=False)
    assert "[..]" in view.tracks["layer_1"].preset_dir_label

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_enter_descends_backspace_goes_parent() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_ctrl_arrows_descend_and_ascend() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_ctrl_arrows_follow_browse_while_auto_preset_elsewhere() -> None:
    """Dir row tracks browse nav. Enter selects the child directory's first preset."""
    root, siblings = _make_sibling_dir_tree(2)
    roles_bed = root / "roles" / "bed"
    roles_bed.mkdir(parents=True)
    cast = roles_bed / "cast.milk"
    _write_milk(cast)
    controls = _controls_with_playlist(root, siblings[0])
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.auto_preset_path = cast.resolve()
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    child = siblings[0] / "child"

    before = controls.build_view_state(paused=False).tracks["layer_1"].preset_dir_label
    assert "roles/" not in before

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert layer.playlist.current_dir.resolve() == child.resolve()
    after_down = controls.build_view_state(paused=False).tracks["layer_1"]
    assert "roles/" not in after_down.preset_dir_label
    assert "[..]" in after_down.preset_dir_label
    assert after_down.preset_label.startswith("nested.milk")

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert layer.playlist.current_dir.resolve() == siblings[0].resolve()
    after_up = controls.build_view_state(paused=False).tracks["layer_1"].preset_dir_label
    assert after_up == before


def test_directory_moves_select_first_preset_file() -> None:
    """Parent and sibling moves land on the first file so Left/Right can step."""
    root, siblings = _make_sibling_dir_tree(2)
    parent = siblings[0]
    other = siblings[1]
    _write_milk(parent / "preset-1.milk")
    _write_milk(other / "preset-1.milk")
    child = parent / "child"
    controls = _controls_with_playlist(root, child)
    layer = controls.session.layers["layer_1"]
    layer.auto_preset_path = (child / "nested.milk").resolve()
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert layer.playlist.current == (parent / "preset-0.milk").resolve()
    assert controls.build_view_state(paused=False).tracks[
        "layer_1"
    ].preset_label.startswith("preset-0.milk")

    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert layer.playlist.current == (parent / "preset-1.milk").resolve()
    assert controls.build_view_state(paused=False).tracks[
        "layer_1"
    ].preset_label.startswith("preset-1.milk")

    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert layer.playlist.current_dir.resolve() == other.resolve()
    assert layer.playlist.current == (other / "preset-0.milk").resolve()
    assert controls.build_view_state(paused=False).tracks[
        "layer_1"
    ].preset_label.startswith("preset-0.milk")


def test_parent_directory_clears_preset_from_previous_directory() -> None:
    root, siblings = _make_sibling_dir_tree(1)
    parent = siblings[0]
    for path in parent.glob("*.milk"):
        path.unlink()
    child = parent / "child"
    controls = _controls_with_playlist(root, child)
    layer = controls.session.layers["layer_1"]
    layer.auto_preset_path = (child / "nested.milk").resolve()
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert layer.playlist.current is None
    assert layer.auto_preset_path is None
    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].preset_label == "NO PRESETS FOUND"

    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.build_view_state(paused=False).tracks[
        "layer_1"
    ].preset_label == "NO PRESETS FOUND"


def test_ctrl_left_at_browse_floor_is_noop() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_ctrl_left_at_preset_root_is_noop_when_floor_is_root() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, root, browse_floor=root)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()


def test_directory_ctrl_arrows_do_not_repeat_parent_climb() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()

    for _ in range(20):
        controls.tick(0.5)
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_backspace_at_browse_floor_is_noop() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_parent_round_trip_reaches_browse_floor() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    child = siblings[0] / "child"
    controls = _controls_with_playlist(root, child)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    floor = siblings[0]

    for _ in range(3):
        press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == floor.resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() != floor.resolve()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == floor.resolve()


def test_preset_lr_noop_when_paths_empty() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    empty_dir = root / "empty"
    empty_dir.mkdir()
    controls = _controls_with_playlist(root, empty_dir)
    changed: list[tuple[str, int]] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_change=lambda stem, pl: changed.append((stem, pl.index))
    )
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    assert playlist.paths == ()

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_RIGHT))
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_LEFT))
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_PAGEDOWN))
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
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_PAGEDOWN))
    assert playlist.index == 3
    assert changed == [("layer_1", 3)]

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_PAGEUP))
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
    header = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")
    controls.focus_descriptor = header
    assert press_layer_row(controls, header, _keydown(_MOVE_MODE_KEY)) is True

    view = controls.build_view_state(paused=False)
    _mount_track_sections(view)
    header_row = _row(view, "layer_2", RowKind.TRACK_HEADER)
    child_row = header_row + 1
    assert _row_value_color(view, header_row) == MOVE_MODE
    assert _row_bg_color(view, header_row) == MOVE_MODE
    assert _row_value_color(view, child_row) == MOVE_MODE
    assert _row_bg_color(view, child_row) == MOVE_MODE


def test_move_mode_colors_preset_list_item() -> None:
    controls = _make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = ["/tmp/presets/a.milk", "/tmp/presets/b.milk"]

    view = controls.build_view_state(paused=False)
    _mount_track_sections(view)
    item_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=0,
        )
    )
    sibling_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=1,
        )
    )
    item = RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=0
    )
    controls.focus_descriptor = item
    assert press_layer_row(controls, item, _keydown(_MOVE_MODE_KEY)) is True
    assert controls.preset_list.move_mode_preset == ("layer_1", 0)

    view = controls.build_view_state(paused=False)
    _mount_track_sections(view)
    item_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=0,
        )
    )
    sibling_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=1,
        )
    )
    assert _row_value_color(view, item_row) == MOVE_MODE
    assert _row_bg_color(view, item_row) == MOVE_MODE
    assert _row_value_color(view, sibling_row) != MOVE_MODE
    assert _row_bg_color(view, sibling_row) != MOVE_MODE


def test_preset_list_enter_auditions_item_and_resumes() -> None:
    controls = _make_controls(("layer_1",))
    auditioned: list[tuple[str, int]] = []
    resumed: list[str] = []

    def audition(slot: str, index: int) -> None:
        auditioned.append((slot, index))

    def resume(slot: str) -> None:
        resumed.append(slot)

    controls.preset_list.audition = audition
    controls.preset_list.resume = resume
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.switching_paused = True
    layer.preset_list = [
        "/tmp/presets/a.milk",
        "/tmp/presets/b.milk",
        "/tmp/presets/c.milk",
    ]
    item = RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=2
    )
    resume_row = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_RESUME, slot="layer_1")

    assert press_layer_row(controls, item, _keydown(pygame.K_RETURN)) is True
    assert auditioned == [("layer_1", 2)]

    layer.locked = True
    assert press_layer_row(controls, item, _keydown(pygame.K_RETURN)) is True
    assert auditioned == [("layer_1", 2)]

    layer.locked = False
    assert press_layer_row(controls, resume_row, _keydown(pygame.K_RETURN)) is True
    assert resumed == ["layer_1"]

    layer.locked = True
    assert press_layer_row(controls, resume_row, _keydown(pygame.K_RETURN)) is True
    assert resumed == ["layer_1"]


def test_active_preset_list_item_uses_highlight_color() -> None:
    controls = _make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    a = Path("/tmp/presets/list-a.milk").resolve()
    b = Path("/tmp/presets/list-b.milk").resolve()
    layer.preset_list = [str(a), str(b)]
    layer.auto_preset_path = b

    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    view = controls.build_view_state(paused=False)
    _mount_track_sections(view)
    assert view.tracks["layer_1"].active_preset_list_index == 1
    active_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=1,
        )
    )
    idle_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=0,
        )
    )
    assert _row_value_color(view, active_row) == HIGHLIGHT
    assert _row_value_color(view, idle_row) == VALUE
    assert _row_bg_color(view, active_row) is None

    layer.auto_preset_path = a
    view = controls.build_view_state(paused=False)
    _mount_track_sections(view)
    active_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=1,
        )
    )
    idle_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=0,
        )
    )
    assert view.tracks["layer_1"].active_preset_list_index == 0
    assert _row_value_color(view, active_row) == VALUE
    assert _row_value_color(view, idle_row) == HIGHLIGHT


def test_first_preset_list_item_highlighted_when_auto_unset() -> None:
    controls = _make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "projectm"
    listed = Path("/tmp/user/presets/copy-a.milk").resolve()
    layer.preset_list = [str(listed)]
    layer.auto_preset_path = None
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    view = controls.build_view_state(paused=False)
    _mount_track_sections(view)
    assert view.tracks["layer_1"].active_preset_list_index == 0
    item_row = view.layout.find_descriptor(
        RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot="layer_1",
            preset_index=0,
        )
    )
    assert _row_value_color(view, item_row) == HIGHLIGHT


def test_row_value_color_dim_for_focused_empty_preset() -> None:
    state = TuningViewState(
        layer_z_order=("layer_1",),
        tracks={
            "layer_1": make_track_block(
                stem="drums",
                preset_dir_label="empty (1/1)",
                preset_label="NO PRESETS FOUND",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                preset_empty=True,
            )
        },
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)),
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
        layout=state.layout,
    )
    assert _row_value_color(state, preset_row) == DISABLED
    assert _row_bg_color(state, preset_row) == HIGHLIGHT


def test_preset_overlay_shows_directory_and_position() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    block = view.tracks["layer_1"]
    assert block.preset_dir_label.startswith("layer_1/ (")
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
        assert directory_display(playlist, root) == "[..]pack/Aurora/ (1/1)"


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
        RowKind.TRACK_COMPOSITING_HEADER,
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


def test_l_toggles_lock() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    assert controls.session.layers["layer_1"].locked is False

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_l))
    assert controls.session.layers["layer_1"].locked is True

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_l))
    assert controls.session.layers["layer_1"].locked is False


def test_l_toggles_render_overlay_lock() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    assert controls.session.render_overlays.locked is False
    _press_focused(controls, _keydown(pygame.K_l))
    assert controls.session.render_overlays.locked is True
    _press_focused(controls, _keydown(pygame.K_l))
    assert controls.session.render_overlays.locked is False


def test_l_toggles_render_post_fx_lock() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    assert controls.session.render_post_fx.locked is False
    _press_focused(controls, _keydown(pygame.K_l))
    assert controls.session.render_post_fx.locked is True


def test_l_toggles_render_timeline_lock() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.session.timeline.locked is False
    assert _press_timeline_hotkey(controls, pygame.K_l) is True
    assert controls.session.timeline.locked is True


def test_l_refused_on_timeline_header_while_recording() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.recording = True
    _press_timeline_hotkey(controls, pygame.K_l)
    assert controls.session.timeline.locked is False


def test_render_overlay_lock_blocks_e_enable_disable() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.render_overlays.locked = True
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    assert controls.session.render_overlays.opening_card.enabled is True
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_overlays.opening_card.enabled is True


def test_render_overlay_lock_allows_solo() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.render_overlays.locked = True
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    _press_focused(controls, _keydown(pygame.K_s))
    assert controls.session.render_overlay_solo is True


def test_render_overlay_locked_skips_children_in_nav() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.render_overlays.locked = True
    view = controls.build_view_state(paused=False)
    leftover = {row.kind for row in view.layout.rows}
    assert RowKind.RENDER_OVERLAYS_HEADER not in leftover
    assert RowKind.RENDER_OVERLAY_CARD_POSITION not in leftover
    position_row = RowDescriptor(
        RowKind.RENDER_OVERLAY_CARD_POSITION, card="opening_card"
    )
    assert _row_value_color(view, position_row) == LOCKED
    assert RowKind.RENDER_OVERLAY_CARD_POSITION in _page_kinds(
        view, overlay_card_node_id("opening_card")
    )


def test_render_timeline_locked_dims_inspector_children() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.enabled = True
    controls.session.timeline.locked = True
    view = controls.build_view_state(paused=False)
    assert RowKind.TIMELINE_PRESETS_HEADER not in {
        row.kind for row in view.layout.rows
    }
    assert _row_value_color(
        view, RowDescriptor(RowKind.TIMELINE_PRESET_CHARACTER)
    ) == LOCKED
    assert RowKind.TIMELINE_PRESET_CHARACTER in _page_kinds(view, "render.timeline")


def test_locked_blocks_enable_disable() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    assert controls.session.layers["layer_1"].enabled is True

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_e))
    assert controls.session.layers["layer_1"].enabled is True

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_e))
    assert controls.session.layers["layer_1"].enabled is True


def test_ctrl_arrow_on_value_row_does_not_change_value() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    before = controls.session.layers["layer_1"].opacity_pct
    _press_focused(controls, _keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    _press_focused(controls, _keydown(pygame.K_LEFT, mod=pygame.KMOD_SHIFT))
    assert controls.session.layers["layer_1"].opacity_pct == before


def test_e_toggles_each_enable_header() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)

    assert controls.session.layers["layer_1"].enabled is True
    press_layer_row(
        controls,
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"),
        _keydown(pygame.K_e),
    )
    assert controls.session.layers["layer_1"].enabled is False

    controls.focus_descriptor = _desc(
        view, RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    )
    assert controls.session.render_overlays.opening_card.enabled is True
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_overlays.opening_card.enabled is False
    assert controls.session.render_overlays.closing_card.enabled is False

    controls.session.render_overlays.opening_card.enabled = True
    view = controls.build_view_state(paused=False)
    card_row = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_HEADER, card="opening_card")
    controls.focus_descriptor = _desc(view, card_row)
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_overlays.opening_card.enabled is False

    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    assert controls.session.render_post_fx.enabled is True
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_post_fx.enabled is False

    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_PATTERN_MASK_HEADER)
    before_mask = controls.session.render_pattern_mask.enabled
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_pattern_mask.enabled is not before_mask

    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    assert controls.session.timeline.enabled is False
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.timeline.enabled is True


def test_s_toggles_overlays_always_on() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    _press_focused(controls, _keydown(pygame.K_s))
    assert controls.session.render_overlay_solo is True
    _press_focused(controls, _keydown(pygame.K_s))
    assert controls.session.render_overlay_solo is False


def test_locked_headers_block_e() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.render_post_fx.locked = True
    controls.session.render_pattern_mask.locked = True
    controls.session.timeline.locked = True
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_post_fx.enabled is True
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_PATTERN_MASK_HEADER)
    before_mask = controls.session.render_pattern_mask.enabled
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.render_pattern_mask.enabled is before_mask
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    _press_focused(controls, _keydown(pygame.K_e))
    assert controls.session.timeline.enabled is False


def test_locked_blocks_move_mode() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(_MOVE_MODE_KEY))
    assert controls.layer_lifecycle.move_mode_slot is None




def test_locked_sub_rows_use_locked_color() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
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
        layout=view.layout,
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
        layout=view.layout,
    )
    assert _row_value_color(focused_header, header_row) == HIGHLIGHT
    assert _row_value_color(focused_header, preset_dir_row) == LOCKED


def test_locked_disabled_layer_sub_rows_prefer_locked_color() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    controls.session.layers["layer_1"].enabled = False
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
        layout=view.layout,
    )
    assert _row_value_color(unfocused, header_row) == DISABLED
    assert _row_value_color(unfocused, preset_dir_row) == LOCKED


def test_locked_not_toggleable_during_move_mode() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")
    assert controls.session.layers["layer_2"].locked is False

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(_MOVE_MODE_KEY))
    assert controls.layer_lifecycle.move_mode_slot == "layer_2"

    controls.handle_move_mode_keydown(_keydown(pygame.K_l))
    assert controls.session.layers["layer_2"].locked is False


def test_ctrl_quick_nav_blocked_during_move_mode() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(_MOVE_MODE_KEY))
    assert controls.layer_lifecycle.move_mode_slot == "layer_2"

    controls.handle_move_mode_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]
    assert controls.focus_descriptor == RowDescriptor(
        RowKind.TRACK_HEADER, slot="layer_2"
    )



def test_effect_pulse_clamps() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    pulse = RowDescriptor(
        RowKind.TRACK_EFFECT, slot="layer_1", effect_id="pulse", driver_slug="onset"
    )
    bass_pulse = RowDescriptor(
        RowKind.TRACK_EFFECT,
        slot="layer_2",
        effect_id="pulse",
        driver_slug="sub_bass",
    )
    for _ in range(120):
        press_layer_row(controls, pulse, _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].effects["pulse"]["onset"] == 100

    for _ in range(120):
        press_layer_row(controls, pulse, _keydown(pygame.K_LEFT))
    assert "pulse" not in controls.session.layers["layer_1"].effects

    for _ in range(20):
        press_layer_row(controls, bass_pulse, _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_2"].effects["pulse"]["sub_bass"] == 20


def test_effect_pulse_row_label() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].effects = {"pulse": {"onset": 35}}
    view = controls.build_view_state(paused=False)
    pulse_row = _row(
        view, "layer_1", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    )
    assert _row_text(view, pulse_row) == "pulse (onset): 35%"




def test_compositing_rows_dim_only_in_pattern_mask_mode() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    kinds = (
        RowKind.TRACK_COMPOSITING_HEADER,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
    )
    for kind in kinds:
        assert _row_value_color(view, _row(view, "layer_1", kind)) != DISABLED

    controls.session.render_pattern_mask.enabled = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    view = controls.build_view_state(paused=False)
    for kind in kinds:
        assert _row_value_color(view, _row(view, "layer_1", kind)) == DISABLED

    controls.session.settings.editor_mode = "preset_curation"
    controls.session.render_pattern_mask.enabled = True
    view = controls.build_view_state(paused=False)
    assert all(
        view.layout.kind(i) != RowKind.TRACK_COMPOSITING_HEADER
        for i in range(len(view.layout))
    )








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


def test_s_enters_solo() -> None:
    solo_calls: list[str | None] = []
    controls = _make_controls(("layer_1", "layer_2"))
    controls._layer_bindings = noop_layer_bindings(
        on_solo_change=lambda: solo_calls.append(controls.session.solo_slot)
    )

    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_s))
    assert controls.session.solo_slot == "layer_1"
    assert solo_calls == ["layer_1"]
    state = controls.build_view_state(paused=False)
    assert state.solo_active is True
    assert state.solo_slot == "layer_1"


def test_s_switches_solo_target() -> None:
    controls = _make_controls(("layer_1", "layer_2"))

    press_layer_row(
        controls,
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"),
        _keydown(pygame.K_s),
    )
    assert controls.session.solo_slot == "layer_1"

    press_layer_row(
        controls,
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"),
        _keydown(pygame.K_s),
    )
    assert controls.session.solo_slot == "layer_2"


def test_s_exits_solo_only_for_active_target() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    drums = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    bass = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")

    press_layer_row(controls, drums, _keydown(pygame.K_s))
    assert controls.session.solo_slot == "layer_1"

    press_layer_row(controls, bass, _keydown(pygame.K_s))
    assert controls.session.solo_slot == "layer_2"

    press_layer_row(controls, drums, _keydown(pygame.K_s))
    assert controls.session.solo_slot == "layer_1"

    press_layer_row(controls, drums, _keydown(pygame.K_s))
    assert controls.session.solo_slot is None


def test_save_blocked_while_solo_active() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"), _keydown(pygame.K_s))

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        command_by_id("file.save").run(controls)
    assert stderr.getvalue() == ""
    assert controls.build_view_state(paused=False).solo_active is True
    assert command_by_id("file.save").enabled(command_context(controls)) is False


def test_solo_visibility_icon_same_width_as_normal() -> None:
    line_h = 17
    soloed = render_visibility_icon(enabled=True, solo=True, line_height=line_h)
    normal = render_visibility_icon(enabled=True, solo=False, line_height=line_h)
    assert soloed.get_width() == normal.get_width()
    assert soloed.get_at((1, line_h // 2))[:3] == SOLO_BG


def test_track_header_prefix_width_matches_visibility_icon() -> None:
    font = overlay_font()
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


def test_try_quit_save_writes_immediately() -> None:
    launch_path = Path("/tmp/projects/my-track/cleave-viz.yaml")
    writes: list[Path] = []
    controls = _make_controls(("layer_1",), launch_config_path=launch_path)
    controls._config_save._on_save_config = lambda path: writes.append(path) or path.name
    _mutate_dirty(controls)

    controls.try_quit()
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.UNSAVED_QUIT
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert writes == [launch_path]
    assert not controls.modal_host.active
    assert not controls.config_dirty
    assert controls.try_quit() is True


def test_stem_row_cycles_sources() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    assert controls.session.layers["layer_1"].stem == "drums"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_STEM, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].stem == "bass"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_STEM, slot="layer_1"), _keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].stem == "drums"


def test_stem_change_clears_effects() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].effects = {"pulse": {"onset": 50}}
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_STEM, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].effects == {}


def test_locked_blocks_stem_change() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    assert controls.session.layers["layer_1"].stem == "drums"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_STEM, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].stem == "drums"


def test_locked_blocks_preset_dir_enter_and_backspace() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = controls.session.layers["layer_1"].playlist
    child = siblings[0] / "child"

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.session.layers["layer_1"].locked = True

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.session.layers["layer_1"].locked = False
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()

    controls.session.layers["layer_1"].locked = True
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_cycle_stem_to_full_mix() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].stem = "other"
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_STEM, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].stem == "full_mix"

    view = controls.build_view_state(paused=False)
    assert _row_text(view, _row(view, "layer_1", RowKind.TRACK_STEM)) == (
        "driving stem: full-mix"
    )






def test_settings_editor_window_adjusts_width_height_upscale() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.width == DEFAULT_EDITOR_WIDTH
    assert controls.cfg.editor.height == DEFAULT_EDITOR_HEIGHT
    assert controls.cfg.editor.upscale == DEFAULT_EDITOR_UPSCALE

    controls.settings.adjust_editor_window_width(forward=True, large=False)
    assert controls.cfg.editor.width == DEFAULT_EDITOR_WIDTH + 10
    controls.settings.adjust_editor_window_width(forward=False, large=True)
    assert controls.cfg.editor.width == DEFAULT_EDITOR_WIDTH - 90

    controls.settings.adjust_editor_window_height(forward=True, large=False)
    assert controls.cfg.editor.height == DEFAULT_EDITOR_HEIGHT + 10
    controls.settings.adjust_editor_window_height(forward=False, large=True)
    assert controls.cfg.editor.height == DEFAULT_EDITOR_HEIGHT - 90

    controls.settings.adjust_editor_window_upscale(forward=True, large=False)
    assert controls.cfg.editor.upscale == pytest.approx(DEFAULT_EDITOR_UPSCALE + 0.1)
    controls.settings.adjust_editor_window_upscale(forward=True, large=True)
    assert controls.cfg.editor.upscale == pytest.approx(DEFAULT_EDITOR_UPSCALE + 0.6)

    from dataclasses import replace as _replace

    controls.cfg.editor = _replace(controls.cfg.editor, width=330)
    controls.settings.adjust_editor_window_width(forward=False, large=False)
    assert controls.cfg.editor.width == 320
    controls.settings.adjust_editor_window_width(forward=False, large=False)
    assert controls.cfg.editor.width == 320


def test_settings_editor_window_display_size_tracks_width_height_upscale() -> None:
    from cleave.viz.row_spec import format_row_value

    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    desc = RowDescriptor(RowKind.SETTINGS_EDITOR_WINDOW_DISPLAY_SIZE)
    display_w, display_h = editor_display_size(
        DEFAULT_EDITOR_WIDTH, DEFAULT_EDITOR_HEIGHT, upscale=DEFAULT_EDITOR_UPSCALE
    )
    assert format_row_value(view, desc) == f"{display_w} x {display_h}"

    controls.settings.adjust_editor_window_width(forward=True, large=True)
    controls.settings.adjust_editor_window_height(forward=True, large=False)
    controls.settings.adjust_editor_window_upscale(forward=True, large=False)
    view = controls.build_view_state(paused=False)
    display_w, display_h = editor_display_size(
        DEFAULT_EDITOR_WIDTH + 100,
        DEFAULT_EDITOR_HEIGHT + 10,
        upscale=DEFAULT_EDITOR_UPSCALE + 0.1,
    )
    assert format_row_value(view, desc) == f"{display_w} x {display_h}"


def test_settings_editor_window_nudge_toasts_restart_and_persists(
    tmp_path: Path,
) -> None:
    controls = _make_controls(("layer_1",))
    user_path = tmp_path / "config.yaml"
    controls.cfg.user_config_path = user_path
    controls.settings.adjust_editor_window_width(forward=True, large=True)
    assert controls.cfg.editor.width == DEFAULT_EDITOR_WIDTH + 100
    assert not controls.config_dirty
    assert (
        controls.build_view_state(paused=False).notification_message
        == EDITOR_WINDOW_RESTART_TOAST
    )
    loaded = load_user_config(user_path)
    assert loaded.editor.width == DEFAULT_EDITOR_WIDTH + 100
    assert loaded.editor.height == DEFAULT_EDITOR_HEIGHT
    assert loaded.editor.upscale == pytest.approx(DEFAULT_EDITOR_UPSCALE)


def test_settings_editor_window_nudge_at_clamp_does_not_toast() -> None:
    from dataclasses import replace as _replace

    controls = _make_controls(("layer_1",))
    controls.cfg.editor = _replace(controls.cfg.editor, width=320)
    controls.settings.adjust_editor_window_width(forward=False, large=False)
    assert controls.cfg.editor.width == 320
    assert controls.build_view_state(paused=False).notification_message is None




def test_settings_cycle_preview_quality() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.preview_quality == DEFAULT_EDITOR_PREVIEW_QUALITY
    _expand_settings_editor_window(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "balanced"

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "performance"

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "ultra-performance"

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.preview_quality == "full-quality"

    _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.cfg.editor.preview_quality == "ultra-performance"


def test_settings_preview_quality_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_editor_window(controls)
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_settings_preview_quality_writes_user_config_without_dirty(
    tmp_path: Path,
) -> None:
    user_path = tmp_path / "config.yaml"
    controls = _make_controls(("layer_1",))
    controls.cfg.user_config_path = user_path
    assert not controls.config_dirty
    _expand_settings_editor_window(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty
    assert user_path.is_file()
    loaded = load_user_config(user_path)
    assert loaded.editor.preview_quality == controls.cfg.editor.preview_quality


def test_cycle_preview_quality_calls_apply_preview_resolutions() -> None:
    controls, layer_manager = _make_controls_with_manager(("layer_1",))
    _expand_settings_editor_window(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)

    _press_focused(controls, _keydown(pygame.K_RIGHT))

    layer_manager.apply_preview_resolutions.assert_called_once()


def test_settings_adjust_ui_fade() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.ui_fade == 10.0
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_FADE)

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_fade == 11.0

    _press_focused(controls, _keydown(pygame.K_PAGEUP))
    assert controls.cfg.editor.ui_fade == 6.0

    for _ in range(6):
        _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_fade == 0.0


def test_settings_ui_fade_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_FADE)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_settings_ui_fade_writes_user_config_without_dirty(tmp_path: Path) -> None:
    user_path = tmp_path / "config.yaml"
    controls = _make_controls(("layer_1",))
    controls.cfg.user_config_path = user_path
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_FADE)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty
    assert user_path.is_file()
    loaded = load_user_config(user_path)
    assert loaded.editor.ui_fade == controls.cfg.editor.ui_fade


def test_settings_adjust_notification_display() -> None:
    controls = _make_controls(("layer_1",))
    assert (
        controls.cfg.editor.notification_display_sec
        == DEFAULT_NOTIFICATION_DISPLAY_SEC
    )
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY)

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert (
        controls.cfg.editor.notification_display_sec
        == DEFAULT_NOTIFICATION_DISPLAY_SEC + 1
    )
    _press_focused(controls, _keydown(pygame.K_PAGEUP))
    assert (
        controls.cfg.editor.notification_display_sec
        == DEFAULT_NOTIFICATION_DISPLAY_SEC + 1 - 5
    )

    _press_focused(controls, _keydown(pygame.K_PAGEUP))
    assert controls.cfg.editor.notification_display_sec == 1

    _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.cfg.editor.notification_display_sec == 0

    for _ in range(25):
        _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.notification_display_sec == 20


def test_settings_notification_display_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_settings_notification_display_writes_user_config_without_dirty(
    tmp_path: Path,
) -> None:
    user_path = tmp_path / "config.yaml"
    controls = _make_controls(("layer_1",))
    controls.cfg.user_config_path = user_path
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty
    assert user_path.is_file()
    loaded = load_user_config(user_path)
    assert (
        loaded.editor.notification_display_sec
        == controls.cfg.editor.notification_display_sec
    )


def test_settings_residual_latency_writes_user_config_without_dirty(
    tmp_path: Path,
) -> None:
    user_path = tmp_path / "config.yaml"
    controls = _make_controls(("layer_1",))
    controls.cfg.user_config_path = user_path
    assert not controls.config_dirty
    _expand_settings_latency(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_RESIDUAL_LATENCY_MS)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty
    assert user_path.is_file()
    loaded = load_user_config(user_path)
    assert loaded.editor.residual_latency_ms == controls.cfg.editor.residual_latency_ms


def test_settings_adjust_ui_width() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.ui_width == DEFAULT_UI_WIDTH
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH)

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_width == DEFAULT_UI_WIDTH + 1

    _press_focused(controls, _keydown(pygame.K_PAGEUP))
    assert controls.cfg.editor.ui_width == DEFAULT_UI_WIDTH + 1 - 5

    for _ in range(86):
        _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_width == 80


def test_settings_adjust_ui_min_width() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.ui_min_width == DEFAULT_UI_MIN_WIDTH
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_MIN_WIDTH)

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_min_width == DEFAULT_UI_MIN_WIDTH + 1

    _press_focused(controls, _keydown(pygame.K_PAGEUP))
    assert controls.cfg.editor.ui_min_width == DEFAULT_UI_MIN_WIDTH + 1 - 5

    while controls.cfg.editor.ui_min_width > 40:
        _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_min_width == 40
    _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_min_width == 40

    max_width = controls.cfg.editor.ui_width
    while controls.cfg.editor.ui_min_width < max_width:
        _press_focused(controls, _keydown(pygame.K_PAGEDOWN))
    assert controls.cfg.editor.ui_min_width == max_width
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_min_width == max_width
    _press_focused(controls, _keydown(pygame.K_PAGEDOWN))
    assert controls.cfg.editor.ui_min_width == max_width


def test_settings_ui_min_width_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_MIN_WIDTH)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_settings_ui_width_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_settings_cycle_ui_width_mode() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.cfg.editor.ui_width_mode == DEFAULT_UI_WIDTH_MODE
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH_MODE)

    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_width_mode == "fixed"

    _press_focused(controls, _keydown(pygame.K_LEFT))
    assert controls.cfg.editor.ui_width_mode == "flexible"


def test_settings_cycle_and_toggle_shell_layout_mode(tmp_path: Path) -> None:
    controls = _make_controls(("layer_1",))
    user_path = tmp_path / "user.yaml"
    controls.cfg.user_config_path = user_path
    selected_id = controls.shell_focus.selected_id
    inspector_cursor = controls.shell_focus.inspector_cursor
    focus_cursor = controls.focus_cursor
    assert controls.cfg.editor.shell_layout_mode == DEFAULT_SHELL_LAYOUT_MODE
    assert not controls.config_dirty

    controls.settings.cycle_shell_layout_mode(forward=True)
    assert controls.cfg.editor.shell_layout_mode == "docked"
    controls.settings.cycle_shell_layout_mode(forward=True)
    assert controls.cfg.editor.shell_layout_mode == DEFAULT_SHELL_LAYOUT_MODE
    controls.settings.cycle_shell_layout_mode(forward=False)
    assert controls.cfg.editor.shell_layout_mode == "docked"
    controls.settings.toggle_shell_layout_mode()
    assert controls.cfg.editor.shell_layout_mode == DEFAULT_SHELL_LAYOUT_MODE
    controls.settings.toggle_shell_layout_mode()
    assert controls.cfg.editor.shell_layout_mode == "docked"
    assert (
        controls.build_view_state(paused=False).settings.shell_layout_mode == "docked"
    )
    assert load_user_config(user_path).editor.shell_layout_mode == "docked"
    assert not controls.config_dirty
    assert controls.shell_focus.selected_id == selected_id
    assert controls.shell_focus.inspector_cursor == inspector_cursor
    assert controls.focus_cursor is focus_cursor


def test_settings_set_shell_column_widths_clamps_and_persists(tmp_path: Path) -> None:
    controls = _make_controls(("layer_1",))
    user_path = tmp_path / "user.yaml"
    controls.cfg.user_config_path = user_path
    selected_id = controls.shell_focus.selected_id
    inspector_cursor = controls.shell_focus.inspector_cursor
    focus_cursor = controls.focus_cursor
    mode = controls.cfg.editor.shell_layout_mode
    assert not controls.config_dirty

    controls.settings.set_shell_column_widths(12, 40)
    assert controls.cfg.editor.navigator_width == MIN_COLUMN_WIDTH
    assert controls.cfg.editor.inspector_width == MIN_COLUMN_WIDTH
    assert controls.cfg.editor.shell_layout_mode == mode
    assert controls.shell_focus.selected_id == selected_id
    assert controls.shell_focus.inspector_cursor == inspector_cursor
    assert controls.focus_cursor is focus_cursor
    assert not controls.config_dirty
    loaded = load_user_config(user_path)
    assert loaded.editor.navigator_width == MIN_COLUMN_WIDTH
    assert loaded.editor.inspector_width == MIN_COLUMN_WIDTH

    controls.settings.set_shell_column_widths(280, 510)
    assert controls.cfg.editor.navigator_width == 280
    assert controls.cfg.editor.inspector_width == 510
    assert controls.cfg.editor.shell_layout_mode == mode
    loaded = load_user_config(user_path)
    assert loaded.editor.navigator_width == 280
    assert loaded.editor.inspector_width == 510
    assert not controls.config_dirty


def test_settings_ui_width_mode_change_does_not_mark_project_config_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    _expand_settings_ui(controls)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH_MODE)
    _press_focused(controls, _keydown(pygame.K_RIGHT))
    assert not controls.config_dirty


def test_move_mode_swap_calls_apply_preview_resolutions() -> None:
    controls, layer_manager = _make_controls_with_manager(("layer_1", "layer_2", "layer_3"))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_2"), _keydown(_MOVE_MODE_KEY))
    layer_manager.apply_preview_resolutions.reset_mock()

    controls.handle_move_mode_keydown(_keydown(pygame.K_UP))

    layer_manager.apply_preview_resolutions.assert_called_once()


def test_default_focus_is_not_a_layout_row() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    assert controls.focus_descriptor == RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    assert controls.focus_descriptor not in view.layout.rows



def test_projectm_mode_allows_preset_browse() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    changed: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_change=lambda slot, _pl: changed.append(slot)
    )
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert changed == ["layer_1"]

    root, siblings = _make_sibling_dir_tree(3)
    dir_controls = _controls_with_playlist(root, siblings[0])
    dir_controls.session.layers["layer_1"].preset_switching = "on"
    dir_controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    playlist = dir_controls.session.layers["layer_1"].playlist
    press_layer_row(dir_controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_RIGHT))
    assert playlist.current_dir.resolve() == siblings[1].resolve()











def test_persistent_and_timed_notifications_stack() -> None:
    from cleave.viz.panel_notification import NOTIFICATION_ATTENTION_DURATION_SEC
    from cleave.viz.preset_switching import EMPTY_PRESET_LIST_NOTIFICATION

    controls = _make_controls(("layer_1",))
    with patch.object(time, "monotonic", return_value=1000.0):
        controls._notification_host.set_persistent(EMPTY_PRESET_LIST_NOTIFICATION)
        controls.show_notification("Saved")
        controls.build_view_state(paused=False)
    with patch.object(
        time,
        "monotonic",
        return_value=1000.0 + NOTIFICATION_ATTENTION_DURATION_SEC + 0.1,
    ):
        view = controls.build_view_state(paused=False)

    assert view.persistent_notification_message == EMPTY_PRESET_LIST_NOTIFICATION
    assert view.notification_message == "Saved"
    notification_rows = [
        row
        for row in view.layout.rows
        if row.kind == RowKind.PANEL_NOTIFICATION
    ]
    assert [row.marker_index for row in notification_rows] == [0, 1]
    persistent_idx = view.layout.find_descriptor(notification_rows[0])
    timed_idx = view.layout.find_descriptor(notification_rows[1])
    assert _row_value_color(view, persistent_idx) == ERROR_NOTIFICATION
    assert _row_value_color(view, timed_idx) == HIGHLIGHT
    assert _row_text(view, persistent_idx) == EMPTY_PRESET_LIST_NOTIFICATION
    assert _row_text(view, timed_idx) == "Saved"



def test_preset_duration_ctrl_step_is_ten_seconds() -> None:
    controls = _make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    duration = RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    controls.session.layers["layer_1"].preset_duration = 30.0

    press_layer_row(controls, duration, _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].preset_duration == 31.0

    press_layer_row(controls, duration, _keydown(pygame.K_PAGEDOWN))
    assert controls.session.layers["layer_1"].preset_duration == 41.0


def test_hard_cut_enabled_cycles_and_hides_child_rows() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    controls.session.layers["layer_1"].preset_switching_trigger = "projectm"
    switched: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_switching_change=lambda slot: switched.append(slot)
    )
    enabled = RowDescriptor(RowKind.TRACK_HARD_CUT_ENABLED, slot="layer_1")
    assert RowKind.TRACK_HARD_CUT_DURATION in _inspector_kinds(controls, "layer_1")
    assert RowKind.TRACK_HARD_CUT_SENSITIVITY in _inspector_kinds(controls, "layer_1")
    assert controls.session.layers["layer_1"].hard_cut_enabled is True

    press_layer_row(controls, enabled, _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].hard_cut_enabled is False
    assert switched == ["layer_1"]
    assert RowKind.TRACK_HARD_CUT_DURATION not in _inspector_kinds(controls, "layer_1")

    press_layer_row(controls, enabled, _keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].hard_cut_enabled is True
    assert RowKind.TRACK_HARD_CUT_DURATION in _inspector_kinds(controls, "layer_1")


def test_easter_egg_steps_with_standard_and_large_increments() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    controls.session.layers["layer_1"].preset_switching_trigger = "projectm"
    switched: list[str] = []
    controls._layer_bindings = noop_layer_bindings(
        on_preset_switching_change=lambda slot: switched.append(slot)
    )
    egg = RowDescriptor(RowKind.TRACK_EASTER_EGG, slot="layer_1")
    controls.session.layers["layer_1"].easter_egg = 1.0

    press_layer_row(controls, egg, _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].easter_egg == pytest.approx(1.01)
    assert switched == ["layer_1"]

    press_layer_row(controls, egg, _keydown(pygame.K_PAGEDOWN))
    assert controls.session.layers["layer_1"].easter_egg == pytest.approx(1.11)


def test_preset_start_clean_cycles_yes_no() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    controls.session.layers["layer_1"].preset_switching_trigger = "timer"
    start_clean = RowDescriptor(RowKind.TRACK_PRESET_START_CLEAN, slot="layer_1")
    assert controls.session.layers["layer_1"].preset_start_clean is False

    press_layer_row(controls, start_clean, _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].preset_start_clean is True

    press_layer_row(controls, start_clean, _keydown(pygame.K_LEFT))
    assert controls.session.layers["layer_1"].preset_start_clean is False



def test_hard_cut_sensitivity_steps_like_beat_sensitivity() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    controls.session.layers["layer_1"].preset_switching_trigger = "projectm"
    controls.session.layers["layer_1"].hard_cut_enabled = True
    sensitivity = RowDescriptor(RowKind.TRACK_HARD_CUT_SENSITIVITY, slot="layer_1")
    controls.session.layers["layer_1"].hard_cut_sensitivity = 1.5

    press_layer_row(controls, sensitivity, _keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].hard_cut_sensitivity == pytest.approx(
        1.51
    )

    press_layer_row(controls, sensitivity, _keydown(pygame.K_PAGEDOWN))
    assert controls.session.layers["layer_1"].hard_cut_sensitivity == pytest.approx(
        1.61
    )


def _focus_preset_file_row(controls: TuningControls) -> Path:
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
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
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    path = preset_path or Path("/tmp/projects/my-track/user-preset-0.milk")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("milk", encoding="utf-8")
    layer.preset_list = [str(path)]
    desc = RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM,
        slot="layer_1",
        preset_index=0,
    )
    controls.focus_descriptor = desc
    return desc, path


def test_f_on_preset_file_prompts_favourite() -> None:
    controls = _make_controls(("layer_1",))
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert press_layer_row(controls, preset, _keydown(pygame.K_f)) is True

    mock_curation.prompt_favourite.assert_called_once_with("layer_1", current)


def test_c_on_preset_file_prompts_cast() -> None:
    controls = _make_controls(("layer_1",))
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert press_layer_row(controls, preset, _keydown(pygame.K_c)) is True

    mock_curation.prompt_cast.assert_called_once_with("layer_1", current)


def test_b_on_preset_file_prompts_blacklist() -> None:
    controls = _make_controls(("layer_1",))
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert press_layer_row(controls, preset, _keydown(pygame.K_b)) is True

    mock_curation.prompt_blacklist.assert_called_once_with(
        "layer_1",
        current,
        from_user_preset=False,
        user_preset_index=None,
    )


def test_f_on_user_preset_item_prompts_favourite() -> None:
    controls = _make_controls(("layer_1",))
    desc, path = _focus_user_preset_item_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert press_layer_row(controls, desc, _keydown(pygame.K_f)) is True

    mock_curation.prompt_favourite.assert_called_once_with("layer_1", path)


def test_b_on_user_preset_item_prompts_blacklist() -> None:
    controls = _make_controls(("layer_1",))
    desc, path = _focus_user_preset_item_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    assert press_layer_row(controls, desc, _keydown(pygame.K_b)) is True

    mock_curation.prompt_blacklist.assert_called_once_with(
        "layer_1",
        path,
        from_user_preset=True,
        user_preset_index=desc.preset_index,
    )


def test_f_b_not_on_preset_dir() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_f))
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"), _keydown(pygame.K_b))
    mock_curation.prompt_favourite.assert_not_called()
    mock_curation.prompt_blacklist.assert_not_called()


def test_f_b_blocked_when_layer_locked() -> None:
    controls = _make_controls(("layer_1",))
    _focus_preset_file_row(controls)
    controls.session.layers["layer_1"].locked = True
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert press_layer_row(controls, preset, _keydown(pygame.K_f)) is True
    assert press_layer_row(controls, preset, _keydown(pygame.K_b)) is True
    mock_curation.prompt_favourite.assert_not_called()
    mock_curation.prompt_blacklist.assert_not_called()


def test_f_b_allowed_in_projectm_mode() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert press_layer_row(controls, preset, _keydown(pygame.K_f)) is True

    mock_curation.prompt_favourite.assert_called_once_with("layer_1", current)


def test_c_on_preset_file_in_curation_mode_prompts_cast() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.settings.editor_mode = "preset_curation"
    current = _focus_preset_file_row(controls)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert press_layer_row(controls, preset, _keydown(pygame.K_c)) is True

    mock_curation.prompt_cast.assert_called_once_with("layer_1", current)


def test_f_b_ignored_on_non_preset_rows() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation

    _press_focused(controls, _keydown(pygame.K_f))
    _press_focused(controls, _keydown(pygame.K_b))
    mock_curation.prompt_favourite.assert_not_called()
    mock_curation.prompt_blacklist.assert_not_called()


def test_drop_song_marker_does_not_select_or_steal_focus() -> None:
    controls = _make_controls(("layer_1",))
    prior_focus = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    controls.focus_descriptor = prior_focus
    controls.playback.player.seek(15.0)
    controls.song_markers.drop()
    markers = controls.session.song_markers
    assert markers.times == [15.0]
    assert markers.markers == [SongMarker(15.0, "standard")]
    assert markers.selected_index is None
    assert controls.session.timeline.panel_open is True
    assert controls.focus_descriptor == prior_focus
    view = controls.build_view_state(paused=False)
    assert RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=0) not in view.layout.rows


def test_song_marker_left_right_cycles_type() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    markers = controls.session.song_markers
    markers.markers = [SongMarker(26.02, "standard")]
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=0)
    controls.clear_config_dirty()

    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=0)
    assert "[00:26.02] -" in _row_text(view, row)

    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert markers.markers[0].marker_type == "begin"
    assert controls.config_dirty
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=0)
    assert "[00:26.02] begin" in _row_text(view, row)

    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert markers.markers[0].marker_type == "sustain"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert markers.markers[0].marker_type == "crescendo"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert markers.markers[0].marker_type == "diminuendo"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert markers.markers[0].marker_type == "standard"
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert markers.markers[0].marker_type == "diminuendo"


def test_song_marker_type_cycle_toasts_orphan_begin() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    markers = controls.session.song_markers
    markers.markers = [SongMarker(10.0, "standard"), SongMarker(20.0)]
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=0)
    noted: list[str] = []
    controls.show_notification = noted.append  # type: ignore[method-assign]

    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert markers.markers[0].marker_type == "begin"
    assert noted == ["begin has no crescendo/diminuendo after it"]


def test_song_marker_type_cycle_toasts_orphan_sustain() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    markers = controls.session.song_markers
    markers.markers = [SongMarker(10.0, "begin"), SongMarker(20.0)]
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=0)
    noted: list[str] = []
    controls.show_notification = noted.append  # type: ignore[method-assign]

    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert markers.markers[0].marker_type == "sustain"
    assert noted == ["sustain has no crescendo/diminuendo after it"]


def test_drop_song_marker_insert_preserves_prior_selection_by_time() -> None:
    """Insert before the selected marker remaps selected_index by prior time."""
    controls = _make_controls(("layer_1",))
    markers = controls.session.song_markers
    markers.times = [20.0, 40.0]
    markers.selected_index = 1
    controls.playback.player.seek(10.0)
    controls.song_markers.drop()
    assert markers.times == [10.0, 20.0, 40.0]
    # Prior selection was 40.0 at index 1; after insert it is index 2.
    assert markers.selected_index == 2


def test_drop_song_marker_replace_non_selected_does_not_select_replaced() -> None:
    controls = _make_controls(("layer_1",))
    markers = controls.session.song_markers
    markers.times = [10.0, 40.0]
    markers.selected_index = 0
    controls.playback.player.seek(41.0)
    controls.song_markers.drop()
    assert markers.times == [10.0, 41.0]
    assert markers.selected_index == 0


def test_drop_song_marker_replace_selected_keeps_that_slot() -> None:
    controls = _make_controls(("layer_1",))
    markers = controls.session.song_markers
    markers.times = [10.0, 40.0]
    markers.selected_index = 1
    controls.playback.player.seek(41.0)
    controls.song_markers.drop()
    assert markers.times == [10.0, 41.0]
    assert markers.selected_index == 1


def test_enter_on_song_marker_seeks() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    controls.session.song_markers.times = [10.0, 40.0]
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=1)
    controls.playback.player.seek(0.0)
    assert _press_focused(controls, _keydown(pygame.K_RETURN)) is True
    assert controls.playback.player.audible_position_sec() == 40.0


def test_delete_song_marker_opens_confirm_modal() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    markers = controls.session.song_markers
    markers.times = [5.0, 15.0, 25.0]
    markers.selected_index = 1
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=1)
    assert _press_focused(controls, _keydown(pygame.K_DELETE)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.YES_NO
    assert modal_view.options == ("Yes", "No")
    assert modal_view.message == "Remove song marker 00:15.00?"
    assert markers.times == [5.0, 15.0, 25.0]
    assert markers.selected_index == 1


def test_delete_song_marker_confirm_removes_and_adjusts_selection() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    markers = controls.session.song_markers
    markers.times = [5.0, 15.0, 25.0]
    markers.selected_index = 1
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=1)
    assert _press_focused(controls, _keydown(pygame.K_DELETE)) is True
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert not controls.modal_host.active
    assert markers.times == [5.0, 25.0]
    assert markers.selected_index == 1
    assert controls.shell_focus.inspector_cursor == RowDescriptor(
        RowKind.SONG_MARKER_ITEM, marker_index=1
    )
    view = controls.build_view_state(paused=False)
    assert view.notification_message == "Song marker removed 00:15.00"


def test_delete_song_marker_cancel_leaves_unchanged() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    markers = controls.session.song_markers
    markers.times = [5.0, 15.0, 25.0]
    markers.selected_index = 1
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=1)
    assert _press_focused(controls, _keydown(pygame.K_DELETE)) is True
    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert not controls.modal_host.active
    assert markers.times == [5.0, 15.0, 25.0]
    assert markers.selected_index == 1
    assert controls.shell_focus.inspector_cursor == RowDescriptor(
        RowKind.SONG_MARKER_ITEM, marker_index=1
    )


def test_up_down_syncs_song_marker_selected_index() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.panel_open = True
    markers = controls.session.song_markers
    markers.times = [5.0, 15.0]
    markers.selected_index = 0
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=0)
    assert _press_focused(controls, _keydown(pygame.K_DOWN)) is True
    assert markers.selected_index == 1
    assert controls.shell_focus.inspector_cursor == RowDescriptor(
        RowKind.SONG_MARKER_ITEM, marker_index=1
    )
    assert _press_focused(controls, _keydown(pygame.K_UP)) is True
    assert markers.selected_index == 0


def _song_markers(*times: float) -> tuple[SongMarker, ...]:
    return tuple(SongMarker(t) for t in times)


def _project_with_markers(tmp_path: Path, markers: tuple[float, ...] = ()) -> Path:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
        song_markers=markers,
    )
    assert load_manifest(project).song_markers == _song_markers(*markers)
    return project


def test_drop_song_marker_does_not_write_project_yaml(tmp_path: Path) -> None:
    project = _project_with_markers(tmp_path, (10.0,))
    controls = _make_controls(("layer_1",), project_dir=project)
    controls.session.song_markers.times = [10.0]
    controls.clear_config_dirty()
    controls.playback.player.seek(25.0)
    controls.song_markers.drop()
    assert controls.session.song_markers.times == [10.0, 25.0]
    assert load_manifest(project).song_markers == _song_markers(10.0)
    assert controls.config_dirty


def test_delete_song_marker_does_not_write_project_yaml(tmp_path: Path) -> None:
    project = _project_with_markers(tmp_path, (5.0, 15.0, 25.0))
    controls = _make_controls(("layer_1",), project_dir=project)
    markers = controls.session.song_markers
    markers.times = [5.0, 15.0, 25.0]
    markers.selected_index = 1
    controls.clear_config_dirty()
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.SONG_MARKER_ITEM, marker_index=1)
    assert _press_focused(controls, _keydown(pygame.K_DELETE)) is True
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert markers.times == [5.0, 25.0]
    assert load_manifest(project).song_markers == _song_markers(5.0, 15.0, 25.0)
    assert controls.config_dirty


def test_marker_only_edit_marks_dirty_and_save_clears(tmp_path: Path) -> None:
    project = _project_with_markers(tmp_path, ())
    controls = _make_controls(("layer_1",), project_dir=project)
    assert not controls.config_dirty

    controls.playback.player.seek(12.5)
    controls.song_markers.drop()
    assert controls.config_dirty
    assert load_manifest(project).song_markers == ()

    _save_now(controls)

    assert not controls.config_dirty
    assert load_manifest(project).song_markers == _song_markers(12.5)


def test_save_flushes_song_markers(tmp_path: Path) -> None:
    project = _project_with_markers(tmp_path, (8.0,))
    launch = project / "cleave-viz.yaml"
    launch.write_text("editor: {}\n", encoding="utf-8")
    writes: list[Path] = []
    controls = _make_controls(
        ("layer_1",),
        project_dir=project,
        launch_config_path=launch,
    )
    controls.session.song_markers.times = [8.0]
    controls.clear_config_dirty()
    controls._config_save._on_save_config = (
        lambda path: writes.append(path) or path.name
    )

    controls.playback.player.seek(40.0)
    controls.song_markers.drop()
    assert controls.config_dirty
    assert load_manifest(project).song_markers == _song_markers(8.0)

    _save_now(controls)

    assert writes == [launch]
    assert load_manifest(project).song_markers == _song_markers(8.0, 40.0)
    assert not controls.config_dirty


def test_quit_discard_leaves_project_markers_unchanged(tmp_path: Path) -> None:
    project = _project_with_markers(tmp_path, (10.0, 20.0))
    controls = _make_controls(("layer_1",), project_dir=project)
    controls.session.song_markers.times = [10.0, 20.0]
    controls.clear_config_dirty()

    controls.playback.player.seek(55.0)
    controls.song_markers.drop()
    assert controls.config_dirty

    assert controls.try_quit() is False
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.kind == ModalKind.UNSAVED_QUIT
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert controls.consume_pending_exit() is True
    assert load_manifest(project).song_markers == _song_markers(10.0, 20.0)


def test_save_flushes_markers_to_project_yaml(tmp_path: Path) -> None:
    project = _project_with_markers(tmp_path, ())
    controls = _make_controls(("layer_1",), project_dir=project)

    controls.playback.player.seek(3.0)
    controls.song_markers.drop()
    _save_now(controls)

    assert load_manifest(project).song_markers == _song_markers(3.0)
    assert not controls.config_dirty


def test_song_marker_inspector_open_does_not_mark_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    controls.shell_focus.selected_id = "song_markers"
    controls.inspector.toggle_group(InspectorGroupKey(RowKind.SONG_MARKERS_HEADER))
    assert not controls.config_dirty


def test_no_project_dir_marker_edit_still_marks_dirty() -> None:
    controls = _make_controls(("layer_1",), project_dir=None)
    controls.playback.player.seek(1.0)
    controls.song_markers.drop()
    assert controls.config_dirty
    controls.clear_config_dirty()
    assert not controls.config_dirty


def test_drop_song_marker_snaps_to_beat_by_default() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0, 2.0),
        bar_times=(0.0, 4.0),
    )
    assert controls.session.timeline.placement_snap == "beat"
    controls.playback.player.seek(0.6)
    controls.song_markers.drop()
    assert controls.session.song_markers.times == [1.0]


def test_drop_song_marker_placement_snap_off_keeps_audible_time() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0, 2.0),
    )
    controls.session.timeline.placement_snap = "off"
    controls.playback.player.seek(0.6)
    controls.song_markers.drop()
    assert controls.session.song_markers.times == [0.6]


def test_drop_song_marker_snaps_to_bar() -> None:
    controls = _make_controls(
        ("layer_1",),
        beat_times=(0.0, 1.0, 2.0, 3.0, 4.0),
        bar_times=(0.0, 4.0),
    )
    controls.session.timeline.placement_snap = "bar"
    controls.playback.player.seek(1.5)
    controls.song_markers.drop()
    assert controls.session.song_markers.times == [0.0]


def test_placement_snap_row_cycles() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.panel_open = True
    _focus_inspector_kind(controls, RowKind.TIMELINE_PLACEMENT_SNAP)
    view = controls.build_view_state(paused=False)
    row = RowDescriptor(RowKind.TIMELINE_PLACEMENT_SNAP)
    assert controls.session.timeline.placement_snap == "beat"
    assert "beat" in _row_text(view, row)
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.placement_snap == "bar"
    assert _press_focused(controls, _keydown(pygame.K_RIGHT)) is True
    assert controls.session.timeline.placement_snap == "off"
    assert _press_focused(controls, _keydown(pygame.K_LEFT)) is True
    assert controls.session.timeline.placement_snap == "bar"
    view = controls.build_view_state(paused=False)
    assert "bar" in _row_text(view, row)



def test_preset_switching_trigger_cycles() -> None:
    from tests.support.viz import make_controls, keydown
    import pygame
    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from cleave.viz.focus_nav import MainFocus

    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    controls.session.timeline.enabled = True
    controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1")
    )
    assert layer.preset_switching_trigger == "timer"
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1"), keydown(pygame.K_RIGHT))
    assert layer.preset_switching_trigger == "projectm"
    assert layer.preset_switching == "on"
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1"), keydown(pygame.K_RIGHT))
    assert layer.preset_switching_trigger == "timeline"
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1"), keydown(pygame.K_RIGHT))
    assert layer.preset_switching_trigger == "off"
    assert layer.preset_switching == "off"
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1"), keydown(pygame.K_RIGHT))
    assert layer.preset_switching_trigger == "timer"
    assert layer.preset_switching == "on"


def test_timeline_trigger_hides_duration_row() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    controls.session.layers["layer_1"].preset_switching_trigger = "timeline"
    assert RowKind.TRACK_PRESET_DURATION not in _inspector_kinds(controls, "layer_1")


def test_timeline_trigger_while_disabled_shows_warning() -> None:
    from cleave.viz.layer_mutations import NOTIFICATION_TIMELINE_TRIGGER_DISABLED_TEXT
    from tests.support.viz import make_controls, keydown, noop_layer_bindings
    import pygame
    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from cleave.viz.focus_nav import MainFocus

    controls = make_controls(("layer_1",))
    controls._layer_bindings = noop_layer_bindings()
    controls.session.layers["layer_1"].preset_switching = "on"
    controls.session.timeline.enabled = False
    controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1")
    )
    controls.session.layers["layer_1"].preset_switching_trigger = "projectm"
    press_layer_row(controls, RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1"), keydown(pygame.K_RIGHT))
    assert controls.session.layers["layer_1"].preset_switching_trigger == "timeline"
    view = controls.build_view_state(paused=False)
    assert view.notification_message == (
        f"Layer 1: {NOTIFICATION_TIMELINE_TRIGGER_DISABLED_TEXT}"
    )


def test_populate_modal_options_keyed_by_timeline_trigger() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].preset_switching = "on"
    controls.session.layers["layer_1"].preset_switching_trigger = "timeline"
    controls.session.timeline.enabled = False
    prompted: list[tuple[str, list[str]]] = []

    def capture_prompt(title, options, on_dismiss=None):
        del on_dismiss
        prompted.append((title, [opt.label for opt in options]))

    controls._modal_host.prompt_choice = capture_prompt  # type: ignore[method-assign]
    controls.preset_list.project_dir = Path("/tmp/project")
    controls.preset_list.prompt_populate("layer_1")
    assert prompted
    assert prompted[0][0] == "Populate the preset list with 1 presets from?"
    labels = prompted[0][1]
    assert labels == [
        "Using Cue Marker Roles (random)",
        "Current Directory (random)",
        "Current Directory (sequential)",
        "Cancel",
    ]

    prompted.clear()
    controls.session.layers["layer_1"].preset_switching_trigger = "timer"
    controls.session.timeline.enabled = True
    controls.preset_list.prompt_populate("layer_1")
    # 120s song / 30s duration = 4 needed; fixture browse dir has 1 milk
    assert prompted[0][0] == "Populate the preset list with 1 presets from?"
    labels = prompted[0][1]
    assert labels == [
        "Current Directory (random)",
        "Current Directory (sequential)",
        "Cancel",
    ]
    assert "Using Cue Marker Roles (random)" not in labels


def test_step_preset_duration_toasts_when_list_too_short() -> None:
    controls = _make_controls(("layer_1",), duration_sec=120.0)
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_duration = 30.0
    layer.preset_list = ["a.milk", "b.milk", "c.milk", "d.milk"]
    noted: list[str] = []
    controls.show_notification = noted.append  # type: ignore[method-assign]
    controls.layer_mutations.step_preset_duration("layer_1", forward=False)
    assert layer.preset_duration == 29.0
    assert noted == ["Layer 1: Preset list may need more presets"]


def test_cycle_preset_switching_trigger_toasts_when_list_nonempty() -> None:
    controls = _make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = ["a.milk"]
    noted: list[str] = []
    controls.show_notification = noted.append  # type: ignore[method-assign]
    controls.layer_mutations.cycle_preset_switching_trigger("layer_1", forward=True)
    assert layer.preset_switching_trigger != "timer"
    assert noted == ["Layer 1: Preset list may need adjusting"]


def test_cycle_preset_switching_trigger_skips_list_toast_for_timeline_disabled() -> None:
    from cleave.viz.layer_mutations import NOTIFICATION_TIMELINE_TRIGGER_DISABLED_TEXT

    controls = _make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "projectm"
    layer.preset_list = ["a.milk"]
    controls.session.timeline.enabled = False
    noted: list[str] = []
    controls.show_notification = noted.append  # type: ignore[method-assign]
    controls.layer_mutations.cycle_preset_switching_trigger("layer_1", forward=True)
    assert layer.preset_switching_trigger == "timeline"
    assert noted == [f"Layer 1: {NOTIFICATION_TIMELINE_TRIGGER_DISABLED_TEXT}"]
