"""Tests for inspector row colors and the visibility icon."""

from __future__ import annotations

import pygame

from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.navigator import overlay_card_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import (
    render_visibility_icon,
    row_value_color_for,
)
from cleave.viz.row_spec import row_full_line_display_text
from cleave.viz.theme import (
    ACTION,
    DISABLED,
    LABEL,
    LOCKED,
    SOLO_BG,
)
from cleave.viz.tuning_view_state import (
    RenderOverlaysBlock,
    RenderTimelineBlock,
    TimelineFadeGroupBlock,
    TuningViewState,
)
from tests.support.viz import make_overlay_card_block, make_track_block


def test_solo_visibility_icon_uses_red_background() -> None:
    pygame.init()
    line_h = 17
    soloed = render_visibility_icon(enabled=True, solo=True, line_height=line_h)
    normal = render_visibility_icon(enabled=True, solo=False, line_height=line_h)
    assert soloed.get_height() == line_h
    assert soloed.get_width() == normal.get_width()
    assert soloed.get_at((1, line_h // 2))[:3] == SOLO_BG
    assert normal.get_at((normal.get_width() // 2, line_h // 2))[:3] != SOLO_BG


def test_solo_visibility_icon_disabled_stem_uses_value_not_disabled() -> None:
    pygame.init()
    line_h = 17
    disabled = render_visibility_icon(enabled=False, solo=False, line_height=line_h)
    soloed_off = render_visibility_icon(enabled=False, solo=True, line_height=line_h)
    assert soloed_off.get_at((1, line_h // 2))[:3] == SOLO_BG
    assert pygame.mask.from_surface(soloed_off).count() != pygame.mask.from_surface(
        disabled
    ).count()


def _minimal_view_state(**kwargs: object) -> TuningViewState:
    defaults: dict[str, object] = {
        "layer_z_order": ("layer_1",),
        "tracks": {
            "layer_1": make_track_block(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
            )
        },
        "paused": False,
        "position_sec": 0.0,
        "focus_cursor": MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)),
        "move_mode_slot": None,
        "notification_message": None,
        "notification_remaining_sec": 0.0,
    }
    defaults.update(kwargs)
    return TuningViewState(**defaults)  # type: ignore[arg-type]


def _track(**kwargs: object):
    defaults: dict[str, object] = {
        "stem": "drums",
        "preset_dir_label": "dir",
        "preset_label": "preset.milk",
        "blend_mode": "black-key",
        "opacity_pct": 50,
        "beat_sensitivity": 1.0,
        "effects": {},
    }
    defaults.update(kwargs)
    return make_track_block(**defaults)  # type: ignore[arg-type]


def test_locked_stem_row_uses_locked_color() -> None:
    state = _minimal_view_state(tracks={"layer_1": _track(locked=True)})
    stem = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    assert row_value_color_for(state, stem) == LOCKED


def test_delete_row_disabled_color_single_layer() -> None:
    state = _minimal_view_state()
    delete_row = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_1")
    assert row_value_color_for(state, delete_row) == DISABLED


def test_action_row_value_color() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": _track(),
            "layer_2": _track(stem="bass"),
        },
        layer_z_order=("layer_1", "layer_2"),
    )
    add_row = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_2")
    delete_row = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_1")
    assert row_value_color_for(state, add_row) == ACTION
    assert row_value_color_for(state, delete_row) == ACTION


def test_snap_to_song_markers_row_uses_action_color() -> None:
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True),
    )
    desc = RowDescriptor(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS)
    assert row_value_color_for(state, desc) == ACTION
    text = row_full_line_display_text(state, desc)
    assert "▶" not in text
    assert "▼" not in text


def test_apply_cuts_to_cues_rows_use_action_color() -> None:
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(
            enabled=True,
            hard_cut_fades=TimelineFadeGroupBlock(enabled=True),
            soft_cut_fades=TimelineFadeGroupBlock(enabled=True),
        ),
    )
    soft_row = RowDescriptor(RowKind.TIMELINE_APPLY_SOFT_CUTS)
    hard_row = RowDescriptor(RowKind.TIMELINE_APPLY_HARD_CUTS)
    remove_soft_row = RowDescriptor(RowKind.TIMELINE_REMOVE_SOFT_CUTS)
    remove_hard_row = RowDescriptor(RowKind.TIMELINE_REMOVE_HARD_CUTS)
    assert row_value_color_for(state, soft_row) == ACTION
    assert row_value_color_for(state, hard_row) == ACTION
    assert row_value_color_for(state, remove_soft_row) == ACTION
    assert row_value_color_for(state, remove_hard_row) == ACTION
    assert "Remove from Cues" in row_full_line_display_text(state, remove_soft_row)
    assert "Remove from Cues" in row_full_line_display_text(state, remove_hard_row)
    for desc in (soft_row, hard_row):
        text = row_full_line_display_text(state, desc)
        assert "▶" not in text
        assert "▼" not in text


def test_display_size_row_uses_label_color() -> None:
    state = _minimal_view_state()
    desc = RowDescriptor(RowKind.SETTINGS_EDITOR_WINDOW_DISPLAY_SIZE)
    assert row_value_color_for(state, desc) == LABEL


def test_preset_list_populate_uses_action_color() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": _track(
                preset_switching="on",
                preset_switching_trigger="timer",
            )
        },
    )
    populate_row = RowDescriptor(RowKind.TRACK_PRESET_LIST_POPULATE, slot="layer_1")
    assert row_value_color_for(state, populate_row) == ACTION


def test_disabled_action_row_stays_disabled() -> None:
    state = _minimal_view_state()
    delete_row = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_1")
    state.focus_descriptor = delete_row
    assert row_value_color_for(state, delete_row) == DISABLED


def _inspector_kinds(state, node_id: str) -> list[RowKind]:
    rows = build_inspector_rows(state, node_id, frozenset())
    return [row.descriptor.kind for row in rows if row.descriptor is not None]


def test_render_overlay_inspector_includes_header_and_sub_rows_when_expanded() -> None:
    state = _minimal_view_state()
    opening = _inspector_kinds(state, overlay_card_node_id("opening_card"))
    for kind in (
        RowKind.RENDER_OVERLAY_CARD_ANIMATION_HEADER,
        RowKind.RENDER_OVERLAY_CARD_POSITION,
        RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER,
        RowKind.RENDER_OVERLAY_CARD_BODY_HEADER,
        RowKind.RENDER_OVERLAY_CARD_OPACITY,
        RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN,
        RowKind.RENDER_OVERLAY_CARD_BACKGROUND_PADDING,
        RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE,
        RowKind.RENDER_OVERLAY_CARD_BODY_FONT_SIZE,
    ):
        assert kind in opening
    assert RowKind.RENDER_OVERLAY_CARD_TIME in opening
    assert RowKind.RENDER_OVERLAY_CARD_DISPLAY_TIME in opening


def test_render_overlay_animation_rows_when_expanded() -> None:
    state = _minimal_view_state(
        render_overlays=RenderOverlaysBlock(
            opening_card=make_overlay_card_block(animation_type="slide")
        ),
    )
    kinds = _inspector_kinds(state, overlay_card_node_id("opening_card"))
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_TYPE in kinds
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION in kinds
    assert RowKind.RENDER_OVERLAY_CARD_TIME in kinds
    assert RowKind.RENDER_OVERLAY_CARD_DISPLAY_TIME in kinds


def test_render_overlay_animation_hides_slide_direction_for_fade() -> None:
    state = _minimal_view_state(
        render_overlays=RenderOverlaysBlock(
            opening_card=make_overlay_card_block(animation_type="fade")
        ),
    )
    kinds = _inspector_kinds(state, overlay_card_node_id("opening_card"))
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_TYPE in kinds
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in kinds


def test_render_overlay_title_and_body_font_rows_when_expanded() -> None:
    state = _minimal_view_state()
    kinds = _inspector_kinds(state, overlay_card_node_id("opening_card"))
    for kind in (
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE,
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT,
        RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT,
        RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_TITLE_MARGIN_BOTTOM,
        RowKind.RENDER_OVERLAY_CARD_BODY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_CARD_BODY_FONT,
        RowKind.RENDER_OVERLAY_CARD_BODY_TEXT,
        RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
    ):
        assert kind in kinds


def test_render_overlay_collapsed_hides_sub_rows() -> None:
    state = _minimal_view_state()
    opening = _inspector_kinds(state, overlay_card_node_id("opening_card"))
    closing = _inspector_kinds(state, overlay_card_node_id("closing_card"))
    assert RowKind.RENDER_OVERLAY_CARD_POSITION in opening
    assert RowKind.RENDER_OVERLAY_CARD_POSITION in closing
    overlays = _inspector_kinds(state, "render.overlays")
    assert overlays.count(RowKind.RENDER_OVERLAY_CARD_HEADER) == 2
