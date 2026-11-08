"""Navigator model: roots, child pages, expansion, and tree keys."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.preset_playlist import PresetPlaylist
from cleave.stems import StemSource
from cleave.viz.editor_mode_controls import curation_focus_slot
from cleave.viz.navigator import (
    HIDDEN_BADGE,
    SOLO_BADGE,
    TOGGLE_ENABLED,
    TOGGLE_LOCK,
    TOGGLE_SOLO,
    NavToggle,
    TOP_LEVEL_IDS,
    build_navigator,
    ancestor_ids,
    layer_node_id,
    layer_page_node_id,
    layer_page_of,
    layer_slot_of,
    navigator_row_bright,
    navigator_tree_rails,
    parent_id_of,
    root_id,
    visible_top_level_ids,
)
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.shell_focus import ShellRegion
from tests.cleave.viz.test_controls import _keydown, _make_controls


def _session() -> TuningSession:
    return TuningSession(layer_z_order=[])


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


def _two_layers() -> TuningSession:
    return TuningSession(
        layer_z_order=["layer_2", "layer_1"],
        layers={
            "layer_1": _layer("bass"),
            "layer_2": _layer("drums"),
        },
    )


def _all_open(session: TuningSession) -> set[str]:
    return set(TOP_LEVEL_IDS) | {layer_node_id(s) for s in session.layer_z_order}


def test_tree_rails_mark_tees_and_closing_elbows() -> None:
    session = _session()
    nodes = build_navigator(session, {"overlay", "layers"})
    rails = dict(zip((node.id for node in nodes), navigator_tree_rails(nodes)))

    assert rails["overlay"] == ()
    assert rails["overlay.opening_card"] == (True,)
    assert rails["overlay.closing_card"] == (False,)
    assert rails["layers"] == ()


def test_tree_rails_carry_the_outer_branch_past_nested_pages() -> None:
    session = _two_layers()
    first, second = session.layer_z_order
    nodes = build_navigator(session, _all_open(session))
    rails = dict(zip((node.id for node in nodes), navigator_tree_rails(nodes)))

    assert rails[layer_node_id(first)] == (True,)
    assert rails[layer_page_node_id(first, "preset_switching")] == (True, True)
    assert rails[layer_page_node_id(first, "effects")] == (True, False)
    assert rails[layer_node_id(second)] == (False,)
    assert rails[layer_page_node_id(second, "preset_switching")] == (False, True)
    assert rails[layer_page_node_id(second, "effects")] == (False, False)


def test_top_level_order_and_labels() -> None:
    session = _session()
    top = tuple(
        node for node in build_navigator(session, frozenset()) if node.depth == 0
    )

    assert TOP_LEVEL_IDS == (
        "overlay",
        "post_fx",
        "pattern_mask",
        "timeline",
        "layers",
    )
    assert visible_top_level_ids(session) == TOP_LEVEL_IDS
    assert tuple(node.id for node in top) == TOP_LEVEL_IDS
    assert tuple(node.label for node in top) == (
        "Overlay",
        "Post-FX",
        "Pattern Mask",
        "Timeline",
        "Layers",
    )
    assert tuple(node.expandable for node in top) == (
        True,
        True,
        False,
        True,
        True,
    )


def test_full_tree_order_and_labels() -> None:
    session = _two_layers()
    session.layers["layer_2"].preset_switching_trigger = "timer"
    nodes = build_navigator(session, _all_open(session) | {layer_node_id("layer_2")})

    assert tuple(node.label for node in nodes) == (
        "Overlay",
        "Opening Card",
        "Closing Card",
        "Post-FX",
        "Fade",
        "Highlight Rolloff",
        "Chroma Boost",
        "Visual Limiter",
        "Pattern Mask",
        "Timeline",
        "Beat / Bar Grid",
        "Cue Fades",
        "Song Markers",
        "Layers",
        "1  DRUMS",
        "Milkdrop Preset",
        "Preset Switching",
        "Preset List",
        "Compositing",
        "Cleave Effects",
        "2  BASS",
        "Milkdrop Preset",
        "Preset Switching",
        "Compositing",
        "Cleave Effects",
    )
    assert "render" not in {node.id for node in nodes}


def test_default_tree_opens_only_layers() -> None:
    nodes = build_navigator(_two_layers())
    assert tuple(node.id for node in nodes) == (
        *TOP_LEVEL_IDS,
        layer_node_id("layer_2"),
        layer_node_id("layer_1"),
    )


def test_node_id_helpers() -> None:
    page = layer_page_node_id("layer_1", "compositing")
    assert page == "layer:layer_1:compositing"
    assert layer_slot_of(page) == "layer_1"
    assert layer_slot_of(layer_node_id("layer_1")) == "layer_1"
    assert layer_slot_of("settings") is None
    assert layer_page_of(page) == "compositing"
    assert layer_page_of(layer_node_id("layer_1")) is None
    assert parent_id_of(page) == layer_node_id("layer_1")
    assert parent_id_of(layer_node_id("layer_1")) == "layers"
    assert parent_id_of("post_fx.fade") == "post_fx"
    assert parent_id_of("post_fx") is None
    assert root_id(page) == "layers"
    assert root_id("timeline.grid") == "timeline"
    assert root_id("pattern_mask") == "pattern_mask"
    assert ancestor_ids(page) == {layer_node_id("layer_1"), "layers"}
    assert ancestor_ids("settings") == set()


def test_song_markers_badge_is_marker_count() -> None:
    session = _session()
    markers = next(
        node
        for node in build_navigator(session, {"timeline"})
        if node.id == "timeline.song_markers"
    )
    assert markers.parent_id == "timeline"
    assert markers.depth == 1
    assert markers.badge == "0"

    session.song_markers.times = [1.0, 4.5, 9.0]
    nodes = {node.id: node for node in build_navigator(session, {"timeline"})}
    assert nodes["timeline.song_markers"].badge == "3"


def test_preset_curation_keeps_only_layers() -> None:
    session = _session()
    session.settings.editor_mode = "preset_curation"
    nodes = build_navigator(session, frozenset())

    assert visible_top_level_ids(session) == ("layers",)
    assert tuple(node.id for node in nodes) == ("layers",)
    assert nodes[0].expandable is True
    assert all(node.badge is None for node in nodes)


def test_layer_children_follow_z_order() -> None:
    nodes = build_navigator(_two_layers(), {"layers"})
    children = tuple(node for node in nodes if node.parent_id == "layers")

    assert tuple(node.slot for node in children) == ("layer_2", "layer_1")
    assert tuple(node.label for node in children) == ("1  DRUMS", "2  BASS")
    assert all(node.depth == 1 for node in children)
    assert all(node.expandable for node in children)


def test_roots_and_layer_rows_are_bright_but_not_their_children() -> None:
    open_id = layer_node_id("layer_1")
    nodes = build_navigator(_two_layers(), {"layers", "post_fx", open_id})

    for node in nodes:
        expected = node.depth == 0 or node.parent_id == "layers"
        assert navigator_row_bright(node) is expected
    assert any(node.depth == 1 and not navigator_row_bright(node) for node in nodes)
    assert any(node.depth == 2 and not navigator_row_bright(node) for node in nodes)


def test_open_layer_shows_its_pages_only() -> None:
    open_id = layer_node_id("layer_1")
    session = _two_layers()
    session.layers["layer_1"].preset_switching_trigger = "timer"
    nodes = build_navigator(session, {"layers", open_id})
    pages = tuple(node for node in nodes if node.depth == 2)

    assert tuple(node.id for node in pages) == (
        layer_page_node_id("layer_1", "milkdrop_preset"),
        layer_page_node_id("layer_1", "preset_switching"),
        layer_page_node_id("layer_1", "compositing"),
        layer_page_node_id("layer_1", "effects"),
    )
    assert all(node.parent_id == open_id for node in pages)
    assert all(node.slot == "layer_1" for node in pages)


def test_preset_list_page_nests_under_preset_switching() -> None:
    switching_id = layer_page_node_id("layer_1", "preset_switching")
    list_id = layer_page_node_id("layer_1", "preset_list")
    session = _two_layers()
    session.layers["layer_1"].preset_switching_trigger = "timer"
    nodes = build_navigator(session, {"layers", layer_node_id("layer_1")})
    ids = [node.id for node in nodes]
    by_id = {node.id: node for node in nodes}

    assert ids.index(list_id) == ids.index(switching_id) + 1
    assert by_id[list_id].depth == 3
    assert by_id[list_id].parent_id == switching_id
    assert by_id[switching_id].expandable is False
    assert parent_id_of(list_id) == switching_id
    assert ancestor_ids(list_id) == {
        "layers",
        layer_node_id("layer_1"),
        switching_id,
    }


def test_preset_list_page_hides_while_switching_is_off() -> None:
    open_id = layer_node_id("layer_1")
    nodes = build_navigator(_two_layers(), {"layers", open_id})
    assert layer_page_node_id("layer_1", "preset_list") not in {
        node.id for node in nodes
    }


def test_collapsed_tree_is_roots_only() -> None:
    nodes = build_navigator(_two_layers(), expanded=frozenset())
    assert tuple(node.id for node in nodes) == TOP_LEVEL_IDS


def test_curation_shows_only_the_focus_layer_without_pages() -> None:
    session = TuningSession(
        layer_z_order=["layer_2", "layer_1"],
        layers={
            "layer_1": _layer("bass"),
            "layer_2": _layer("vocals", locked=True),
        },
    )
    session.settings.editor_mode = "preset_curation"
    focus_id = layer_node_id("layer_2")
    nodes = build_navigator(session, {"layers", focus_id})
    children = tuple(node for node in nodes if node.parent_id == "layers")

    assert curation_focus_slot(session) == "layer_2"
    assert tuple(node.id for node in children) == (focus_id,)
    assert children[0].label == "1  VOCALS"
    assert children[0].locked is True
    assert children[0].toggles == ()
    assert children[0].expandable is False
    assert children[0].draggable is False
    assert not any(node.depth == 2 for node in nodes)


def _toggles(node) -> dict[str, NavToggle]:
    return {toggle.id: toggle for toggle in node.toggles}


def test_root_toggles_follow_session_and_replace_marks() -> None:
    session = _session()
    session.overlays.opening_card.enabled = False
    session.overlays.closing_card.enabled = False
    session.post_fx.enabled = False
    session.pattern_mask.enabled = False
    session.timeline.enabled = False
    session.overlay_solo = True
    session.overlays.locked = True
    session.post_fx.locked = True
    session.pattern_mask.locked = True
    session.timeline.locked = True
    nodes = {node.id: node for node in build_navigator(session)}

    overlay = _toggles(nodes["overlay"])
    assert tuple(overlay) == (TOGGLE_ENABLED, TOGGLE_SOLO, TOGGLE_LOCK)
    assert overlay[TOGGLE_ENABLED] == NavToggle(TOGGLE_ENABLED, False, True)
    assert overlay[TOGGLE_SOLO] == NavToggle(TOGGLE_SOLO, True)
    assert overlay[TOGGLE_LOCK] == NavToggle(TOGGLE_LOCK, True)
    for node_id in ("post_fx", "pattern_mask", "timeline"):
        toggles = _toggles(nodes[node_id])
        assert tuple(toggles) == (TOGGLE_ENABLED, TOGGLE_LOCK)
        assert toggles[TOGGLE_ENABLED] == NavToggle(TOGGLE_ENABLED, False, True)
        assert toggles[TOGGLE_LOCK] == NavToggle(TOGGLE_LOCK, True)
    for node_id in ("overlay", "post_fx", "pattern_mask", "timeline"):
        assert nodes[node_id].badge is None
        assert nodes[node_id].locked is False


def test_cards_have_their_own_enabled_toggle() -> None:
    session = _session()
    session.overlays.opening_card.enabled = False
    nodes = {node.id: node for node in build_navigator(session, {"overlay"})}

    assert nodes["overlay.opening_card"].toggles == (
        NavToggle(TOGGLE_ENABLED, False),
    )
    assert nodes["overlay.closing_card"].toggles == (
        NavToggle(TOGGLE_ENABLED, True),
    )
    assert nodes["overlay.opening_card"].badge is None


def test_other_pages_have_no_toggles() -> None:
    session = _session()
    expanded = {"layers", "post_fx", "settings", layer_node_id("layer_1")}
    nodes = build_navigator(session, expanded)
    with_toggles = {node.id for node in nodes if node.toggles}
    assert with_toggles == {
        "layers",
        "overlay",
        "post_fx",
        "pattern_mask",
        "timeline",
        *(layer_node_id(slot) for slot in session.layer_z_order),
    }


def test_layer_lock_and_visibility_badges() -> None:
    session = TuningSession(
        layer_z_order=["layer_1", "layer_2", "layer_3"],
        layers={
            "layer_1": _layer("drums", locked=True),
            "layer_2": _layer("bass", enabled=False),
            "layer_3": _layer("vocals", enabled=False),
        },
        solo_slot="layer_3",
    )
    nodes = {node.id: node for node in build_navigator(session, {"layers"})}

    assert nodes[layer_node_id("layer_1")].toggles == (
        NavToggle(TOGGLE_ENABLED, True, True),
        NavToggle(TOGGLE_SOLO, False),
        NavToggle(TOGGLE_LOCK, True),
    )
    assert nodes[layer_node_id("layer_2")].toggles == (
        NavToggle(TOGGLE_ENABLED, False),
        NavToggle(TOGGLE_SOLO, False),
        NavToggle(TOGGLE_LOCK, False),
    )
    assert nodes[layer_node_id("layer_3")].toggles[1] == NavToggle(TOGGLE_SOLO, True)
    for slot in ("layer_1", "layer_2", "layer_3"):
        node = nodes[layer_node_id(slot)]
        assert node.badge is None
        assert node.locked is False


def test_select_opens_ancestors_and_closes_nothing() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    nav = controls.navigator
    focus.nav_expanded = {"timeline"}

    nav.select("post_fx.fade")
    assert focus.nav_expanded == {"timeline", "post_fx"}

    page = layer_page_node_id("layer_2", "compositing")
    nav.select(page)
    assert focus.selected_id == page
    assert focus.nav_expanded == {
        "timeline",
        "post_fx",
        "layers",
        layer_node_id("layer_2"),
    }


def test_select_does_not_open_the_selected_node() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    focus.nav_expanded = set()

    controls.navigator.select("overlay")
    assert focus.nav_expanded == set()
    controls.navigator.select(layer_node_id("layer_1"))
    assert focus.nav_expanded == {"layers"}


def test_tree_up_down_does_not_wrap() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    nav = controls.navigator
    focus.region = ShellRegion.NAVIGATOR

    for _ in range(60):
        nav.handle_keydown(_keydown(pygame.K_UP))
    assert focus.selected_id == "overlay"

    seen = [focus.selected_id]
    for _ in range(60):
        nav.handle_keydown(_keydown(pygame.K_DOWN))
        if focus.selected_id == seen[-1]:
            break
        seen.append(focus.selected_id)
        assert focus.region is ShellRegion.NAVIGATOR

    assert seen == [node.id for node in build_navigator(controls.session, focus.nav_expanded)]
    last = layer_node_id("layer_2")
    assert seen[-1] == last
    nav.handle_keydown(_keydown(pygame.K_DOWN))
    assert focus.selected_id == last


def test_left_right_expand_move_collapse_and_parent() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    focus.nav_expanded.clear()
    focus.selected_id = "layers"
    focus.region = ShellRegion.NAVIGATOR
    nav = controls.navigator

    nav.handle_keydown(_keydown(pygame.K_RIGHT))
    assert focus.selected_id == "layers"
    assert focus.nav_expanded == {"layers"}

    nav.handle_keydown(_keydown(pygame.K_RIGHT))
    assert focus.selected_id == layer_node_id("layer_1")
    assert focus.nav_expanded == {"layers"}

    nav.handle_keydown(_keydown(pygame.K_RIGHT))
    assert focus.selected_id == layer_node_id("layer_1")
    assert focus.nav_expanded == {"layers", layer_node_id("layer_1")}

    nav.handle_keydown(_keydown(pygame.K_LEFT))
    assert focus.selected_id == layer_node_id("layer_1")
    assert layer_node_id("layer_1") not in focus.nav_expanded

    nav.handle_keydown(_keydown(pygame.K_LEFT))
    assert focus.selected_id == "layers"
    assert "layers" in focus.nav_expanded

    nav.handle_keydown(_keydown(pygame.K_LEFT))
    assert focus.selected_id == "layers"
    assert "layers" not in focus.nav_expanded

    nav.handle_keydown(_keydown(pygame.K_LEFT))
    assert focus.selected_id == "layers"
    assert focus.region is ShellRegion.NAVIGATOR


def test_layer_rows_are_draggable_unless_locked() -> None:
    session = TuningSession(
        layer_z_order=["layer_2", "layer_1"],
        layers={
            "layer_1": _layer("bass"),
            "layer_2": _layer("vocals", locked=True),
        },
    )
    nodes = build_navigator(session, {"layers"})
    rows = {node.slot: node for node in nodes if node.parent_id == "layers"}

    assert all(node.draggable for node in rows.values())
    assert rows["layer_1"].drag_blocked is False
    assert rows["layer_2"].drag_blocked is True
    assert not any(node.draggable for node in nodes if node.parent_id != "layers")
