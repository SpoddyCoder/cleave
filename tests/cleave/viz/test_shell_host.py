"""Shell navigator and inspector header decisions. No ImGui window."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cleave.preset_playlist import PresetPlaylist
from cleave.stems import StemSource
from cleave.viz.navigator import (
    HIDDEN_BADGE,
    SOLO_BADGE,
    TWISTY_COLLAPSED,
    TWISTY_EXPANDED,
    build_navigator,
    expansion_path,
    layer_node_id,
    layer_page_node_id,
)
from cleave.viz.row_hotkeys import activate_inspector_chip
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.shell_host import (
    inspector_header,
    inspector_selectable_id,
    navigator_lock_mark,
    navigator_twisty,
    selectable_wash,
    selection_after_nav_collapse,
)
from cleave.viz.theme import FOCUS_WASH_ALPHA, HIGHLIGHT, SELECTED_WASH_ALPHA
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


def _chips(header) -> dict[str, object]:
    return {chip.id: chip for chip in header.chips}


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

    header = inspector_header(nodes, child.id, session, curation=False)

    assert header.title == f"Layers > {child.label}"
    assert _chips(header)["enabled"].label == "off"
    assert _chips(header)["lock"].label == "lock"

    locked = next(node for node in nodes if node.slot == "layer_1")
    locked_header = inspector_header(nodes, locked.id, session, curation=False)
    assert locked_header.title == f"Layers > {locked.label}"
    assert _chips(locked_header)["lock"].label == "locked"
    assert _chips(locked_header)["enabled"].label == "on"


def test_settings_project_and_layers_have_no_chips() -> None:
    session = _session()
    nodes = build_navigator(session)

    layers = inspector_header(nodes, "layers", session, curation=False)
    settings = inspector_header(nodes, "settings", session, curation=False)
    project = inspector_header(nodes, "project", session, curation=False)
    assert layers.title == "Layers"
    assert settings.title == "Settings"
    assert project.title == "Project"
    assert layers.chips == ()
    assert settings.chips == ()
    assert project.chips == ()


def test_child_pages_breadcrumb_and_show_owner_chips() -> None:
    session = _session()
    page = layer_page_node_id("layer_3", "compositing")
    nodes = build_navigator(session, expansion_path(page))
    layer = next(node for node in nodes if node.id == layer_node_id("layer_3"))

    header = inspector_header(nodes, page, session, curation=False)
    assert header.title == f"Layers > {layer.label} > Compositing"
    assert tuple(_chips(header)) == ("enabled", "solo", "lock")
    assert header.descriptor == RowDescriptor(RowKind.TRACK_HEADER, slot="layer_3")

    fade = inspector_header(
        build_navigator(session, {"post_fx"}),
        "post_fx.fade",
        session,
        curation=False,
    )
    assert fade.title == "Post-FX > Fade"
    assert fade.descriptor == RowDescriptor(RowKind.RENDER_POST_FX_HEADER)

    ui = inspector_header(
        build_navigator(session, {"settings"}),
        "settings.ui",
        session,
        curation=False,
    )
    assert ui.title == "Settings > UI"
    assert ui.chips == ()


def test_layer_header_has_enabled_solo_and_lock_chips() -> None:
    session = _session()
    nodes = build_navigator(session, {"layers", "timeline"})
    solo = inspector_header(
        nodes, layer_node_id("layer_3"), session, curation=False
    )
    chips = _chips(solo)
    assert tuple(chips) == ("enabled", "solo", "lock")
    assert chips["enabled"].label == "off"
    assert chips["enabled"].active is False
    assert chips["solo"].label == "solo"
    assert chips["solo"].active is True
    assert chips["lock"].label == "lock"
    assert chips["lock"].active is False


def test_render_block_headers_have_enabled_solo_and_lock_chips() -> None:
    session = _session()
    nodes = build_navigator(session)
    overlays = _chips(
        inspector_header(nodes, "overlay", session, curation=False)
    )
    assert tuple(overlays) == ("enabled", "solo", "lock")
    assert overlays["enabled"].label == "on"
    assert overlays["enabled"].active is True
    assert overlays["solo"].label == "solo"
    assert overlays["solo"].active is False
    assert overlays["lock"].label == "lock"

    session.render_overlays.opening_card.enabled = False
    session.render_overlays.closing_card.enabled = False
    session.render_overlay_solo = True
    session.render_overlays.locked = True
    solo_off = _chips(
        inspector_header(nodes, "overlay", session, curation=False)
    )
    assert solo_off["enabled"].label == "off"
    assert solo_off["enabled"].active is False
    assert solo_off["solo"].active is True
    assert solo_off["lock"].label == "locked"

    post = _chips(inspector_header(nodes, "post_fx", session, curation=False))
    mask = _chips(
        inspector_header(nodes, "pattern_mask", session, curation=False)
    )
    assert tuple(post) == ("enabled", "lock")
    assert tuple(mask) == ("enabled", "lock")
    assert post["enabled"].label == "on"
    assert mask["enabled"].label == "off"
    assert "solo" not in post
    assert "solo" not in mask


def test_timeline_inspector_header_chips_follow_enabled_and_lock() -> None:
    session = _session()
    nodes = build_navigator(session)
    header = inspector_header(nodes, "timeline", session, curation=False)
    chips = _chips(header)
    assert header.title == "Timeline"
    assert tuple(chips) == ("enabled", "lock")
    assert chips["enabled"].label == "on"
    assert chips["enabled"].active is True
    assert chips["lock"].label == "lock"
    assert chips["lock"].active is False

    session.timeline.enabled = False
    session.timeline.locked = True
    off = _chips(
        inspector_header(nodes, "timeline", session, curation=False)
    )
    assert off["enabled"].label == "off"
    assert off["enabled"].active is False
    assert off["lock"].label == "locked"
    assert off["lock"].active is True

    markers = inspector_header(
        build_navigator(session, {"timeline"}),
        "timeline.song_markers",
        session,
        curation=False,
    )
    assert markers.title == "Timeline > Song Markers"
    assert tuple(_chips(markers)) == ("enabled", "lock")

    controls = _make_controls(("layer_1",), timeline_enabled=True)
    assert controls.session.timeline.panel_open is False
    desc = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    activate_inspector_chip(controls, "enabled", desc)
    assert controls.session.timeline.enabled is False
    assert controls.session.timeline.panel_open is False
    activate_inspector_chip(controls, "enabled", desc)
    assert controls.session.timeline.enabled is True
    assert controls.session.timeline.panel_open is True
    activate_inspector_chip(controls, "lock", desc)
    assert controls.session.timeline.locked is True


def test_preset_curation_omits_header_chips() -> None:
    session = _session()
    nodes = build_navigator(session, {"layers", "timeline"})
    layer = inspector_header(
        nodes, layer_node_id("layer_1"), session, curation=True
    )
    overlays = inspector_header(nodes, "overlay", session, curation=True)
    assert layer.title.startswith("Layers > ")
    assert layer.chips == ()
    assert overlays.chips == ()


def test_inspector_chip_click_toggles_the_header_flag() -> None:
    controls = _make_controls(("layer_1",))
    post = RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    assert controls.session.render_post_fx.enabled is True
    activate_inspector_chip(controls, "enabled", post)
    assert controls.session.render_post_fx.enabled is False
    activate_inspector_chip(controls, "lock", post)
    assert controls.session.render_post_fx.locked is True

    overlays = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    activate_inspector_chip(controls, "solo", overlays)
    assert controls.session.render_overlay_solo is True
    activate_inspector_chip(controls, "enabled", overlays)
    assert controls.session.render_overlays.opening_card.enabled is False
    assert controls.session.render_overlays.closing_card.enabled is False


def test_lock_mark_is_separate_from_badges() -> None:
    session = _session()
    nodes = {
        node.id: node for node in build_navigator(session, {"layers", "timeline"})
    }
    locked = nodes[layer_node_id("layer_1")]
    hidden = nodes[layer_node_id("layer_2")]
    solo = nodes[layer_node_id("layer_3")]
    markers = nodes["timeline.song_markers"]

    assert navigator_lock_mark(locked) == "[lock]"
    assert locked.badge is None
    assert navigator_lock_mark(hidden) is None
    assert hidden.badge == HIDDEN_BADGE
    assert navigator_lock_mark(solo) is None
    assert solo.badge == SOLO_BADGE
    assert navigator_lock_mark(markers) is None
    assert markers.badge == "2"


def test_only_expandable_nodes_show_a_twisty() -> None:
    nodes = build_navigator(_session(), {"layers"})
    layers = next(node for node in nodes if node.id == "layers")

    assert navigator_twisty(layers, {"layers"}) == TWISTY_EXPANDED
    assert navigator_twisty(layers, set()) == TWISTY_COLLAPSED
    for node in nodes:
        if node.expandable:
            continue
        assert navigator_twisty(node, {"layers", node.id}) is None


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
        RowKind.RENDER_OVERLAY_CARD_HEADER,
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


def test_scrollable_shell_flags_drop_only_the_scroll_bits() -> None:
    from imgui_bundle import imgui

    from cleave.viz.shell_host import _POPUP_FLAGS, _SHELL_FLAGS, shell_window_flags

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
    assert _POPUP_FLAGS & no_scrollbar == no_scrollbar
    assert _POPUP_FLAGS & int(imgui.WindowFlags_.no_nav) == int(
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
    assert selection_after_nav_collapse(collapsed, "settings", "layers") == "settings"
