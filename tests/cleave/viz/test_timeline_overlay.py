"""Tests for the bottom timeline strip overlay."""

from __future__ import annotations

import pygame

from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue, layer_visible_at, stem_abbreviation
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.overlay import render_visibility_icon
from cleave.viz.theme import (
    ARMED_BG,
    DISABLED,
    OVERRIDE_BG,
    OVERRIDE_GLYPH,
    OVERRIDE_GLYPH_OFF,
    SOLO_BG,
)
from cleave.viz.timeline_overlay import (
    TimelineOverlay,
    TimelineViewState,
    bar_tick_times_for_row,
    cue_times_for_stem,
    layer_num_prefix,
    playhead_x,
    rec_flash_visible,
    row_prefix_width,
    stem_abbrev_label,
    stem_label_text,
    transport_time_text,
    time_to_x,
    unique_cue_times,
    visibility_segments,
)


def _view_state(
    *,
    cues: list[TimelineCue] | None = None,
    defaults: dict[str, bool] | None = None,
    position_sec: float = 0.0,
    duration_sec: float = 100.0,
    focus_row: int = 0,
    submenu_focused: bool = False,
    armed_stems: set[str] | None = None,
    recording: bool = False,
    record_start_sec: float | None = None,
    record_baseline: dict[str, bool] | None = None,
    record_buffer: list[TimelineCue] | None = None,
    enabled: bool = True,
    layer_z_order: list[str] | None = None,
    monitor_visible: dict[str, bool] | None = None,
    timeline_visible: dict[str, bool] | None = None,
    override_stems: set[str] | None = None,
) -> TimelineViewState:
    order = list(layer_z_order or STEM_NAMES)
    cue_list = list(cues or [])
    default_map = dict(defaults or {stem: True for stem in STEM_NAMES})
    if monitor_visible is None:
        monitor_visible = {
            stem: layer_visible_at(cue_list, default_map, stem, position_sec)
            for stem in order
        }
    if timeline_visible is None:
        timeline_visible = dict(monitor_visible)
    return TimelineViewState(
        layer_z_order=order,
        cues=cue_list,
        defaults=default_map,
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=focus_row,
        monitor_visible=monitor_visible,
        timeline_visible=timeline_visible,
        override_stems=set(override_stems or ()),
        armed_stems=set(armed_stems or ()),
        recording=recording,
        record_start_sec=record_start_sec,
        record_baseline=dict(record_baseline or ()),
        record_buffer=list(record_buffer or ()),
        enabled=enabled,
        submenu_focused=submenu_focused,
    )


def _draw(
    overlay: TimelineOverlay,
    surface: pygame.Surface,
    state: TimelineViewState,
    *,
    content_height: int | None = None,
) -> None:
    overlay.draw(
        surface,
        state,
        content_height=content_height if content_height is not None else surface.get_height(),
    )


def test_row_prefix_width_includes_monitor_eye_slot() -> None:
    pygame.init()
    font = pygame.font.SysFont("monospace", 14)
    layer_num_w = font.render(layer_num_prefix(4), True, (255, 255, 255)).get_width()
    abbrev_w = font.render(stem_abbrev_label("drums"), True, (255, 255, 255)).get_width()
    row_h = 20
    eye_slot_w = visibility_icon_slot_width(row_h)
    assert row_prefix_width(layer_num_w, abbrev_w, row_h) == layer_num_w + abbrev_w + eye_slot_w


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


def test_armed_recording_monitor_eye_flashes_when_focused(monkeypatch) -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_stems={"bass"}, recording=True, focus_row=1, submenu_focused=True)

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

    bass_layout = next(row for row in overlay.row_layout if row[5] == "bass")
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
    state = _view_state(armed_stems={"bass"}, recording=True, focus_row=1, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "bass")
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
    state = _view_state(armed_stems={"bass"}, recording=True, focus_row=1, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "bass")
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
    state = _view_state(armed_stems={"bass"}, recording=True, focus_row=0, submenu_focused=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "bass")
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
    armed_state = _view_state(armed_stems={"bass"}, recording=False, focus_row=0)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, armed_state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "bass")
    _, _, row_y, _, row_h, _ = bass_layout
    armed_color = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    _draw(overlay, surface, _view_state(armed_stems=set(), recording=False, focus_row=0))
    unarmed_color = _abbrev_bg_pixel(surface, overlay, row_y, row_h)

    assert armed_color[0] > unarmed_color[0] + 40
    assert armed_color[0] > 150


def test_unarmed_recording_monitor_eye_not_override_bg() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_stems={"bass"}, recording=True)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    drums_layout = next(row for row in overlay.row_layout if row[5] == "drums")
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
        armed_stems={"bass"},
        override_stems={"bass"},
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

    bass_layout = next(row for row in overlay.row_layout if row[5] == "bass")
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


def test_override_stems_use_override_bg_on_monitor_eye() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(override_stems={"bass"}, focus_row=1)
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    bass_layout = next(row for row in overlay.row_layout if row[5] == "bass")
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
        cues=[TimelineCue(t=0.0, layers={"drums": False})],
        position_sec=10.0,
        armed_stems={"drums"},
        recording=True,
        record_start_sec=10.0,
        record_baseline={"drums": True},
        monitor_visible={"drums": True, "bass": True, "vocals": True, "other": True},
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    assert bar_tick_times_for_row(state, "drums") == [0.0]


def test_draw_dual_eye_state_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        cues=[TimelineCue(t=25.0, layers={"drums": False})],
        position_sec=25.0,
        focus_row=1,
        armed_stems={"bass"},
        recording=True,
        monitor_visible={"drums": True, "bass": False, "vocals": True, "other": True},
        timeline_visible={"drums": False, "bass": True, "vocals": True, "other": True},
        override_stems={"drums"},
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is not None


def test_visibility_segments_default_only() -> None:
    defaults = {"drums": True, "bass": False, "vocals": True, "other": True}
    segments = visibility_segments([], defaults, "bass", 60.0)
    assert segments == [(0.0, 60.0, False)]


def test_visibility_segments_from_cues() -> None:
    defaults = {stem: True for stem in STEM_NAMES}
    cues = [
        TimelineCue(t=10.0, layers={"drums": False}),
        TimelineCue(t=30.0, layers={"drums": True}),
    ]
    segments = visibility_segments(cues, defaults, "drums", 60.0)
    assert segments == [
        (0.0, 10.0, True),
        (10.0, 30.0, False),
        (30.0, 60.0, True),
    ]


def test_visibility_segments_other_stem_unchanged_across_unrelated_cue() -> None:
    defaults = {stem: True for stem in STEM_NAMES}
    cues = [TimelineCue(t=5.0, layers={"drums": False})]
    segments = visibility_segments(cues, defaults, "bass", 20.0)
    assert segments == [(0.0, 5.0, True), (5.0, 20.0, True)]


def test_unique_cue_times_clamps_to_duration() -> None:
    cues = [
        TimelineCue(t=-1.0, layers={"drums": False}),
        TimelineCue(t=5.0, layers={"bass": False}),
        TimelineCue(t=50.0, layers={"vocals": False}),
    ]
    assert unique_cue_times(cues, 10.0) == [5.0]


def test_cue_times_for_stem_skips_show_tick_false() -> None:
    cues = [
        TimelineCue(t=5.0, layers={"drums": False}),
        TimelineCue(t=10.0, layers={"drums": True}, show_tick=False),
    ]
    assert cue_times_for_stem(cues, "drums", 30.0) == [5.0]


def test_cue_times_for_stem_only_includes_relevant_layers() -> None:
    cues = [
        TimelineCue(t=5.0, layers={"drums": False}),
        TimelineCue(t=15.0, layers={"bass": False, "vocals": True}),
        TimelineCue(t=25.0, layers={"other": False}),
    ]
    assert cue_times_for_stem(cues, "drums", 30.0) == [5.0]
    assert cue_times_for_stem(cues, "bass", 30.0) == [15.0]
    assert cue_times_for_stem(cues, "vocals", 30.0) == [15.0]
    assert cue_times_for_stem(cues, "other", 30.0) == [25.0]


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
        cues=[TimelineCue(t=25.0, layers={"drums": False})],
        position_sec=25.0,
        focus_row=1,
        armed_stems={"bass"},
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


def test_draw_skipped_when_disabled() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(enabled=False)
    surface = pygame.Surface((640, 360), pygame.SRCALPHA)
    _draw(overlay, surface, state)
    assert overlay.panel_rect is None


def test_armed_row_layout_recorded() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_stems={"drums"}, layer_z_order=list(STEM_NAMES))
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    drums_layout = next(row for row in overlay.row_layout if row[5] == "drums")
    row_index, x, y, w, h, stem = drums_layout
    assert stem == "drums"
    assert row_index == 0
    assert w > 0 and h > 0
    assert overlay.panel_rect is not None


def test_focus_row_index_matches_stem() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(focus_row=2, layer_z_order=list(STEM_NAMES))
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    _draw(overlay, surface, state)

    vocals_layout = next(row for row in overlay.row_layout if row[5] == "vocals")
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
    content_height = 720

    baseline_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    _draw(overlay, baseline_surface, state, content_height=content_height)
    baseline_panel = overlay.panel_rect
    baseline_row_h = overlay.row_layout[0][4]
    _, baseline_bar_width, _ = overlay.bar_layout
    assert baseline_panel is not None
    assert overlay.bar_layout is not None

    upscaled_surface = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    _draw(overlay, upscaled_surface, state, content_height=content_height)
    upscaled_panel = overlay.panel_rect
    upscaled_row_h = overlay.row_layout[0][4]
    _, upscaled_bar_width, _ = overlay.bar_layout
    assert upscaled_panel is not None
    assert overlay.bar_layout is not None

    assert upscaled_row_h == baseline_row_h
    assert upscaled_panel[3] == baseline_panel[3]
    assert upscaled_bar_width > baseline_bar_width
    assert upscaled_panel[2] > baseline_panel[2]
