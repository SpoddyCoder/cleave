"""Tests for the bottom timeline strip overlay."""

from __future__ import annotations

import pygame
import pytest

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.extract import STEM_NAMES
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
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.tuning_panel_draw import render_visibility_icon
from cleave.viz.theme import (
    ARMED_BG,
    DISABLED,
    HIGHLIGHT,
    OVERRIDE_BG,
    OVERRIDE_GLYPH,
    OVERRIDE_GLYPH_OFF,
    PLAYHEAD,
    PLAYHEAD_FLASH,
    SOLO_BG,
    SONG_MARKER,
    SONG_MARKER_SELECTED,
    timeline_ui_metrics,
)
from cleave.viz.timeline_overlay import (
    ARM_FLASH_DURATION_MS,
    ARM_FLASH_HALF_MS,
    BAR_VERTICAL_INSET,
    PLAYHEAD_FLASH_MS,
    ROLE_GLYPH_BOTTOM_PAD,
    ROLE_GLYPH_TICK_GAP,
    SELECTED_CUE_COLOR,
    SELECTED_CUE_FLASH_DURATION_MS,
    SELECTED_CUE_FLASH_HALF_MS,
    SELECTED_CUE_FLASH_RED,
    SELECTED_CUE_FLASH_TICK_WIDTH,
    SELECTED_CUE_FLASH_YELLOW,
    SELECTED_CUE_TICK_WIDTH,
    TimelineOverlay,
    TimelineViewState,
    arm_abbrev_flash_active,
    blit_role_glyph_xor,
    arm_abbrev_flash_visible,
    armed_abbrev_bg_visible,
    bar_level_breakpoints_for_row,
    bar_tick_times_for_row,
    cue_times_for_stem,
    layer_num_prefix,
    playhead_color,
    playhead_flash_bright,
    playhead_x,
    prune_expired_arm_flashes,
    prune_expired_selected_cue_flash,
    rec_flash_visible,
    role_glyph_anchor,
    role_glyph_previous_level,
    role_glyph_side,
    row_prefix_width,
    selected_cue_flash_active,
    selected_cue_flash_bright,
    selected_cue_readout_text,
    selected_cue_tick_color,
    stem_abbrev_label,
    stem_label_text,
    transport_time_text,
    time_to_x,
    clip_breakpoints,
)


def _as_level(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def _lane(
    baseline,
    *transitions,
) -> TimelineLane:
    base = _as_level(baseline)
    cues = [SlotCue(t=t, level=float(_as_level(level))) for t, level in transitions]
    return TimelineLane(baseline=base, cues=canonicalize(base, cues))


def _view_state(
    *,
    lanes: dict[str, TimelineLane] | None = None,
    defaults: dict[str, float] | None = None,
    position_sec: float = 0.0,
    duration_sec: float = 100.0,
    focus_row: int = 0,
    submenu_focused: bool = False,
    armed_slots: set[str] | None = None,
    recording: bool = False,
    record_start_sec: float | None = None,
    record_baseline: dict[str, float] | None = None,
    record_buffer: dict[str, list[SlotCue]] | None = None,
    record_high_water_mark: float | None = None,
    enabled: bool = True,
    layer_z_order: list[str] | None = None,
    monitor_visible: dict[str, bool] | None = None,
    timeline_level: dict[str, float] | None = None,
    override_slots: set[str] | None = None,
    arm_flash_start_ms: dict[str, int] | None = None,
    show_bar_grid: bool = False,
    bar_grid_times: tuple[float, ...] = (),
    song_marker_times: tuple[float, ...] = (),
    selected_song_marker_index: int | None = None,
    song_marker_fades_enabled: bool = False,
    song_marker_fade_in: float = 2.0,
    song_marker_fade_out: float = 2.0,
    standard_cue_fades_enabled: bool = False,
    standard_cue_fade_in: float = 2.0,
    standard_cue_fade_out: float = 2.0,
    selected_cue_t: dict[str, float] | None = None,
    selected_cue_flash_start_ms: int | None = None,
) -> TimelineViewState:
    order = list(layer_z_order or list(DEFAULT_LAYER_SLOTS))
    lane_map = dict(lanes or {})
    default_map = {
        slot: float(_as_level(level))
        for slot, level in (
            defaults or {slot: 1.0 for slot in (layer_z_order or list(DEFAULT_LAYER_SLOTS))}
        ).items()
    }
    if timeline_level is None:
        timeline_level = {
            stem: float(
                lane_level_at(
                    lane_map.get(stem) or TimelineLane(baseline=None, cues=[]),
                    position_sec,
                    inherit=float(_as_level(default_map[stem])),
                )
            )
            for stem in order
        }
    else:
        timeline_level = {
            slot: float(_as_level(level)) for slot, level in timeline_level.items()
        }
    if monitor_visible is None:
        monitor_visible = {
            stem: timeline_level[stem] > LEVEL_EPS for stem in order
        }
    return TimelineViewState(
        layer_z_order=order,
        slot_stems={
            slot: TEST_LAYER_STEMS.get(slot, "drums")
            for slot in order
        },
        lanes=lane_map,
        defaults=default_map,
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=focus_row,
        monitor_visible=monitor_visible,
        timeline_level=timeline_level,
        override_slots=set(override_slots or ()),
        armed_slots=set(armed_slots or ()),
        recording=recording,
        record_start_sec=record_start_sec,
        record_baseline={slot: float(_as_level(level)) for slot, level in dict(record_baseline or ()).items()},
        record_buffer=dict(record_buffer or ()),
        record_high_water_mark=record_high_water_mark,
        enabled=enabled,
        submenu_focused=submenu_focused,
        arm_flash_start_ms=dict(arm_flash_start_ms or ()),
        show_bar_grid=show_bar_grid,
        bar_grid_times=bar_grid_times,
        song_marker_times=song_marker_times,
        selected_song_marker_index=selected_song_marker_index,
        song_marker_fades=TimelineFadeGroup(
            enabled=song_marker_fades_enabled,
            fade_in=song_marker_fade_in,
            fade_out=song_marker_fade_out,
        ),
        standard_cue_fades=TimelineFadeGroup(
            enabled=standard_cue_fades_enabled,
            fade_in=standard_cue_fade_in,
            fade_out=standard_cue_fade_out,
        ),
        selected_cue_t=dict(selected_cue_t or ()),
        selected_cue_flash_start_ms=selected_cue_flash_start_ms,
    )


def _draw(
    overlay: TimelineOverlay,
    surface: pygame.Surface,
    state: TimelineViewState,
) -> None:
    overlay.draw(surface, state)


def test_row_prefix_width_includes_monitor_eye_slot() -> None:
    pygame.init()
    font = pygame.font.SysFont("monospace", timeline_ui_metrics().font_size)
    layer_num_w = font.render(layer_num_prefix(4), True, (255, 255, 255)).get_width()
    abbrev_w = font.render(stem_abbrev_label("drums"), True, (255, 255, 255)).get_width()
    row_h = 20
    eye_slot_w = visibility_icon_slot_width(row_h)
    assert row_prefix_width(layer_num_w, abbrev_w, row_h) == layer_num_w + abbrev_w + eye_slot_w


def test_layer_num_width_probe_scales_with_eight_layers() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    order = [f"layer_{i}" for i in range(1, 9)]
    defaults = {slot: True for slot in order}
    _draw(overlay, surface, _view_state(layer_z_order=order, defaults=defaults))

    font = pygame.font.SysFont("monospace", timeline_ui_metrics().font_size)
    expected = font.render(layer_num_prefix(8), True, (255, 255, 255)).get_width()
    assert overlay._layer_num_width == expected


def test_dual_eye_positions_monitor_left_committed_right() -> None:
    pygame.init()
    margin = 10
    padding = 8
    overlay = TimelineOverlay(margin=margin, padding=padding)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, _view_state())

    panel = overlay.panel_rect
    bar_layout = overlay.bar_layout
    assert panel is not None
    assert bar_layout is not None
    panel_w = panel[2]
    bar_left, bar_width, eye_slot_w = bar_layout

    monitor_eye_x = padding + overlay._layer_num_width + overlay._stem_abbrev_width
    committed_eye_x = panel_w - padding - eye_slot_w
    row_h = overlay.row_layout[0][4]

    assert bar_left == padding + row_prefix_width(
        overlay._layer_num_width, overlay._stem_abbrev_width, row_h
    )
    assert bar_width == panel_w - padding * 2 - (bar_left - padding) - eye_slot_w
    assert committed_eye_x > monitor_eye_x + eye_slot_w
    assert committed_eye_x + eye_slot_w <= panel_w - padding


def test_armed_bg_matches_solo_bg() -> None:
    assert ARMED_BG == SOLO_BG


def test_override_visibility_icon_glyph_colors() -> None:
    pygame.init()
    line_h = 20
    enabled = render_visibility_icon(enabled=True, override=True, line_height=line_h)
    disabled = render_visibility_icon(enabled=False, override=True, line_height=line_h)
    assert enabled.get_at((1, line_h // 2))[:3] == OVERRIDE_BG
    assert disabled.get_at((1, line_h // 2))[:3] == OVERRIDE_BG
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


def test_arm_abbrev_flash_visible_blinks_twice() -> None:
    start = 1000
    flash = {"layer_1": start}
    assert arm_abbrev_flash_active(flash, "layer_1", ticks_ms=start) is True
    assert arm_abbrev_flash_visible(flash, "layer_1", ticks_ms=start) is True
    assert arm_abbrev_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS - 1) is True
    assert arm_abbrev_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS) is False
    assert arm_abbrev_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS * 2) is True
    assert arm_abbrev_flash_visible(flash, "layer_1", ticks_ms=start + ARM_FLASH_HALF_MS * 3) is False
    assert arm_abbrev_flash_active(
        flash, "layer_1", ticks_ms=start + ARM_FLASH_DURATION_MS - 1
    ) is True
    assert arm_abbrev_flash_active(
        flash, "layer_1", ticks_ms=start + ARM_FLASH_DURATION_MS
    ) is False


def test_prune_expired_arm_flashes() -> None:
    flash = {"layer_1": 0, "layer_2": 1000}
    prune_expired_arm_flashes(flash, ticks_ms=ARM_FLASH_DURATION_MS)
    assert flash == {"layer_2": 1000}
    prune_expired_arm_flashes(flash, ticks_ms=1000 + ARM_FLASH_DURATION_MS)
    assert flash == {}


def test_armed_abbrev_bg_visible_prefers_arm_flash_over_steady_armed() -> None:
    start = 5000
    flash = {"layer_1": start}
    off_tick = start + ARM_FLASH_HALF_MS
    assert armed_abbrev_bg_visible(
        armed=True,
        recording=False,
        flash_starts=flash,
        slot="layer_1",
        ticks_ms=off_tick,
    ) is False
    assert armed_abbrev_bg_visible(
        armed=True,
        recording=False,
        flash_starts={},
        slot="layer_1",
        ticks_ms=off_tick,
    ) is True


def test_disarm_flash_draws_armed_abbrev_bg_on_phase(monkeypatch) -> None:
    start = 5000
    monkeypatch.setattr("pygame.time.get_ticks", lambda: start + 10)
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        armed_slots=set(),
        arm_flash_start_ms={"layer_2": start},
        focus_row=1,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    flash_on = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    monkeypatch.setattr("pygame.time.get_ticks", lambda: start + ARM_FLASH_HALF_MS + 10)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    flash_off = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    assert flash_on[0] > flash_off[0] + 40
    assert flash_on[0] > 150


def test_armed_recording_monitor_eye_flashes_when_focused(monkeypatch) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_slots={"layer_2"}, recording=True, focus_row=1, submenu_focused=True)

    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: True
    )
    surface_on = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_on, state)

    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: False
    )
    surface_off = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_off, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    monitor_eye_x = overlay._padding + overlay._layer_num_width + overlay._stem_abbrev_width
    sample = (panel_x + monitor_eye_x + 1, panel_y + row_y + row_h // 2)
    flash_on = surface_on.get_at(sample)[:3]
    flash_off = surface_off.get_at(sample)[:3]

    assert flash_on == OVERRIDE_BG
    assert flash_off != OVERRIDE_BG
    assert flash_on != flash_off


def test_armed_recording_monitor_eye_uses_override_bg_when_flash_on(monkeypatch) -> None:
    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: True
    )
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_slots={"layer_2"}, recording=True, focus_row=1, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    monitor_eye_x = overlay._padding + overlay._layer_num_width + overlay._stem_abbrev_width
    assert surface.get_at((panel_x + monitor_eye_x + 1, panel_y + row_y + row_h // 2))[:3] == OVERRIDE_BG


def test_armed_recording_monitor_eye_hides_override_bg_when_flash_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: False
    )
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_slots={"layer_2"}, recording=True, focus_row=1, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    monitor_eye_x = overlay._padding + overlay._layer_num_width + overlay._stem_abbrev_width
    assert surface.get_at((panel_x + monitor_eye_x + 1, panel_y + row_y + row_h // 2))[:3] != OVERRIDE_BG


def _abbrev_bg_pixel(surface: pygame.Surface, overlay: TimelineOverlay, row_y: int, row_h: int) -> tuple[int, ...]:
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    abbrev_x = overlay._padding + overlay._layer_num_width
    sample_x = panel_x + abbrev_x + overlay._stem_abbrev_width - 2
    sample_y = panel_y + row_y + row_h // 2
    return surface.get_at((sample_x, sample_y))[:3]


def test_armed_recording_abbrev_flashes_with_rec(monkeypatch) -> None:
    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: True
    )
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_slots={"layer_2"}, recording=True, focus_row=0, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    flash_on = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: False
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    flash_off = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    assert flash_on[0] > flash_off[0] + 40
    assert flash_on[0] > 150


def test_armed_not_recording_abbrev_always_red() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    armed_state = _view_state(armed_slots={"layer_2"}, recording=False, focus_row=0)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, armed_state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    armed_color = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    _draw(overlay, surface, _view_state(armed_slots=set(), recording=False, focus_row=0))
    unarmed_color = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    assert armed_color[0] > unarmed_color[0] + 40
    assert armed_color[0] > 150


def test_armed_abbrev_letter_uses_highlight() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_slots={"layer_2"}, recording=False, focus_row=0)
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
    state = _view_state(armed_slots={"layer_2"}, recording=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    drums_layout = next(row for row in overlay.row_layout if row[5] == "layer_1")
    _, _, row_y, _, row_h, _ = drums_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    monitor_eye_x = overlay._padding + overlay._layer_num_width + overlay._stem_abbrev_width
    assert surface.get_at((panel_x + monitor_eye_x + 1, panel_y + row_y + row_h // 2))[:3] != OVERRIDE_BG


def test_override_armed_recording_monitor_eye_flashes(monkeypatch) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        armed_slots={"layer_2"},
        override_slots={"layer_2"},
        recording=True,
        focus_row=1,
        submenu_focused=True,
    )

    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: True
    )
    surface_on = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_on, state)

    monkeypatch.setattr(
        "cleave.viz.timeline_overlay.rec_flash_visible", lambda ticks_ms=None: False
    )
    surface_off = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface_off, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    monitor_eye_x = overlay._padding + overlay._layer_num_width + overlay._stem_abbrev_width
    sample = (panel_x + monitor_eye_x + 1, panel_y + row_y + row_h // 2)
    flash_on = surface_on.get_at(sample)[:3]
    flash_off = surface_off.get_at(sample)[:3]

    assert flash_on == OVERRIDE_BG
    assert flash_off != OVERRIDE_BG
    assert flash_on != flash_off


def test_override_slots_use_override_bg_on_monitor_eye() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(override_slots={"layer_2"}, focus_row=1)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "layer_2")
    _, _, row_y, _, row_h, _ = bass_layout
    panel = overlay.panel_rect
    assert panel is not None
    panel_x, panel_y, _, _ = panel
    monitor_eye_x = overlay._padding + overlay._layer_num_width + overlay._stem_abbrev_width
    assert surface.get_at((panel_x + monitor_eye_x + 1, panel_y + row_y + row_h // 2))[:3] == OVERRIDE_BG


def test_recording_baseline_does_not_draw_cue_tick() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        lanes={"layer_1": _lane(False)},
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


def test_draw_dual_eye_state_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        lanes={"layer_1": _lane(True, (25.0, False))},
        position_sec=25.0,
        focus_row=1,
        armed_slots={"layer_2"},
        recording=True,
        monitor_visible={"layer_1": True, "layer_2": False, "layer_3": True, "layer_4": True},
        timeline_level={"layer_1": 0.0, "layer_2": 1.0, "layer_3": 1.0, "layer_4": 1.0},
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


def test_partial_level_bar_shorter_than_full() -> None:
    """Partial level yields a shorter filled height than level 1.0."""
    import pygame as _pygame

    from cleave.viz.timeline_overlay import bar_level_y

    bar_rect = _pygame.Rect(0, 0, 100, 20)
    assert bar_level_y(bar_rect, 0.25) > bar_level_y(bar_rect, 1.0)
    assert bar_level_y(bar_rect, 0.0) == bar_rect.bottom
    assert bar_level_y(bar_rect, 1.0) == bar_rect.y


def test_lane_level_segments_default_only() -> None:
    lane = TimelineLane(baseline=0.0, cues=[])
    segments = lane_level_segments(lane, 60.0, inherit=1.0)
    assert segments == [(0.0, 60.0, 0.0)]


def test_lane_level_segments_from_cues() -> None:
    lane = _lane(True, (10.0, False), (30.0, True))
    segments = lane_level_segments(lane, 60.0, inherit=1.0)
    assert segments == [
        (0.0, 10.0, 1.0),
        (10.0, 30.0, 0.0),
        (30.0, 60.0, 1.0),
    ]


def test_lane_level_segments_other_stem_unchanged_across_unrelated_cue() -> None:
    lane = _lane(True)
    segments = lane_level_segments(lane, 20.0, inherit=1.0)
    assert segments == [(0.0, 20.0, 1.0)]


def test_cue_times_for_stem_lists_lane_transitions() -> None:
    lane = _lane(True, (5.0, False), (15.0, True))
    assert cue_times_for_stem(lane, 30.0) == [5.0, 15.0]


def test_cue_times_for_stem_clamps_to_duration() -> None:
    lane = _lane(True, (5.0, False), (50.0, True))
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
    assert playhead_x(0.0, bar_left, bar_width, duration) == bar_left
    assert playhead_x(50.0, bar_left, bar_width, duration) == bar_left + 100
    assert playhead_x(100.0, bar_left, bar_width, duration) == bar_left + bar_width


def test_time_to_x_clamps_out_of_range() -> None:
    bar_left = 10
    bar_width = 90
    assert time_to_x(-5.0, bar_left, bar_width, 60.0) == bar_left
    assert time_to_x(120.0, bar_left, bar_width, 60.0) == bar_left + bar_width


def test_draw_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        lanes={"layer_1": _lane(True, (25.0, False))},
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


def test_song_markers_drawn_on_static_panel() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        duration_sec=100.0,
        song_marker_times=(25.0, 75.0),
        selected_song_marker_index=1,
    )
    composed = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    static = overlay._cache.panel
    assert static is not None
    assert overlay.bar_layout is not None
    bar_left, bar_width, _ = overlay.bar_layout
    mid_y = static.get_height() // 2
    x_unselected = time_to_x(25.0, bar_left, bar_width, 100.0)
    x_selected = time_to_x(75.0, bar_left, bar_width, 100.0)
    assert static.get_at((x_unselected, mid_y))[:3] == SONG_MARKER
    assert static.get_at((x_selected, mid_y))[:3] == SONG_MARKER_SELECTED


def test_draw_when_disabled() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(enabled=False)
    surface = pygame.Surface((640, 360), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is not None


def test_draw_skipped_when_visibility_zero() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(enabled=True)
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
    state = _view_state(armed_slots={"layer_1"}, layer_z_order=list(DEFAULT_LAYER_SLOTS))
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
    state = _view_state(focus_row=2, layer_z_order=list(DEFAULT_LAYER_SLOTS))
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    vocals_layout = next(row for row in overlay.row_layout if row[5] == "layer_3")
    assert vocals_layout[0] == 2
    assert overlay.panel_rect is not None


def test_transport_time_text_matches_main_ui_format() -> None:
    assert transport_time_text(0.0) == "[00:00]"
    assert transport_time_text(65.0) == "[01:05]"
    assert transport_time_text(3725.9) == "[62:05]"


def test_header_badge_rect_is_above_panel() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(position_sec=30.0)
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    panel = overlay.panel_rect
    header = overlay.header_badge_rect
    assert panel is not None
    assert header is not None
    _, panel_y, _, _ = panel
    _, header_y, _, header_h = header
    assert header_y + header_h <= panel_y


def test_header_badge_wider_when_recording() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)

    _draw(overlay, surface, _view_state(position_sec=0.0, recording=False))
    idle_w = overlay.header_badge_rect
    assert idle_w is not None

    _draw(overlay, surface, _view_state(position_sec=0.0, recording=True))
    rec_w = overlay.header_badge_rect
    assert rec_w is not None
    assert rec_w[2] > idle_w[2]


def test_upscale_expands_bar_width_not_row_height() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state()

    baseline_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, baseline_surface, state)
    baseline_panel = overlay.panel_rect
    baseline_row_h = overlay.row_layout[0][4]
    _, baseline_bar_width, _ = overlay.bar_layout
    assert baseline_panel is not None
    assert overlay.bar_layout is not None

    upscaled_surface = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    _draw(overlay, upscaled_surface, state)
    upscaled_panel = overlay.panel_rect
    upscaled_row_h = overlay.row_layout[0][4]
    _, upscaled_bar_width, _ = overlay.bar_layout
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
    from cleave.viz.timeline_overlay import level_at_breakpoints

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
    state = _view_state(
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
    state = _view_state(
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
    state = _view_state(
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


def test_selected_cue_readout_text_format() -> None:
    assert selected_cue_readout_text(
        SlotCue(t=65.0, level=1.0, blend="add", role="lead")
    ) == "[01:05] lvl 1.00 blend add cast lead"
    assert selected_cue_readout_text(
        SlotCue(t=0.0, level=0.25, blend=None, role=None)
    ) == "[00:00] lvl 0.25 blend - cast -"


def test_draw_with_selected_cue_and_role_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
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
        selected_cue_t={"layer_1": 10.0},
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is not None
    assert overlay.header_badge_rect is not None


def test_role_glyph_not_drawn_on_off_cue() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    # Bypass canonicalize so an off cue can still carry a stale role.
    state = _view_state(
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
    from cleave.viz.timeline_overlay import bar_cues_for_row

    state = _view_state(
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


def test_selected_cue_highlight_drawn_on_static_panel() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
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
        selected_cue_t={"layer_1": 25.0},
    )
    composed = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    static = overlay._cache.panel
    assert static is not None
    assert overlay.bar_layout is not None
    bar_left, bar_width, _ = overlay.bar_layout
    tick_x = time_to_x(25.0, bar_left, bar_width, 100.0)
    row_h = overlay.row_layout[0][4]
    padding = overlay._padding
    # Settled selected tick: full-height HIGHLIGHT, thinner than flash width.
    assert SELECTED_CUE_COLOR == HIGHLIGHT
    assert SELECTED_CUE_TICK_WIDTH < SELECTED_CUE_FLASH_TICK_WIDTH
    assert static.get_at((tick_x, padding + 1))[:3] == SELECTED_CUE_COLOR
    assert static.get_at((tick_x, padding + row_h // 2))[:3] == SELECTED_CUE_COLOR
    # Thicker than a 1px tick: neighbours within SELECTED_CUE_TICK_WIDTH stay selected.
    half = SELECTED_CUE_TICK_WIDTH // 2
    assert static.get_at((tick_x - half, padding + row_h // 2))[:3] == SELECTED_CUE_COLOR
    assert static.get_at((tick_x + half, padding + row_h // 2))[:3] == SELECTED_CUE_COLOR
    # Settled width does not reach flash thickness.
    flash_half = SELECTED_CUE_FLASH_TICK_WIDTH // 2
    assert static.get_at((tick_x - flash_half, padding + row_h // 2))[:3] != SELECTED_CUE_COLOR
    assert static.get_at((tick_x + flash_half, padding + row_h // 2))[:3] != SELECTED_CUE_COLOR


def test_selected_cue_marker_only_on_focused_track() -> None:
    """Remembered selections stay in selected_cue_t; only focus_row draws the marker."""
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
        selected_cue_t=selected,
    )

    def _compose(focus_row: int):
        return overlay.compose_panel(
            _view_state(focus_row=focus_row, **base_kwargs),
            viewport_width=1280,
            viewport_height=720,
        )

    def _tick_rgb(cue_t: float, row_index: int) -> tuple[int, int, int]:
        static = overlay._cache.panel
        assert static is not None
        assert overlay.bar_layout is not None
        bar_left, bar_width, _ = overlay.bar_layout
        tick_x = time_to_x(cue_t, bar_left, bar_width, 100.0)
        row_h = overlay.row_layout[row_index][4]
        y = overlay._padding + row_index * (row_h + overlay._row_gap) + row_h // 2
        return static.get_at((tick_x, y))[:3]

    assert _compose(0) is not None
    assert _tick_rgb(25.0, 0) == SELECTED_CUE_COLOR
    assert _tick_rgb(50.0, 1) != SELECTED_CUE_COLOR

    assert _compose(1) is not None
    assert _tick_rgb(25.0, 0) != SELECTED_CUE_COLOR
    assert _tick_rgb(50.0, 1) == SELECTED_CUE_COLOR

    assert _compose(0) is not None
    assert _tick_rgb(25.0, 0) == SELECTED_CUE_COLOR
    assert _tick_rgb(50.0, 1) != SELECTED_CUE_COLOR


def test_prune_expired_selected_cue_flash() -> None:
    assert prune_expired_selected_cue_flash(None, ticks_ms=0) is None
    assert prune_expired_selected_cue_flash(1000, ticks_ms=1000) == 1000
    assert (
        prune_expired_selected_cue_flash(
            1000, ticks_ms=1000 + SELECTED_CUE_FLASH_DURATION_MS - 1
        )
        == 1000
    )
    assert (
        prune_expired_selected_cue_flash(
            1000, ticks_ms=1000 + SELECTED_CUE_FLASH_DURATION_MS
        )
        is None
    )


def test_selected_cue_flash_blink_colors() -> None:
    start = 1000
    assert selected_cue_flash_active(start, ticks_ms=start)
    assert selected_cue_flash_bright(start, ticks_ms=start)
    assert selected_cue_tick_color(start, ticks_ms=start) == SELECTED_CUE_FLASH_YELLOW
    assert SELECTED_CUE_FLASH_YELLOW == HIGHLIGHT
    assert SELECTED_CUE_COLOR == HIGHLIGHT
    assert SELECTED_CUE_FLASH_RED == ARMED_BG
    alt_t = start + SELECTED_CUE_FLASH_HALF_MS
    assert selected_cue_flash_active(start, ticks_ms=alt_t)
    assert not selected_cue_flash_bright(start, ticks_ms=alt_t)
    assert selected_cue_tick_color(start, ticks_ms=alt_t) == SELECTED_CUE_FLASH_RED
    expired = start + SELECTED_CUE_FLASH_DURATION_MS
    assert not selected_cue_flash_active(start, ticks_ms=expired)
    assert not selected_cue_flash_bright(start, ticks_ms=expired)
    assert selected_cue_tick_color(start, ticks_ms=expired) == SELECTED_CUE_COLOR


def test_selected_cue_flash_live_patches_yellow(monkeypatch) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    start = 5000
    state = _view_state(
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
        selected_cue_t={"layer_1": 25.0},
        selected_cue_flash_start_ms=start,
    )
    # Yellow half of the blink: thick live-patch over the thinner settled static tick.
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: start)
    composed = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    upload = composed.upload_surface
    assert overlay.bar_layout is not None
    bar_left, bar_width, _ = overlay.bar_layout
    tick_x = time_to_x(25.0, bar_left, bar_width, 100.0)
    from cleave.viz.timeline_panel_cache import timeline_badge_reserve_px

    y = timeline_badge_reserve_px() + overlay._padding + overlay.row_layout[0][4] // 2
    assert upload.get_at((tick_x, y))[:3] == SELECTED_CUE_FLASH_YELLOW
    flash_half = SELECTED_CUE_FLASH_TICK_WIDTH // 2
    assert upload.get_at((tick_x - flash_half, y))[:3] == SELECTED_CUE_FLASH_YELLOW
    assert upload.get_at((tick_x + flash_half, y))[:3] == SELECTED_CUE_FLASH_YELLOW
    static = overlay._cache.panel
    assert static is not None
    static_y = overlay._padding + overlay.row_layout[0][4] // 2
    assert static.get_at((tick_x, static_y))[:3] == SELECTED_CUE_COLOR
    assert static.get_at((tick_x - flash_half, static_y))[:3] != SELECTED_CUE_COLOR


def test_blit_role_glyph_xor_inverts_destination_rgb() -> None:
    pygame.init()
    panel = pygame.Surface((48, 48), pygame.SRCALPHA)
    bg = (40, 80, 120)
    panel.fill((*bg, 255))
    font = pygame.font.SysFont("monospace", 16, bold=True)
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
    assert ROLE_GLYPH_TICK_GAP >= SELECTED_CUE_FLASH_TICK_WIDTH // 2


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
    state = _view_state(
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
    bar_left, bar_width, _ = overlay.bar_layout
    tick_x = time_to_x(25.0, bar_left, bar_width, 100.0)
    row_h = overlay.row_layout[0][4]
    row_y = overlay._padding
    bar_rect = pygame.Rect(
        bar_left,
        row_y + BAR_VERTICAL_INSET,
        bar_width,
        max(1, row_h - BAR_VERTICAL_INSET * 2),
    )
    bold = pygame.font.SysFont(
        "monospace", timeline_ui_metrics().font_size, bold=True
    )
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
        state = _view_state(layer_z_order=order)
        _draw(overlay, surface, state)
        assert overlay.row_layout
        assert overlay.row_layout[0][4] == expected_row_h
        assert overlay.panel_rect is not None
        assert overlay.panel_rect[3] == (
            timeline_ui_metrics().padding * 2
            + row_count * expected_row_h
            + max(0, row_count - 1) * timeline_ui_metrics().row_gap
        )