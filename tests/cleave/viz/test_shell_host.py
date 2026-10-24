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
    overlay_card_node_id,
)
from cleave.viz.row_hotkeys import activate_inspector_chip
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import row_lock_section
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


def test_layer_breadcrumb_uses_navigator_label() -> None:
    session = _session()
    nodes = build_navigator(session)
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


def test_layer_header_has_enabled_solo_and_lock_chips() -> None:
    session = _session()
    nodes = build_navigator(session)
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
        inspector_header(nodes, "render.overlays", session, curation=False)
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
        inspector_header(nodes, "render.overlays", session, curation=False)
    )
    assert solo_off["enabled"].label == "off"
    assert solo_off["enabled"].active is False
    assert solo_off["solo"].active is True
    assert solo_off["lock"].label == "locked"

    post = _chips(inspector_header(nodes, "render.post_fx", session, curation=False))
    mask = _chips(
        inspector_header(nodes, "render.pattern_mask", session, curation=False)
    )
    assert tuple(post) == ("enabled", "lock")
    assert tuple(mask) == ("enabled", "lock")
    assert post["enabled"].label == "on"
    assert mask["enabled"].label == "off"
    assert "solo" not in post
    assert "solo" not in mask


def test_card_node_has_enabled_chip_and_overlays_lock_chip() -> None:
    session = _session()
    nodes = build_navigator(
        session, expanded={"render", "render.overlays", "layers"}
    )
    opening_id = overlay_card_node_id("opening_card")
    assert row_lock_section(RowKind.RENDER_OVERLAY_CARD_HEADER) == "render_overlay"
    header = inspector_header(nodes, opening_id, session, curation=False)
    chips = _chips(header)
    assert tuple(chips) == ("enabled", "lock")
    assert chips["enabled"].label == "on"
    assert chips["lock"].label == "lock"
    assert "solo" not in chips

    session.render_overlays.opening_card.enabled = False
    session.render_overlays.locked = True
    locked = _chips(inspector_header(nodes, opening_id, session, curation=False))
    assert locked["enabled"].label == "off"
    assert locked["lock"].label == "locked"
    assert locked["lock"].active is True


def test_preset_curation_omits_header_chips() -> None:
    session = _session()
    nodes = build_navigator(session)
    layer = inspector_header(
        nodes, layer_node_id("layer_1"), session, curation=True
    )
    overlays = inspector_header(nodes, "render.overlays", session, curation=True)
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
