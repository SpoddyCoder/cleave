"""Tests for the bottom timeline strip overlay."""

from __future__ import annotations

import pygame

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.extract import STEM_NAMES
from cleave.timeline import SlotCue, TimelineLane, canonicalize, lane_visible_at, stem_abbreviation
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.tuning_panel_draw import render_visibility_icon
from cleave.viz.theme import (
    ARMED_BG,
    DISABLED,
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
    PLAYHEAD_FLASH_MS,
    TimelineOverlay,
    TimelineViewState,
    arm_abbrev_flash_active,
    arm_abbrev_flash_visible,
    armed_abbrev_bg_visible,
    bar_segments_for_row,
    bar_tick_times_for_row,
    cue_times_for_stem,
    layer_num_prefix,
    playhead_color,
    playhead_flash_bright,
    playhead_x,
    prune_expired_arm_flashes,
    rec_flash_visible,
    row_prefix_width,
    stem_abbrev_label,
    stem_label_text,
    transport_time_text,
    time_to_x,
    visibility_segments,
)


def _lane(
    baseline: bool | None,
    *transitions: tuple[float, bool],
) -> TimelineLane:
    cues = [SlotCue(t=t, visible=v) for t, v in transitions]
    return TimelineLane(baseline=baseline, cues=canonicalize(baseline, cues))


def _view_state(
    *,
    lanes: dict[str, TimelineLane] | None = None,
    defaults: dict[str, bool] | None = None,
    position_sec: float = 0.0,
    duration_sec: float = 100.0,
    focus_row: int = 0,
    submenu_focused: bool = False,
    armed_slots: set[str] | None = None,
    recording: bool = False,
    record_start_sec: float | None = None,
    record_baseline: dict[str, bool] | None = None,
    record_buffer: dict[str, list[SlotCue]] | None = None,
    record_high_water_mark: float | None = None,
    enabled: bool = True,
    layer_z_order: list[str] | None = None,
    monitor_visible: dict[str, bool] | None = None,
    timeline_visible: dict[str, bool] | None = None,
    override_slots: set[str] | None = None,
    arm_flash_start_ms: dict[str, int] | None = None,
    show_bar_grid: bool = False,
    bar_grid_times: tuple[float, ...] = (),
    song_marker_times: tuple[float, ...] = (),
    selected_song_marker_index: int | None = None,
) -> TimelineViewState:
    order = list(layer_z_order or list(DEFAULT_LAYER_SLOTS))
    lane_map = dict(lanes or {})
    default_map = dict(
        defaults or {slot: True for slot in (layer_z_order or list(DEFAULT_LAYER_SLOTS))}
    )
    if monitor_visible is None:
        monitor_visible = {
            stem: lane_visible_at(
                lane_map.get(stem) or TimelineLane(baseline=None, cues=[]),
                position_sec,
                inherit=default_map[stem],
            )
            for stem in order
        }
    if timeline_visible is None:
        timeline_visible = dict(monitor_visible)
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
        timeline_visible=timeline_visible,
        override_slots=set(override_slots or ()),
        armed_slots=set(armed_slots or ()),
        recording=recording,
        record_start_sec=record_start_sec,
        record_baseline=dict(record_baseline or ()),
        record_buffer=dict(record_buffer or ()),
        record_high_water_mark=record_high_water_mark,
        enabled=enabled,
        submenu_focused=submenu_focused,
        arm_flash_start_ms=dict(arm_flash_start_ms or ()),
        show_bar_grid=show_bar_grid,
        bar_grid_times=bar_grid_times,
        song_marker_times=song_marker_times,
        selected_song_marker_index=selected_song_marker_index,
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
        timeline_visible={"layer_1": False, "layer_2": True, "layer_3": True, "layer_4": True},
        override_slots={"layer_1"},
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is not None


def test_visibility_segments_default_only() -> None:
    lane = TimelineLane(baseline=False, cues=[])
    segments = visibility_segments(lane, 60.0, inherit=True)
    assert segments == [(0.0, 60.0, False)]


def test_visibility_segments_from_cues() -> None:
    lane = _lane(True, (10.0, False), (30.0, True))
    segments = visibility_segments(lane, 60.0, inherit=True)
    assert segments == [
        (0.0, 10.0, True),
        (10.0, 30.0, False),
        (30.0, 60.0, True),
    ]


def test_visibility_segments_other_stem_unchanged_across_unrelated_cue() -> None:
    lane = _lane(True)
    segments = visibility_segments(lane, 20.0, inherit=True)
    assert segments == [(0.0, 20.0, True)]


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


def _bar_visible_at(
    state: TimelineViewState,
    slot: str,
    t: float,
) -> bool:
    """Return the bar's visibility value for a slot at time t."""
    segs = bar_segments_for_row(state, slot)
    visible = False
    for seg_start, seg_end, seg_visible in segs:
        if seg_start <= t < seg_end:
            visible = seg_visible
    return visible


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
        record_buffer={"layer_1": [SlotCue(t=20.0, visible=False)]},
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
        record_buffer={"layer_1": [SlotCue(t=10.0, visible=True)]},
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
        record_buffer={"layer_1": [SlotCue(t=20.0, visible=False)]},
        record_high_water_mark=None,
    )
    assert _bar_visible_at(state, slot, 22.0) is False
    assert _bar_visible_at(state, slot, 30.0) is True


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