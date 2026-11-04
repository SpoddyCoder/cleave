"""Navigator model: roots, child pages, accordion, and tree keys."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.preset_playlist import PresetPlaylist
from cleave.stems import StemSource
from cleave.viz.editor_mode_controls import curation_focus_slot
from cleave.viz.navigator import (
    HIDDEN_BADGE,
    OFF_BADGE,
    SOLO_BADGE,
    TOP_LEVEL_IDS,
    build_navigator,
    expansion_path,
    layer_node_id,
    layer_page_node_id,
    layer_page_of,
    layer_slot_of,
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


def test_top_level_order_labels_and_inspectors() -> None:
    session = _session()
    top = tuple(
        node for node in build_navigator(session, frozenset()) if node.depth == 0
    )

    assert TOP_LEVEL_IDS == (
        "settings",
        "project",
        "overlay",
        "post_fx",
        "pattern_mask",
        "timeline",
        "layers",
    )
    assert visible_top_level_ids(session) == TOP_LEVEL_IDS
    assert tuple(node.id for node in top) == TOP_LEVEL_IDS
    assert tuple(node.label for node in top) == (
        "Settings",
        "Project",
        "Overlay",
        "Post-FX",
        "Pattern Mask",
        "Timeline",
        "Layers",
    )
    assert tuple(node.has_inspector for node in top) == (
        False,
        False,
        True,
        True,
        True,
        True,
        True,
    )
    assert tuple(node.expandable for node in top) == (
        True,
        True,
        True,
        True,
        False,
        True,
        True,
    )


def test_full_tree_order_and_labels() -> None:
    session = _two_layers()
    nodes = build_navigator(session, _all_open(session) | {layer_node_id("layer_2")})

    assert tuple(node.label for node in nodes) == (
        "Settings",
        "Editor Window",
        "UI",
        "Latency Compensation",
        "Project",
        "ProjectM",
        "Compositor",
        "Render Project",
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
        "Timeline Preset",
        "Layers",
        "1  DRUMS",
        "Preset Switching",
        "Compositing",
        "Cleave Effects",
        "2  BASS",
        "Preset Switching",
        "Compositing",
        "Cleave Effects",
    )
    assert "render" not in {node.id for node in nodes}


def test_default_tree_opens_only_settings() -> None:
    nodes = build_navigator(_two_layers())
    assert tuple(node.id for node in nodes) == (
        "settings",
        "settings.editor_window",
        "settings.ui",
        "settings.latency",
        "project",
        "overlay",
        "post_fx",
        "pattern_mask",
        "timeline",
        "layers",
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
    assert expansion_path(page) == {page, layer_node_id("layer_1"), "layers"}


def test_song_markers_badge_is_marker_count() -> None:
    session = _session()
    markers = next(
        node
        for node in build_navigator(session, {"timeline"})
        if node.id == "timeline.song_markers"
    )
    assert markers.parent_id == "timeline"
    assert markers.depth == 1
    assert markers.has_inspector is True
    assert markers.badge == "0"

    session.song_markers.times = [1.0, 4.5, 9.0]
    nodes = {node.id: node for node in build_navigator(session, {"timeline"})}
    assert nodes["timeline.song_markers"].badge == "3"


def test_preset_curation_keeps_settings_and_layers() -> None:
    session = _session()
    session.settings.editor_mode = "preset_curation"
    nodes = build_navigator(session, frozenset())

    assert visible_top_level_ids(session) == ("settings", "layers")
    assert tuple(node.id for node in nodes) == ("settings", "layers")
    assert tuple(node.label for node in nodes) == ("Settings", "Layers")
    assert nodes[0].has_inspector is False
    assert nodes[1].has_inspector is True
    assert nodes[1].expandable is True
    assert all(node.badge is None for node in nodes)


def test_layer_children_follow_z_order() -> None:
    nodes = build_navigator(_two_layers(), {"layers"})
    children = tuple(node for node in nodes if node.parent_id == "layers")

    assert tuple(node.slot for node in children) == ("layer_2", "layer_1")
    assert tuple(node.label for node in children) == ("1  DRUMS", "2  BASS")
    assert all(node.depth == 1 for node in children)
    assert all(node.has_inspector for node in children)
    assert all(node.expandable for node in children)


def test_open_layer_shows_its_pages_only() -> None:
    open_id = layer_node_id("layer_1")
    nodes = build_navigator(_two_layers(), {"layers", open_id})
    pages = tuple(node for node in nodes if node.depth == 2)

    assert tuple(node.id for node in pages) == (
        layer_page_node_id("layer_1", "preset_switching"),
        layer_page_node_id("layer_1", "compositing"),
        layer_page_node_id("layer_1", "effects"),
    )
    assert all(node.parent_id == open_id for node in pages)
    assert all(node.slot == "layer_1" for node in pages)


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
    assert children[0].expandable is False
    assert not any(node.depth == 2 for node in nodes)


def test_timeline_lock_follows_session_and_has_no_badge() -> None:
    session = _session()
    session.timeline.enabled = False
    session.timeline.locked = True
    timeline = next(node for node in build_navigator(session) if node.id == "timeline")

    assert timeline.badge is None
    assert timeline.locked is True

    session.timeline.locked = False
    unlocked = next(node for node in build_navigator(session) if node.id == "timeline")
    assert unlocked.locked is False


def test_off_solo_and_lock_marks() -> None:
    session = _session()
    session.overlays.opening_card.enabled = False
    session.overlays.closing_card.enabled = False
    session.post_fx.enabled = False
    session.pattern_mask.enabled = False
    nodes = {node.id: node for node in build_navigator(session, {"overlay"})}

    assert nodes["overlay"].badge == OFF_BADGE
    assert nodes["overlay.opening_card"].badge == OFF_BADGE
    assert nodes["overlay.closing_card"].badge == OFF_BADGE
    assert nodes["post_fx"].badge == OFF_BADGE
    assert nodes["pattern_mask"].badge == OFF_BADGE

    session.overlay_solo = True
    solo = {node.id: node for node in build_navigator(session)}
    assert solo["overlay"].badge == SOLO_BADGE

    session.overlays.locked = True
    session.post_fx.locked = True
    session.pattern_mask.locked = True
    locked = {node.id: node for node in build_navigator(session)}
    assert locked["overlay"].locked is True
    assert locked["post_fx"].locked is True
    assert locked["pattern_mask"].locked is True


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

    assert nodes[layer_node_id("layer_1")].locked is True
    assert nodes[layer_node_id("layer_1")].badge is None
    assert nodes[layer_node_id("layer_2")].badge == HIDDEN_BADGE
    assert nodes[layer_node_id("layer_3")].badge == SOLO_BADGE


def test_select_closes_other_branches() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    nav = controls.navigator

    nav.select("post_fx.fade")
    assert focus.nav_expanded == {"post_fx", "post_fx.fade"}

    nav.select(layer_page_node_id("layer_2", "compositing"))
    assert focus.selected_id == layer_page_node_id("layer_2", "compositing")
    assert focus.nav_expanded == {
        "layers",
        layer_node_id("layer_2"),
        layer_page_node_id("layer_2", "compositing"),
    }
    ids = {node.id for node in build_navigator(controls.session, focus.nav_expanded)}
    assert "post_fx.fade" not in ids
    assert layer_page_node_id("layer_1", "compositing") not in ids


def test_tree_up_down_does_not_wrap() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    nav = controls.navigator
    focus.region = ShellRegion.NAVIGATOR

    nav.handle_keydown(_keydown(pygame.K_UP))
    assert focus.selected_id == "settings"

    seen = [focus.selected_id]
    for _ in range(60):
        nav.handle_keydown(_keydown(pygame.K_DOWN))
        if focus.selected_id == seen[-1]:
            break
        seen.append(focus.selected_id)
        assert focus.region is ShellRegion.NAVIGATOR

    assert seen[:5] == [
        "settings",
        "settings.editor_window",
        "settings.ui",
        "settings.latency",
        "project",
    ]
    last = layer_page_node_id("layer_2", "effects")
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
