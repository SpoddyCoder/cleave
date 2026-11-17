"""Tests for the bottom timeline strip overlay."""

from __future__ import annotations

import pygame
import pytest

from cleave.config_schema.layers import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.stems import STEM_NAMES
from cleave.timeline import (
    LEVEL_EPS,
    SlotCue,
    TimelineFadeGroup,
    TimelineLane,
    canonicalize,
    lane_level_at,
    lane_level_segments,
    stem_abbreviation,
)
from cleave.viz.icon_button import icon_gap
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.overlay_primitives import overlay_font
from cleave.viz.row_present_renderers import render_visibility_icon
from cleave.viz.theme import (
    ARMED_BG,
    LABEL,
    DISABLED,
    HIGHLIGHT,
    OVERRIDE_BG,
    OVERRIDE_GLYPH,
    OVERRIDE_GLYPH_OFF,
    PLAYHEAD,
    PLAYHEAD_FLASH,
    SOLO_BG,
    VALUE,
    SONG_MARKER,
    SONG_MARKER_SELECTED,
    timeline_ui_metrics,
)
from cleave.viz.timeline_overlay import TimelineOverlay
from cleave.viz.timeline_strip_flash import (
    REC_FLASH_MS,
    ARM_FLASH_DURATION_MS,
    ARM_FLASH_HALF_MS,
    PLAYHEAD_FLASH_MS,
    SELECTED_CLIP_COLOR,
    SELECTED_CLIP_FLASH_DURATION_MS,
    SELECTED_CLIP_FLASH_HALF_MS,
    SELECTED_CLIP_FLASH_RED,
    SELECTED_CLIP_FLASH_YELLOW,
    arm_button_lit,
    arm_flash_active,
    arm_flash_visible,
    playhead_color,
    playhead_flash_bright,
    prune_expired_arm_flashes,
    prune_expired_selected_clip_flash,
    rec_flash_visible,
    selected_clip_flash_active,
    selected_clip_flash_bright,
    selected_clip_flash_color,
)
from cleave.viz.timeline_strip_layout import (
    ROW_HEADER_BUTTONS,
    header_button_x,
    header_buttons_width,
    layer_num_prefix,
    playhead_x,
    row_header_target_at,
    row_prefix_width,
    visible_header_buttons,
    stem_abbrev_label,
    stem_label_text,
    time_to_x,
)
from cleave.viz.timeline_strip_live import (
    ROLE_GLYPH_BOTTOM_PAD,
    ROLE_GLYPH_TICK_GAP,
    SELECTED_CLIP_FLASH_OUTLINE_WIDTH,
    SELECTED_CLIP_FLASH_TICK_WIDTH,
    blit_role_glyph_xor,
    role_glyph_anchor,
    role_glyph_previous_level,
    role_glyph_side,
)
from cleave.viz.timeline_strip_state import (
    TimelineViewState,
    bar_level_breakpoints_for_row,
    bar_tick_times_for_row,
    clip_breakpoints,
    cue_times_for_stem,
)
from cleave.viz.timeline_strip_static import (
    CLIP_HANDLE_WIDTH,
    SELECTED_CLIP_OUTLINE_WIDTH,
)
from tests.support.timeline import (
    make_lane,
    strip_view_state,
)


def _draw(
    overlay: TimelineOverlay,
    surface: pygame.Surface,
    state: TimelineViewState,
) -> None:
    overlay.draw(surface, state)


def test_row_prefix_width_includes_header_buttons() -> None:
    pygame.init()
    font = overlay_font(timeline_ui_metrics().font_size)
    layer_num_w = font.render(layer_num_prefix(4), True, (255, 255, 255)).get_width()
    abbrev_w = font.render(stem_abbrev_label("drums"), True, (255, 255, 255)).get_width()
    row_h = 20
    slot_w = visibility_icon_slot_width(row_h)
    assert slot_w == row_h
    buttons = visible_header_buttons(any_override=True)
    assert row_prefix_width(layer_num_w, abbrev_w, row_h, buttons, padding=8) == (
        layer_num_w + abbrev_w + header_buttons_width(slot_w, buttons) + 8
    )


def test_back_to_timeline_column_only_while_overridden() -> None:
    assert visible_header_buttons(any_override=True) == ROW_HEADER_BUTTONS
    assert visible_header_buttons(any_override=False) == ("arm", "solo", "eye")


def test_row_header_target_at_maps_each_column() -> None:
    padding, label_w, slot_w = 8, 40, 20
    def at(x: float):
        return row_header_target_at(
            x, padding=padding, label_width=label_w, slot_w=slot_w, buttons=ROW_HEADER_BUTTONS
        )
    assert at(padding - 1) is None
    assert at(padding) == "label"
    assert at(padding + label_w - 1) == "label"
    gap = int(icon_gap())
    for index, target in enumerate(ROW_HEADER_BUTTONS):
        left = padding + label_w + index * (slot_w + gap)
        assert at(left) == target
        assert at(left + slot_w - 1) == target
        assert header_button_x(target, padding=padding, label_width=label_w, slot_w=slot_w) == left
        if gap and index < len(ROW_HEADER_BUTTONS) - 1:
            assert at(left + slot_w) is None
    assert at(padding + label_w + header_buttons_width(slot_w, ROW_HEADER_BUTTONS)) is None
    hidden = row_header_target_at(
        header_button_x("release", padding=padding, label_width=label_w, slot_w=slot_w),
        padding=padding,
        label_width=label_w,
        slot_w=slot_w,
        buttons=visible_header_buttons(any_override=False),
    )
    assert hidden is None
    assert ROW_HEADER_BUTTONS == ("arm", "solo", "eye", "release")


def test_layer_num_width_probe_scales_with_eight_layers() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    order = [f"layer_{i}" for i in range(1, 9)]
    defaults = {slot: True for slot in order}
    _draw(overlay, surface, strip_view_state(layer_z_order=order, defaults=defaults))

    font = overlay_font(timeline_ui_metrics().font_size)
    expected = font.render(layer_num_prefix(8), True, (255, 255, 255)).get_width()
    assert overlay._layer_num_width == expected


def test_bar_runs_from_header_buttons_to_right_padding() -> None:
    pygame.init()
    padding = 8
    overlay = TimelineOverlay(padding=padding)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state())

    panel = overlay.panel_rect
    bar_layout = overlay.bar_layout
    assert panel is not None
    assert bar_layout is not None
    panel_w = panel[2]
    bar_left, bar_width = bar_layout
    row_h = overlay.row_layout[0][4]

    assert bar_left == padding + row_prefix_width(
        overlay._layer_num_width,
        overlay._stem_abbrev_width,
        row_h,
        visible_header_buttons(any_override=False),
        padding=padding,
    )
    assert bar_left + bar_width == panel_w - padding


def test_armed_bg_matches_solo_bg() -> None:
    assert ARMED_BG == SOLO_BG


def test_override_visibility_icon_glyph_colors() -> None:
    pygame.init()
    line_h = 20
    enabled = render_visibility_icon(enabled=True, override=True, line_height=line_h)
    disabled = render_visibility_icon(enabled=False, override=True, line_height=line_h)
    assert enabled.get_at((1, 1))[:3] == OVERRIDE_BG
    assert disabled.get_at((1, 1))[:3] == OVERRIDE_BG
    glyph_x = enabled.get_width() // 2
    assert enabled.get_at((glyph_x, line_h // 2))[:3] == OVERRIDE_GLYPH
    assert disabled.get_at((glyph_x, line_h // 2))[:3] == OVERRIDE_GLYPH_OFF
    assert OVERRIDE_GLYPH_OFF == DISABLED


def test_rec_flash_visible_alternates_every_500ms() -> None:
    assert rec_flash_visible(0) is True
    assert rec_flash_visible(499) is True
    assert rec_flash_visible(500) is False
    assert rec_flash_visible(999) is False
    assert rec_flash_visible(1000) is True


def test_playhead_flash_alternates_color() -> None:
    half = PLAYHEAD_FLASH_MS
    assert playhead_flash_bright(0) is True
    assert playhead_flash_bright(half - 1) is True
    assert playhead_flash_bright(half) is False
    assert playhead_flash_bright(half * 2 - 1) is False
    assert playhead_flash_bright(half * 2) is True
    assert playhead_color(0) == PLAYHEAD_FLASH
    assert playhead_color(half) == PLAYHEAD


def test_arm_flash_visible_blinks_twice() -> None:
    start = 1000
    flash = {"layer_1": start}
    assert arm_flash_active(flash, "layer_1", ticks_ms=start) is True
    assert arm_flash_visible(flash, "layer_1", ticks_ms=start) is True
    assert arm_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS - 1) is True
    assert arm_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS) is False
    assert arm_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS * 2) is True
    assert arm_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS * 3) is False
    assert arm_flash_active(
        flash, "layer_1", ticks_ms=start + ARM_FLASH_DURATION_MS - 1
    ) is True
    assert arm_flash_active(
        flash, "layer_1", ticks_ms=start + ARM_FLASH_DURATION_MS
    ) is False


def test_prune_expired_arm_flashes() -> None:
    flash = {"layer_1": 0, "layer_2": 1000}
    prune_expired_arm_flashes(flash, ticks_ms=ARM_FLASH_DURATION_MS)
    assert flash == {"layer_2": 1000}
    prune_expired_arm_flashes(flash, ticks_ms=1000 + ARM_FLASH_DURATION_MS)
    assert flash == {}


def test_arm_button_lit_prefers_arm_flash_over_steady_armed() -> None:
    start = 5000
    flash = {"layer_1": start}
    off_tick = start + ARM_FLASH_HALF_MS
    assert arm_button_lit(
        armed=True,
        recording=False,
        flash_starts=flash,
        slot="layer_1",
        ticks_ms=off_tick,
    ) is False
    assert arm_button_lit(
        armed=True,
        recording=False,
        flash_starts={},
        slot="layer_1",
        ticks_ms=off_tick,
    ) is True


def test_disarm_flash_lights_the_arm_button_on_phase(monkeypatch) -> None:
    start = 5000
    monkeypatch.setattr("pygame.time.get_ticks", lambda: start + 10)
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        armed_slots=set(),
        arm_flash_start_ms={"layer_2": start},
        focus_row=1,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    flash_on = _arm_bg_pixel(surface, overlay, row_y, row_h)

    monkeypatch.setattr("pygame.time.get_ticks", lambda: start + ARM_FLASH_HALF_MS + 10)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    flash_off = _arm_bg_pixel(surface, overlay, row_y, row_h)

    assert flash_on[0] > flash_off[0] + 40
    assert flash_on[0] > 150


def _set_rec_flash(monkeypatch, visible: bool) -> None:
    """Pin the clock to the lit or dark half of the REC blink."""
    monkeypatch.setattr(
        "pygame.time.get_ticks", lambda: 0 if visible else REC_FLASH_MS
    )


def test_armed_recording_monitor_eye_flashes_when_focused(monkeypatch) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(armed_slots={"layer_2"}, recording=True, focus_row=1, submenu_focused=True)

    _set_rec_flash(monkeypatch, True)
    surface_on = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_on, state)

    _set_rec_flash(monkeypatch, False)
    surface_off = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_off, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    flash_on = _header_bg_pixel(surface_on, overlay, "eye", row_y, row_h)
    flash_off = _header_bg_pixel(surface_off, overlay, "eye", row_y, row_h)

    assert flash_on == OVERRIDE_BG
    assert flash_off != OVERRIDE_BG
    assert flash_on != flash_off


def test_armed_recording_monitor_eye_uses_override_bg_when_flash_on(monkeypatch) -> None:
    _set_rec_flash(monkeypatch, True)
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(armed_slots={"layer_2"}, recording=True, focus_row=1, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    assert _header_bg_pixel(surface, overlay, "eye", row_y, row_h) == OVERRIDE_BG


def test_armed_recording_monitor_eye_hides_override_bg_when_flash_off(monkeypatch) -> None:
    _set_rec_flash(monkeypatch, False)
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(armed_slots={"layer_2"}, recording=True, focus_row=1, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    assert _header_bg_pixel(surface, overlay, "eye", row_y, row_h) != OVERRIDE_BG


def _header_x(overlay: TimelineOverlay, target: str) -> int:
    layout = overlay.layout
    assert layout is not None
    return header_button_x(
        target,
        padding=overlay._padding,
        label_width=overlay._layer_num_width + overlay._stem_abbrev_width,
        slot_w=layout.slot_w,
    )


def _header_bg_pixel(
    surface: pygame.Surface,
    overlay: TimelineOverlay,
    target: str,
    row_y: int,
    row_h: int,
) -> tuple[int, ...]:
    """A pixel at the top-left corner of a header button's box, clear of its glyph."""
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    layout = overlay.layout
    assert layout is not None
    sample_x = panel_x + _header_x(overlay, target) + 1
    sample_y = panel_y + row_y + (row_h - layout.slot_w) // 2 + 1
    return surface.get_at((sample_x, sample_y))[:3]


def _arm_bg_pixel(surface: pygame.Surface, overlay: TimelineOverlay, row_y: int, row_h: int) -> tuple[int, ...]:
    return _header_bg_pixel(surface, overlay, "arm", row_y, row_h)


def test_armed_recording_arm_button_flashes_with_rec(monkeypatch) -> None:
    _set_rec_flash(monkeypatch, True)
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(armed_slots={"layer_2"}, recording=True, focus_row=0, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    flash_on = _arm_bg_pixel(surface, overlay, row_y, row_h)

    _set_rec_flash(monkeypatch, False)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    flash_off = _arm_bg_pixel(surface, overlay, row_y, row_h)

    assert flash_on[0] > flash_off[0] + 40
    assert flash_on[0] > 150


def test_armed_not_recording_arm_button_always_red() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    armed_state = strip_view_state(armed_slots={"layer_2"}, recording=False, focus_row=0)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, armed_state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    armed_color = _arm_bg_pixel(surface, overlay, row_y, row_h)

    _draw(overlay, surface, strip_view_state(armed_slots=set(), recording=False, focus_row=0))
    unarmed_color = _arm_bg_pixel(surface, overlay, row_y, row_h)

    assert armed_color[0] > unarmed_color[0] + 40
    assert armed_color[0] > 150


def test_armed_stem_label_uses_highlight() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(armed_slots={"layer_2"}, recording=False, focus_row=0)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    abbrev_x = overlay._padding + overlay._layer_num_width
    left = panel_x + abbrev_x
    top = panel_y + row_y
    found_highlight = any(
        surface.get_at((x, y))[:3] == HIGHLIGHT
        for y in range(top, top + row_h)
        for x in range(left, left + overlay._stem_abbrev_width)
    )
    assert found_highlight


def test_unarmed_recording_monitor_eye_not_override_bg() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(armed_slots={"layer_2"}, recording=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    drums_layout = next(row for row in overlay.row_layout if row[5] == "layer_1")
    _, _, row_y, _, row_h, _ = drums_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    assert _header_bg_pixel(surface, overlay, "eye", row_y, row_h) != OVERRIDE_BG


def test_override_armed_recording_monitor_eye_flashes(monkeypatch) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        armed_slots={"layer_2"},
        override_slots={"layer_2"},
        recording=True,
        focus_row=1,
        submenu_focused=True,
    )

    _set_rec_flash(monkeypatch, True)
    surface_on = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_on, state)

    _set_rec_flash(monkeypatch, False)
    surface_off = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_off, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    flash_on = _header_bg_pixel(surface_on, overlay, "eye", row_y, row_h)
    flash_off = _header_bg_pixel(surface_off, overlay, "eye", row_y, row_h)

    assert flash_on == OVERRIDE_BG
    assert flash_off != OVERRIDE_BG
    assert flash_on != flash_off


def test_override_row_shows_back_to_timeline_button() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state(override_slots={"layer_2"}, focus_row=0))
    rows = {row[5]: row for row in overlay.row_layout}
    _, _, row_y, _, row_h, _ = rows["layer_2"]
    assert _header_bg_pixel(surface, overlay, "release", row_y, row_h) == OVERRIDE_BG
    _, _, row_y, _, row_h, _ = rows["layer_1"]
    assert _header_bg_pixel(surface, overlay, "release", row_y, row_h) != OVERRIDE_BG


def _header_snapshot(state: TimelineViewState) -> tuple[pygame.Surface, TimelineOverlay]:
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    return surface, overlay


def _row_header_pixels(surface: pygame.Surface, overlay: TimelineOverlay, row: int) -> list:
    panel = overlay.panel_rect
    assert panel is not None
    _, _, row_y, _, row_h, _ = overlay.row_layout[row]
    bar_left, _ = overlay.bar_layout
    y = panel[1] + row_y + row_h // 2
    return [surface.get_at((panel[0] + x, y)) for x in range(overlay._padding, bar_left)]


def test_hovered_label_and_empty_release_slot_draw_no_wash() -> None:
    pygame.init()
    plain, overlay = _header_snapshot(strip_view_state(focus_row=1))
    for target in ("label", "release"):
        hovered, _ = _header_snapshot(
            strip_view_state(focus_row=1, hover_row_target=(target, 0))
        )
        assert _row_header_pixels(hovered, overlay, 0) == _row_header_pixels(plain, overlay, 0)


def test_hovered_buttons_draw_a_wash() -> None:
    pygame.init()
    plain, overlay = _header_snapshot(strip_view_state(focus_row=1))
    _, _, row_y, _, row_h, _ = overlay.row_layout[0]
    for target in ("arm", "solo", "eye"):
        hovered, _ = _header_snapshot(
            strip_view_state(focus_row=1, hover_row_target=(target, 0))
        )
        assert _header_bg_pixel(hovered, overlay, target, row_y, row_h) != (
            _header_bg_pixel(plain, overlay, target, row_y, row_h)
        )


def test_solo_row_lights_its_solo_button() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state(solo_slot="layer_2", focus_row=0))
    rows = {row[5]: row for row in overlay.row_layout}
    _, _, row_y, _, row_h, _ = rows["layer_2"]
    assert _header_bg_pixel(surface, overlay, "solo", row_y, row_h) == SOLO_BG
    _, _, row_y, _, row_h, _ = rows["layer_1"]
    assert _header_bg_pixel(surface, overlay, "solo", row_y, row_h) != SOLO_BG


def test_override_slots_use_override_bg_on_monitor_eye() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(override_slots={"layer_2"}, focus_row=1)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    assert _header_bg_pixel(surface, overlay, "eye", row_y, row_h) == OVERRIDE_BG


def test_recording_baseline_does_not_draw_cue_tick() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        lanes={"layer_1": make_lane(False)},
        position_sec=10.0,
        armed_slots={"layer_1"},
        recording=True,
        record_start_sec=10.0,
        record_baseline={"layer_1": True},
        monitor_visible={"layer_1": True, "layer_2": True, "layer_3": True, "layer_4": True},
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    assert bar_tick_times_for_row(state, "layer_1") == []


def test_draw_override_and_take_state_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        lanes={"layer_1": make_lane(True, (25.0, False))},
        position_sec=25.0,
        focus_row=1,
        armed_slots={"layer_2"},
        recording=True,
        monitor_visible={"layer_1": True, "layer_2": False, "layer_3": True, "layer_4": True},
        override_slots={"layer_1"},
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is not None


def test_clip_breakpoints_interpolates_at_edges() -> None:
    bps = [(0.0, 0.0), (10.0, 1.0), (20.0, 0.5)]
    clipped = clip_breakpoints(bps, 5.0, 15.0)
    assert clipped[0][0] == 5.0
    assert clipped[0][1] == pytest.approx(0.5)
    assert clipped[-1][0] == 15.0
    assert clipped[-1][1] == pytest.approx(0.75)
    assert any(abs(t - 10.0) < 1e-9 for t, _ in clipped)


def test_clip_breakpoints_keeps_step_at_end_vertical() -> None:
    """A step exactly at the clip end must not ramp the segment before it."""
    bps = [(0.0, 0.0), (10.0, 0.0), (10.0, 1.0)]
    clipped = clip_breakpoints(bps, 5.0, 10.0)
    assert clipped == [(5.0, 0.0), (10.0, 0.0), (10.0, 1.0)]


def test_clip_breakpoints_keeps_step_at_start_vertical() -> None:
    """A step exactly at the clip start must not ramp the segment after it."""
    bps = [(0.0, 0.0), (0.0, 1.0), (50.0, 1.0)]
    clipped = clip_breakpoints(bps, 0.0, 30.0)
    assert clipped == [(0.0, 0.0), (0.0, 1.0), (30.0, 1.0)]


def test_partial_level_bar_shorter_than_full() -> None:
    """Partial level yields a shorter filled height than level 1.0."""
    import pygame as _pygame

    from cleave.viz.timeline_strip_static import bar_level_y

    bar_rect = _pygame.Rect(0, 0, 100, 20)
    assert bar_level_y(bar_rect, 0.25) > bar_level_y(bar_rect, 1.0)
    assert bar_level_y(bar_rect, 0.0) == bar_rect.bottom
    assert bar_level_y(bar_rect, 1.0) == bar_rect.y


def test_lane_level_segments_default_only() -> None:
    lane = TimelineLane(baseline=0.0, cues=[])
    segments = lane_level_segments(lane, 60.0, inherit=1.0)
    assert segments == [(0.0, 60.0, 0.0)]


def test_lane_level_segments_from_cues() -> None:
    lane = make_lane(True, (10.0, False), (30.0, True))
    segments = lane_level_segments(lane, 60.0, inherit=1.0)
    assert segments == [
        (0.0, 10.0, 1.0),
        (10.0, 30.0, 0.0),
        (30.0, 60.0, 1.0),
    ]


def test_lane_level_segments_other_stem_unchanged_across_unrelated_cue() -> None:
    lane = make_lane(True)
    segments = lane_level_segments(lane, 20.0, inherit=1.0)
    assert segments == [(0.0, 20.0, 1.0)]


def test_cue_times_for_stem_lists_lane_transitions() -> None:
    lane = make_lane(True, (5.0, False), (15.0, True))
    assert cue_times_for_stem(lane, 30.0) == [5.0, 15.0]


def test_cue_times_for_stem_clamps_to_duration() -> None:
    lane = make_lane(True, (5.0, False), (50.0, True))
    assert cue_times_for_stem(lane, 10.0) == [5.0]


def test_stem_labels_use_abbreviations() -> None:
    assert stem_abbreviation("drums") == "D"
    assert stem_abbreviation("bass") == "B"
    assert stem_abbreviation("vocals") == "V"
    assert stem_abbreviation("other") == "O"
    assert layer_num_prefix(1) == " 1 "
    assert stem_abbrev_label("drums") == " D "
    assert stem_label_text(1, "drums") == " 1  D "
    assert stem_label_text(4, "bass") == " 4  B "


def test_playhead_x_at_known_position() -> None:
    bar_left = 40
    bar_width = 200
    duration = 100.0
    assert playhead_x(0.0, bar_left, bar_width, 0.0, duration) == bar_left
    assert playhead_x(50.0, bar_left, bar_width, 0.0, duration) == bar_left + 100
    assert playhead_x(100.0, bar_left, bar_width, 0.0, duration) == bar_left + bar_width


def test_time_to_x_clamps_out_of_range() -> None:
    bar_left = 10
    bar_width = 90
    assert time_to_x(-5.0, bar_left, bar_width, 0.0, 60.0) == bar_left
    assert time_to_x(120.0, bar_left, bar_width, 0.0, 60.0) == bar_left + bar_width


def test_draw_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        lanes={"layer_1": make_lane(True, (25.0, False))},
        position_sec=25.0,
        focus_row=1,
        armed_slots={"layer_2"},
        recording=True,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    panel = overlay.panel_rect
    assert panel is not None
    px, py, pw, ph = panel
    sw, sh = surface.get_size()
    assert px >= 0 and py >= 0
    assert px + pw <= sw and py + ph <= sh
    surface.subsurface(panel)


def test_compose_panel_occupies_timeline_band() -> None:
    pygame.init()
    from cleave.viz.theme import timeline_panel_height_px
    from cleave.viz.timeline_strip_layout import timeline_band_height_px

    overlay = TimelineOverlay()
    state = strip_view_state()
    row_count = len(state.layer_z_order)
    viewport_w, viewport_h = 1280, 720
    band_h = timeline_band_height_px(row_count)
    band = (0, viewport_h - band_h, viewport_w, band_h)
    composed = overlay.compose_panel(
        state,
        viewport_width=viewport_w,
        viewport_height=viewport_h,
        timeline_rect=band,
    )
    assert composed is not None
    panel = overlay.panel_rect
    assert panel is not None
    px, py, pw, ph = panel
    assert px == 0
    assert pw == viewport_w
    assert ph == timeline_panel_height_px(row_count)
    assert py == viewport_h - ph


def test_compose_panel_fills_band_width_inside_container() -> None:
    pygame.init()
    from cleave.viz.timeline_strip_layout import timeline_band_height_px

    overlay = TimelineOverlay()
    state = strip_view_state()
    band_h = timeline_band_height_px(len(state.layer_z_order))
    band = (40, 720 - band_h, 1000, band_h)
    overlay.compose_panel(
        state, viewport_width=1280, viewport_height=720, timeline_rect=band
    )
    assert overlay.panel_rect is not None
    px, _py, pw, _ph = overlay.panel_rect
    assert (px, pw) == (40, 1000)


def test_static_panel_has_no_border() -> None:
    pygame.init()
    from cleave.viz.theme import PANEL_EDGE

    overlay = TimelineOverlay()
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state())
    panel = overlay._cache.panel
    assert panel is not None
    assert panel.get_at((0, 0))[:3] != PANEL_EDGE
    edge = (panel.get_width() - 1, panel.get_height() // 2)
    assert panel.get_at(edge)[:3] != PANEL_EDGE


def _marker_upload(
    overlay: TimelineOverlay, state: TimelineViewState
) -> tuple[pygame.Surface, int, int, int]:
    """Compose *state*; return the upload, bar left/width, and ruler tick-top y."""
    from cleave.viz.timeline_panel_cache import timeline_badge_reserve_px
    from cleave.viz.timeline_ruler import ruler_tick_top

    composed = overlay.compose_panel(state, viewport_width=1280, viewport_height=720)
    assert composed is not None
    assert overlay.bar_layout is not None
    bar_left, bar_width = overlay.bar_layout
    tick_top = ruler_tick_top(timeline_badge_reserve_px() + overlay._padding)
    return composed.upload_surface, bar_left, bar_width, tick_top


def test_song_markers_rise_through_ruler_and_rows() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        duration_sec=100.0,
        song_marker_times=(25.0, 75.0),
        selected_song_marker_index=1,
    )
    upload, bar_left, bar_width, tick_top = _marker_upload(overlay, state)
    from cleave.viz.timeline_panel_cache import timeline_badge_reserve_px

    row_y = timeline_badge_reserve_px() + overlay._padding + overlay.row_layout[0][4] // 2
    x_plain = time_to_x(25.0, bar_left, bar_width, 0.0, 100.0)
    x_selected = time_to_x(75.0, bar_left, bar_width, 0.0, 100.0)
    for y in (tick_top + 1, row_y):
        assert upload.get_at((x_plain, y))[:3] == SONG_MARKER
        assert upload.get_at((x_selected, y))[:3] == SONG_MARKER_SELECTED
    assert upload.get_at((x_plain, tick_top - 1))[:3] != SONG_MARKER
    # Plain is SONG_MARKER_WIDTH wide; the selected one is wider.
    assert upload.get_at((x_plain + 1, row_y))[:3] == SONG_MARKER
    assert upload.get_at((x_plain + 2, row_y))[:3] != SONG_MARKER
    assert upload.get_at((x_selected + 2, row_y))[:3] == SONG_MARKER_SELECTED
    # Markers are drawn live, so the static panel has none.
    static = overlay._cache.panel
    assert static is not None
    static_y = overlay._padding + overlay.row_layout[0][4] // 2
    assert static.get_at((x_plain, static_y))[:3] != SONG_MARKER


def test_selected_song_marker_flashes_and_dirties_its_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    start = 10_000
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: start)
    state = strip_view_state(
        duration_sec=100.0,
        song_marker_times=(40.0,),
        selected_song_marker_index=0,
        song_marker_flash_start_ms=start,
    )
    upload, bar_left, bar_width, tick_top = _marker_upload(overlay, state)
    x = time_to_x(40.0, bar_left, bar_width, 0.0, 100.0)
    half = SELECTED_CLIP_FLASH_TICK_WIDTH // 2
    assert upload.get_at((x + half, tick_top + 1))[:3] == SELECTED_CLIP_FLASH_YELLOW
    assert any(
        rx <= x < rx + rw and ry <= tick_top + 1 < ry + rh
        for rx, ry, rw, rh in overlay._cache.last_flash_rects
    )

    monkeypatch.setattr(
        pygame.time, "get_ticks", lambda: start + SELECTED_CLIP_FLASH_HALF_MS
    )
    upload, *_ = _marker_upload(overlay, state)
    assert upload.get_at((x, tick_top + 1))[:3] == SELECTED_CLIP_FLASH_RED

    monkeypatch.setattr(
        pygame.time, "get_ticks", lambda: start + SELECTED_CLIP_FLASH_DURATION_MS
    )
    upload, *_ = _marker_upload(overlay, state)
    assert upload.get_at((x, tick_top + 1))[:3] == SONG_MARKER_SELECTED
    assert upload.get_at((x + half, tick_top + 1))[:3] != SONG_MARKER_SELECTED


def test_hit_at_reports_song_marker_on_ruler_and_rows() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state(duration_sec=100.0, song_marker_times=(30.0,)))
    px, py, _, _ = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    x = px + time_to_x(30.0, bar_left, bar_width, 0.0, 100.0)
    row_y = py + overlay.row_layout[0][2] + 1

    assert overlay.hit_at(x, py - 2).marker_index == 0
    assert overlay.hit_at(x + 2, row_y).marker_index == 0
    assert overlay.hit_at(x + 40, row_y).marker_index is None
    assert overlay.hit_at(px + 10, row_y).marker_index is None


def test_draw_when_disabled() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(enabled=False)
    surface = pygame.Surface((640, 360), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is not None


def test_draw_skipped_when_visibility_zero() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(enabled=True)
    composed = overlay.compose_panel(
        state,
        viewport_width=640,
        viewport_height=360,
        visibility=0.0,
    )
    assert composed is None
    assert overlay.panel_rect is None


def test_armed_row_layout_recorded() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(armed_slots={"layer_1"}, layer_z_order=list(DEFAULT_LAYER_SLOTS))
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    drums_layout = next(row for row in overlay.row_layout if row[5] == "layer_1")
    row_index, x, y, w, h, stem = drums_layout
    assert stem == "layer_1"
    assert row_index == 0
    assert w > 0 and h > 0
    assert overlay.panel_rect is not None


def test_focus_row_index_matches_stem() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(focus_row=2, layer_z_order=list(DEFAULT_LAYER_SLOTS))
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    vocals_layout = next(row for row in overlay.row_layout if row[5] == "layer_3")
    assert vocals_layout[0] == 2
    assert overlay.panel_rect is not None


def test_corner_buttons_drop_below_the_band_top() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state(position_sec=30.0, recording=True))
    from cleave.viz.timeline_strip_layout import TRANSPORT_BUTTON_DROP_PX

    play, record = overlay.layout.transport_rects()
    assert play[1] == record[1] == TRANSPORT_BUTTON_DROP_PX


def test_record_button_stops_padding_short_of_ruler() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state(position_sec=0.0))
    _, record = overlay.layout.transport_rects()
    bar_left, _ = overlay.bar_layout
    assert record[0] + record[2] == bar_left - overlay.layout.padding


def test_bars_make_room_for_back_to_timeline_only_while_overridden() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state())
    layout = overlay.layout
    eye_right = layout.header_button_x("eye") + layout.slot_w
    assert layout.bar_left == eye_right + layout.padding
    _draw(overlay, surface, strip_view_state(override_slots={"layer_1"}))
    layout = overlay.layout
    assert layout.bar_left == layout.header_button_x("release") + layout.slot_w + layout.padding
    assert layout.bar_left > eye_right + layout.padding


def test_upscale_expands_bar_width_not_row_height() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state()

    baseline_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, baseline_surface, state)
    baseline_panel = overlay.panel_rect
    baseline_row_h = overlay.row_layout[0][4]
    _, baseline_bar_width = overlay.bar_layout
    assert baseline_panel is not None
    assert overlay.bar_layout is not None

    upscaled_surface = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    _draw(overlay, upscaled_surface, state)
    upscaled_panel = overlay.panel_rect
    upscaled_row_h = overlay.row_layout[0][4]
    _, upscaled_bar_width = overlay.bar_layout
    assert upscaled_panel is not None
    assert overlay.bar_layout is not None

    assert upscaled_row_h == baseline_row_h
    assert upscaled_panel[3] == baseline_panel[3]
    assert upscaled_bar_width > baseline_bar_width
    assert upscaled_panel[2] > baseline_panel[2]


def _bar_level_at(
    state: TimelineViewState,
    slot: str,
    t: float,
) -> float:
    """Return the strip level for a slot at time t from breakpoints."""
    from cleave.viz.timeline_strip_state import level_at_breakpoints

    bps = bar_level_breakpoints_for_row(state, slot)
    return level_at_breakpoints(bps, t)


def _bar_visible_at(
    state: TimelineViewState,
    slot: str,
    t: float,
) -> bool:
    return _bar_level_at(state, slot, t) > LEVEL_EPS


def test_bar_shows_fill_for_backward_skipped_range() -> None:
    """After a backward seek during recording, the bar shows the fill state."""
    slot = "layer_1"
    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": True},
        position_sec=20.0,
        duration_sec=100.0,
        recording=True,
        record_start_sec=20.0,
        record_baseline={"layer_1": True},
        record_buffer={"layer_1": [SlotCue(t=20.0, level=0.0)]},
        record_high_water_mark=30.0,
    )
    assert _bar_visible_at(state, slot, 25.0) is False
    assert _bar_visible_at(state, slot, 20.0) is False
    assert _bar_visible_at(state, slot, 10.0) is True


def test_bar_shows_fill_for_backward_seek_with_expanded_punch_start() -> None:
    """Backward seek past record_start: bar still shows fill for skipped range."""
    slot = "layer_1"
    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": False},
        position_sec=10.0,
        duration_sec=100.0,
        recording=True,
        record_start_sec=10.0,
        record_baseline={"layer_1": False},
        record_buffer={"layer_1": [SlotCue(t=10.0, level=1.0)]},
        record_high_water_mark=20.0,
    )
    assert _bar_visible_at(state, slot, 15.0) is True
    assert _bar_visible_at(state, slot, 10.0) is True
    assert _bar_visible_at(state, slot, 5.0) is False


def test_bar_without_high_water_mark_behaves_as_before() -> None:
    """No backward seek: bar shows record_buffer only up to playhead."""
    slot = "layer_1"
    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": True},
        position_sec=25.0,
        duration_sec=100.0,
        recording=True,
        record_start_sec=20.0,
        record_baseline={"layer_1": True},
        record_buffer={"layer_1": [SlotCue(t=20.0, level=0.0)]},
        record_high_water_mark=None,
    )
    assert _bar_visible_at(state, slot, 22.0) is False
    assert _bar_visible_at(state, slot, 30.0) is True


def test_draw_with_selected_clip_and_role_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=[
                    SlotCue(t=10.0, level=1.0, blend="add", role="lead"),
                    SlotCue(t=20.0, level=0.0),
                ],
            )
        },
        position_sec=12.0,
        focus_row=0,
        submenu_focused=True,
        selected_clip_t={"layer_1": 10.0},
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is not None


def test_role_glyph_not_drawn_on_off_cue() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    # Bypass canonicalize so an off cue can still carry a stale role.
    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": 1.0},
        lanes={
            "layer_1": TimelineLane(
                baseline=1.0,
                cues=[SlotCue(t=25.0, level=0.0, role="pulse")],
            )
        },
        duration_sec=100.0,
        focus_row=0,
        position_sec=0.0,
    )
    composed = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    assert not overlay._cache.last_glyph_rects


def test_bar_cues_include_synthetic_opening_baseline() -> None:
    from cleave.viz.timeline_strip_state import bar_cues_for_row

    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": 1.0},
        lanes={
            "layer_1": TimelineLane(
                baseline=0.5,
                cues=[SlotCue(t=10.0, level=0.0), SlotCue(t=20.0, level=1.0)],
            )
        },
        duration_sec=100.0,
    )
    cues = bar_cues_for_row(state, "layer_1")
    assert cues[0] == SlotCue(t=0.0, level=0.5)
    assert [cue.t for cue in cues] == [0.0, 10.0, 20.0]


def _clip_strip(overlay: TimelineOverlay, **kwargs):
    """Compose one row with a clip from 25 s to 75 s; return the static panel and its geometry."""
    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": 1.0},
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=[SlotCue(t=25.0, level=1.0), SlotCue(t=75.0, level=0.0)],
            )
        },
        duration_sec=100.0,
        focus_row=0,
        **kwargs,
    )
    composed = overlay.compose_panel(state, viewport_width=1280, viewport_height=720)
    assert composed is not None
    static = overlay._cache.panel
    assert static is not None
    assert overlay.bar_layout is not None
    bar_left, bar_width = overlay.bar_layout
    start_x = time_to_x(25.0, bar_left, bar_width, 0.0, 100.0)
    end_x = time_to_x(75.0, bar_left, bar_width, 0.0, 100.0)
    row_h = overlay.row_layout[0][4]
    return composed, static, start_x, end_x, overlay._padding, row_h


def test_selected_clip_outline_drawn_on_static_panel() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    _, static, start_x, end_x, top, row_h = _clip_strip(
        overlay, selected_clip_t={"layer_1": 25.0}
    )
    mid_x = (start_x + end_x) // 2
    mid_y = top + row_h // 2
    assert SELECTED_CLIP_COLOR == HIGHLIGHT
    # The outline runs along the top and bottom of the clip, and down each edge.
    assert static.get_at((mid_x, top))[:3] == SELECTED_CLIP_COLOR
    assert static.get_at((mid_x, top + row_h - 1))[:3] == SELECTED_CLIP_COLOR
    assert static.get_at((start_x, mid_y))[:3] == SELECTED_CLIP_COLOR
    assert static.get_at((end_x - 1, mid_y))[:3] == SELECTED_CLIP_COLOR
    # It stays on the clip: not inside it, and not past its edges.
    assert static.get_at((mid_x, mid_y))[:3] != SELECTED_CLIP_COLOR
    assert static.get_at((start_x - 2, mid_y))[:3] != SELECTED_CLIP_COLOR
    assert static.get_at((end_x + 2, mid_y))[:3] != SELECTED_CLIP_COLOR
    assert static.get_at((mid_x, top + SELECTED_CLIP_OUTLINE_WIDTH))[:3] != (
        SELECTED_CLIP_COLOR
    )


def test_hovered_clip_draws_edge_handles_only_where_clips_can_be_edited() -> None:
    pygame.init()

    def edge_rgb(**kwargs) -> tuple[int, int, int]:
        _, static, start_x, _end_x, top, row_h = _clip_strip(TimelineOverlay(), **kwargs)
        return static.get_at((start_x + CLIP_HANDLE_WIDTH - 1, top + row_h // 2))[:3]

    plain = edge_rgb()
    assert edge_rgb(hover_clip=(0, 25.0, None)) == LABEL != plain
    # A hover on another row, or on a locked timeline, draws no handles.
    assert edge_rgb(hover_clip=(1, 25.0, None)) == plain
    assert edge_rgb(hover_clip=(0, 25.0, None), locked=True) == plain


def test_selected_clip_outline_only_on_focused_track() -> None:
    """Remembered selections stay in selected_clip_t; only focus_row draws the outline."""
    pygame.init()
    overlay = TimelineOverlay()
    lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=25.0, level=1.0)],
        ),
        "layer_2": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=50.0, level=1.0)],
        ),
    }
    selected = {"layer_1": 25.0, "layer_2": 50.0}
    base_kwargs = dict(
        layer_z_order=["layer_1", "layer_2"],
        defaults={"layer_1": 1.0, "layer_2": 1.0},
        lanes=lanes,
        duration_sec=100.0,
        selected_clip_t=selected,
    )

    def _compose(focus_row: int):
        return overlay.compose_panel(
            strip_view_state(focus_row=focus_row, **base_kwargs),
            viewport_width=1280,
            viewport_height=720,
        )

    def _tick_rgb(cue_t: float, row_index: int) -> tuple[int, int, int]:
        static = overlay._cache.panel
        assert static is not None
        assert overlay.bar_layout is not None
        bar_left, bar_width = overlay.bar_layout
        tick_x = time_to_x(cue_t, bar_left, bar_width, 0.0, 100.0)
        row_h = overlay.row_layout[row_index][4]
        y = overlay._padding + row_index * (row_h + overlay._row_gap) + row_h // 2
        return static.get_at((tick_x, y))[:3]

    assert _compose(0) is not None
    assert _tick_rgb(25.0, 0) == SELECTED_CLIP_COLOR
    assert _tick_rgb(50.0, 1) != SELECTED_CLIP_COLOR

    assert _compose(1) is not None
    assert _tick_rgb(25.0, 0) != SELECTED_CLIP_COLOR
    assert _tick_rgb(50.0, 1) == SELECTED_CLIP_COLOR

    assert _compose(0) is not None
    assert _tick_rgb(25.0, 0) == SELECTED_CLIP_COLOR
    assert _tick_rgb(50.0, 1) != SELECTED_CLIP_COLOR


def test_prune_expired_selected_clip_flash() -> None:
    assert prune_expired_selected_clip_flash(None, ticks_ms=0) is None
    assert prune_expired_selected_clip_flash(1000, ticks_ms=1000) == 1000
    assert (
        prune_expired_selected_clip_flash(
            1000, ticks_ms=1000 + SELECTED_CLIP_FLASH_DURATION_MS - 1
        )
        == 1000
    )
    assert (
        prune_expired_selected_clip_flash(
            1000, ticks_ms=1000 + SELECTED_CLIP_FLASH_DURATION_MS
        )
        is None
    )


def test_selected_clip_flash_blink_colors() -> None:
    start = 1000
    assert selected_clip_flash_active(start, ticks_ms=start)
    assert selected_clip_flash_bright(start, ticks_ms=start)
    assert selected_clip_flash_color(start, ticks_ms=start) == SELECTED_CLIP_FLASH_YELLOW
    assert SELECTED_CLIP_FLASH_YELLOW == HIGHLIGHT
    assert SELECTED_CLIP_COLOR == HIGHLIGHT
    assert SELECTED_CLIP_FLASH_RED == ARMED_BG
    alt_t = start + SELECTED_CLIP_FLASH_HALF_MS
    assert selected_clip_flash_active(start, ticks_ms=alt_t)
    assert not selected_clip_flash_bright(start, ticks_ms=alt_t)
    assert selected_clip_flash_color(start, ticks_ms=alt_t) == SELECTED_CLIP_FLASH_RED
    expired = start + SELECTED_CLIP_FLASH_DURATION_MS
    assert not selected_clip_flash_active(start, ticks_ms=expired)
    assert not selected_clip_flash_bright(start, ticks_ms=expired)
    assert selected_clip_flash_color(start, ticks_ms=expired) == SELECTED_CLIP_COLOR


def test_selected_clip_flash_live_patches_yellow(monkeypatch) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    start = 5000
    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": 1.0},
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=[SlotCue(t=25.0, level=1.0)],
            )
        },
        duration_sec=100.0,
        focus_row=0,
        selected_clip_t={"layer_1": 25.0},
        selected_clip_flash_start_ms=start,
    )
    # Yellow half of the blink: a thicker outline live-patched over the settled one.
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: start)
    composed = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    upload = composed.upload_surface
    assert overlay.bar_layout is not None
    bar_left, bar_width = overlay.bar_layout
    tick_x = time_to_x(25.0, bar_left, bar_width, 0.0, 100.0)
    from cleave.viz.timeline_panel_cache import timeline_badge_reserve_px

    row_h = overlay.row_layout[0][4]
    top = timeline_badge_reserve_px() + overlay._padding
    mid_x = tick_x + 40
    inner = SELECTED_CLIP_FLASH_OUTLINE_WIDTH - 1
    assert upload.get_at((mid_x, top + inner))[:3] == SELECTED_CLIP_FLASH_YELLOW
    assert upload.get_at((mid_x, top + row_h - 1 - inner))[:3] == (
        SELECTED_CLIP_FLASH_YELLOW
    )
    static = overlay._cache.panel
    assert static is not None
    assert static.get_at((mid_x, overlay._padding))[:3] == SELECTED_CLIP_COLOR
    # The settled outline is thinner than the flash.
    assert static.get_at((mid_x, overlay._padding + inner))[:3] != SELECTED_CLIP_COLOR
    assert any(
        rx <= mid_x < rx + rw and ry <= top < ry + rh
        for rx, ry, rw, rh in overlay._cache.last_flash_rects
    )


def test_blit_role_glyph_xor_inverts_destination_rgb() -> None:
    pygame.init()
    panel = pygame.Surface((48, 48), pygame.SRCALPHA)
    bg = (40, 80, 120)
    panel.fill((*bg, 255))
    font = overlay_font(16, bold=True)
    touched = blit_role_glyph_xor(panel, "L", x=8, y=8, font=font)
    assert touched is not None
    expected = (bg[0] ^ 255, bg[1] ^ 255, bg[2] ^ 255)
    found = False
    x0, y0, w, h = touched
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if panel.get_at((x, y))[:3] == expected:
                found = True
                break
        if found:
            break
    assert found


def test_role_glyph_side_on_right_off_left() -> None:
    assert role_glyph_side(previous_level=0.0, cue_level=1.0) == "right"
    assert role_glyph_side(previous_level=LEVEL_EPS, cue_level=0.5) == "right"
    assert role_glyph_side(previous_level=1.0, cue_level=0.0) == "left"
    assert role_glyph_side(previous_level=0.25, cue_level=LEVEL_EPS) == "left"


def test_role_glyph_side_both_enabled_prefers_right() -> None:
    assert role_glyph_side(previous_level=0.25, cue_level=1.0) == "right"
    assert role_glyph_side(previous_level=1.0, cue_level=0.5) == "right"


def test_role_glyph_previous_level_before_cue() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=10.0, level=1.0, role="lead"),
            SlotCue(t=20.0, level=0.0),
        ],
    )
    assert role_glyph_previous_level(lane, 10.0, inherit=1.0) == pytest.approx(0.0)
    assert role_glyph_previous_level(lane, 20.0, inherit=1.0) == pytest.approx(1.0)
    assert role_glyph_previous_level(lane, 0.0, inherit=1.0) == pytest.approx(0.0)


def test_role_glyph_anchor_bottom_and_side_offset() -> None:
    pygame.init()
    bar_rect = pygame.Rect(40, 10, 200, 20)
    tick_x = 100
    glyph_w, glyph_h = 8, 12
    right_x, right_y = role_glyph_anchor(
        tick_x=tick_x,
        bar_rect=bar_rect,
        glyph_w=glyph_w,
        glyph_h=glyph_h,
        side="right",
    )
    left_x, left_y = role_glyph_anchor(
        tick_x=tick_x,
        bar_rect=bar_rect,
        glyph_w=glyph_w,
        glyph_h=glyph_h,
        side="left",
    )
    assert right_x == tick_x + ROLE_GLYPH_TICK_GAP
    assert left_x == tick_x - ROLE_GLYPH_TICK_GAP - glyph_w
    assert right_y == left_y == bar_rect.bottom - glyph_h - ROLE_GLYPH_BOTTOM_PAD
    assert right_y + glyph_h <= bar_rect.bottom
    assert right_y >= bar_rect.top
    assert ROLE_GLYPH_TICK_GAP >= SELECTED_CLIP_FLASH_TICK_WIDTH // 2


def test_role_glyph_anchor_clamps_inside_bar() -> None:
    pygame.init()
    bar_rect = pygame.Rect(40, 10, 30, 16)
    glyph_w, glyph_h = 20, 20
    left_x, left_y = role_glyph_anchor(
        tick_x=bar_rect.left + 2,
        bar_rect=bar_rect,
        glyph_w=glyph_w,
        glyph_h=glyph_h,
        side="left",
    )
    right_x, right_y = role_glyph_anchor(
        tick_x=bar_rect.right - 2,
        bar_rect=bar_rect,
        glyph_w=glyph_w,
        glyph_h=glyph_h,
        side="right",
    )
    assert left_x == bar_rect.left
    assert right_x == bar_rect.right - glyph_w
    assert left_y == bar_rect.top
    assert right_y == bar_rect.top


def test_role_glyph_xor_drawn_late_on_upload_not_static() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        layer_z_order=["layer_1"],
        defaults={"layer_1": 1.0},
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=[SlotCue(t=25.0, level=1.0, role="lead")],
            )
        },
        duration_sec=100.0,
        focus_row=0,
        position_sec=0.0,
    )
    composed = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    static = overlay._cache.panel
    assert static is not None
    upload = composed.upload_surface
    assert overlay.bar_layout is not None
    bar_left, bar_width = overlay.bar_layout
    tick_x = time_to_x(25.0, bar_left, bar_width, 0.0, 100.0)
    row_h = overlay.row_layout[0][4]
    row_y = overlay._padding
    bar_rect = pygame.Rect(
        bar_left,
        row_y + timeline_ui_metrics().bar_vertical_inset,
        bar_width,
        max(1, row_h - timeline_ui_metrics().bar_vertical_inset * 2),
    )
    bold = overlay_font(timeline_ui_metrics().font_size, bold=True)
    glyph_w, glyph_h = bold.size("L")
    # On cue (baseline 0 -> level 1): glyph to the right of the tick, bar bottom.
    glyph_x, glyph_y = role_glyph_anchor(
        tick_x=tick_x,
        bar_rect=bar_rect,
        glyph_w=glyph_w,
        glyph_h=glyph_h,
        side="right",
    )
    assert role_glyph_side(previous_level=0.0, cue_level=1.0) == "right"
    assert glyph_x > tick_x
    assert glyph_y + glyph_h <= bar_rect.bottom
    from cleave.viz.timeline_panel_cache import timeline_badge_reserve_px

    upload_y = timeline_badge_reserve_px() + glyph_y
    # Static panel omits glyphs (drawn late on the upload surface after playhead).
    assert overlay._cache.last_glyph_rects
    diff_found = False
    for dy in range(glyph_h):
        for dx in range(glyph_w):
            static_px = static.get_at((glyph_x + dx, glyph_y + dy))[:3]
            upload_px = upload.get_at((glyph_x + dx, upload_y + dy))[:3]
            if static_px != upload_px:
                diff_found = True
                break
        if diff_found:
            break
    assert diff_found


def test_row_height_constant_across_layer_counts() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    expected_row_h = timeline_ui_metrics().row_height

    for row_count in (1, 2, 4, 8):
        order = [f"layer_{i}" for i in range(1, row_count + 1)]
        state = strip_view_state(layer_z_order=order)
        _draw(overlay, surface, state)
        assert overlay.row_layout
        assert overlay.row_layout[0][4] == expected_row_h
        assert overlay.panel_rect is not None
        assert overlay.panel_rect[3] == (
            timeline_ui_metrics().padding * 2
            + row_count * expected_row_h
            + max(0, row_count - 1) * timeline_ui_metrics().row_gap
            + timeline_ui_metrics().scrollbar_gap
            + timeline_ui_metrics().scrollbar_height
        )

def test_compose_panel_draws_time_scale_above_first_row() -> None:
    pygame.init()
    from cleave.viz.theme import MUTED, SONG_BOUND
    from cleave.viz.timeline_strip_layout import timeline_band_height_px

    overlay = TimelineOverlay()
    # Keep the playhead off the zero tick it would cover.
    state = strip_view_state(position_sec=50.0)
    band_h = timeline_band_height_px(len(state.layer_z_order))
    band = (0, 720 - band_h, 1280, band_h)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.draw(surface, state, timeline_rect=band)
    bar_left, _bar_width = overlay.bar_layout
    panel = overlay.panel_rect
    assert panel is not None
    first_row_y = panel[1] + timeline_ui_metrics().padding
    # Zero-second major tick sits at the bar's left edge, just above row one.
    from cleave.viz.timeline_ruler import RULER_BOTTOM_GAP_PX

    baseline_y = first_row_y - 1 - RULER_BOTTOM_GAP_PX
    assert tuple(surface.get_at((bar_left, baseline_y - 1)))[:3] == MUTED
    # The song end mark runs from the ruler to the bottom of the last row.
    end_x = bar_left + _bar_width - 1
    metrics = timeline_ui_metrics()
    last_row_bottom = (
        panel[1]
        + panel[3]
        - metrics.padding
        - metrics.scrollbar_height
        - metrics.scrollbar_gap
        - 1
    )
    assert tuple(surface.get_at((end_x, baseline_y)))[:3] == MUTED
    for y in (baseline_y + 1, first_row_y + 1, last_row_bottom):
        assert tuple(surface.get_at((end_x, y)))[:3] == SONG_BOUND


def test_playhead_rises_to_ruler_major_tick_top() -> None:
    pygame.init()
    from cleave.viz.timeline_strip_layout import playhead_x, timeline_band_height_px
    from cleave.viz.timeline_ruler import ruler_tick_top

    overlay = TimelineOverlay()
    state = strip_view_state(position_sec=50.0)
    band_h = timeline_band_height_px(len(state.layer_z_order))
    band = (0, 720 - band_h, 1280, band_h)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.draw(surface, state, timeline_rect=band)
    bar_left, bar_width = overlay.bar_layout
    panel = overlay.panel_rect
    assert panel is not None
    x = playhead_x(state.position_sec, bar_left, bar_width, 0.0, state.duration_sec)
    first_row_y = panel[1] + timeline_ui_metrics().padding
    ruler_h = first_row_y - band[1]
    tick_top_y = band[1] + ruler_tick_top(ruler_h)
    colour = tuple(surface.get_at((x, tick_top_y)))[:3]
    # Same colour as the line through row one, whichever blink phase drew it.
    assert colour == tuple(surface.get_at((x, first_row_y + 1)))[:3]
    assert tuple(surface.get_at((x, tick_top_y - 1)))[:3] != colour


def test_moving_playhead_keeps_ruler_baseline() -> None:
    pygame.init()
    from cleave.viz.timeline_strip_layout import playhead_x, timeline_band_height_px

    state = strip_view_state(position_sec=50.0)
    band_h = timeline_band_height_px(len(state.layer_z_order))
    band = (0, 720 - band_h, 1280, band_h)
    moved = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    moved.draw(surface, state, timeline_rect=band)
    old_x = playhead_x(50.0, *moved.bar_layout, 0.0, state.duration_sec)
    state.position_sec = 60.0
    surface.fill((0, 0, 0, 0))
    moved.draw(surface, state, timeline_rect=band)

    fresh = TimelineOverlay()
    expected = pygame.Surface((1280, 720), pygame.SRCALPHA)
    fresh.draw(expected, state, timeline_rect=band)

    panel = moved.panel_rect
    assert panel is not None
    # Every ruler pixel the old strip covered, baseline included, is back.
    for y in range(band[1], panel[1] + timeline_ui_metrics().padding):
        assert surface.get_at((old_x, y)) == expected.get_at((old_x, y)), y


def test_hit_at_maps_ruler_rows_prefix_and_gaps() -> None:
    from cleave.viz.timeline_strip_layout import time_to_x, x_to_time

    pygame.init()
    overlay = TimelineOverlay(padding=8, row_gap=4)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    assert overlay.hit_at(10, 700) is None
    _draw(overlay, surface, strip_view_state(duration_sec=100.0, override_slots={"layer_1"}))

    px, py, _, _ = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    rows = overlay.row_layout
    mid_x = px + bar_left + bar_width // 2

    ruler = overlay.hit_at(mid_x, py + 2)
    assert ruler is not None and ruler.row is None
    assert ruler.t_sec == pytest.approx(50.0, abs=0.2)

    for row_index, _, row_y, _, row_h, _ in rows:
        hit = overlay.hit_at(mid_x, py + row_y + row_h // 2)
        assert hit is not None and hit.row == row_index
        assert hit.tolerance_sec == pytest.approx(4 * 100.0 / bar_width)

    prefix = overlay.hit_at(px + 10, py + rows[0][2] + 1)
    assert prefix is not None and prefix.row == 0 and prefix.t_sec is None
    assert prefix.target == "label"
    for target in ("arm", "solo", "eye", "release"):
        hit = overlay.hit_at(px + _header_x(overlay, target) + 1, py + rows[0][2] + 1)
        assert hit is not None and hit.row == 0 and hit.target == target
        assert hit.t_sec is None
    assert ruler.target is None

    corner_y = py - 2
    play = overlay.hit_at(px + 9, corner_y)
    record = overlay.hit_at(
        px + 8 + overlay._layer_num_width + overlay._stem_abbrev_width + 2, corner_y
    )
    assert play is not None and play.target == "play" and play.row is None
    assert record is not None and record.target == "record"

    gap_y = py + rows[0][2] + rows[0][4] + 1
    assert overlay.hit_at(mid_x, gap_y) is None

    assert overlay.hit_at(px + bar_left, py + rows[0][2] + 1).t_sec == 0.0
    assert overlay.time_at_x(px + bar_left + bar_width + 50) == 100.0
    assert overlay.time_at_x(px - 50) == 0.0


    for t in (0.0, 12.5, 63.0, 100.0):
        x = time_to_x(t, bar_left, bar_width, 0.0, 100.0)
        back = x_to_time(x, bar_left, bar_width, 0.0, 100.0)
        assert abs(time_to_x(back, bar_left, bar_width, 0.0, 100.0) - x) <= 1

def test_ruler_hit_starts_at_major_tick_top() -> None:
    from cleave.viz.timeline_panel_cache import timeline_badge_reserve_px
    from cleave.viz.timeline_ruler import ruler_tick_top

    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state(duration_sec=100.0))
    px, py, _, _ = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    mid_x = px + bar_left + bar_width // 2
    reserve = timeline_badge_reserve_px()
    ruler_top = py - reserve
    tick_top = ruler_top + ruler_tick_top(reserve + overlay._padding)
    hit = overlay.hit_at(mid_x, tick_top)
    assert hit is not None and hit.row is None and hit.t_sec is not None
    # Time labels and the band's top edge belong to nothing, so the resize
    # splitter there is not shadowed by the scrub.
    assert overlay.hit_at(mid_x, tick_top - 1) is None
    assert overlay.hit_at(mid_x, ruler_top) is None
    # The corner buttons keep their full height.
    play = overlay.hit_at(px + overlay._padding + 1, ruler_top + 4)
    assert play is not None and play.target == "play"


def _zoomed(state: TimelineViewState, start: float, end: float) -> TimelineViewState:
    from dataclasses import replace

    return replace(state, view_start_sec=start, view_end_sec=end)


def test_zoomed_hit_at_maps_the_window_and_tightens_cue_tolerance() -> None:
    pygame.init()
    overlay = TimelineOverlay(padding=8, row_gap=4)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, _zoomed(strip_view_state(duration_sec=100.0), 40.0, 60.0))

    px, py, _, _ = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    row_y = py + overlay.row_layout[0][2] + 2
    hit = overlay.hit_at(px + bar_left + bar_width // 2, row_y)
    assert hit is not None and hit.row == 0
    assert hit.t_sec == pytest.approx(50.0, abs=0.1)
    assert hit.tolerance_sec == pytest.approx(4 * 20.0 / bar_width)
    assert overlay.view_sec_per_px() == pytest.approx(20.0 / bar_width)
    assert overlay.time_at_x(px - 50) == 40.0
    assert overlay.time_at_x(px + bar_left + bar_width + 50) == 60.0


def test_scrollbar_thumb_span_tracks_the_window() -> None:
    from cleave.viz.timeline_strip_layout import scrollbar_thumb_span

    assert scrollbar_thumb_span(1000, 0.0, 100.0, 100.0, min_thumb=12) == (0, 1000)
    assert scrollbar_thumb_span(1000, 40.0, 60.0, 100.0, min_thumb=12) == (400, 200)
    assert scrollbar_thumb_span(1000, 80.0, 100.0, 100.0, min_thumb=12) == (800, 200)
    # A tiny window keeps a grabbable thumb that still reaches both ends.
    assert scrollbar_thumb_span(1000, 0.0, 0.1, 100.0, min_thumb=12) == (0, 12)
    assert scrollbar_thumb_span(1000, 99.9, 100.0, 100.0, min_thumb=12) == (988, 12)
    assert scrollbar_thumb_span(0, 0.0, 10.0, 100.0, min_thumb=12) == (0, 0)


def test_scrollbar_hits_thumb_and_track_under_the_rows() -> None:
    from cleave.viz.theme import TIMELINE_SCROLL_RAIL, TIMELINE_SCROLL_THUMB

    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, _zoomed(strip_view_state(duration_sec=100.0), 40.0, 60.0))

    px, py, _, ph = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    metrics = timeline_ui_metrics()
    bar_y = py + ph - metrics.padding - metrics.scrollbar_height // 2 - 1
    thumb_x = px + bar_left + bar_width // 2
    track_x = px + bar_left + bar_width // 10

    thumb = overlay.hit_at(thumb_x, bar_y)
    assert thumb is not None and thumb.target == "scroll_thumb" and thumb.row is None
    track = overlay.hit_at(track_x, bar_y)
    assert track is not None and track.target == "scroll_track"
    assert track.t_sec == pytest.approx(10.0, abs=0.2)
    assert overlay.hit_at(px + 4, bar_y) is None
    assert tuple(surface.get_at((thumb_x, bar_y)))[:3] == TIMELINE_SCROLL_THUMB
    assert tuple(surface.get_at((track_x, bar_y)))[:3] == TIMELINE_SCROLL_RAIL
    # 80 hidden seconds over the thumb's free travel.
    travel = bar_width - round(bar_width * 0.2)
    assert overlay.scrollbar_sec_per_px() == pytest.approx(80.0 / travel, rel=0.01)


def test_scrollbar_cannot_move_at_full_zoom() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, strip_view_state(duration_sec=100.0))
    assert overlay.scrollbar_sec_per_px() == 0.0
    # Only the rail shows: no thumb to mistake for a full level bar.
    from cleave.viz.theme import TIMELINE_SCROLL_RAIL

    px, py, _, ph = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    metrics = timeline_ui_metrics()
    mid_y = py + ph - metrics.padding - metrics.scrollbar_height // 2 - 1
    top_y = py + ph - metrics.padding - metrics.scrollbar_height
    mid_x = px + bar_left + bar_width // 2
    assert tuple(surface.get_at((mid_x, mid_y)))[:3] == TIMELINE_SCROLL_RAIL
    assert tuple(surface.get_at((mid_x, top_y)))[:3] != TIMELINE_SCROLL_RAIL


def test_playhead_and_cues_outside_the_window_are_not_drawn() -> None:
    from cleave.viz.theme import PLAYHEAD, PLAYHEAD_FLASH
    from cleave.viz.timeline_strip_static import OFF_SEGMENT_COLOR

    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    lanes = {"layer_1": TimelineLane(baseline=1.0, cues=[SlotCue(t=10.0, level=0.0)])}
    state = strip_view_state(duration_sec=100.0, position_sec=10.0, lanes=lanes)
    _draw(overlay, surface, _zoomed(state, 40.0, 60.0))

    px, py, _, _ = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    _, _, row_y, _, row_h, _ = overlay.row_layout[0]
    y = py + row_y + row_h // 2
    row = {
        tuple(surface.get_at((px + bar_left + dx, y)))[:3] for dx in range(bar_width)
    }
    # The cue at 10s switched the layer off, so the window shows one flat bar.
    assert row == {OFF_SEGMENT_COLOR}
    assert PLAYHEAD not in row and PLAYHEAD_FLASH not in row
    assert overlay._cache.last_playhead_rect is None


def test_zoomed_level_bar_cuts_segments_at_the_window_edges() -> None:
    from cleave.viz.timeline_strip_static import OFF_SEGMENT_COLOR, track_color

    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=10.0, level=1.0), SlotCue(t=50.0, level=0.0)],
        )
    }
    state = strip_view_state(duration_sec=100.0, position_sec=0.0, lanes=lanes)
    _draw(overlay, surface, _zoomed(state, 40.0, 60.0))

    px, py, _, _ = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    _, _, row_y, _, row_h, _ = overlay.row_layout[0]
    y = py + row_y + row_h // 2
    # On from before the window to its middle, then off.
    assert tuple(surface.get_at((px + bar_left + 2, y)))[:3] == track_color(0)
    assert tuple(surface.get_at((px + bar_left + bar_width // 4, y)))[:3] == track_color(0)
    assert (
        tuple(surface.get_at((px + bar_left + 3 * bar_width // 4, y)))[:3]
        == OFF_SEGMENT_COLOR
    )


def test_each_track_has_its_own_on_colour() -> None:
    from cleave.viz.timeline_strip_static import track_color

    colors = [track_color(index) for index in range(8)]
    assert len(set(colors)) == 8


def _hit_clips() -> list:
    from cleave.timeline import lane_clips

    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=20.0, level=1.0),
            SlotCue(t=40.0, level=0.5),
            SlotCue(t=60.0, level=0.0),
            SlotCue(t=80.0, level=1.0),
            SlotCue(t=80.4, level=0.0),
        ],
    )
    return lane_clips(lane, inherit=0.0, duration_sec=100.0)


def _clip_hit(x: float):
    from cleave.viz.timeline_strip_hit import clip_hit_at_x

    # One pixel per tenth of a second: bar pixel = 100 + t * 10.
    return clip_hit_at_x(
        _hit_clips(),
        x,
        bar_left=100,
        bar_width=1000,
        view_start_sec=0.0,
        view_end_sec=100.0,
    )


def test_clip_hit_edge_wins_over_body_at_the_threshold() -> None:
    from cleave.viz.timeline_strip_hit import CLIP_EDGE_HIT_PX

    start_x = 100 + 200
    assert _clip_hit(start_x) == (20.0, "start")
    assert _clip_hit(start_x + CLIP_EDGE_HIT_PX) == (20.0, "start")
    assert _clip_hit(start_x + CLIP_EDGE_HIT_PX + 1) == (20.0, None)
    # An edge is reachable from just outside the clip; beyond that is a gap.
    assert _clip_hit(start_x - CLIP_EDGE_HIT_PX) == (20.0, "start")
    assert _clip_hit(start_x - CLIP_EDGE_HIT_PX - 1) is None
    end_x = 100 + 600
    assert _clip_hit(end_x - 1) == (40.0, "end")
    assert _clip_hit(end_x + CLIP_EDGE_HIT_PX) == (40.0, "end")


def test_clip_hit_butted_boundary_is_the_earlier_clips_end() -> None:
    boundary_x = 100 + 400
    assert _clip_hit(boundary_x) == (20.0, "end")
    assert _clip_hit(boundary_x - 3) == (20.0, "end")
    assert _clip_hit(boundary_x + 3) == (20.0, "end")
    assert _clip_hit(boundary_x + 30) == (40.0, None)


def test_clip_hit_keeps_the_body_of_a_narrow_clip_grabbable() -> None:
    # The clip at 80 s is four pixels wide.
    assert _clip_hit(100 + 800) == (80.0, "start")
    assert _clip_hit(100 + 802) == (80.0, None)
    assert _clip_hit(100 + 804) == (80.0, "end")


def test_hit_at_reports_the_clip_and_edge_under_a_row_point() -> None:
    from cleave.viz.timeline_strip_layout import time_to_x

    pygame.init()
    overlay = TimelineOverlay(padding=8, row_gap=4)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    state = strip_view_state(
        duration_sec=100.0,
        layer_z_order=["layer_1", "layer_2"],
        defaults={"layer_1": 0.0, "layer_2": 0.0},
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=[SlotCue(t=20.0, level=1.0), SlotCue(t=60.0, level=0.0)],
            )
        },
    )
    _draw(overlay, surface, state)
    px, py, _, _ = overlay.panel_rect
    bar_left, bar_width = overlay.bar_layout
    rows = overlay.row_layout

    def hit(t_sec: float, row: int = 0, dx: int = 0):
        x = px + time_to_x(t_sec, bar_left, bar_width, 0.0, 100.0) + dx
        return overlay.hit_at(x, py + rows[row][2] + rows[row][4] // 2)

    body = hit(40.0)
    assert (body.clip_start, body.clip_edge) == (20.0, None)
    assert (hit(20.0).clip_start, hit(20.0).clip_edge) == (20.0, "start")
    assert (hit(60.0, dx=-2).clip_start, hit(60.0, dx=-2).clip_edge) == (20.0, "end")
    gap = hit(80.0)
    assert (gap.clip_start, gap.clip_edge) == (None, None)
    other_row = hit(40.0, row=1)
    assert (other_row.clip_start, other_row.clip_edge) == (None, None)
    # The ruler and the row label name no clip.
    assert overlay.hit_at(px + 10, py + rows[0][2] + 1).clip_start is None


def _compose_bytes(overlay: TimelineOverlay, state: TimelineViewState) -> bytes:
    from cleave.viz.timeline_strip_layout import timeline_band_height_px

    band_h = timeline_band_height_px(len(state.layer_z_order))
    composed = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
        timeline_rect=(0, 720 - band_h, 1280, band_h),
    )
    assert composed is not None
    return pygame.image.tobytes(composed.upload_surface, "RGBA")


def test_incremental_compose_matches_full_rebuild(monkeypatch) -> None:
    """Each live change, patched in place, leaves the pixels a fresh compose draws."""
    pygame.init()
    ticks = [100_000]
    monkeypatch.setattr("pygame.time.get_ticks", lambda: ticks[0])
    slot = DEFAULT_LAYER_SLOTS[0]
    lanes = {
        slot: TimelineLane(
            baseline=None,
            cues=[
                SlotCue(t=10.0, level=1.0, role="lead"),
                SlotCue(t=30.0, level=0.0, role="pulse"),
            ],
        )
    }
    state = strip_view_state(
        lanes=lanes,
        position_sec=5.0,
        song_marker_times=(20.0, 40.0),
        selected_song_marker_index=1,
        armed_slots={DEFAULT_LAYER_SLOTS[1]},
    )
    overlay = TimelineOverlay()
    _compose_bytes(overlay, state)

    steps = [
        # The playhead crosses a role glyph, a marker, and the selected marker.
        dict(position_sec=10.0),
        dict(position_sec=20.0),
        dict(position_sec=30.0),
        dict(position_sec=40.0),
        dict(hover_button="play"),
        dict(hover_button="record"),
        dict(hover_button=None),
        dict(arm_flash_start_ms={DEFAULT_LAYER_SLOTS[2]: ticks[0]}),
        dict(arm_flash_start_ms={}),
        dict(song_marker_flash_start_ms=ticks[0]),
        dict(song_marker_flash_start_ms=None),
        dict(paused=False, position_sec=41.0),
    ]
    for step in steps:
        ticks[0] += 1_000
        for name, value in step.items():
            setattr(state, name, value)
        incremental = _compose_bytes(overlay, state)
        assert incremental == _compose_bytes(TimelineOverlay(), state), step


def test_unchanged_frame_skips_fill_and_live_patch(monkeypatch) -> None:
    pygame.init()
    monkeypatch.setattr("pygame.time.get_ticks", lambda: 100_000)
    state = strip_view_state(position_sec=50.0)
    overlay = TimelineOverlay()
    _compose_bytes(overlay, state)

    calls: list[str] = []
    monkeypatch.setattr(
        "cleave.viz.timeline_strip_static.StaticLayers.lay",
        lambda *a, **k: calls.append("compose"),
    )
    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.patch_live_overlay",
        lambda *a, **k: calls.append("patch") or [],
    )
    _compose_bytes(overlay, state)
    assert calls == []

    state.position_sec = 51.0
    _compose_bytes(overlay, state)
    assert calls == ["patch"]
