"""Shell navigator and inspector header decisions. No ImGui window."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cleave.preset_playlist import PresetPlaylist
from cleave.stems import StemSource
from cleave.viz.material_icons import (
    LOCK_GLYPH,
    LOCK_OPEN_GLYPH,
    POWER_GLYPH,
    SOLO_GLYPH,
)
from cleave.viz.navigator import (
    TOGGLE_ENABLED,
    TOGGLE_LOCK,
    TOGGLE_SOLO,
    TWISTY_COLLAPSED,
    TWISTY_EXPANDED,
    NavToggle,
    build_navigator,
    ancestor_ids,
    layer_node_id,
    layer_page_node_id,
)
from cleave.viz.row_hotkeys import activate_header_toggle
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.shell_host import (
    marker_token_spans,
    drag_handle_lead,
    inspector_selectable_id,
    inspector_title,
    navigator_height_for_rows,
    navigator_lock_mark,
    navigator_toggle_color,
    navigator_toggle_glyph,
    navigator_toggle_tooltip,
    navigator_toggle_x,
    navigator_tree_lines,
    strip_eye_tooltip,
    strip_label_tooltip,
    navigator_twisty,
    path_icon_color,
    path_row_icon,
    scroll_clip_span,
    selectable_wash,
    selection_after_nav_collapse,
)
from cleave.viz.material_icons import FILE_GLYPH, FOLDER_GLYPH
from cleave.viz.theme import (
    DISABLED,
    PRESET_FILE_ICON,
    PRESET_ICON,
    VALUE,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    LOCK_ICON,
    LOCKED,
    MUTED,
    SELECTED_WASH_ALPHA,
)
from tests.cleave.viz.test_controls import _make_controls


def _layer(
    stem: StemSource,
    *,
    locked: bool = False,
    enabled: bool = True,
) -> LayerRuntime:
    return LayerRuntime(
        playlist=PresetPlaylist(current_dir=Path("/tmp/presets"), paths=(), index=0),
        browse_floor=Path("/tmp/presets"),
        stem=stem,
        locked=locked,
        enabled=enabled,
    )


def _session() -> TuningSession:
    session = TuningSession(
        layer_z_order=["layer_1", "layer_2", "layer_3"],
        layers={
            "layer_1": _layer("drums", locked=True),
            "layer_2": _layer("bass", enabled=False),
            "layer_3": _layer("vocals", enabled=False),
        },
        solo_slot="layer_3",
    )
    session.song_markers.times = [1.0, 4.0]
    return session


def _wash_channels(color) -> tuple[float, float, float, float]:
    return (color.x, color.y, color.z, color.w)


def test_selectable_wash_splits_navigator_and_inspector() -> None:
    navigator = (
        HIGHLIGHT[0] / 255.0,
        HIGHLIGHT[1] / 255.0,
        HIGHLIGHT[2] / 255.0,
        SELECTED_WASH_ALPHA / 255.0,
    )
    inspector = (
        HIGHLIGHT[0] / 255.0,
        HIGHLIGHT[1] / 255.0,
        HIGHLIGHT[2] / 255.0,
        FOCUS_WASH_ALPHA / 255.0,
    )

    hovered, active = selectable_wash(inspector=False)
    assert _wash_channels(hovered) == pytest.approx(navigator)
    assert _wash_channels(active) == pytest.approx(navigator)

    hovered, active = selectable_wash(inspector=True)
    assert _wash_channels(hovered) == pytest.approx(inspector)
    assert _wash_channels(active) == pytest.approx(inspector)


def test_layer_breadcrumb_uses_navigator_label() -> None:
    session = _session()
    nodes = build_navigator(session, {"layers", "timeline"})
    child = next(node for node in nodes if node.slot == "layer_2")

    assert inspector_title(nodes, child.id) == f"Layers > {child.label}"


def test_child_page_breadcrumbs() -> None:
    session = _session()
    page = layer_page_node_id("layer_3", "compositing")
    nodes = build_navigator(session, ancestor_ids(page))
    layer = next(node for node in nodes if node.id == layer_node_id("layer_3"))

    assert inspector_title(nodes, page) == f"Layers > {layer.label} > Compositing"
    assert inspector_title(build_navigator(session), "layers") == "Layers"
    assert (
        inspector_title(build_navigator(session), "project.resolution")
        == "Project > Resolution"
    )
    assert (
        inspector_title(build_navigator(session, {"post_fx"}), "post_fx.fade")
        == "Post-FX > Fade"
    )
    assert (
        inspector_title(build_navigator(session, {"settings"}), "settings.ui")
        == "Settings > UI"
    )


def test_timeline_toggle_opens_and_closes_the_strip() -> None:
    controls = _make_controls(("layer_1",), timeline_enabled=True)
    assert controls.session.timeline.panel_open is False
    desc = RowDescriptor(RowKind.TIMELINE_HEADER)
    activate_header_toggle(controls, "enabled", desc)
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is False
    activate_header_toggle(controls, "enabled", desc)
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.panel_open is True
    activate_header_toggle(controls, "lock", desc)
    assert controls.session.timeline.locked is True


def test_navigator_toggle_presentation() -> None:
    on = NavToggle(TOGGLE_ENABLED, True)
    off = NavToggle(TOGGLE_ENABLED, False)
    blocked = NavToggle(TOGGLE_ENABLED, True, True)
    locked = NavToggle(TOGGLE_LOCK, True)
    unlocked = NavToggle(TOGGLE_LOCK, False)
    solo = NavToggle(TOGGLE_SOLO, True)

    assert navigator_toggle_glyph(on) == POWER_GLYPH
    assert navigator_toggle_glyph(locked) == LOCK_GLYPH
    assert navigator_toggle_glyph(unlocked) == LOCK_OPEN_GLYPH
    assert navigator_toggle_glyph(solo) == SOLO_GLYPH
    assert navigator_toggle_color(on) == VALUE
    assert navigator_toggle_color(off) == MUTED
    assert navigator_toggle_color(blocked) == LOCKED
    assert navigator_toggle_color(locked) == LOCK_ICON
    assert navigator_toggle_color(unlocked) == MUTED
    assert navigator_toggle_tooltip(off) == "Off: click to turn on"
    inert = NavToggle(TOGGLE_ENABLED, True, inert=True)
    assert navigator_toggle_tooltip(inert) == "Timeline controls layer visibility"
    assert navigator_toggle_tooltip(blocked) == "Locked: unlock to change"


def test_strip_label_tooltip_names_double_click_arm() -> None:
    assert strip_label_tooltip(armed=False, locked=False) == (
        "Double-click to arm for recording, right-click for options"
    )
    assert strip_label_tooltip(armed=True, locked=False) == (
        "Double-click to disarm, right-click for options"
    )
    assert strip_label_tooltip(armed=False, locked=True) == (
        "Locked: unlock the timeline to arm, right-click for options"
    )


def test_strip_eye_tooltip_explains_overrides() -> None:
    assert strip_eye_tooltip(overridden=False, recording=False, armed=False) == (
        "Right-click to override visibility"
    )
    assert strip_eye_tooltip(overridden=True, recording=False, armed=False) == (
        "Override: click to show / hide, right-click to release"
    )
    assert strip_eye_tooltip(overridden=True, recording=True, armed=True) == (
        "Click to record show / hide"
    )
    assert strip_eye_tooltip(overridden=False, recording=True, armed=False) == (
        "Arm this row to record show / hide"
    )


def test_navigator_toggles_sit_in_fixed_columns() -> None:
    assert navigator_toggle_x(TOGGLE_LOCK, 100.0, 20.0, 2.0) == 80.0
    assert navigator_toggle_x(TOGGLE_SOLO, 100.0, 20.0, 2.0) == 58.0
    assert navigator_toggle_x(TOGGLE_ENABLED, 100.0, 20.0, 2.0) == 36.0


def test_header_toggle_changes_the_header_flag() -> None:
    controls = _make_controls(("layer_1",))
    post = RowDescriptor(RowKind.POST_FX_HEADER)
    assert controls.session.post_fx.enabled is True
    activate_header_toggle(controls, "enabled", post)
    assert controls.session.post_fx.enabled is False
    activate_header_toggle(controls, "lock", post)
    assert controls.session.post_fx.locked is True

    overlays = RowDescriptor(RowKind.OVERLAYS_HEADER)
    activate_header_toggle(controls, "solo", overlays)
    assert controls.session.overlay_solo is True
    activate_header_toggle(controls, "enabled", overlays)
    assert controls.session.overlays.opening_card.enabled is False
    assert controls.session.overlays.closing_card.enabled is False


def test_lock_mark_shows_only_in_preset_curation() -> None:
    session = _session()
    layer_id = layer_node_id("layer_1")
    node = next(
        node for node in build_navigator(session, {"layers"}) if node.id == layer_id
    )
    assert navigator_lock_mark(node) is None

    session.settings.editor_mode = "preset_curation"
    session.solo_slot = None
    curation = next(
        node
        for node in build_navigator(session, {"layers"})
        if node.slot is not None
    )
    assert curation.toggles == ()
    assert navigator_lock_mark(replace(curation, locked=True)) == "[lock]"


def test_only_expandable_nodes_show_a_twisty() -> None:
    nodes = build_navigator(_session(), {"layers"})
    layers = next(node for node in nodes if node.id == "layers")

    assert navigator_twisty(layers, {"layers"}) == TWISTY_EXPANDED
    assert navigator_twisty(layers, set()) == TWISTY_COLLAPSED
    for node in nodes:
        if node.expandable:
            continue
        assert navigator_twisty(node, {"layers", node.id}) is None


def test_tree_lines_for_a_root_are_empty() -> None:
    assert navigator_tree_lines((), 4.5, 16.0, 12.0, 0.0, 10.0, 20.0) == []


def test_tree_tee_runs_the_stem_through_the_row() -> None:
    assert navigator_tree_lines((True,), 4.5, 16.0, 12.0, 0.0, 10.0, 20.0) == [
        (4.5, 0.0, 4.5, 20.0),
        (4.5, 10.0, 12.0, 10.0),
    ]


def test_tree_elbow_stops_the_stem_at_the_arm() -> None:
    assert navigator_tree_lines((False,), 4.5, 16.0, 12.0, 0.0, 10.0, 20.0) == [
        (4.5, 0.0, 4.5, 10.0),
        (4.5, 10.0, 12.0, 10.0),
    ]


def test_tree_outer_rail_passes_only_while_its_branch_continues() -> None:
    open_outer = navigator_tree_lines((True, False), 4.5, 16.0, 28.0, 0.0, 10.0, 20.0)
    closed_outer = navigator_tree_lines(
        (False, False), 4.5, 16.0, 28.0, 0.0, 10.0, 20.0
    )

    assert open_outer == [
        (4.5, 0.0, 4.5, 20.0),
        (20.5, 0.0, 20.5, 10.0),
        (20.5, 10.0, 28.0, 10.0),
    ]
    assert closed_outer == open_outer[1:]


def test_navigator_height_scales_with_row_count() -> None:
    chrome = 8.0
    spacing = 4.0
    two_rows = int(2 * 20 + spacing + chrome)

    grown = navigator_height_for_rows(
        two_rows, 2, 3, chrome_px=chrome, spacing_px=spacing
    )

    assert grown == two_rows + 20 + int(spacing)
    assert (
        navigator_height_for_rows(0, 0, 3, chrome_px=chrome, spacing_px=spacing)
        == 0
    )


def test_inspector_selectable_id_changes_with_effect_and_preset() -> None:
    effect = RowDescriptor(
        RowKind.TRACK_EFFECT,
        slot="layer_1",
        effect_id="kaleido",
        driver_slug="kaleido",
    )
    other_effect = replace(effect, effect_id="mirror")
    preset = RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM,
        slot="layer_1",
        preset_index=0,
    )
    other_preset = replace(preset, preset_index=1)
    group = RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1")
    other_group = replace(group, slot="layer_2")
    card = RowDescriptor(
        RowKind.OVERLAY_CARD_HEADER,
        card="opening_card",
    )
    other_card = replace(card, card="closing_card")

    effect_id = inspector_selectable_id(effect)
    preset_id = inspector_selectable_id(preset)
    group_id = inspector_selectable_id(group)
    assert effect_id != inspector_selectable_id(other_effect)
    assert "kaleido" in effect_id
    assert effect_id != f"##row-{RowKind.TRACK_EFFECT.name}"
    assert preset_id != inspector_selectable_id(other_preset)
    assert "0" in preset_id
    assert group_id != inspector_selectable_id(other_group)
    assert group_id.startswith("##row-")
    assert "layer_1" in group_id
    assert inspector_selectable_id(card) != inspector_selectable_id(other_card)
    marker = RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=0)
    other_marker = replace(marker, marker_index=1)
    assert inspector_selectable_id(marker) != inspector_selectable_id(other_marker)


def test_scrollable_shell_flags_drop_only_the_scroll_bits() -> None:
    from imgui_bundle import imgui

    from cleave.viz.menu_rows import POPUP_FLAGS
    from cleave.viz.shell_host import _SHELL_FLAGS, shell_window_flags

    no_scrollbar = int(imgui.WindowFlags_.no_scrollbar)
    no_scroll_with_mouse = int(imgui.WindowFlags_.no_scroll_with_mouse)
    scroll_off = no_scrollbar | no_scroll_with_mouse
    kept = (
        int(imgui.WindowFlags_.no_title_bar)
        | int(imgui.WindowFlags_.no_resize)
        | int(imgui.WindowFlags_.no_move)
        | int(imgui.WindowFlags_.no_saved_settings)
        | int(imgui.WindowFlags_.no_focus_on_appearing)
        | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
        | int(imgui.WindowFlags_.no_nav)
    )

    fixed = shell_window_flags(_SHELL_FLAGS, scrollable=False)
    scrolling = shell_window_flags(_SHELL_FLAGS, scrollable=True)

    assert fixed == _SHELL_FLAGS
    assert fixed & scroll_off == scroll_off
    assert fixed & kept == kept
    assert scrolling & scroll_off == 0
    assert scrolling & kept == kept
    assert scrolling == _SHELL_FLAGS & ~scroll_off
    assert POPUP_FLAGS & no_scrollbar == no_scrollbar
    assert POPUP_FLAGS & int(imgui.WindowFlags_.no_nav) == int(
        imgui.WindowFlags_.no_nav
    )


def test_collapsing_layers_moves_selection_off_a_hidden_child() -> None:
    session = _session()
    child_id = layer_node_id("layer_1")
    collapsed = tuple(
        node.id for node in build_navigator(session, frozenset())
    )
    opened = tuple(node.id for node in build_navigator(session, {"layers"}))

    assert child_id not in collapsed
    assert child_id in opened
    assert selection_after_nav_collapse(collapsed, child_id, "layers") == "layers"
    assert selection_after_nav_collapse(collapsed, "post_fx", "layers") == "post_fx"
    assert (
        selection_after_nav_collapse(collapsed, "project.render", "layers")
        == "project.render"
    )


def test_drag_handle_lead_covers_glyph_plus_a_gap() -> None:
    assert drag_handle_lead(16.0, 8.0) == 3
    assert drag_handle_lead(15.0, 8.0) == 3
    assert drag_handle_lead(8.0, 8.0) == 2
    assert drag_handle_lead(16.0, 0.0) == 0


def test_path_row_icon_folder_for_preset_directory() -> None:
    assert path_row_icon(RowKind.TRACK_PRESET_DIR) == (FOLDER_GLYPH, PRESET_ICON)


def test_path_row_icon_file_for_presets_and_render_output() -> None:
    for kind in (
        RowKind.TRACK_PRESET,
        RowKind.TRACK_PRESET_LIST_ITEM,
        RowKind.PROJECT_RENDER_OUTPUT,
    ):
        assert path_row_icon(kind) == (FILE_GLYPH, PRESET_FILE_ICON)


def test_path_row_icon_none_for_other_rows() -> None:
    assert path_row_icon(RowKind.TRACK_PRESET_SWITCHING_TRIGGER) is None


def test_path_icon_color_dims_with_row() -> None:
    assert path_icon_color(PRESET_ICON, VALUE) == PRESET_ICON
    assert path_icon_color(PRESET_ICON, DISABLED) == DISABLED
    assert path_icon_color(PRESET_ICON, LOCKED) == LOCKED


def test_layer_enabled_row_is_inert_while_the_timeline_is_on() -> None:
    from types import SimpleNamespace

    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from cleave.viz.row_spec import row_inert

    enabled = RowDescriptor(RowKind.TRACK_ENABLED, slot="layer_1")
    solo = RowDescriptor(RowKind.TRACK_SOLO, slot="layer_1")
    on = SimpleNamespace(timeline=SimpleNamespace(enabled=True))
    off = SimpleNamespace(timeline=SimpleNamespace(enabled=False))
    assert row_inert(on, enabled) is True
    assert row_inert(off, enabled) is False
    assert row_inert(on, solo) is False


def test_scroll_clip_span_insets_by_window_padding() -> None:
    assert scroll_clip_span(100.0, 300.0, 8.0) == (108.0, 392.0)


def test_scroll_clip_span_never_inverts() -> None:
    top, bottom = scroll_clip_span(0.0, 10.0, 8.0)
    assert bottom == top == 8.0


def test_marker_token_spans_follow_the_fitted_text() -> None:
    assert marker_token_spans("[FU] [R:B]", "[FU] [R:B]") == [
        (0, 4, "[FU]"),
        (5, 10, "[R:B]"),
    ]
    assert marker_token_spans("[FU] [R:B]", "[FU] [R") == [
        (0, 4, "[FU]"),
        (5, 7, "[R:B]"),
    ]
    assert marker_token_spans("[FU] [R:B]", "[F") == [(0, 2, "[FU]")]
