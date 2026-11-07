"""Tests for inspector row colors and the visibility icon."""

from __future__ import annotations

import pygame

from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import (
    render_visibility_icon,
    row_value_color_for,
)
from cleave.viz.row_spec import row_panel_label
from cleave.viz.theme import (
    VALUE,
    DISABLED,
    LABEL,
    LOCKED,
    SOLO_BG,
)
from cleave.viz.tuning_view_state import (
    OverlaysBlock,
    TimelineBlock,
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
        "focus_cursor": MainFocus(RowDescriptor(RowKind.OVERLAYS_HEADER)),
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
    assert row_value_color_for(state, add_row) == VALUE
    assert row_value_color_for(state, delete_row) == VALUE


def test_display_row_uses_label_color() -> None:
    state = _minimal_view_state()
    desc = RowDescriptor(RowKind.LAYER_MANAGEMENT_COUNT)
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
    assert row_value_color_for(state, populate_row) == VALUE


def _inspector_kinds(state, node_id: str) -> list[RowKind]:
    rows = build_inspector_rows(state, node_id)
    return [row.descriptor.kind for row in rows if row.descriptor is not None]


def test_overlay_inspector_includes_header_and_sub_rows_when_expanded() -> None:
    state = _minimal_view_state()
    opening = _inspector_kinds(state, "overlay.opening_card")
    for kind in (
        RowKind.OVERLAY_CARD_ANIMATION_HEADER,
        RowKind.OVERLAY_CARD_POSITION,
        RowKind.OVERLAY_CARD_TITLE_HEADER,
        RowKind.OVERLAY_CARD_BODY_HEADER,
        RowKind.OVERLAY_CARD_OPACITY,
        RowKind.OVERLAY_CARD_BACKGROUND_COLOUR,
        RowKind.OVERLAY_CARD_BACKGROUND_MARGIN,
        RowKind.OVERLAY_CARD_BACKGROUND_PADDING,
        RowKind.OVERLAY_CARD_BORDER_WIDTH,
        RowKind.OVERLAY_CARD_BORDER_COLOUR,
        RowKind.OVERLAY_CARD_TITLE_FONT_SIZE,
        RowKind.OVERLAY_CARD_BODY_FONT_SIZE,
    ):
        assert kind in opening
    assert RowKind.OVERLAY_CARD_TIME in opening
    assert RowKind.OVERLAY_CARD_DISPLAY_TIME in opening


def test_overlay_animation_rows_when_expanded() -> None:
    state = _minimal_view_state(
        overlays=OverlaysBlock(
            opening_card=make_overlay_card_block(animation_type="slide")
        ),
    )
    kinds = _inspector_kinds(state, "overlay.opening_card")
    assert RowKind.OVERLAY_CARD_ANIMATION_TYPE in kinds
    assert RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION in kinds
    assert RowKind.OVERLAY_CARD_TIME in kinds
    assert RowKind.OVERLAY_CARD_DISPLAY_TIME in kinds


def test_overlay_animation_hides_slide_direction_for_fade() -> None:
    state = _minimal_view_state(
        overlays=OverlaysBlock(
            opening_card=make_overlay_card_block(animation_type="fade")
        ),
    )
    kinds = _inspector_kinds(state, "overlay.opening_card")
    assert RowKind.OVERLAY_CARD_ANIMATION_TYPE in kinds
    assert RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in kinds


def test_overlay_title_and_body_font_rows_when_expanded() -> None:
    state = _minimal_view_state()
    kinds = _inspector_kinds(state, "overlay.opening_card")
    for kind in (
        RowKind.OVERLAY_CARD_TITLE_FONT_SIZE,
        RowKind.OVERLAY_CARD_TITLE_FONT,
        RowKind.OVERLAY_CARD_TITLE_TEXT,
        RowKind.OVERLAY_CARD_TITLE_COLOUR,
        RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
        RowKind.OVERLAY_CARD_TITLE_MARGIN_BOTTOM,
        RowKind.OVERLAY_CARD_BODY_FONT_SIZE,
        RowKind.OVERLAY_CARD_BODY_FONT,
        RowKind.OVERLAY_CARD_BODY_TEXT,
        RowKind.OVERLAY_CARD_BODY_COLOUR,
        RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
    ):
        assert kind in kinds


def test_overlay_root_has_switches_and_cards_have_settings() -> None:
    state = _minimal_view_state()
    opening = _inspector_kinds(state, "overlay.opening_card")
    closing = _inspector_kinds(state, "overlay.closing_card")
    assert RowKind.OVERLAY_CARD_POSITION in opening
    assert RowKind.OVERLAY_CARD_POSITION in closing
    assert _inspector_kinds(state, "overlay") == [
        RowKind.OVERLAYS_ENABLED,
        RowKind.OVERLAYS_SOLO,
        RowKind.OVERLAYS_LOCKED,
    ]
