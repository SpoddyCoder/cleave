"""Shell navigator and inspector header decisions. No ImGui window."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from cleave.preset_playlist import PresetPlaylist
from cleave.stems import StemSource
from cleave.viz.navigator import (
    HIDDEN_BADGE,
    SOLO_BADGE,
    build_navigator,
    layer_node_id,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_sections import (
    INSPECTOR_GROUP_COLLAPSED,
    INSPECTOR_GROUP_EXPANDED,
)
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.shell_host import (
    inspector_header,
    inspector_selectable_id,
    navigator_lock_mark,
    navigator_twisty,
    selection_after_nav_toggle,
)


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


def test_layer_breadcrumb_uses_navigator_label() -> None:
    nodes = build_navigator(_session())
    child = next(node for node in nodes if node.slot == "layer_2")

    header = inspector_header(nodes, child.id, curation=False)

    assert header.title == f"Layers > {child.label}"
    assert header.lock_label == "lock"
    assert header.slot == "layer_2"

    locked = next(node for node in nodes if node.slot == "layer_1")
    locked_header = inspector_header(nodes, locked.id, curation=False)
    assert locked_header.title == f"Layers > {locked.label}"
    assert locked_header.lock_label == "locked"
    assert locked_header.slot == "layer_1"


def test_lock_toggle_is_only_on_a_layer_outside_curation() -> None:
    session = _session()
    nodes = build_navigator(session)

    layers = inspector_header(nodes, "layers", curation=False)
    settings = inspector_header(nodes, "settings", curation=False)
    project = inspector_header(nodes, "project", curation=False)
    assert layers.title == "Layers"
    assert settings.title == "Settings"
    assert project.title == "Project"
    assert layers.lock_label is None
    assert settings.lock_label is None
    assert project.lock_label is None

    session.settings.editor_mode = "preset_curation"
    curated = build_navigator(session)
    focus = next(node for node in curated if node.slot is not None)
    header = inspector_header(curated, focus.id, curation=True)
    assert header.title == f"Layers > {focus.label}"
    assert header.lock_label is None


def test_lock_mark_is_separate_from_badges() -> None:
    nodes = {node.id: node for node in build_navigator(_session())}
    locked = nodes[layer_node_id("layer_1")]
    hidden = nodes[layer_node_id("layer_2")]
    solo = nodes[layer_node_id("layer_3")]
    markers = nodes["song_markers"]

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

    assert navigator_twisty(layers, {"layers"}) == INSPECTOR_GROUP_EXPANDED
    assert navigator_twisty(layers, set()) == INSPECTOR_GROUP_COLLAPSED
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

    effect_id = inspector_selectable_id(effect, group=False)
    preset_id = inspector_selectable_id(preset, group=False)
    group_id = inspector_selectable_id(group, group=True)
    assert effect_id != inspector_selectable_id(other_effect, group=False)
    assert "kaleido" in effect_id
    assert effect_id != f"##row-{RowKind.TRACK_EFFECT.name}"
    assert preset_id != inspector_selectable_id(other_preset, group=False)
    assert "0" in preset_id
    assert group_id != inspector_selectable_id(other_group, group=True)
    assert group_id.startswith("##grp-")
    assert "layer_1" in group_id
    assert inspector_selectable_id(card, group=True) != inspector_selectable_id(
        other_card, group=True
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
    assert (
        selection_after_nav_toggle(
            collapsed, child_id, "layers", expanded=False
        )
        == "layers"
    )
    assert (
        selection_after_nav_toggle(opened, child_id, "layers", expanded=True)
        == child_id
    )
    assert (
        selection_after_nav_toggle(
            collapsed, "settings", "layers", expanded=False
        )
        == "settings"
    )
