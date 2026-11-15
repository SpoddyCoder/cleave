"""Bottom timeline strip overlay for per-stem layer visibility cues."""

from __future__ import annotations

import bisect
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import pygame

from cleave.cue_roles import CueRole
from cleave.song_markers import marker_index_near
from cleave.stems import StemSource
from cleave.timeline import (
    LEVEL_EPS,
    ClipEdge,
    SlotCue,
    TimelineClip,
    TimelineFadeGroup,
    TimelineLane,
    empty_lane,
    lane_clips,
    lane_level_at,
    lane_level_breakpoints,
    lane_tick_times,
    levels_equal,
    opening_cue,
    stem_abbreviation,
)
from cleave.viz.material_icons import (
    PAUSE_GLYPH,
    PLAY_GLYPH,
    RECORD_GLYPH,
    REPLAY_GLYPH,
    SOLO_GLYPH,
    material_font,
    visibility_icon_slot_width,
)
from cleave.viz.overlay_primitives import (
    ComposedPanel,
    clip_rect_to_bounds,
    overlay_font,
    overlay_panel_surface,
)
from cleave.viz.overlay_upload import (
    clip_dirty_rects,
    dirty_rects_for_clip_rect,
    upload_plan_for_signature,
)
from cleave.viz.row_present_renderers import (
    render_header_toggle,
    render_visibility_icon,
)
from cleave.viz.timeline_panel_cache import (
    TimelinePanelCache,
    timeline_badge_reserve_px,
    timeline_panel_max_dimensions,
    timeline_static_signature,
    timeline_upload_signature,
)
from cleave.viz.timeline_ruler import render_time_ruler, ruler_tick_top, song_bound_xs
from cleave.viz.theme import (
    ARMED_BG,
    BAR_GRID,
    DISABLED,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    LABEL,
    MUTED,
    NUDGE_HOVER_BG,
    NUDGE_HOVER_BG_ALPHA,
    NUDGE_HOVER_FG,
    OVERRIDE_BG,
    OVERRIDE_GLYPH,
    PLAYHEAD,
    PLAYHEAD_FLASH,
    REC_BG,
    ROW_FOCUS_BORDER,
    SONG_BOUND,
    SONG_MARKER,
    SONG_MARKER_SELECTED,
    SOLO_BG,
    TIMELINE_TRACK_COLORS,
    TIMELINE_SCROLL_RAIL,
    TIMELINE_SCROLL_THUMB,
    VALUE,
    timeline_panel_height_px,
    timeline_ui_metrics,
)
from cleave.viz.ui_tint import blit_tint

OFF_SEGMENT_COLOR: tuple[int, int, int] = (40, 40, 40)
# Dim end of the level-bar colour ramp sits this far from off toward the
# track colour (quarter beds stay readable).
_BAR_LEVEL_DIM_MIX: float = 0.4
_ROLE_GLYPH: dict[CueRole, str] = {
    "bed": "B",
    "pulse": "P",
    "lead": "L",
    "accent": "A",
}


def timeline_band_height_px(row_count: int) -> int:
    """Shell band under the columns: the strip and the badge row above it."""
    if row_count <= 0:
        return 0
    metrics = timeline_ui_metrics()
    return timeline_panel_height_px(row_count) + timeline_badge_reserve_px(
        font_size=metrics.font_size
    )


ARMED_BG_ALPHA: int = 220
CUE_TICK_ALPHA: int = 120
CUE_TICK_WIDTH: int = 2
# Outline around the selected clip; thicker while the selection flash runs.
SELECTED_CLIP_OUTLINE_WIDTH: int = 2
SELECTED_CLIP_FLASH_OUTLINE_WIDTH: int = 3
# Trim handles at the edges of the hovered or selected clip.
CLIP_HANDLE_WIDTH: int = 3
# Thick width of a selected song marker while its flash is active.
SELECTED_CLIP_FLASH_TICK_WIDTH: int = 7
REC_FLASH_MS: int = 500
PLAYHEAD_FLASH_MS: int = 400
ARM_FLASH_HALF_MS: int = 150
ARM_FLASH_DURATION_MS: int = ARM_FLASH_HALF_MS * 4
# Selected-clip flash: same blink cadence as arm flash, two flashes.
SELECTED_CLIP_FLASH_HALF_MS: int = ARM_FLASH_HALF_MS
SELECTED_CLIP_FLASH_DURATION_MS: int = SELECTED_CLIP_FLASH_HALF_MS * 4
# Settled selected outline (HIGHLIGHT yellow); the flash pulses yellow/red.
SELECTED_CLIP_COLOR: tuple[int, int, int] = HIGHLIGHT
SELECTED_CLIP_FLASH_YELLOW: tuple[int, int, int] = HIGHLIGHT
SELECTED_CLIP_FLASH_RED: tuple[int, int, int] = ARMED_BG
# Clear half the flash tick plus 1px so glyphs sit beside the thick marker.
ROLE_GLYPH_TICK_GAP: int = SELECTED_CLIP_FLASH_TICK_WIDTH // 2 + 1
ROLE_GLYPH_BOTTOM_PAD: int = 1
# Song markers span the ruler and every row. The selected one flashes like a
# selected cue (SELECTED_CLIP_FLASH_TICK_WIDTH), then settles at its own width.
SONG_MARKER_WIDTH: int = 3
SONG_MARKER_SELECTED_WIDTH: int = 5


@dataclass
class TimelineViewState:
    layer_z_order: list[str]
    lanes: dict[str, TimelineLane]
    defaults: dict[str, float]
    position_sec: float
    duration_sec: float
    focus_row: int  # 0..N-1, index into layer_z_order (0 = bottom stem)
    monitor_visible: dict[str, bool]
    slot_stems: dict[str, StemSource] = field(default_factory=dict)
    override_slots: set[str] = field(default_factory=set)
    solo_slot: str | None = None
    armed_slots: set[str] = field(default_factory=set)
    recording: bool = False
    paused: bool = True
    locked: bool = False
    # Pointer hover: a row's label or header button as (target, row), drawn
    # in static chrome, or a corner button (live).
    hover_row_target: tuple[str, int] | None = None
    hover_button: str | None = None
    record_start_sec: float | None = None
    record_slot_start_sec: dict[str, float] = field(default_factory=dict)
    record_baseline: dict[str, float] = field(default_factory=dict)
    record_buffer: dict[str, list[SlotCue]] = field(default_factory=dict)
    record_high_water_mark: float | None = None
    enabled: bool = False
    submenu_focused: bool = False
    arm_flash_start_ms: dict[str, int] = field(default_factory=dict)
    show_bar_grid: bool = False
    bar_grid_times: tuple[float, ...] = ()
    song_marker_times: tuple[float, ...] = ()
    selected_song_marker_index: int | None = None
    song_marker_flash_start_ms: int | None = None
    hard_cut_fades: TimelineFadeGroup = field(default_factory=TimelineFadeGroup)
    soft_cut_fades: TimelineFadeGroup = field(default_factory=TimelineFadeGroup)
    selected_clip_t: dict[str, float] = field(default_factory=dict)
    selected_clip_flash_start_ms: int | None = None
    # Clip under the pointer: (row, clip start, edge or None for the body).
    hover_clip: tuple[int, float, ClipEdge | None] | None = None
    # Visible time window mapped onto the bar. An end of None is the song end.
    view_start_sec: float = 0.0
    view_end_sec: float | None = None


def view_window(state: TimelineViewState) -> tuple[float, float]:
    """Visible ``(start, end)`` in song seconds."""
    if state.view_end_sec is None:
        return (0.0, state.duration_sec)
    return (state.view_start_sec, state.view_end_sec)


def cue_times_for_stem(
    lane: TimelineLane,
    duration_sec: float,
) -> list[float]:
    """Cue times within ``[0, duration_sec]`` (every stored cue is a real transition)."""
    return lane_tick_times(lane, duration_sec)


def _lane_for_view(state: TimelineViewState, slot: str) -> TimelineLane:
    return state.lanes.get(slot) or empty_lane()


def _inherit_for_view(state: TimelineViewState, slot: str) -> float:
    return float(state.defaults.get(slot, 1.0))


def _recording_view_lane(state: TimelineViewState, slot: str) -> TimelineLane:
    return TimelineLane(
        baseline=state.record_baseline[slot],
        cues=list(state.record_buffer.get(slot, [])),
    )


def level_at_breakpoints(
    breakpoints: list[tuple[float, float]],
    t: float,
) -> float:
    """Linear level along a breakpoint polyline (strip geometry, not smoothstep)."""
    if not breakpoints:
        return 0.0
    if t <= breakpoints[0][0]:
        return float(breakpoints[0][1])
    if t >= breakpoints[-1][0]:
        return float(breakpoints[-1][1])
    for index in range(len(breakpoints) - 1):
        t0, v0 = breakpoints[index]
        t1, v1 = breakpoints[index + 1]
        # Half-open [t0, t1) so a hard step at t1 wins over the prior segment end.
        if t >= t1:
            continue
        if t1 <= t0:
            last = index + 1
            while (
                last + 1 < len(breakpoints)
                and breakpoints[last + 1][0] <= t0
            ):
                last += 1
            return float(breakpoints[last][1])
        u = (t - t0) / (t1 - t0)
        return float(v0 + (v1 - v0) * u)
    return float(breakpoints[-1][1])


def clip_breakpoints(
    breakpoints: list[tuple[float, float]],
    start: float,
    end: float,
) -> list[tuple[float, float]]:
    """Clip a breakpoint polyline to ``[start, end]``, interpolating at the edges.

    A step exactly at ``start`` or ``end`` is kept as its own vertical pair,
    so the segment next to it stays flat instead of ramping across the clip.
    """
    if end <= start or not breakpoints:
        return []
    clipped: list[tuple[float, float]] = [
        (float(t), float(level))
        for t, level in breakpoints
        if start <= t <= end
    ]
    if not clipped or clipped[0][0] > start:
        clipped.insert(0, (start, level_at_breakpoints(breakpoints, start)))
    if clipped[-1][0] < end:
        clipped.append((end, level_at_breakpoints(breakpoints, end)))
    return clipped


def _span_breakpoints_for_lane(
    state: TimelineViewState,
    lane: TimelineLane,
    *,
    inherit: float,
    duration_sec: float,
) -> list[tuple[float, float]]:
    """Breakpoints covering ``[0, duration_sec]`` for strip drawing."""
    if duration_sec <= 0.0:
        return []
    breakpoints = lane_level_breakpoints(
        lane,
        inherit=inherit,
        hard_cut_fades=state.hard_cut_fades,
        soft_cut_fades=state.soft_cut_fades,
        duration_sec=duration_sec,
    )
    if not breakpoints:
        level = inherit if lane.baseline is None else float(lane.baseline)
        return [(0.0, level), (duration_sec, level)]
    spanned = list(breakpoints)
    if spanned[0][0] > 0.0:
        spanned.insert(0, (0.0, spanned[0][1]))
    if spanned[-1][0] < duration_sec:
        spanned.append((duration_sec, spanned[-1][1]))
    return spanned


def _extend_breakpoints(
    dest: list[tuple[float, float]],
    more: list[tuple[float, float]],
) -> None:
    for t, level in more:
        if (
            dest
            and dest[-1][0] == t
            and levels_equal(dest[-1][1], level)
        ):
            continue
        dest.append((t, level))


def bar_level_breakpoints_for_row(
    state: TimelineViewState,
    slot: str,
) -> list[tuple[float, float]]:
    """Level breakpoints for one timeline row, including live record preview."""
    duration = state.duration_sec
    if duration <= 0:
        return []
    inherit = _inherit_for_view(state, slot)
    lane = _lane_for_view(state, slot)
    if not (state.recording and slot in state.record_baseline):
        return _span_breakpoints_for_lane(
            state, lane, inherit=inherit, duration_sec=duration
        )

    record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
    if record_start is None:
        record_start = state.position_sec
    record_start = max(0.0, min(record_start, duration))
    playhead = max(0.0, min(state.position_sec, duration))

    committed = _span_breakpoints_for_lane(
        state, lane, inherit=inherit, duration_sec=duration
    )
    result: list[tuple[float, float]] = []

    if record_start > 0.0:
        _extend_breakpoints(result, clip_breakpoints(committed, 0.0, record_start))

    effective_end = max(playhead, state.record_high_water_mark or 0.0)
    if effective_end > record_start:
        live = _span_breakpoints_for_lane(
            state,
            _recording_view_lane(state, slot),
            inherit=1.0,
            duration_sec=effective_end,
        )
        _extend_breakpoints(
            result, clip_breakpoints(live, record_start, effective_end)
        )

    if effective_end < duration:
        _extend_breakpoints(
            result, clip_breakpoints(committed, effective_end, duration)
        )
    return result


def row_clips_for_view(state: TimelineViewState, slot: str) -> list[TimelineClip]:
    """The committed clips of one timeline row."""
    return lane_clips(
        _lane_for_view(state, slot),
        inherit=_inherit_for_view(state, slot),
        duration_sec=state.duration_sec,
    )


def clip_bar_span(
    clip: TimelineClip,
    *,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> tuple[int, int] | None:
    """Pixel ``(left, right)`` of the clip's visible part, or None out of view."""
    if clip.end <= view_start_sec or clip.start >= view_end_sec:
        return None
    left = time_to_x(
        max(clip.start, view_start_sec), bar_left, bar_width, view_start_sec, view_end_sec
    )
    right = time_to_x(
        min(clip.end, view_end_sec), bar_left, bar_width, view_start_sec, view_end_sec
    )
    return (left, max(left + 1, right))


def bar_cues_for_row(state: TimelineViewState, slot: str) -> list[SlotCue]:
    """Cues whose ticks are drawn for one timeline row.

    Includes a synthetic ``t=0`` cue when the opening period is on via baseline
    only, so the first section can be selected for cast/blend.
    """
    duration = state.duration_sec
    lane = _lane_for_view(state, slot)
    if not (state.recording and slot in state.record_baseline):
        cues = [cue for cue in lane.cues if 0.0 <= cue.t <= duration]
        synthetic = opening_cue(lane)
        if synthetic is not None and duration >= 0.0:
            cues = [synthetic, *cues]
        return cues

    record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
    if record_start is None:
        record_start = state.position_sec
    playhead = state.position_sec
    effective_end = max(playhead, state.record_high_water_mark or 0.0)
    committed = [
        cue
        for cue in lane.cues
        if 0.0 <= cue.t <= duration
        and (cue.t < record_start or cue.t > effective_end)
    ]
    live = [
        cue
        for cue in _recording_view_lane(state, slot).cues
        if record_start <= cue.t <= effective_end and cue.t <= duration
    ]
    by_t = {cue.t: cue for cue in committed}
    for cue in live:
        by_t[cue.t] = cue
    synthetic = opening_cue(lane)
    if synthetic is not None and 0.0 not in by_t and duration >= 0.0:
        by_t[0.0] = synthetic
    return [by_t[t] for t in sorted(by_t)]


def bar_tick_times_for_row(state: TimelineViewState, slot: str) -> list[float]:
    """Cue tick times for one timeline row."""
    return [cue.t for cue in bar_cues_for_row(state, slot)]


def _draw_focus_outline(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """1px row focus outline, as on inspector rows."""
    for edge in (
        pygame.Rect(rect.x, rect.y, rect.w, 1),
        pygame.Rect(rect.x, rect.bottom - 1, rect.w, 1),
        pygame.Rect(rect.x, rect.y + 1, 1, rect.h - 2),
        pygame.Rect(rect.right - 1, rect.y + 1, 1, rect.h - 2),
    ):
        surface.fill(ROW_FOCUS_BORDER, edge)


def _lerp_rgb(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    u = max(0.0, min(1.0, float(t)))
    return (
        int(round(a[0] + (b[0] - a[0]) * u)),
        int(round(a[1] + (b[1] - a[1]) * u)),
        int(round(a[2] + (b[2] - a[2]) * u)),
    )


def track_color(row_index: int) -> tuple[int, int, int]:
    """On-section colour of the timeline track at *row_index*."""
    return TIMELINE_TRACK_COLORS[row_index % len(TIMELINE_TRACK_COLORS)]


def bar_level_y(bar_rect: pygame.Rect, level: float) -> int:
    """Y of the top of a bottom-filled level within ``bar_rect``."""
    filled = max(0.0, min(1.0, float(level))) * bar_rect.h
    return bar_rect.bottom - int(round(filled))


def _draw_level_bar(
    panel: pygame.Surface,
    *,
    breakpoints: list[tuple[float, float]],
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
    bar_rect: pygame.Rect,
    on_color: tuple[int, int, int],
) -> None:
    pygame.draw.rect(panel, OFF_SEGMENT_COLOR, bar_rect)
    if view_end_sec <= view_start_sec or len(breakpoints) < 2:
        return
    dim_color = _lerp_rgb(OFF_SEGMENT_COLOR, on_color, _BAR_LEVEL_DIM_MIX)
    # Polygon fills include their vertices; Rect.bottom/right are exclusive.
    bottom = bar_rect.bottom - 1
    right = bar_rect.right - 1
    for index in range(len(breakpoints) - 1):
        t0, level0 = breakpoints[index]
        t1, level1 = breakpoints[index + 1]
        if t1 <= t0 or t1 <= view_start_sec or t0 >= view_end_sec:
            continue
        # Cut a segment that crosses a window edge at that edge.
        slope = (level1 - level0) / (t1 - t0)
        if t1 > view_end_sec:
            level1 = level0 + slope * (view_end_sec - t0)
            t1 = view_end_sec
        if t0 < view_start_sec:
            level0 = level0 + slope * (view_start_sec - t0)
            t0 = view_start_sec
        x0 = time_to_x(t0, bar_left, bar_width, view_start_sec, view_end_sec)
        x1 = min(
            time_to_x(t1, bar_left, bar_width, view_start_sec, view_end_sec), right
        )
        if x1 <= x0:
            continue
        if level0 <= LEVEL_EPS and level1 <= LEVEL_EPS:
            continue
        y0 = min(bar_level_y(bar_rect, level0), bottom)
        y1 = min(bar_level_y(bar_rect, level1), bottom)
        mean_level = 0.5 * (level0 + level1)
        color = _lerp_rgb(dim_color, on_color, mean_level)
        pygame.draw.polygon(
            panel,
            color,
            [(x0, y0), (x1, y1), (x1, bottom), (x0, bottom)],
        )


def rec_flash_visible(ticks_ms: int | None = None) -> bool:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return (ticks_ms // REC_FLASH_MS) % 2 == 0


def playhead_flash_bright(ticks_ms: int | None = None) -> bool:
    """True on the bright half of the playhead blink cycle."""
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return (ticks_ms // PLAYHEAD_FLASH_MS) % 2 == 0


def playhead_color(ticks_ms: int | None = None) -> tuple[int, int, int]:
    if playhead_flash_bright(ticks_ms):
        return PLAYHEAD_FLASH
    return PLAYHEAD


def prune_expired_arm_flashes(
    flash_starts: dict[str, int],
    ticks_ms: int | None = None,
) -> None:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    expired = [
        slot
        for slot, start_ms in flash_starts.items()
        if ticks_ms - start_ms >= ARM_FLASH_DURATION_MS
    ]
    for slot in expired:
        flash_starts.pop(slot, None)


def prune_expired_selected_clip_flash(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> int | None:
    if flash_start_ms is None:
        return None
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    if ticks_ms - flash_start_ms >= SELECTED_CLIP_FLASH_DURATION_MS:
        return None
    return flash_start_ms


def arm_flash_active(
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    start_ms = flash_starts.get(slot)
    if start_ms is None:
        return False
    return ticks_ms - start_ms < ARM_FLASH_DURATION_MS


def arm_flash_visible(
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if not arm_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    start_ms = flash_starts[slot]
    elapsed = ticks_ms - start_ms
    return (elapsed // ARM_FLASH_HALF_MS) % 2 == 0


def selected_clip_flash_active(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> bool:
    if flash_start_ms is None:
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return ticks_ms - flash_start_ms < SELECTED_CLIP_FLASH_DURATION_MS


def selected_clip_flash_bright(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> bool:
    """True on the yellow (HIGHLIGHT) half of the selected-cue blink cycle."""
    if not selected_clip_flash_active(flash_start_ms, ticks_ms=ticks_ms):
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    assert flash_start_ms is not None
    elapsed = ticks_ms - flash_start_ms
    return (elapsed // SELECTED_CLIP_FLASH_HALF_MS) % 2 == 0


def selected_clip_flash_color(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> tuple[int, int, int]:
    if selected_clip_flash_bright(flash_start_ms, ticks_ms=ticks_ms):
        return SELECTED_CLIP_FLASH_YELLOW
    if selected_clip_flash_active(flash_start_ms, ticks_ms=ticks_ms):
        return SELECTED_CLIP_FLASH_RED
    return SELECTED_CLIP_COLOR


def arm_button_lit(
    *,
    armed: bool,
    recording: bool,
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if arm_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return arm_flash_visible(flash_starts, slot, ticks_ms=ticks_ms)
    return armed and (not recording or rec_flash_visible(ticks_ms))


def blit_role_glyph_xor(
    panel: pygame.Surface,
    glyph: str,
    *,
    x: int,
    y: int,
    font: pygame.font.Font,
) -> tuple[int, int, int, int] | None:
    """Bold role letter via per-pixel RGB XOR (pygame 2.6 has no ``BLEND_XOR``).

    Opaque glyph samples invert the destination RGB so the letter stays readable
    on both bright level bars and dark beds. Returns the touched panel rect, or
    ``None`` when the glyph is fully clipped.
    """
    src = font.render(glyph, True, (255, 255, 255))
    gw, gh = src.get_width(), src.get_height()
    if gw <= 0 or gh <= 0:
        return None
    dest_rect = pygame.Rect(x, y, gw, gh).clip(panel.get_rect())
    if dest_rect.w <= 0 or dest_rect.h <= 0:
        return None
    src_x = dest_rect.x - x
    src_y = dest_rect.y - y
    src_view = src.subsurface((src_x, src_y, dest_rect.w, dest_rect.h))
    # surfarray axes are (x, y); threshold soft edges to a binary XOR mask.
    # Manual XOR: pygame 2.6 exposes no BLEND_XOR blit flag.
    dest_rgb = pygame.surfarray.pixels3d(panel)
    alpha = pygame.surfarray.array_alpha(src_view)
    x0, y0 = dest_rect.x, dest_rect.y
    region = dest_rgb[x0 : x0 + dest_rect.w, y0 : y0 + dest_rect.h]
    mask = alpha > 127
    region[mask] ^= 255
    del dest_rgb
    return (dest_rect.x, dest_rect.y, dest_rect.w, dest_rect.h)


def role_glyph_side(*, previous_level: float, cue_level: float) -> Literal["left", "right"]:
    """Which side of the cue tick hosts the role glyph (enabled segment).

    On cues (off -> on) place right; off cues (on -> off) place left. When both
    sides are enabled, prefer right (toward the new state). When both are off,
    prefer right as a stable default.
    """
    prev_on = float(previous_level) > LEVEL_EPS
    next_on = float(cue_level) > LEVEL_EPS
    if next_on and not prev_on:
        return "right"
    if prev_on and not next_on:
        return "left"
    if next_on:
        return "right"
    if prev_on:
        return "left"
    return "right"


def role_glyph_previous_level(
    lane: TimelineLane,
    cue_t: float,
    *,
    inherit: float,
) -> float:
    """Stepped lane level immediately before ``cue_t``."""
    if cue_t <= 0.0:
        return inherit if lane.baseline is None else float(lane.baseline)
    return float(lane_level_at(lane, cue_t - 1e-9, inherit=inherit))


def role_glyph_anchor(
    *,
    tick_x: int,
    bar_rect: pygame.Rect,
    glyph_w: int,
    glyph_h: int,
    side: Literal["left", "right"],
) -> tuple[int, int]:
    """Top-left of a role glyph at the bar bottom, beside its cue tick."""
    if side == "right":
        glyph_x = tick_x + ROLE_GLYPH_TICK_GAP
    else:
        glyph_x = tick_x - ROLE_GLYPH_TICK_GAP - glyph_w
    glyph_y = bar_rect.bottom - glyph_h - ROLE_GLYPH_BOTTOM_PAD
    max_x = bar_rect.right - glyph_w
    if max_x >= bar_rect.left:
        glyph_x = max(bar_rect.left, min(glyph_x, max_x))
    else:
        glyph_x = bar_rect.left
    max_y = bar_rect.bottom - glyph_h
    if max_y >= bar_rect.top:
        glyph_y = max(bar_rect.top, min(glyph_y, max_y))
    else:
        glyph_y = bar_rect.top
    return glyph_x, glyph_y


def _glyph_lane_for_cue(
    state: TimelineViewState,
    slot: str,
    cue_t: float,
) -> tuple[TimelineLane, float]:
    """Lane and inherit used for stepped previous-level at a drawn cue."""
    inherit = _inherit_for_view(state, slot)
    if state.recording and slot in state.record_baseline:
        record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
        if record_start is None:
            record_start = state.position_sec
        effective_end = max(state.position_sec, state.record_high_water_mark or 0.0)
        if record_start <= cue_t <= effective_end:
            return _recording_view_lane(state, slot), 1.0
    return _lane_for_view(state, slot), inherit


def time_to_x(
    t_sec: float,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> int:
    """X of *t_sec* with the visible window mapped onto the bar, clamped to it."""
    span = view_end_sec - view_start_sec
    if span <= 0:
        return bar_left
    ratio = max(0.0, min(1.0, (t_sec - view_start_sec) / span))
    return bar_left + int(ratio * bar_width)


def x_to_time(
    x: float,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> float:
    """Inverse of ``time_to_x``, clamped to the visible window."""
    span = view_end_sec - view_start_sec
    if span <= 0 or bar_width <= 0:
        return view_start_sec
    ratio = max(0.0, min(1.0, (x - bar_left) / bar_width))
    return view_start_sec + ratio * span


def time_in_view(t_sec: float, view_start_sec: float, view_end_sec: float) -> bool:
    return view_start_sec <= t_sec <= view_end_sec


def scrollbar_thumb_span(
    track_w: int,
    view_start_sec: float,
    view_end_sec: float,
    duration_sec: float,
    *,
    min_thumb: int,
) -> tuple[int, int]:
    """Thumb ``(offset, width)`` along a track *track_w* pixels wide.

    The width is the visible share of the song, never under *min_thumb*. The
    offset runs the thumb's free travel as the window runs the song.
    """
    track_w = max(0, track_w)
    span = view_end_sec - view_start_sec
    if duration_sec <= 0 or span <= 0 or span >= duration_sec:
        return (0, track_w)
    thumb_w = max(min(min_thumb, track_w), int(round(track_w * span / duration_sec)))
    thumb_w = min(thumb_w, track_w)
    travel = track_w - thumb_w
    offset = int(round(travel * view_start_sec / (duration_sec - span)))
    return (max(0, min(travel, offset)), thumb_w)


# Pointer slack around a song marker, in pixels.
STRIP_HIT_PX: int = 4
# A clip edge takes the pointer within this many pixels, ahead of the body.
CLIP_EDGE_HIT_PX: int = 5


StripTarget = Literal[
    "play",
    "record",
    "label",
    "arm",
    "solo",
    "eye",
    "release",
    "scroll_thumb",
    "scroll_track",
]

# A row's header buttons after its label, left to right, each one
# ``visibility_icon_slot_width`` wide: arm for recording, solo, the live
# visibility eye, and back to timeline (shown only while overridden).
ROW_HEADER_BUTTONS: tuple[StripTarget, ...] = ("arm", "solo", "eye", "release")
ROW_HEADER_TARGETS: frozenset[str] = frozenset(("label", *ROW_HEADER_BUTTONS))


def header_button_x(
    target: StripTarget,
    *,
    padding: int,
    label_width: int,
    slot_w: int,
) -> int:
    """Left edge of header button *target* in panel coordinates."""
    return padding + label_width + ROW_HEADER_BUTTONS.index(target) * slot_w


def row_header_target_at(
    local_x: float,
    *,
    padding: int,
    label_width: int,
    slot_w: int,
) -> StripTarget | None:
    """The label or header button under panel *local_x*, or None past them."""
    if padding <= local_x < padding + label_width:
        return "label"
    offset = local_x - padding - label_width
    if offset < 0 or slot_w <= 0:
        return None
    index = int(offset // slot_w)
    if index < len(ROW_HEADER_BUTTONS):
        return ROW_HEADER_BUTTONS[index]
    return None


@dataclass(frozen=True)
class StripHit:
    """What a screen point lands on in the strip.

    ``row`` is None for the ruler and the scrollbar. ``t_sec`` is None outside
    the bar span (row labels and buttons). ``tolerance_sec`` is
    ``STRIP_HIT_PX`` in song time. ``target`` names a control: the corner
    ``"play"`` / ``"record"`` buttons, a row's ``"label"`` (layer number and
    stem abbreviation), one of its ``ROW_HEADER_BUTTONS`` (``"arm"``,
    ``"solo"``, ``"eye"``, ``"release"``), or the scrollbar's
    ``"scroll_thumb"`` / ``"scroll_track"``. On the
    scrollbar ``t_sec`` is the song time at that point along the track.
    ``marker_index`` is the song marker within ``STRIP_HIT_PX`` of the point on
    the ruler or in a row's bar, or None. ``clip_start`` is the start of the
    row's clip under the point, and ``clip_edge`` names the edge within
    ``CLIP_EDGE_HIT_PX`` of it (an edge wins over the body, and a boundary
    two clips share is the earlier clip's end).
    """

    row: int | None
    t_sec: float | None
    tolerance_sec: float
    target: StripTarget | None = None
    marker_index: int | None = None
    clip_start: float | None = None
    clip_edge: ClipEdge | None = None


def clip_hit_at_x(
    clips: Sequence[TimelineClip],
    x: float,
    *,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> tuple[float, ClipEdge | None] | None:
    """The clip under bar pixel *x* as ``(clip start, edge)``, or None in a gap.

    The nearest edge within ``CLIP_EDGE_HIT_PX`` wins over a body; the edge
    zone never takes more than a third of a narrow clip, so its body stays
    grabbable. Where two clips butt, the shared boundary is the earlier
    clip's end.
    """
    best: tuple[float, int, float, ClipEdge] | None = None
    body: float | None = None
    for order, clip in enumerate(clips):
        if clip.end < view_start_sec or clip.start > view_end_sec:
            continue
        start_x = time_to_x(clip.start, bar_left, bar_width, view_start_sec, view_end_sec)
        end_x = time_to_x(clip.end, bar_left, bar_width, view_start_sec, view_end_sec)
        zone = min(float(CLIP_EDGE_HIT_PX), max(1.0, (end_x - start_x) / 3.0))
        for edge, edge_x, edge_t in (
            ("end", end_x, clip.end),
            ("start", start_x, clip.start),
        ):
            if not time_in_view(edge_t, view_start_sec, view_end_sec):
                continue
            distance = abs(x - edge_x)
            # Earlier clips sort first, and an end before a start, on a tie.
            rank = (distance, order * 2 + (0 if edge == "end" else 1))
            if distance <= zone and (best is None or rank < (best[0], best[1])):
                best = (distance, rank[1], clip.start, edge)
        if start_x <= x < end_x:
            body = clip.start
    if best is not None:
        return (best[2], best[3])
    return None if body is None else (body, None)


# Corner buttons sit this far below the top of the badge row.
TRANSPORT_BUTTON_DROP_PX: int = 2
REC_BUTTON_TEXT: str = "REC"
# The flashing red REC fill stops this far short of the button's top and bottom.
REC_FILL_INSET_Y_PX: int = 2


def rec_fill_rect(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """*rect* inset top and bottom by ``REC_FILL_INSET_Y_PX``."""
    x, y, w, h = rect
    inset = min(REC_FILL_INSET_Y_PX, max(0, (h - 1) // 2))
    return (x, y + inset, w, h - inset * 2)


def transport_button_rects(
    *,
    padding: int,
    label_width: int,
    bar_left: int,
    corner_h: int,
    gap: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Play and record button rects in the corner above the row headers.

    Play sits over the row labels (layer number and stem). Record starts at
    the arm buttons and runs to the start of the ruler, over the other row
    buttons. It holds the record glyph plus ``REC``. Rects are in upload
    coordinates (top of the badge row is y=0).
    """
    y = TRANSPORT_BUTTON_DROP_PX
    h = max(1, corner_h - gap)
    play = (padding, y, label_width, h)
    record_x = padding + label_width
    record = (record_x, y, max(1, bar_left - record_x), h)
    return play, record


def transport_live_signature(state: TimelineViewState, ticks_ms: int) -> tuple:
    return (
        state.paused,
        state.locked,
        state.hover_button,
        bool(state.armed_slots),
        rec_flash_visible(ticks_ms) if state.recording else None,
    )


def playhead_x(
    position_sec: float,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> int:
    return time_to_x(position_sec, bar_left, bar_width, view_start_sec, view_end_sec)


def layer_num_prefix(layer_num: int) -> str:
    return f" {layer_num} "


def stem_abbrev_label(stem: str) -> str:
    return f" {stem_abbreviation(stem)} "


def playback_bar_text(position_sec: float, downbeat_times: Sequence[float]) -> str:
    """1-based bar at the playhead. Empty grids show an em dash."""
    if not downbeat_times:
        return "—"
    count = bisect.bisect_right(downbeat_times, position_sec)
    return str(max(1, count))


def stem_label_text(layer_num: int, stem: str) -> str:
    return f"{layer_num_prefix(layer_num)}{stem_abbrev_label(stem)}"


def row_prefix_width(
    layer_num_width: int,
    stem_abbrev_width: int,
    row_height: int,
) -> int:
    """Width of a row's header: number, stem, and its ``ROW_HEADER_BUTTONS``."""
    slot_w = visibility_icon_slot_width(row_height)
    return layer_num_width + stem_abbrev_width + slot_w * len(ROW_HEADER_BUTTONS)


def timeline_live_signature(
    state: TimelineViewState,
    *,
    playhead_px: int | None,
    bar_left: int,
    bar_width: int,
    row_count: int,
    row_h: int,
    flash_sig: tuple = (),
    ticks_ms: int | None = None,
) -> tuple:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    rec_flash = rec_flash_visible(ticks_ms) if state.recording else None
    return (
        playhead_px,
        bar_left,
        bar_width,
        row_count,
        row_h,
        rec_flash,
        playhead_flash_bright(ticks_ms),
        flash_sig,
        transport_live_signature(state, ticks_ms),
    )


@dataclass(frozen=True)
class _TimelineLayout:
    panel_w: int
    panel_h: int
    panel_x: int
    panel_y: int
    row_count: int
    row_h: int
    # Header button and transport glyph line height: the nominal row, centred
    # in a taller row when the band is dragged taller.
    icon_h: int
    bar_left: int
    bar_width: int
    # Width of each of a row's ROW_HEADER_BUTTONS.
    slot_w: int
    layer_num_width: int
    stem_abbrev_width: int
    badge_reserve: int
    bar_top: int
    bar_bottom: int
    # Scrollbar track under the rows, in panel coordinates.
    scrollbar_rect: tuple[int, int, int, int]


class TimelineOverlay:
    """Bottom-anchored timeline panel drawn over the composited frame."""

    def __init__(
        self,
        *,
        font_size: int | None = None,
        padding: int | None = None,
        row_gap: int | None = None,
    ) -> None:
        # Overrides pin a value for tests; None follows the live UI scale.
        self._font_size_override = font_size
        self._padding_override = padding
        self._row_gap_override = row_gap
        self._panel_rect: tuple[int, int, int, int] | None = None
        self._layer_num_width: int = 0
        self._stem_abbrev_width: int = 0
        self._bar_layout: tuple[int, int, int] | None = None
        self._row_layout: list[tuple[int, int, int, int, str, int]] = []
        self._cache = TimelinePanelCache()
        self._visibility = 1.0
        self._upload_scratch: pygame.Surface | None = None
        self._ruler: pygame.Surface | None = None
        self._blit_src: tuple[int, int] = (0, 0)
        self._hit_layout: _TimelineLayout | None = None
        self._hit_duration_sec: float = 0.0
        self._hit_view: tuple[float, float] = (0.0, 0.0)
        self._hit_markers: tuple[float, ...] = ()
        # Each row's clips at the last compose, by display row.
        self._hit_clips: tuple[tuple[TimelineClip, ...], ...] = ()

    @property
    def _font_size(self) -> int:
        if self._font_size_override is not None:
            return self._font_size_override
        return timeline_ui_metrics().font_size

    @property
    def _padding(self) -> int:
        if self._padding_override is not None:
            return self._padding_override
        return timeline_ui_metrics().padding

    @property
    def _row_gap(self) -> int:
        if self._row_gap_override is not None:
            return self._row_gap_override
        return timeline_ui_metrics().row_gap

    def _font_get(self) -> pygame.font.Font:
        return overlay_font(self._font_size)

    def _bold_font_get(self) -> pygame.font.Font:
        return overlay_font(self._font_size, bold=True)

    @property
    def gpu_state(self):
        return self._cache.gpu

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        return self._panel_rect

    @property
    def bar_layout(self) -> tuple[int, int] | None:
        """Last draw bar metrics: ``(bar_left, bar_width)`` in panel coordinates."""
        return self._bar_layout

    @property
    def row_layout(self) -> list[tuple[int, int, int, int, str, int]]:
        """Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates."""
        return list(self._row_layout)

    def hit_at(self, x: float, y: float) -> StripHit | None:
        """Ruler or layer row under a screen point, from the last compose."""
        layout = self._hit_layout
        if layout is None:
            return None
        local_x = x - layout.panel_x
        local_y = y - layout.panel_y
        if not 0 <= local_x < layout.panel_w:
            return None
        view_start, view_end = self._hit_view
        tolerance = STRIP_HIT_PX * self.view_sec_per_px()
        in_bar = layout.bar_left <= local_x < layout.bar_left + layout.bar_width
        t_sec = (
            x_to_time(
                local_x, layout.bar_left, layout.bar_width, view_start, view_end
            )
            if in_bar
            else None
        )
        marker_index = (
            marker_index_near(self._hit_markers, t_sec, tolerance)
            if t_sec is not None
            else None
        )
        if -layout.badge_reserve <= local_y < layout.bar_top:
            upload_y = local_y + layout.badge_reserve
            for target, rect in zip(
                ("play", "record"), self._transport_rects(layout), strict=True
            ):
                if pygame.Rect(rect).collidepoint(local_x, upload_y):
                    return StripHit(
                        row=None, t_sec=None, tolerance_sec=tolerance, target=target
                    )
            # The time scale starts at its major ticks; the labels above them
            # and the band's top edge stay clear for the resize splitter.
            ruler_h = layout.badge_reserve + layout.bar_top
            if upload_y < ruler_tick_top(ruler_h):
                return None
            return StripHit(
                row=None,
                t_sec=t_sec,
                tolerance_sec=tolerance,
                marker_index=marker_index,
            )
        # The scrollbar takes the gap above it and the padding below, so the
        # thin track is an easy target.
        if in_bar and layout.bar_bottom <= local_y < layout.panel_h:
            thumb_x, thumb_w = self._thumb_span(layout)
            on_thumb = thumb_x <= local_x - layout.bar_left < thumb_x + thumb_w
            return StripHit(
                row=None,
                t_sec=self.scrollbar_time_at_x(x),
                tolerance_sec=tolerance,
                target="scroll_thumb" if on_thumb else "scroll_track",
            )
        header_target = row_header_target_at(
            local_x,
            padding=self._padding,
            label_width=layout.layer_num_width + layout.stem_abbrev_width,
            slot_w=layout.slot_w,
        )
        for display_i in range(layout.row_count):
            row_y = self._row_y(display_i, layout.row_h)
            if row_y <= local_y < row_y + layout.row_h:
                clip_hit = (
                    clip_hit_at_x(
                        self._hit_clips[display_i],
                        local_x,
                        bar_left=layout.bar_left,
                        bar_width=layout.bar_width,
                        view_start_sec=view_start,
                        view_end_sec=view_end,
                    )
                    if in_bar and display_i < len(self._hit_clips)
                    else None
                )
                return StripHit(
                    row=display_i,
                    t_sec=t_sec,
                    tolerance_sec=tolerance,
                    target=header_target,
                    marker_index=marker_index,
                    clip_start=None if clip_hit is None else clip_hit[0],
                    clip_edge=None if clip_hit is None else clip_hit[1],
                )
        return None

    def row_label_rect(self, row: int) -> tuple[int, int, int, int] | None:
        """Screen rect of *row*'s label (number and stem), from the last compose."""
        layout = self._hit_layout
        if layout is None or not 0 <= row < layout.row_count:
            return None
        return (
            layout.panel_x + self._padding,
            layout.panel_y + self._row_y(row, layout.row_h),
            layout.layer_num_width + layout.stem_abbrev_width,
            layout.row_h,
        )

    def _transport_rects(
        self, layout: _TimelineLayout
    ) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        return transport_button_rects(
            padding=self._padding,
            label_width=layout.layer_num_width + layout.stem_abbrev_width,
            bar_left=layout.bar_left,
            corner_h=layout.badge_reserve + layout.bar_top,
            gap=timeline_ui_metrics().rec_badge_gap,
        )

    @staticmethod
    def _transport_icon_size(layout: _TimelineLayout) -> int:
        """Glyph size: as tall as a row's level bar."""
        return max(1, layout.icon_h - 2 * timeline_ui_metrics().bar_vertical_inset)

    def _draw_transport_buttons(
        self,
        surface: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
    ) -> tuple[int, int, int, int]:
        """Play/pause and record glyphs in the corner (upload coordinates)."""
        play_rect, record_rect = self._transport_rects(layout)
        rec_text_color = VALUE
        if state.recording:
            # Flash: red fill with white glyph and text, then a red glyph on
            # no fill.
            if rec_flash_visible():
                pygame.draw.rect(surface, REC_BG, rec_fill_rect(record_rect))
                record_color = VALUE
            else:
                record_color = REC_BG
        elif state.locked:
            record_color = MUTED
        elif state.armed_slots:
            record_color = ARMED_BG
        else:
            record_color = VALUE
        play_color = VALUE
        # Shell hover: nudge wash behind, nudge foreground on glyph and text.
        if state.hover_button == "play":
            blit_tint(surface, play_rect, NUDGE_HOVER_BG, alpha=NUDGE_HOVER_BG_ALPHA)
            play_color = NUDGE_HOVER_FG
        # Recording wins over hover, so a click on record flashes at once.
        if state.hover_button == "record" and not state.recording:
            blit_tint(
                surface, record_rect, NUDGE_HOVER_BG, alpha=NUDGE_HOVER_BG_ALPHA
            )
            record_color = rec_text_color = NUDGE_HOVER_FG

        icon_font = material_font(self._transport_icon_size(layout))
        # Same state convention as the shell readout: the glyph shows the mode.
        play_glyph = PAUSE_GLYPH if state.paused else PLAY_GLYPH
        play_surf = icon_font.render(play_glyph, True, play_color)
        px, py, pw, ph = play_rect
        surface.blit(
            play_surf,
            (
                px + (pw - play_surf.get_width()) // 2,
                py + (ph - play_surf.get_height()) // 2,
            ),
        )

        # Glyph and REC centred as one group in the record button.
        rx, ry, rw, rh = record_rect
        icon_size = self._transport_icon_size(layout)
        text_gap = timeline_ui_metrics().rec_badge_gap // 2
        record_surf = icon_font.render(RECORD_GLYPH, True, record_color)
        text_surf = self._font_get().render(REC_BUTTON_TEXT, True, rec_text_color)
        group_w = icon_size + text_gap + text_surf.get_width()
        glyph_x = rx + (rw - group_w) // 2
        surface.blit(record_surf, (glyph_x, ry + (rh - record_surf.get_height()) // 2))
        surface.blit(
            text_surf,
            (
                glyph_x + icon_size + text_gap,
                ry + (rh - text_surf.get_height()) // 2,
            ),
        )
        left = play_rect[0]
        right = record_rect[0] + record_rect[2]
        bottom = max(play_rect[1] + play_rect[3], record_rect[1] + record_rect[3])
        return (left, 0, right - left, bottom)

    def time_at_x(self, x: float) -> float | None:
        """Song time under screen *x*, clamped to the bar. None before a compose."""
        layout = self._hit_layout
        if layout is None:
            return None
        return x_to_time(
            x - layout.panel_x,
            layout.bar_left,
            layout.bar_width,
            *self._hit_view,
        )

    def view_sec_per_px(self) -> float:
        """Song seconds one bar pixel spans in the visible window. 0 before a compose."""
        layout = self._hit_layout
        if layout is None or layout.bar_width <= 0:
            return 0.0
        view_start, view_end = self._hit_view
        return max(0.0, view_end - view_start) / layout.bar_width

    def scrollbar_time_at_x(self, x: float) -> float | None:
        """Song time at screen *x* along the scrollbar track (the whole song)."""
        layout = self._hit_layout
        if layout is None:
            return None
        return x_to_time(
            x - layout.panel_x,
            layout.bar_left,
            layout.bar_width,
            0.0,
            self._hit_duration_sec,
        )

    def scrollbar_sec_per_px(self) -> float:
        """Seconds the window start moves per pixel of thumb travel. 0 when it cannot move."""
        layout = self._hit_layout
        if layout is None:
            return 0.0
        view_start, view_end = self._hit_view
        _thumb_x, thumb_w = self._thumb_span(layout)
        travel = layout.bar_width - thumb_w
        hidden = self._hit_duration_sec - (view_end - view_start)
        if travel <= 0 or hidden <= 0:
            return 0.0
        return hidden / travel

    def _thumb_span(self, layout: _TimelineLayout) -> tuple[int, int]:
        view_start, view_end = self._hit_view
        return scrollbar_thumb_span(
            layout.scrollbar_rect[2],
            view_start,
            view_end,
            self._hit_duration_sec,
            min_thumb=timeline_ui_metrics().scrollbar_min_thumb,
        )

    def _compute_layout(
        self,
        state: TimelineViewState,
        *,
        viewport_width: int,
        viewport_height: int,
        timeline_rect: tuple[int, int, int, int] | None = None,
    ) -> _TimelineLayout | None:
        row_count = len(state.layer_z_order)
        if row_count == 0:
            return None

        metrics = timeline_ui_metrics()
        icon_h = metrics.row_height
        # The shell's timeline band is the container; the strip fills its width.
        # With no band the strip sits at the viewport bottom at its fit height.
        fills_band = timeline_rect is not None
        if timeline_rect is None:
            timeline_rect = (0, 0, viewport_width, viewport_height)
        band_x, band_y, band_w, band_h = timeline_rect
        if band_w <= 0 or band_h <= 0:
            return None
        badge_reserve = timeline_badge_reserve_px(
            font_size=self._font_size, padding=self._padding
        )
        # Rows share any band height past the nominal fit.
        fit_h = timeline_panel_height_px(row_count)
        spare = band_h - badge_reserve - fit_h if fills_band else 0
        row_h = icon_h + max(0, spare) // row_count
        panel_h = fit_h + (row_h - icon_h) * row_count
        panel_w = band_w
        panel_x = band_x
        panel_y = band_y + band_h - panel_h

        font = self._font_get()
        num_sample = font.render(layer_num_prefix(max(row_count, 1)), True, LABEL)
        abbrev_sample = font.render(stem_abbrev_label("drums"), True, LABEL)
        layer_num_width = num_sample.get_width()
        stem_abbrev_width = abbrev_sample.get_width()
        slot_w = visibility_icon_slot_width(icon_h)
        prefix_width = row_prefix_width(layer_num_width, stem_abbrev_width, icon_h)
        bar_left = self._padding + prefix_width
        bar_width = max(1, panel_w - self._padding * 2 - prefix_width)
        bar_top = self._padding
        bar_bottom = self._padding + row_count * row_h + (row_count - 1) * self._row_gap
        scrollbar_rect = (
            bar_left,
            bar_bottom + metrics.scrollbar_gap,
            bar_width,
            metrics.scrollbar_height,
        )

        self._layer_num_width = layer_num_width
        self._stem_abbrev_width = stem_abbrev_width
        self._bar_layout = (bar_left, bar_width)

        return _TimelineLayout(
            panel_w=panel_w,
            panel_h=panel_h,
            panel_x=panel_x,
            panel_y=panel_y,
            row_count=row_count,
            row_h=row_h,
            icon_h=icon_h,
            bar_left=bar_left,
            bar_width=bar_width,
            slot_w=slot_w,
            layer_num_width=layer_num_width,
            stem_abbrev_width=stem_abbrev_width,
            badge_reserve=badge_reserve,
            bar_top=bar_top,
            bar_bottom=bar_bottom,
            scrollbar_rect=scrollbar_rect,
        )

    def _build_static_panel(
        self,
        state: TimelineViewState,
        layout: _TimelineLayout,
    ) -> pygame.Surface:
        panel_w = layout.panel_w
        panel_h = layout.panel_h
        row_count = layout.row_count
        row_h = layout.row_h
        bar_left = layout.bar_left
        bar_width = layout.bar_width

        view_start, view_end = view_window(state)

        panel = overlay_panel_surface((panel_w, panel_h))
        font = self._font_get()
        self._row_layout = []

        if state.show_bar_grid and state.bar_grid_times:
            for t in state.bar_grid_times:
                if not time_in_view(t, view_start, view_end):
                    continue
                grid_x = time_to_x(t, bar_left, bar_width, view_start, view_end)
                pygame.draw.line(
                    panel,
                    BAR_GRID,
                    (grid_x, layout.bar_top),
                    (grid_x, layout.bar_bottom - 1),
                    1,
                )

        for display_i in range(row_count):
            row_index = display_i
            slot = state.layer_z_order[row_index]
            stem_source = state.slot_stems.get(slot, slot)
            row_y = self._padding + display_i * (row_h + self._row_gap)
            icon_y = row_y + (row_h - layout.icon_h) // 2
            row_rect = pygame.Rect(self._padding, row_y, panel_w - self._padding * 2, row_h)
            bar_rect = pygame.Rect(
                bar_left,
                row_y + timeline_ui_metrics().bar_vertical_inset,
                bar_width,
                max(1, row_h - timeline_ui_metrics().bar_vertical_inset * 2),
            )
            armed = slot in state.armed_slots
            focused = state.submenu_focused and row_index == state.focus_row

            self._row_layout.append(
                (row_index, row_rect.x, row_rect.y, row_rect.w, row_rect.h, slot)
            )

            layer_num = row_index + 1
            layer_num_x = self._padding
            stem_abbrev_x = layer_num_x + layout.layer_num_width
            hover_target = (
                state.hover_row_target[0]
                if state.hover_row_target is not None
                and state.hover_row_target[1] == row_index
                else None
            )

            if focused:
                blit_tint(panel, row_rect, HIGHLIGHT, alpha=FOCUS_WASH_ALPHA)
            # Shell hover washes a header button that is drawn: not the label
            # (it only selects) or the empty back-to-timeline slot.
            if hover_target in ("arm", "solo", "eye") or (
                hover_target == "release" and slot in state.override_slots
            ):
                blit_tint(
                    panel,
                    self._header_button_rect(layout, hover_target, row_y),
                    NUDGE_HOVER_BG,
                    alpha=NUDGE_HOVER_BG_ALPHA,
                )

            if focused or armed:
                label_color = HIGHLIGHT
            else:
                label_color = LABEL
            num_surf = font.render(layer_num_prefix(layer_num), True, label_color)
            abbrev_surf = font.render(stem_abbrev_label(stem_source), True, label_color)
            num_y = row_y + max(0, (row_h - num_surf.get_height()) // 2)
            abbrev_y = row_y + max(0, (row_h - abbrev_surf.get_height()) // 2)
            panel.blit(num_surf, (layer_num_x, num_y))
            panel.blit(abbrev_surf, (stem_abbrev_x, abbrev_y))

            # The lit arm button and the recording eye are live-patched.
            panel.blit(
                render_header_toggle(
                    RECORD_GLYPH,
                    color=self._header_rest_color(
                        hover_target == "arm", blocked=state.locked
                    ),
                    line_height=layout.icon_h,
                ),
                (self._header_button_x(layout, "arm"), icon_y),
            )
            solo = state.solo_slot == slot
            panel.blit(
                render_header_toggle(
                    SOLO_GLYPH,
                    color=VALUE if solo else self._header_rest_color(
                        hover_target == "solo"
                    ),
                    bg=SOLO_BG if solo else None,
                    line_height=layout.icon_h,
                ),
                (self._header_button_x(layout, "solo"), icon_y),
            )
            if not (state.recording and armed):
                panel.blit(
                    render_visibility_icon(
                        enabled=state.monitor_visible.get(slot, True),
                        override=slot in state.override_slots,
                        line_height=layout.icon_h,
                    ),
                    (self._header_button_x(layout, "eye"), icon_y),
                )
            if slot in state.override_slots:
                panel.blit(
                    render_header_toggle(
                        REPLAY_GLYPH,
                        color=OVERRIDE_GLYPH,
                        bg=OVERRIDE_BG,
                        line_height=layout.icon_h,
                    ),
                    (self._header_button_x(layout, "release"), icon_y),
                )

            _draw_level_bar(
                panel,
                breakpoints=bar_level_breakpoints_for_row(state, slot),
                bar_left=bar_left,
                bar_width=bar_width,
                view_start_sec=view_start,
                view_end_sec=view_end,
                bar_rect=bar_rect,
                on_color=track_color(row_index),
            )

            # Cue ticks mark every clip boundary, so butted clips show a divider.
            for cue in bar_cues_for_row(state, slot):
                if not time_in_view(cue.t, view_start, view_end):
                    continue
                tick_x = time_to_x(cue.t, bar_left, bar_width, view_start, view_end)
                pygame.draw.line(
                    panel,
                    (*LABEL, CUE_TICK_ALPHA),
                    (tick_x, bar_rect.y),
                    (tick_x, bar_rect.bottom - 1),
                    CUE_TICK_WIDTH,
                )

            # Per-slot selection memory stays in selected_clip_t; only the
            # focused row outlines its selected clip.
            row_clips = row_clips_for_view(state, slot)
            selected_t = (
                state.selected_clip_t.get(slot)
                if row_index == state.focus_row and not state.recording
                else None
            )
            hover_t = (
                state.hover_clip[1]
                if state.hover_clip is not None and state.hover_clip[0] == row_index
                else None
            )
            editable = not state.locked and not state.recording
            for clip in row_clips:
                selected = selected_t is not None and clip.start == selected_t
                hovered = hover_t is not None and clip.start == hover_t
                if not selected and not (hovered and editable):
                    continue
                span = clip_bar_span(
                    clip,
                    bar_left=bar_left,
                    bar_width=bar_width,
                    view_start_sec=view_start,
                    view_end_sec=view_end,
                )
                if span is None:
                    continue
                left, right = span
                if editable:
                    for edge_t, handle_x in (
                        (clip.start, left),
                        (clip.end, right - CLIP_HANDLE_WIDTH),
                    ):
                        if time_in_view(edge_t, view_start, view_end):
                            pygame.draw.rect(
                                panel,
                                SELECTED_CLIP_COLOR if selected else LABEL,
                                pygame.Rect(
                                    max(left, handle_x),
                                    row_y,
                                    min(CLIP_HANDLE_WIDTH, right - left),
                                    row_h,
                                ),
                            )
                if selected:
                    pygame.draw.rect(
                        panel,
                        SELECTED_CLIP_COLOR,
                        pygame.Rect(left, row_y, right - left, row_h),
                        SELECTED_CLIP_OUTLINE_WIDTH,
                    )

            if focused:
                _draw_focus_outline(panel, row_rect)

        # Song start and end marks continue the ruler's down through every row.
        for bound_x in song_bound_xs(
            duration_sec=state.duration_sec,
            bar_left=bar_left,
            bar_width=bar_width,
            view_start_sec=view_start,
            view_end_sec=view_end,
        ):
            pygame.draw.line(
                panel,
                SONG_BOUND,
                (bound_x, 0),
                (bound_x, layout.bar_bottom - 1),
                1,
            )

        self._draw_scrollbar(panel, state, layout)
        return panel

    def _draw_scrollbar(
        self,
        panel: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
    ) -> None:
        """Rail under the rows; the pill thumb is the visible share of the song.

        A thin rail and a rounded neutral thumb keep it from reading as a
        level bar. The whole song in view draws the rail alone.
        """
        track_x, track_y, track_w, track_h = layout.scrollbar_rect
        if track_w <= 0 or track_h <= 0:
            return
        view_start, view_end = view_window(state)
        rail_h = max(1, track_h // 3)
        pygame.draw.rect(
            panel,
            TIMELINE_SCROLL_RAIL,
            (track_x, track_y + (track_h - rail_h) // 2, track_w, rail_h),
        )
        if view_end - view_start >= state.duration_sec:
            return
        thumb_x, thumb_w = scrollbar_thumb_span(
            track_w,
            view_start,
            view_end,
            state.duration_sec,
            min_thumb=timeline_ui_metrics().scrollbar_min_thumb,
        )
        pygame.draw.rect(
            panel,
            TIMELINE_SCROLL_THUMB,
            (track_x + thumb_x, track_y, thumb_w, track_h),
            border_radius=track_h // 2,
        )

    def _draw_role_glyphs(
        self,
        surface: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
        *,
        y_offset: int = 0,
    ) -> list[tuple[int, int, int, int]]:
        """XOR role letters after bars/ticks/markers/playhead so they stay on top."""
        bold_font = self._bold_font_get()
        dirty: list[tuple[int, int, int, int]] = []
        row_h = layout.row_h
        view_start, view_end = view_window(state)
        for display_i, slot in enumerate(state.layer_z_order):
            row_y = self._row_y(display_i, row_h)
            bar_rect = pygame.Rect(
                layout.bar_left,
                row_y + timeline_ui_metrics().bar_vertical_inset,
                layout.bar_width,
                max(1, row_h - timeline_ui_metrics().bar_vertical_inset * 2),
            )
            for cue in bar_cues_for_row(state, slot):
                if cue.role is None or cue.level <= LEVEL_EPS:
                    continue
                if not time_in_view(cue.t, view_start, view_end):
                    continue
                letter = _ROLE_GLYPH.get(cue.role)
                if letter is None:
                    continue
                lane, inherit = _glyph_lane_for_cue(state, slot, cue.t)
                previous = role_glyph_previous_level(lane, cue.t, inherit=inherit)
                side = role_glyph_side(
                    previous_level=previous, cue_level=cue.level
                )
                tick_x = time_to_x(
                    cue.t, layout.bar_left, layout.bar_width, view_start, view_end
                )
                glyph_w, glyph_h = bold_font.size(letter)
                glyph_x, glyph_y = role_glyph_anchor(
                    tick_x=tick_x,
                    bar_rect=bar_rect,
                    glyph_w=glyph_w,
                    glyph_h=glyph_h,
                    side=side,
                )
                touched = blit_role_glyph_xor(
                    surface,
                    letter,
                    x=glyph_x,
                    y=glyph_y + y_offset,
                    font=bold_font,
                )
                if touched is not None:
                    dirty.append(touched)
        return dirty

    def _header_button_x(self, layout: _TimelineLayout, target: StripTarget) -> int:
        return header_button_x(
            target,
            padding=self._padding,
            label_width=layout.layer_num_width + layout.stem_abbrev_width,
            slot_w=layout.slot_w,
        )

    def _header_button_rect(
        self, layout: _TimelineLayout, target: StripTarget, row_y: int
    ) -> tuple[int, int, int, int]:
        """Panel rect of a row's header button *target*."""
        x = self._header_button_x(layout, target)
        return (x, row_y, layout.slot_w, layout.row_h)

    @staticmethod
    def _header_rest_color(
        hovered: bool, *, blocked: bool = False
    ) -> tuple[int, int, int]:
        """An unlit header button: muted, nudge on hover, disabled when blocked."""
        if blocked:
            return DISABLED
        return NUDGE_HOVER_FG if hovered else MUTED

    def _row_y(self, display_i: int, row_h: int) -> int:
        return self._padding + display_i * (row_h + self._row_gap)

    def _restore_upload_rect_from_static(
        self,
        upload: pygame.Surface,
        static_panel: pygame.Surface,
        rect: tuple[int, int, int, int],
        *,
        panel_y_offset: int,
    ) -> None:
        x, y, w, h = rect
        panel_y = y - panel_y_offset
        if panel_y < 0:
            # Only the part over the static panel has pixels to restore.
            h += panel_y
            y -= panel_y
            panel_y = 0
        if panel_y >= static_panel.get_height():
            return
        clip_h = min(h, static_panel.get_height() - panel_y)
        if clip_h <= 0:
            return
        source = static_panel.subsurface((x, panel_y, w, clip_h))
        upload.blit(source, (x, y))

    def _draw_row_live_flash(
        self,
        upload: pygame.Surface,
        static_panel: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
        *,
        row_index: int,
        panel_y_offset: int,
    ) -> list[tuple[int, int, int, int]]:
        slot = state.layer_z_order[row_index]
        row_h = layout.row_h
        row_y = self._row_y(row_index, row_h)
        upload_y = panel_y_offset + row_y
        armed = slot in state.armed_slots
        arm_x = self._header_button_x(layout, "arm")
        monitor_eye_x = self._header_button_x(layout, "eye")
        slot_w = layout.slot_w
        icon_y = upload_y + (row_h - layout.icon_h) // 2
        dirty: list[tuple[int, int, int, int]] = []

        arm_rect = (arm_x, upload_y, slot_w, row_h)
        self._restore_upload_rect_from_static(
            upload,
            static_panel,
            arm_rect,
            panel_y_offset=panel_y_offset,
        )
        if arm_button_lit(
            armed=armed,
            recording=state.recording,
            flash_starts=state.arm_flash_start_ms,
            slot=slot,
        ):
            armed_surf = pygame.Surface((slot_w, row_h), pygame.SRCALPHA)
            armed_surf.fill((*ARMED_BG, ARMED_BG_ALPHA))
            upload.blit(armed_surf, (arm_x, upload_y))
            upload.blit(
                render_header_toggle(
                    RECORD_GLYPH, color=VALUE, line_height=layout.icon_h
                ),
                (arm_x, icon_y),
            )
        dirty.append(arm_rect)

        monitor_rect = (monitor_eye_x, upload_y, slot_w, row_h)
        self._restore_upload_rect_from_static(
            upload,
            static_panel,
            monitor_rect,
            panel_y_offset=panel_y_offset,
        )
        monitor_enabled = state.monitor_visible.get(slot, True)
        monitor_override = (
            slot in state.override_slots
            and not (state.recording and armed)
        ) or (state.recording and armed and rec_flash_visible())
        monitor_icon = render_visibility_icon(
            enabled=monitor_enabled,
            override=monitor_override,
            line_height=layout.icon_h,
        )
        upload.blit(monitor_icon, (monitor_eye_x, icon_y))
        dirty.append(monitor_rect)

        selected_t = (
            state.selected_clip_t.get(slot)
            if row_index == state.focus_row and not state.recording
            else None
        )
        view_start, view_end = view_window(state)
        if selected_t is not None and selected_clip_flash_active(
            state.selected_clip_flash_start_ms
        ):
            clip = next(
                (
                    clip
                    for clip in row_clips_for_view(state, slot)
                    if clip.start == selected_t
                ),
                None,
            )
            span = (
                clip_bar_span(
                    clip,
                    bar_left=layout.bar_left,
                    bar_width=layout.bar_width,
                    view_start_sec=view_start,
                    view_end_sec=view_end,
                )
                if clip is not None
                else None
            )
            if span is not None:
                left, right = span
                clip_rect = (left, upload_y, right - left, row_h)
                pygame.draw.rect(
                    upload,
                    selected_clip_flash_color(state.selected_clip_flash_start_ms),
                    pygame.Rect(clip_rect),
                    SELECTED_CLIP_FLASH_OUTLINE_WIDTH,
                )
                dirty.append(clip_rect)
        return dirty

    def _live_flash_row_indices(self, state: TimelineViewState) -> tuple[int, ...]:
        indices: list[int] = []
        cue_flash = selected_clip_flash_active(state.selected_clip_flash_start_ms)
        for row_index, slot in enumerate(state.layer_z_order):
            armed = slot in state.armed_slots
            if arm_flash_active(state.arm_flash_start_ms, slot):
                indices.append(row_index)
            elif state.recording and armed:
                indices.append(row_index)
            elif armed and not state.recording:
                indices.append(row_index)
            elif (
                cue_flash
                and row_index == state.focus_row
                and slot in state.selected_clip_t
            ):
                indices.append(row_index)
        return tuple(indices)

    def _live_flash_signature(self, state: TimelineViewState) -> tuple:
        parts: list[tuple] = []
        cue_flash_bright = (
            selected_clip_flash_bright(state.selected_clip_flash_start_ms)
            if selected_clip_flash_active(state.selected_clip_flash_start_ms)
            else None
        )
        for row_index in self._live_flash_row_indices(state):
            slot = state.layer_z_order[row_index]
            armed = slot in state.armed_slots
            parts.append(
                (
                    slot,
                    arm_button_lit(
                        armed=armed,
                        recording=state.recording,
                        flash_starts=state.arm_flash_start_ms,
                        slot=slot,
                    ),
                    (
                        (slot in state.override_slots and not (state.recording and armed))
                        or (state.recording and armed and rec_flash_visible())
                    ),
                    (
                        state.selected_clip_t.get(slot)
                        if cue_flash_bright is not None
                        and row_index == state.focus_row
                        else None
                    ),
                    (
                        cue_flash_bright
                        if row_index == state.focus_row and slot in state.selected_clip_t
                        else None
                    ),
                )
            )
        if (
            state.selected_song_marker_index is not None
            and selected_clip_flash_active(state.song_marker_flash_start_ms)
        ):
            parts.append(
                (
                    "song_marker",
                    state.selected_song_marker_index,
                    selected_clip_flash_bright(state.song_marker_flash_start_ms),
                )
            )
        return tuple(parts)

    def _draw_song_markers(
        self,
        upload: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
        *,
        y_offset: int,
    ) -> tuple[int, int, int, int] | None:
        """Draw song markers through the ruler and rows.

        Returns the selected marker's column while it flashes, so the upload
        repaints it each blink and once more when it settles; else None.
        """
        view_start, view_end = view_window(state)
        y0 = self._playhead_top_y(layout, y_offset=y_offset)
        y1 = y_offset + layout.bar_bottom - 1
        bar_right = layout.bar_left + layout.bar_width - 1
        flash_rect: tuple[int, int, int, int] | None = None
        selected_index = state.selected_song_marker_index
        selected_x: int | None = None
        for marker_i, marker_t in enumerate(state.song_marker_times):
            if not time_in_view(marker_t, view_start, view_end):
                continue
            marker_x = min(
                bar_right,
                time_to_x(
                    marker_t, layout.bar_left, layout.bar_width, view_start, view_end
                ),
            )
            if marker_i == selected_index:
                selected_x = marker_x
                continue
            pygame.draw.line(
                upload, SONG_MARKER, (marker_x, y0), (marker_x, y1), SONG_MARKER_WIDTH
            )
        # The selected marker draws last so a neighbour never covers it.
        if selected_x is not None:
            flash_start = state.song_marker_flash_start_ms
            if selected_clip_flash_active(flash_start):
                color = selected_clip_flash_color(flash_start)
                width = SELECTED_CLIP_FLASH_TICK_WIDTH
                half_w = width // 2 + 1
                left = max(layout.bar_left, selected_x - half_w)
                right = min(bar_right + 1, selected_x + half_w + 1)
                if right > left:
                    flash_rect = (left, y0, right - left, y1 - y0 + 1)
            else:
                color = SONG_MARKER_SELECTED
                width = SONG_MARKER_SELECTED_WIDTH
            pygame.draw.line(upload, color, (selected_x, y0), (selected_x, y1), width)
        return flash_rect

    def _playhead_strip_rect(
        self,
        layout: _TimelineLayout,
        playhead_px: int,
        *,
        y_offset: int,
    ) -> tuple[int, int, int, int]:
        playhead_left = max(
            layout.bar_left,
            min(layout.bar_left + layout.bar_width - 1, playhead_px),
        )
        x = playhead_left - max(1, timeline_ui_metrics().playhead_width)
        y = self._playhead_top_y(layout, y_offset=y_offset)
        w = max(1, timeline_ui_metrics().playhead_width) * 2 + 1
        h = y_offset + layout.bar_bottom - y
        return (x, y, w, h)

    @staticmethod
    def _playhead_top_y(layout: _TimelineLayout, *, y_offset: int) -> int:
        """The playhead rises through the ruler to the top of its major ticks."""
        ruler_top = y_offset - layout.badge_reserve
        return ruler_top + ruler_tick_top(layout.badge_reserve + layout.bar_top)

    def _draw_playhead(
        self,
        surface: pygame.Surface,
        layout: _TimelineLayout,
        playhead_px: int | None,
        *,
        y_offset: int,
    ) -> tuple[int, int, int, int] | None:
        """Draw the playhead. None when it is outside the visible window."""
        if playhead_px is None:
            return None
        playhead_left = max(
            layout.bar_left,
            min(layout.bar_left + layout.bar_width - 1, playhead_px),
        )
        y0 = self._playhead_top_y(layout, y_offset=y_offset)
        y1 = y_offset + layout.bar_bottom - 1
        pygame.draw.line(
            surface,
            playhead_color(),
            (playhead_left, y0),
            (playhead_left, y1),
            timeline_ui_metrics().playhead_width,
        )
        return self._playhead_strip_rect(layout, playhead_px, y_offset=y_offset)

    def _build_ruler(
        self,
        state: TimelineViewState,
        layout: _TimelineLayout,
    ) -> pygame.Surface | None:
        """Time scale over the badge row and the strip's top padding."""
        view_start, view_end = view_window(state)
        return render_time_ruler(
            width=layout.panel_w,
            height=layout.badge_reserve + layout.bar_top,
            bar_left=layout.bar_left,
            bar_width=layout.bar_width,
            view_start_sec=view_start,
            view_end_sec=view_end,
            duration_sec=state.duration_sec,
            strip_font_size=self._font_size,
        )

    def _ensure_upload_scratch(
        self,
        upload_w: int,
        upload_h: int,
    ) -> pygame.Surface:
        scratch = self._upload_scratch
        if (
            scratch is not None
            and scratch.get_width() == upload_w
            and scratch.get_height() == upload_h
        ):
            return scratch
        scratch = pygame.Surface((upload_w, upload_h), pygame.SRCALPHA)
        self._upload_scratch = scratch
        return scratch

    def _patch_live_overlay(
        self,
        upload: pygame.Surface,
        static_panel: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
        *,
        playhead_px: int | None,
        incremental: bool,
    ) -> list[tuple[int, int, int, int]]:
        cache = self._cache
        panel_y_offset = layout.badge_reserve

        if incremental and cache.last_playhead_rect is not None:
            self._restore_upload_rect_from_static(
                upload,
                static_panel,
                cache.last_playhead_rect,
                panel_y_offset=panel_y_offset,
            )
            # The strip rises through the ruler, whose baseline sits on the
            # panel's top padding; put the ruler back over the restored panel.
            if self._ruler is not None:
                px, py, pw, ph = cache.last_playhead_rect
                ruler_h = self._ruler.get_height()
                if py < ruler_h:
                    clip_h = min(ph, ruler_h - py)
                    upload.blit(self._ruler, (px, py), (px, py, pw, clip_h))

        # Markers after the playhead restore (which repaints that column from
        # the static panel) and before the playhead, which stays on top.
        marker_flash_rect = self._draw_song_markers(
            upload, state, layout, y_offset=panel_y_offset
        )

        # Corner buttons before the playhead, so a red record fill that ends
        # at the ruler never covers the playhead at the song start.
        cache.last_transport_rect = self._draw_transport_buttons(upload, state, layout)
        playhead_rect = self._draw_playhead(
            upload,
            layout,
            playhead_px,
            y_offset=panel_y_offset,
        )
        cache.last_playhead_rect = playhead_rect

        flash_dirty: list[tuple[int, int, int, int]] = []
        if marker_flash_rect is not None:
            flash_dirty.append(marker_flash_rect)
        for row_index in self._live_flash_row_indices(state):
            flash_dirty.extend(
                self._draw_row_live_flash(
                    upload,
                    static_panel,
                    state,
                    layout,
                    row_index=row_index,
                    panel_y_offset=panel_y_offset,
                )
            )
        cache.last_flash_rects = tuple(flash_dirty)

        # Role glyphs last (after playhead / flash) so XOR letters sit on top.
        glyph_dirty = self._draw_role_glyphs(
            upload,
            state,
            layout,
            y_offset=panel_y_offset,
        )
        cache.last_glyph_rects = tuple(glyph_dirty)
        flash_dirty.extend(glyph_dirty)
        return flash_dirty

    def compose_panel(
        self,
        state: TimelineViewState,
        *,
        viewport_width: int,
        viewport_height: int,
        visibility: float = 1.0,
        timeline_rect: tuple[int, int, int, int] | None = None,
    ) -> ComposedPanel | None:
        self._visibility = visibility
        self._panel_rect = None
        self._hit_layout = None
        if visibility <= 0.01:
            return None

        layout = self._compute_layout(
            state,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            timeline_rect=timeline_rect,
        )
        if layout is None:
            return None

        panel_w = layout.panel_w
        panel_h = layout.panel_h
        static_sig = timeline_static_signature(
            state,
            panel_w=panel_w,
            panel_h=panel_h,
            visibility=visibility,
        )
        cache = self._cache
        can_reuse_static = (
            cache.panel is not None
            and cache.static_signature == static_sig
            and cache.panel_size == (panel_w, panel_h)
        )

        if can_reuse_static:
            assert cache.panel is not None
            static_panel = cache.panel
            incremental = True
        else:
            static_panel = self._build_static_panel(state, layout)
            self._ruler = self._build_ruler(state, layout)
            cache.panel = static_panel
            cache.static_signature = static_sig
            cache.panel_size = (panel_w, panel_h)
            cache.last_playhead_rect = None
            cache.last_flash_rects = ()
            cache.last_glyph_rects = ()
            cache.last_live_signature = None
            incremental = False

        upload_w = panel_w
        upload_h = panel_h + layout.badge_reserve
        upload = self._ensure_upload_scratch(upload_w, upload_h)
        upload.fill((0, 0, 0, 0))
        upload.blit(static_panel, (0, layout.badge_reserve))
        if self._ruler is not None:
            upload.blit(self._ruler, (0, 0))

        view_start, view_end = view_window(state)
        playhead_px = (
            playhead_x(
                state.position_sec,
                layout.bar_left,
                layout.bar_width,
                view_start,
                view_end,
            )
            if time_in_view(state.position_sec, view_start, view_end)
            else None
        )
        prev_playhead = cache.last_playhead_rect
        prev_flash = cache.last_flash_rects
        prev_glyphs = cache.last_glyph_rects
        flash_dirty = self._patch_live_overlay(
            upload,
            static_panel,
            state,
            layout,
            playhead_px=playhead_px,
            incremental=incremental,
        )

        upload_top_y = layout.panel_y - layout.badge_reserve
        screen_bounds = clip_rect_to_bounds(
            (layout.panel_x, upload_top_y, upload_w, upload_h),
            viewport_width,
            viewport_height,
        )
        if screen_bounds is None:
            return None

        self._hit_layout = layout
        self._hit_duration_sec = state.duration_sec
        self._hit_view = (view_start, view_end)
        self._hit_markers = state.song_marker_times
        self._hit_clips = tuple(
            tuple(row_clips_for_view(state, slot)) for slot in state.layer_z_order
        )
        sx, sy, sw, sh = screen_bounds
        panel_screen_y = layout.panel_y
        self._panel_rect = clip_rect_to_bounds(
            (layout.panel_x, panel_screen_y, panel_w, panel_h),
            viewport_width,
            viewport_height,
        )

        capacity = timeline_panel_max_dimensions(viewport_width, viewport_height)
        live_sig = timeline_live_signature(
            state,
            playhead_px=playhead_px,
            bar_left=layout.bar_left,
            bar_width=layout.bar_width,
            row_count=layout.row_count,
            row_h=layout.row_h,
            flash_sig=self._live_flash_signature(state),
        )
        upload_signature = timeline_upload_signature(static_sig, screen_bounds, live_sig)

        src_x = sx - layout.panel_x
        src_y = sy - upload_top_y
        if incremental and live_sig == cache.last_live_signature:
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
            )
        elif incremental:
            dirty_rects: list[tuple[int, int, int, int]] = []
            for rect in (
                *prev_flash,
                *flash_dirty,
                *prev_glyphs,
                *cache.last_glyph_rects,
                prev_playhead,
                cache.last_playhead_rect,
                cache.last_transport_rect,
            ):
                if rect is not None:
                    dirty_rects.append(rect)
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
                dirty_rects=clip_dirty_rects(tuple(dirty_rects), upload_w, upload_h),
            )
        else:
            clip_rect = (
                (src_x, src_y, sw, sh)
                if src_x != 0 or src_y != 0 or (sw, sh) != (upload_w, upload_h)
                else None
            )
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
                dirty_rects=dirty_rects_for_clip_rect(clip_rect, upload_w, upload_h),
            )

        cache.last_live_signature = live_sig
        self._blit_src = (src_x, src_y)

        return ComposedPanel(
            upload_surface=upload,
            panel_size=(panel_w, panel_h),
            screen_rect=screen_bounds,
            upload_plan=upload_plan,
            upload_signature=upload_signature,
            capacity=capacity,
        )

    def draw(
        self,
        surface: pygame.Surface,
        state: TimelineViewState,
        *,
        timeline_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        composed = self.compose_panel(
            state,
            viewport_width=surface.get_width(),
            viewport_height=surface.get_height(),
            timeline_rect=timeline_rect,
        )
        if composed is None:
            self._panel_rect = None
            self._bar_layout = None
            self._row_layout = []
            return
        sx, sy, sw, sh = composed.screen_rect
        src_x, src_y = self._blit_src
        surface.blit(composed.upload_surface, (sx, sy), (src_x, src_y, sw, sh))
