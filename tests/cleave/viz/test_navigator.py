"""Navigator model: top-level ids, layer children, and tree keys."""

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
    layer_node_id,
    overlay_card_node_id,
    visible_top_level_ids,
)
from cleave.viz.row_kinds import RowKind
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.shell_focus import ShellRegion
from tests.cleave.viz.test_controls import _keydown, _make_controls


def _session() -> TuningSession:
    return TuningSession(layer_z_order=[])


def test_top_level_ids_in_order() -> None:
    session = _session()
    nodes = build_navigator(session)
    top = tuple(node for node in nodes if node.depth == 0)

    assert TOP_LEVEL_IDS == (
        "settings",
        "project",
        "render",
        "layers",
        "song_markers",
    )
    assert visible_top_level_ids(session) == TOP_LEVEL_IDS
    assert tuple(node.id for node in top) == TOP_LEVEL_IDS
    assert tuple(node.label for node in top) == (
        "Settings",
        "Project",
        "Render",
        "Layers",
        "Song markers",
    )
    assert tuple(node.has_inspector for node in top) == (
        True,
        True,
        False,
        True,
        True,
    )
    assert tuple(node.expandable for node in top) == (
        False,
        False,
        True,
        True,
        False,
    )
    assert all(
        node.parent_id is None and node.slot is None and node.locked is False
        for node in top
    )
    assert top[0].badge is None
    assert top[1].badge is None
    assert top[2].badge is None
    assert top[3].badge is None


def test_song_markers_badge_is_marker_count() -> None:
    empty = _session()
    markers = build_navigator(empty)[-1]
    assert markers.id == "song_markers"
    assert markers.has_inspector is True
    assert markers.badge == "0"

    session = _session()
    session.song_markers.times = [1.0, 4.5, 9.0]
    nodes = build_navigator(session)
    assert nodes[-1].id == "song_markers"
    assert nodes[-1].has_inspector is True
    assert nodes[-1].badge == "3"


def test_preset_curation_omits_project_render_and_song_markers() -> None:
    session = _session()
    session.settings.editor_mode = "preset_curation"
    nodes = build_navigator(session)

    assert visible_top_level_ids(session) == ("settings", "layers")
    assert tuple(node.id for node in nodes) == ("settings", "layers")
    assert tuple(node.label for node in nodes) == ("Settings", "Layers")
    assert nodes[0].has_inspector is True
    assert nodes[1].has_inspector is True
    assert nodes[1].expandable is True
    assert all(node.badge is None for node in nodes)
    assert all(node.depth == 0 for node in nodes)


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


def test_layer_children_follow_z_order() -> None:
    session = TuningSession(
        layer_z_order=["layer_2", "layer_1"],
        layers={
            "layer_1": _layer("bass"),
            "layer_2": _layer("drums"),
        },
    )
    session.song_markers.times = [1.0, 4.0]
    nodes = build_navigator(session)
    children = tuple(node for node in nodes if node.parent_id == "layers")

    assert tuple(node.id for node in nodes) == (
        "settings",
        "project",
        "render",
        "render.overlays",
        "render.post_fx",
        "render.pattern_mask",
        "render.timeline",
        "layers",
        layer_node_id("layer_2"),
        layer_node_id("layer_1"),
        "song_markers",
    )
    assert tuple(node.slot for node in children) == ("layer_2", "layer_1")
    assert tuple(node.label for node in children) == ("1  DRUMS", "2  BASS")
    assert all(node.depth == 1 for node in children)
    assert all(node.parent_id == "layers" for node in children)
    assert all(node.has_inspector for node in children)
    assert all(not node.expandable for node in children)
    assert nodes[-1].id == "song_markers"
    assert nodes[-1].badge == "2"


def test_collapsed_layers_omits_children() -> None:
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={"layer_1": _layer("drums")},
    )
    nodes = build_navigator(session, expanded=frozenset())
    assert tuple(node.id for node in nodes) == TOP_LEVEL_IDS
    assert all(node.parent_id is None for node in nodes)


def test_curation_shows_only_the_focus_layer() -> None:
    session = TuningSession(
        layer_z_order=["layer_2", "layer_1"],
        layers={
            "layer_1": _layer("bass"),
            "layer_2": _layer("vocals", locked=True),
        },
    )
    session.settings.editor_mode = "preset_curation"
    nodes = build_navigator(session)
    children = tuple(node for node in nodes if node.parent_id == "layers")
    focus = curation_focus_slot(session)

    assert tuple(node.id for node in nodes if node.depth == 0) == ("settings", "layers")
    assert focus == "layer_2"
    assert len(children) == 1
    assert children[0].id == layer_node_id("layer_2")
    assert children[0].slot == focus
    assert children[0].label == "1  VOCALS"
    assert children[0].locked is True
    assert children[0].has_inspector is True


def test_render_children_follow_overlays_post_fx_and_pattern_mask() -> None:
    session = _session()
    nodes = build_navigator(session)
    children = tuple(node for node in nodes if node.parent_id == "render")

    assert tuple(node.id for node in nodes) == (
        "settings",
        "project",
        "render",
        "render.overlays",
        "render.post_fx",
        "render.pattern_mask",
        "render.timeline",
        "layers",
        "song_markers",
    )
    assert tuple(node.id for node in children) == (
        "render.overlays",
        "render.post_fx",
        "render.pattern_mask",
        "render.timeline",
    )
    assert tuple(node.label for node in children) == (
        "Overlays",
        "Post-FX",
        "Pattern mask",
        "Timeline",
    )
    assert all(node.depth == 1 for node in children)
    assert all(node.has_inspector for node in children)
    assert all(node.slot is None for node in children)
    assert children[0].expandable is True
    assert children[1].expandable is False
    assert children[2].expandable is False
    assert children[3].expandable is False
    timeline = children[3]
    assert timeline.has_inspector is True
    assert timeline.badge is None
    assert timeline.locked is False
    assert not any(node.parent_id == "render.overlays" for node in nodes)


def test_render_timeline_lock_follows_session_and_has_no_badge() -> None:
    session = _session()
    session.timeline.enabled = False
    session.timeline.locked = True
    children = tuple(
        node for node in build_navigator(session) if node.parent_id == "render"
    )
    timeline = children[-1]

    assert timeline.id == "render.timeline"
    assert timeline.label == "Timeline"
    assert timeline.depth == 1
    assert timeline.parent_id == "render"
    assert timeline.has_inspector is True
    assert timeline.badge is None
    assert timeline.locked is True
    assert timeline.expandable is False

    session.timeline.locked = False
    session.timeline.enabled = True
    unlocked = next(
        node for node in build_navigator(session) if node.id == "render.timeline"
    )
    assert unlocked.locked is False
    assert unlocked.badge is None


def test_overlay_cards_follow_opening_then_closing() -> None:
    session = _session()
    nodes = build_navigator(
        session, expanded={"render", "render.overlays", "layers"}
    )
    cards = tuple(node for node in nodes if node.parent_id == "render.overlays")

    assert tuple(node.id for node in cards) == (
        overlay_card_node_id("opening_card"),
        overlay_card_node_id("closing_card"),
    )
    assert tuple(node.label for node in cards) == ("opening card", "closing card")
    assert all(node.depth == 2 and node.has_inspector for node in cards)
    assert all(node.slot is None and node.locked is False for node in cards)
    assert all(not node.expandable for node in cards)
    overlays = next(node for node in nodes if node.id == "render.overlays")
    post_fx = next(node for node in nodes if node.id == "render.post_fx")
    assert nodes.index(cards[0]) > nodes.index(overlays)
    assert nodes.index(cards[1]) < nodes.index(post_fx)


def test_render_off_solo_and_lock_marks() -> None:
    session = _session()
    session.render_overlays.opening_card.enabled = False
    session.render_overlays.closing_card.enabled = False
    session.render_post_fx.enabled = False
    session.render_pattern_mask.enabled = False
    nodes = {
        node.id: node
        for node in build_navigator(
            session, expanded={"render", "render.overlays", "layers"}
        )
    }

    assert nodes["render.overlays"].badge == OFF_BADGE
    assert nodes["render.post_fx"].badge == OFF_BADGE
    assert nodes["render.pattern_mask"].badge == OFF_BADGE
    opening = nodes[overlay_card_node_id("opening_card")]
    closing = nodes[overlay_card_node_id("closing_card")]
    assert opening.badge == OFF_BADGE
    assert closing.badge == OFF_BADGE
    assert opening.locked is False
    assert closing.locked is False

    session.render_overlay_solo = True
    solo = {
        node.id: node
        for node in build_navigator(
            session, expanded={"render", "render.overlays", "layers"}
        )
    }
    assert solo["render.overlays"].badge == SOLO_BADGE
    assert solo[overlay_card_node_id("opening_card")].badge == OFF_BADGE

    session.render_overlays.locked = True
    session.render_post_fx.locked = True
    session.render_pattern_mask.locked = True
    locked = {
        node.id: node
        for node in build_navigator(
            session, expanded={"render", "render.overlays", "layers"}
        )
    }
    assert locked["render.overlays"].locked is True
    assert locked["render.post_fx"].locked is True
    assert locked["render.pattern_mask"].locked is True
    assert locked[overlay_card_node_id("opening_card")].locked is False
    assert locked[overlay_card_node_id("closing_card")].locked is False


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
    nodes = {node.id: node for node in build_navigator(session)}

    assert nodes[layer_node_id("layer_1")].locked is True
    assert nodes[layer_node_id("layer_1")].badge is None
    assert nodes[layer_node_id("layer_2")].locked is False
    assert nodes[layer_node_id("layer_2")].badge == HIDDEN_BADGE
    assert nodes[layer_node_id("layer_3")].badge == SOLO_BADGE
    assert nodes["song_markers"].badge == "0"

    session.settings.editor_mode = "preset_curation"
    curated = {
        node.id: node
        for node in build_navigator(session)
        if node.parent_id == "layers"
    }
    assert tuple(curated) == (layer_node_id("layer_1"),)
    assert curated[layer_node_id("layer_1")].locked is True


def test_tree_up_down_does_not_wrap() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    nav = controls.navigator
    nav.select("render")
    assert controls.focus_descriptor.kind is RowKind.RENDER_TIMELINE_HEADER
    focus.selected_id = "settings"
    focus.region = ShellRegion.NAVIGATOR

    nav.handle_keydown(_keydown(pygame.K_UP))
    assert focus.selected_id == "settings"
    assert focus.region is ShellRegion.NAVIGATOR

    seen = [focus.selected_id]
    for _ in range(12):
        nav.handle_keydown(_keydown(pygame.K_DOWN))
        if focus.selected_id == seen[-1]:
            break
        seen.append(focus.selected_id)
        assert focus.region is ShellRegion.NAVIGATOR
        if focus.selected_id == "layers" or focus.selected_id.startswith("layer:"):
            assert controls.focus_descriptor.kind is RowKind.RENDER_TIMELINE_HEADER

    nodes = build_navigator(controls.session, focus.nav_expanded)
    assert seen == [node.id for node in nodes]
    assert focus.selected_id == "song_markers"
    nav.handle_keydown(_keydown(pygame.K_DOWN))
    assert focus.selected_id == "song_markers"
    assert focus.region is ShellRegion.NAVIGATOR
    assert controls.focus_descriptor.kind is RowKind.RENDER_TIMELINE_HEADER


def test_left_right_expand_move_collapse_and_parent() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    focus.nav_expanded.clear()
    focus.selected_id = "settings"
    focus.region = ShellRegion.NAVIGATOR
    nav = controls.navigator

    nav.handle_keydown(_keydown(pygame.K_RIGHT))
    assert focus.selected_id == "settings"
    assert focus.nav_expanded == set()

    focus.selected_id = "layers"
    nav.handle_keydown(_keydown(pygame.K_RIGHT))
    assert focus.selected_id == "layers"
    assert focus.nav_expanded == {"layers"}
    expanded_ids = tuple(
        node.id
        for node in build_navigator(controls.session, focus.nav_expanded)
    )
    assert layer_node_id("layer_1") in expanded_ids
    assert layer_node_id("layer_2") in expanded_ids

    nav.handle_keydown(_keydown(pygame.K_RIGHT))
    assert focus.selected_id == layer_node_id("layer_1")
    assert "layers" in focus.nav_expanded

    nav.handle_keydown(_keydown(pygame.K_LEFT))
    assert focus.selected_id == "layers"
    assert "layers" in focus.nav_expanded

    nav.handle_keydown(_keydown(pygame.K_LEFT))
    assert focus.selected_id == "layers"
    assert "layers" not in focus.nav_expanded

    nav.handle_keydown(_keydown(pygame.K_LEFT))
    assert focus.selected_id == "layers"
    assert focus.region is ShellRegion.NAVIGATOR
