"""Inspector row model: Settings, Project, Layers, collapse, and conditional rows."""

from __future__ import annotations

from cleave.effects.registry import effect_roster
from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import build_inspector_rows, rows_for_section
from cleave.viz.navigator import layer_node_id, overlay_card_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_sections import (
    PROJECT_SECTION,
    RENDER_OVERLAY_CLOSING_CARD_SECTION,
    RENDER_OVERLAY_OPENING_CARD_SECTION,
    RENDER_OVERLAYS_SECTION,
    RENDER_PATTERN_MASK_SECTION,
    RENDER_POST_FX_SECTION,
    SETTINGS_SECTION,
    ExpandSectionDef,
)
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_spec import format_row_value, row_spec
from cleave.viz.theme import ACTION, LOCKED
from cleave.viz.shell_focus import InspectorGroupKey
from cleave.viz.tuning_view_state import SettingsBlock, TuningViewState
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import make_track_block


def _view_state() -> TuningViewState:
    return TuningViewState(
        layer_z_order=(),
        tracks={},
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)),
        move_mode_slot=None,
    )


def _kinds(rows: tuple) -> list[RowKind]:
    return [row.descriptor.kind for row in rows if row.descriptor is not None]


def _leaf_descriptors(section: ExpandSectionDef) -> tuple[RowDescriptor, ...]:
    leaves: list[RowDescriptor] = []
    for child in section.children:
        assert child.leaf_kind is not None
        leaves.append(RowDescriptor(child.leaf_kind))
    return tuple(leaves)


def _group_leaves(rows: tuple, header: RowKind) -> tuple:
    found = False
    leaves = []
    for row in rows:
        if row.is_group and row.descriptor.kind == header:
            found = True
            continue
        if not found:
            continue
        if row.is_group:
            break
        leaves.append(row)
    assert found
    return tuple(leaves)


def test_project_builds_three_groups_matching_section_children() -> None:
    state = _view_state()
    rows = build_inspector_rows(state, "project", frozenset())
    assert rows == rows_for_section(state, PROJECT_SECTION, frozenset())

    expands = tuple(child.expand for child in PROJECT_SECTION.children)
    assert len(expands) == 3
    assert all(section is not None for section in expands)

    groups = tuple(row for row in rows if row.is_group)
    assert tuple(row.descriptor.kind for row in groups) == tuple(
        section.header_kind for section in expands if section is not None
    )
    assert all(row.depth == 0 and row.is_group for row in groups)
    for group in groups:
        assert group.navigable is row_spec(group.descriptor.kind).navigable

    for section in expands:
        assert section is not None
        leaves = _group_leaves(rows, section.header_kind)
        fields = tuple(row for row in leaves if row.descriptor is not None)
        commands = tuple(row.command_id for row in leaves if row.command_id)
        assert tuple(row.descriptor for row in fields) == _leaf_descriptors(section)
        if section.header_kind == RowKind.PROJECT_RENDER_HEADER:
            assert commands == ("project.render",)
        else:
            assert commands == ()
        assert all(row.depth == 1 and not row.is_group for row in leaves)
        for leaf in leaves:
            if leaf.descriptor is None:
                assert leaf.navigable
                continue
            assert leaf.navigable is row_spec(leaf.descriptor.kind).navigable


def test_collapsed_group_hides_children_and_keeps_header() -> None:
    state = _view_state()
    header = RowKind.PROJECT_COMPOSITOR_HEADER
    rows = build_inspector_rows(
        state, "project", frozenset({InspectorGroupKey(header)})
    )
    kinds = _kinds(rows)

    assert header in kinds
    assert RowKind.PROJECT_COMPOSITOR_HDR not in kinds
    group = next(row for row in rows if row.descriptor.kind == header)
    assert group.is_group is True
    assert group.depth == 0
    assert RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY in kinds
    assert RowKind.PROJECT_RENDER_OUTPUT in kinds


def test_conditional_rows_follow_pattern_mask_predicate() -> None:
    state = _view_state()
    assert state.render_pattern_mask.type != "plasma"
    hidden = rows_for_section(state, RENDER_PATTERN_MASK_SECTION, frozenset())
    hidden_kinds = _kinds(hidden)
    assert RowKind.RENDER_PATTERN_MASK_SEED not in hidden_kinds
    assert RowKind.RENDER_PATTERN_MASK_TYPE in hidden_kinds

    state.render_pattern_mask.type = "plasma"
    shown = rows_for_section(state, RENDER_PATTERN_MASK_SECTION, frozenset())
    shown_kinds = _kinds(shown)
    assert RowKind.RENDER_PATTERN_MASK_SEED in shown_kinds
    assert RowKind.RENDER_PATTERN_MASK_TYPE in shown_kinds
    seed = next(row for row in shown if row.descriptor.kind == RowKind.RENDER_PATTERN_MASK_SEED)
    assert seed.is_group is False
    assert seed.navigable is row_spec(RowKind.RENDER_PATTERN_MASK_SEED).navigable


def test_settings_and_project_omit_top_headers() -> None:
    state = _view_state()
    settings = build_inspector_rows(state, "settings", frozenset())
    project = build_inspector_rows(state, "project", frozenset())

    assert settings == rows_for_section(state, SETTINGS_SECTION, frozenset())
    latency = _group_leaves(settings, RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER)
    assert latency[-1].command_id == "settings.measure_latency"
    assert RowKind.SETTINGS_EDITOR_WINDOW_HEADER in _kinds(settings)
    assert RowKind.SETTINGS_UI_HEADER in _kinds(settings)
    assert RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER in _kinds(settings)


def test_unmigrated_nodes_return_no_rows() -> None:
    state = _view_state()
    for node_id in (
        "render",
        "song_markers",
        "unknown",
        "render.overlays.card:other",
    ):
        assert build_inspector_rows(state, node_id, frozenset()) == ()


def test_render_overlays_page_is_the_two_card_groups() -> None:
    state = _view_state()
    rows = build_inspector_rows(state, "render.overlays", frozenset())
    assert rows == rows_for_section(state, RENDER_OVERLAYS_SECTION, frozenset())
    assert all(row.command_id is None for row in rows)
    groups = tuple(row for row in rows if row.is_group and row.depth == 0)
    assert tuple(
        (row.descriptor.kind, row.descriptor.card) for row in groups
    ) == (
        (RowKind.RENDER_OVERLAY_CARD_HEADER, "opening_card"),
        (RowKind.RENDER_OVERLAY_CARD_HEADER, "closing_card"),
    )
    assert RowKind.RENDER_OVERLAYS_HEADER not in _kinds(rows)
    for card in ("opening_card", "closing_card"):
        assert any(
            row.descriptor is not None
            and row.descriptor.card == card
            and row.descriptor.kind is RowKind.RENDER_OVERLAY_CARD_POSITION
            for row in rows
        )

    collapsed = frozenset(
        {InspectorGroupKey(RowKind.RENDER_OVERLAY_CARD_HEADER, card="opening_card")}
    )
    hidden = build_inspector_rows(state, "render.overlays", collapsed)
    opening = tuple(
        row.descriptor.kind
        for row in hidden
        if row.descriptor is not None and row.descriptor.card == "opening_card"
    )
    assert opening == (RowKind.RENDER_OVERLAY_CARD_HEADER,)
    assert any(
        row.descriptor is not None
        and row.descriptor.card == "closing_card"
        and row.descriptor.kind is RowKind.RENDER_OVERLAY_CARD_POSITION
        for row in hidden
    )


def test_opening_card_page_omits_its_header() -> None:
    state = _view_state()
    node_id = overlay_card_node_id("opening_card")
    rows = build_inspector_rows(state, node_id, frozenset())
    assert rows == rows_for_section(
        state, RENDER_OVERLAY_OPENING_CARD_SECTION, frozenset()
    )
    kinds = _kinds(rows)
    assert RowKind.RENDER_OVERLAY_CARD_HEADER not in kinds
    for kind in (
        RowKind.RENDER_OVERLAY_CARD_ANIMATION_HEADER,
        RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER,
        RowKind.RENDER_OVERLAY_CARD_BODY_HEADER,
        RowKind.RENDER_OVERLAY_CARD_POSITION,
        RowKind.RENDER_OVERLAY_CARD_OPACITY,
        RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN,
        RowKind.RENDER_OVERLAY_CARD_BACKGROUND_PADDING,
        RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR,
    ):
        assert kind in kinds
    assert all(
        row.descriptor is not None and row.descriptor.card == "opening_card"
        for row in rows
    )

    closing = build_inspector_rows(
        state, overlay_card_node_id("closing_card"), frozenset()
    )
    assert closing == rows_for_section(
        state, RENDER_OVERLAY_CLOSING_CARD_SECTION, frozenset()
    )
    assert RowKind.RENDER_OVERLAY_CARD_HEADER not in _kinds(closing)
    assert all(
        row.descriptor is not None and row.descriptor.card == "closing_card"
        for row in closing
    )


def test_render_predicates_omit_rows() -> None:
    state = _view_state()
    mask = build_inspector_rows(state, "render.pattern_mask", frozenset())
    assert mask == rows_for_section(state, RENDER_PATTERN_MASK_SECTION, frozenset())
    assert state.render_pattern_mask.type != "plasma"
    assert RowKind.RENDER_PATTERN_MASK_TYPE in _kinds(mask)
    assert RowKind.RENDER_PATTERN_MASK_SEED not in _kinds(mask)
    assert RowKind.RENDER_PATTERN_MASK_HEADER not in _kinds(mask)

    card = build_inspector_rows(
        state, overlay_card_node_id("opening_card"), frozenset()
    )
    assert state.render_overlays.opening_card.runtime.animation.type == "fade"
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_TYPE in _kinds(card)
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in _kinds(card)

    post = build_inspector_rows(state, "render.post_fx", frozenset())
    assert post == rows_for_section(state, RENDER_POST_FX_SECTION, frozenset())
    assert state.render_post_fx.chroma_boost.mode == "off"
    post_kinds = _kinds(post)
    assert RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE in post_kinds
    assert RowKind.RENDER_POST_FX_CHROMA_BOOST_VARIANT not in post_kinds
    assert RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT not in post_kinds
    assert RowKind.RENDER_POST_FX_HEADER not in post_kinds


def test_locked_render_blocks_still_build() -> None:
    state = _view_state()
    state.render_overlays.locked = True
    state.render_post_fx.locked = True
    state.render_pattern_mask.locked = True

    overlays = build_inspector_rows(state, "render.overlays", frozenset())
    position = next(
        row.descriptor
        for row in overlays
        if row.descriptor is not None
        and row.descriptor.kind is RowKind.RENDER_OVERLAY_CARD_POSITION
        and row.descriptor.card == "opening_card"
    )
    assert inspector_field_colors(state, position) == (LOCKED, LOCKED)

    post = build_inspector_rows(state, "render.post_fx", frozenset())
    fade_start = next(
        row.descriptor
        for row in post
        if row.descriptor is not None
        and row.descriptor.kind is RowKind.RENDER_POST_FX_FADE_IN_START
    )
    assert inspector_field_colors(state, fade_start) == (LOCKED, LOCKED)

    mask = build_inspector_rows(state, "render.pattern_mask", frozenset())
    density = next(
        row.descriptor
        for row in mask
        if row.descriptor is not None
        and row.descriptor.kind is RowKind.RENDER_PATTERN_MASK_DENSITY
    )
    assert inspector_field_colors(state, density) == (LOCKED, LOCKED)


def _layer_view(
    slots: tuple[str, ...],
    *,
    editor_mode: str = "visualizer",
    trigger: str = "off",
    preset_list: list[str] | None = None,
) -> TuningViewState:
    tracks = {
        slot: make_track_block(
            stem=TEST_LAYER_STEMS.get(slot, "drums"),
            preset_switching_trigger=trigger,
            preset_list=list(preset_list or []),
        )
        for slot in slots
    }
    return TuningViewState(
        layer_z_order=slots,
        tracks=tracks,
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRACK_HEADER, slot=slots[0])),
        move_mode_slot=None,
        settings=SettingsBlock(editor_mode=editor_mode),
    )


def test_layer_slot_page_has_groups_without_track_header() -> None:
    state = _layer_view(("layer_1",))
    rows = build_inspector_rows(state, layer_node_id("layer_1"), frozenset())
    kinds = _kinds(rows)
    assert RowKind.TRACK_HEADER not in kinds
    for kind in (
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_PRESET_SWITCHING,
        RowKind.TRACK_COMPOSITING_HEADER,
        RowKind.TRACK_EFFECTS_HEADER,
    ):
        assert kind in kinds
    assert any(row.command_id == "layers.delete" and row.navigable for row in rows)
    assert RowKind.LAYER_MANAGEMENT_DELETE not in kinds
    assert RowKind.TRACK_BLEND in kinds
    assert RowKind.TRACK_OPACITY in kinds
    assert RowKind.TRACK_EFFECT not in kinds


def test_dynamic_effect_and_preset_rows_keep_slot_identity() -> None:
    state = _layer_view(
        ("layer_1",),
        trigger="timer",
        preset_list=["/tmp/a.milk", "/tmp/b.milk"],
    )
    opened = frozenset(
        {InspectorGroupKey(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1")}
    )
    rows = build_inspector_rows(state, layer_node_id("layer_1"), frozenset(), opened)
    effects = [
        row.descriptor
        for row in rows
        if row.descriptor is not None and row.descriptor.kind is RowKind.TRACK_EFFECT
    ]
    roster = effect_roster(state.tracks["layer_1"].runtime.stem)
    assert [(desc.effect_id, desc.driver_slug, desc.slot) for desc in effects] == [
        (item.effect_id, item.driver_slug, "layer_1") for item in roster
    ]
    items = [
        row.descriptor
        for row in rows
        if row.descriptor is not None
        and row.descriptor.kind is RowKind.TRACK_PRESET_LIST_ITEM
    ]
    assert [(desc.slot, desc.preset_index) for desc in items] == [
        ("layer_1", 0),
        ("layer_1", 1),
    ]
    kinds = _kinds(rows)
    assert RowKind.TRACK_PRESET_LIST_ADD in kinds
    assert RowKind.TRACK_PRESET_LIST_POPULATE in kinds

    hidden = build_inspector_rows(
        state,
        layer_node_id("layer_1"),
        frozenset({InspectorGroupKey(RowKind.TRACK_PRESET_LIST, slot="layer_1")}),
        opened,
    )
    hidden_kinds = _kinds(hidden)
    assert RowKind.TRACK_PRESET_LIST in hidden_kinds
    assert RowKind.TRACK_PRESET_LIST_ITEM not in hidden_kinds
    assert RowKind.TRACK_PRESET_LIST_ADD not in hidden_kinds
    assert RowKind.TRACK_PRESET_LIST_POPULATE not in hidden_kinds
    assert RowKind.TRACK_EFFECT in hidden_kinds


def test_collapsing_compositing_is_per_slot() -> None:
    state = _layer_view(("layer_1", "layer_2"))
    collapsed = frozenset(
        {InspectorGroupKey(RowKind.TRACK_COMPOSITING_HEADER, slot="layer_1")}
    )
    hidden = _kinds(
        build_inspector_rows(state, layer_node_id("layer_1"), collapsed)
    )
    shown = _kinds(
        build_inspector_rows(state, layer_node_id("layer_2"), collapsed)
    )
    assert RowKind.TRACK_COMPOSITING_HEADER in hidden
    assert RowKind.TRACK_BLEND not in hidden
    assert RowKind.TRACK_OPACITY not in hidden
    assert RowKind.TRACK_BLEND in shown
    assert RowKind.TRACK_OPACITY in shown


def test_cleave_effects_start_closed_and_toggle_sticks_per_slot() -> None:
    from tests.cleave.viz.test_controls import _make_controls

    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    focus = controls.shell_focus
    key = InspectorGroupKey(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1")

    def effect_slots(node_id: str) -> list[str | None]:
        rows = build_inspector_rows(
            view, node_id, focus.collapsed, focus.opened
        )
        return [
            row.descriptor.slot
            for row in rows
            if row.descriptor is not None
            and row.descriptor.kind is RowKind.TRACK_EFFECT
        ]

    assert effect_slots(layer_node_id("layer_1")) == []
    assert effect_slots(layer_node_id("layer_2")) == []
    controls.inspector.toggle_group(key)
    assert effect_slots(layer_node_id("layer_1"))
    assert all(slot == "layer_1" for slot in effect_slots(layer_node_id("layer_1")))
    assert effect_slots(layer_node_id("layer_2")) == []
    assert effect_slots(layer_node_id("layer_1"))
    controls.inspector.toggle_group(key)
    assert effect_slots(layer_node_id("layer_1")) == []
    assert effect_slots(layer_node_id("layer_2")) == []


def test_section_lock_inspector_field_colors() -> None:
    state = _layer_view(("layer_1", "layer_2"))
    state.tracks["layer_1"].runtime.locked = True
    state.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    )
    opacity = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    delete = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_1")
    assert inspector_field_colors(state, opacity) == (LOCKED, LOCKED)
    label, value = inspector_field_colors(state, delete)
    assert label == ACTION
    assert value != LOCKED
    rows = build_inspector_rows(state, layer_node_id("layer_1"), frozenset())
    assert any(row.navigable and row.command_id == "layers.delete" for row in rows)


def test_layers_root_count_and_curation_omits_add() -> None:
    state = _layer_view(("layer_1", "layer_2"))
    rows = build_inspector_rows(state, "layers", frozenset())
    assert _kinds(rows) == [RowKind.LAYER_MANAGEMENT_COUNT]
    assert rows[1].command_id == "layers.add"
    assert rows[1].navigable is True
    assert rows[1].descriptor is None
    count = rows[0]
    assert count.descriptor is not None
    assert count.navigable is False
    assert count.is_group is False
    assert format_row_value(state, count.descriptor) == "2 of 8 layers"

    state.settings.editor_mode = "preset_curation"
    curation_rows = build_inspector_rows(state, "layers", frozenset())
    assert _kinds(curation_rows) == [RowKind.LAYER_MANAGEMENT_COUNT]
    assert all(row.command_id != "layers.add" for row in curation_rows)
    assert _kinds(build_inspector_rows(state, layer_node_id("layer_1"), frozenset())) == [
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
    ]
