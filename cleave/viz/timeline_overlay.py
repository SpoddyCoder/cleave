"""Bottom timeline strip overlay for per-stem layer visibility cues."""

from __future__ import annotations

import bisect
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import pygame

from cleave.cue_roles import CueRole
from cleave.stems import StemSource
from cleave.timeline import (
    LEVEL_EPS,
    SlotCue,
    TimelineFadeGroup,
    TimelineLane,
    empty_lane,
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
from cleave.viz.row_present_renderers import render_visibility_icon
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
    FOCUS_BORDER_ALPHA,
    HIGHLIGHT,
    LABEL,
    NUDGE_HOVER_BG,
    NUDGE_HOVER_BG_ALPHA,
    NUDGE_HOVER_FG,
    MUTED,
    PLAYHEAD,
    PLAYHEAD_FLASH,
    REC_BG,
    SCROLLBAR_THUMB,
    SCROLLBAR_TRACK,
    SELECTED_WASH_ALPHA,
    SONG_BOUND,
    SONG_MARKER,
    SONG_MARKER_SELECTED,
    TIMELINE_BAR_ON,
    VALUE,
    timeline_panel_height_px,
    timeline_ui_metrics,
)
from cleave.viz.ui_tint import blit_tint

OFF_SEGMENT_COLOR: tuple[int, int, int] = (40, 40, 40)
# Dim end of the level-bar colour ramp (quarter beds stay readable).
_BAR_LEVEL_DIM: tuple[int, int, int] = tuple(
    int(round(OFF_SEGMENT_COLOR[i] + (TIMELINE_BAR_ON[i] - OFF_SEGMENT_COLOR[i]) * 0.4))
    for i in range(3)
)
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
CUE_TICK_WIDTH: int = 1
# Settled selected tick (thinner than flash; still thicker than a normal cue tick).
SELECTED_CUE_TICK_WIDTH: int = 3
# Thick width while the selection flash is active.
SELECTED_CUE_FLASH_TICK_WIDTH: int = 7
REC_FLASH_MS: int = 500
PLAYHEAD_FLASH_MS: int = 400
ARM_FLASH_HALF_MS: int = 150
ARM_FLASH_DURATION_MS: int = ARM_FLASH_HALF_MS * 4
# Selected-cue flash: same blink cadence as arm flash, held for 3s.
SELECTED_CUE_FLASH_HALF_MS: int = ARM_FLASH_HALF_MS
SELECTED_CUE_FLASH_DURATION_MS: int = 3000
# Settled selected tick (HIGHLIGHT yellow); flash pulses yellow/red at flash width.
SELECTED_CUE_COLOR: tuple[int, int, int] = HIGHLIGHT
SELECTED_CUE_FLASH_YELLOW: tuple[int, int, int] = HIGHLIGHT
SELECTED_CUE_FLASH_RED: tuple[int, int, int] = ARMED_BG
# Clear half the flash tick plus 1px so glyphs sit beside the thick marker.
ROLE_GLYPH_TICK_GAP: int = SELECTED_CUE_FLASH_TICK_WIDTH // 2 + 1
ROLE_GLYPH_BOTTOM_PAD: int = 1


@dataclass
class TimelineViewState:
    layer_z_order: list[str]
    lanes: dict[str, TimelineLane]
    defaults: dict[str, float]
    position_sec: float
    duration_sec: float
    focus_row: int  # 0..N-1, index into layer_z_order (0 = bottom stem)
    monitor_visible: dict[str, bool]
    timeline_level: dict[str, float]
    slot_stems: dict[str, StemSource] = field(default_factory=dict)
    override_slots: set[str] = field(default_factory=set)
    armed_slots: set[str] = field(default_factory=set)
    recording: bool = False
    paused: bool = True
    locked: bool = False
    # Pointer hover: a row label (static chrome) or a corner button (live).
    hover_label_row: int | None = None
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
    hard_cut_fades: TimelineFadeGroup = field(default_factory=TimelineFadeGroup)
    soft_cut_fades: TimelineFadeGroup = field(default_factory=TimelineFadeGroup)
    selected_cue_t: dict[str, float] = field(default_factory=dict)
    selected_cue_flash_start_ms: int | None = None
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
    """Clip a breakpoint polyline to ``[start, end]``, interpolating at the edges."""
    if end <= start or not breakpoints:
        return []
    clipped: list[tuple[float, float]] = [
        (start, level_at_breakpoints(breakpoints, start))
    ]
    for t, level in breakpoints:
        if start < t < end:
            clipped.append((float(t), float(level)))
    end_level = level_at_breakpoints(breakpoints, end)
    if clipped[-1][0] < end:
        clipped.append((end, end_level))
    elif not levels_equal(clipped[-1][1], end_level):
        clipped[-1] = (end, end_level)
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
    """1px highlight outline at the shell's focus alpha, as on inspector rows."""
    for edge in (
        pygame.Rect(rect.x, rect.y, rect.w, 1),
        pygame.Rect(rect.x, rect.bottom - 1, rect.w, 1),
        pygame.Rect(rect.x, rect.y + 1, 1, rect.h - 2),
        pygame.Rect(rect.right - 1, rect.y + 1, 1, rect.h - 2),
    ):
        blit_tint(surface, edge, HIGHLIGHT, alpha=FOCUS_BORDER_ALPHA)


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
) -> None:
    pygame.draw.rect(panel, OFF_SEGMENT_COLOR, bar_rect)
    if view_end_sec <= view_start_sec or len(breakpoints) < 2:
        return
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
        color = _lerp_rgb(_BAR_LEVEL_DIM, TIMELINE_BAR_ON, mean_level)
        pygame.draw.polygon(
            panel,
            color,
            [(x0, y0), (x1, y1), (x1, bottom), (x0, bottom)],
        )


def _render_committed_level_icon(level: float, *, line_height: int) -> pygame.Surface:
    """Far-right committed eye: full at 1.0, dimmed when partial, DISABLED at 0."""
    if level <= LEVEL_EPS:
        return render_visibility_icon(enabled=False, line_height=line_height)
    icon = render_visibility_icon(enabled=True, line_height=line_height)
    if level >= 1.0 - LEVEL_EPS:
        return icon
    faded = icon.copy()
    alpha = max(1, min(255, int(round(level * 255))))
    faded.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
    return faded


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


def prune_expired_selected_cue_flash(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> int | None:
    if flash_start_ms is None:
        return None
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    if ticks_ms - flash_start_ms >= SELECTED_CUE_FLASH_DURATION_MS:
        return None
    return flash_start_ms


def arm_abbrev_flash_active(
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


def arm_abbrev_flash_visible(
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if not arm_abbrev_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    start_ms = flash_starts[slot]
    elapsed = ticks_ms - start_ms
    return (elapsed // ARM_FLASH_HALF_MS) % 2 == 0


def selected_cue_flash_active(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> bool:
    if flash_start_ms is None:
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return ticks_ms - flash_start_ms < SELECTED_CUE_FLASH_DURATION_MS


def selected_cue_flash_bright(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> bool:
    """True on the yellow (HIGHLIGHT) half of the selected-cue blink cycle."""
    if not selected_cue_flash_active(flash_start_ms, ticks_ms=ticks_ms):
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    assert flash_start_ms is not None
    elapsed = ticks_ms - flash_start_ms
    return (elapsed // SELECTED_CUE_FLASH_HALF_MS) % 2 == 0


def selected_cue_tick_color(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> tuple[int, int, int]:
    if selected_cue_flash_bright(flash_start_ms, ticks_ms=ticks_ms):
        return SELECTED_CUE_FLASH_YELLOW
    if selected_cue_flash_active(flash_start_ms, ticks_ms=ticks_ms):
        return SELECTED_CUE_FLASH_RED
    return SELECTED_CUE_COLOR


def armed_abbrev_bg_visible(
    *,
    armed: bool,
    recording: bool,
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if arm_abbrev_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return arm_abbrev_flash_visible(flash_starts, slot, ticks_ms=ticks_ms)
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


# Pointer slack around a cue tick, in pixels.
CUE_HIT_PX: int = 4


StripTarget = Literal[
    "play", "record", "label", "eye", "scroll_thumb", "scroll_track"
]


@dataclass(frozen=True)
class StripHit:
    """What a screen point lands on in the strip.

    ``row`` is None for the ruler and the scrollbar. ``t_sec`` is None outside
    the bar span (row labels and icons). ``cue_tolerance_sec`` is
    ``CUE_HIT_PX`` in song time. ``target`` names a control: the corner
    ``"play"`` / ``"record"`` buttons, a row's ``"label"`` (layer number and
    stem abbreviation), its monitor ``"eye"`` (the visibility icon after the
    label), or the scrollbar's ``"scroll_thumb"`` / ``"scroll_track"``. On the
    scrollbar ``t_sec`` is the song time at that point along the track.
    """

    row: int | None
    t_sec: float | None
    cue_tolerance_sec: float
    target: StripTarget | None = None


# Corner buttons sit this far below the top of the badge row.
TRANSPORT_BUTTON_DROP_PX: int = 2
REC_BUTTON_TEXT: str = "REC"
# The flashing red REC fill stops this far short of its badge's top and bottom.
REC_FILL_INSET_Y_PX: int = 2


def rec_fill_rect(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """*rect* inset top and bottom by ``REC_FILL_INSET_Y_PX``."""
    x, y, w, h = rect
    inset = min(REC_FILL_INSET_Y_PX, max(0, (h - 1) // 2))
    return (x, y + inset, w, h - inset * 2)


def transport_button_rects(
    *,
    padding: int,
    layer_num_width: int,
    bar_left: int,
    corner_h: int,
    gap: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Play and record button rects in the corner above the row labels.

    Play sits over the layer number column. Record starts at the stem
    abbreviation, the column that lights when a row is armed, and runs to
    the start of the ruler, over the monitor eye. It holds the record glyph
    plus ``REC``. Rects are in upload coordinates (top of the badge row is
    y=0).
    """
    y = TRANSPORT_BUTTON_DROP_PX
    h = max(1, corner_h - gap)
    play = (padding, y, layer_num_width, h)
    record_x = padding + layer_num_width
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
    """Width of the row label prefix (num, abbrev, monitor eye slot)."""
    eye_slot_w = visibility_icon_slot_width(row_height)
    return layer_num_width + stem_abbrev_width + eye_slot_w


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
    bar_left: int
    bar_width: int
    eye_slot_w: int
    timeline_eye_x: int
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
        self._header_badge_rect: tuple[int, int, int, int] | None = None
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
    def header_badge_rect(self) -> tuple[int, int, int, int] | None:
        return self._header_badge_rect

    @property
    def bar_layout(self) -> tuple[int, int, int] | None:
        """Last draw bar metrics: ``(bar_left, bar_width, eye_slot_w)`` in panel coordinates."""
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
        tolerance = CUE_HIT_PX * self.view_sec_per_px()
        in_bar = layout.bar_left <= local_x < layout.bar_left + layout.bar_width
        t_sec = (
            x_to_time(
                local_x, layout.bar_left, layout.bar_width, view_start, view_end
            )
            if in_bar
            else None
        )
        if -layout.badge_reserve <= local_y < layout.bar_top:
            upload_y = local_y + layout.badge_reserve
            for target, rect in zip(
                ("play", "record"), self._transport_rects(layout), strict=True
            ):
                if pygame.Rect(rect).collidepoint(local_x, upload_y):
                    return StripHit(
                        row=None, t_sec=None, cue_tolerance_sec=tolerance, target=target
                    )
            return StripHit(row=None, t_sec=t_sec, cue_tolerance_sec=tolerance)
        # The scrollbar takes the gap above it and the padding below, so the
        # thin track is an easy target.
        if in_bar and layout.bar_bottom <= local_y < layout.panel_h:
            thumb_x, thumb_w = self._thumb_span(layout)
            on_thumb = thumb_x <= local_x - layout.bar_left < thumb_x + thumb_w
            return StripHit(
                row=None,
                t_sec=self.scrollbar_time_at_x(x),
                cue_tolerance_sec=tolerance,
                target="scroll_thumb" if on_thumb else "scroll_track",
            )
        label_left = self._padding
        label_right = label_left + layout.layer_num_width + layout.stem_abbrev_width
        on_label = label_left <= local_x < label_right
        eye_right = label_right + visibility_icon_slot_width(layout.row_h)
        on_eye = label_right <= local_x < eye_right
        for display_i in range(layout.row_count):
            row_y = self._row_y(display_i, layout.row_h)
            if row_y <= local_y < row_y + layout.row_h:
                return StripHit(
                    row=display_i,
                    t_sec=t_sec,
                    cue_tolerance_sec=tolerance,
                    target="label" if on_label else "eye" if on_eye else None,
                )
        return None

    def _transport_rects(
        self, layout: _TimelineLayout
    ) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        return transport_button_rects(
            padding=self._padding,
            layer_num_width=layout.layer_num_width,
            bar_left=layout.bar_left,
            corner_h=layout.badge_reserve + layout.bar_top,
            gap=timeline_ui_metrics().rec_badge_gap,
        )

    @staticmethod
    def _transport_icon_size(layout: _TimelineLayout) -> int:
        """Glyph size: as tall as a row's level bar."""
        return max(1, layout.row_h - 2 * timeline_ui_metrics().bar_vertical_inset)

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
            # Flash in step with the REC badge: red fill with white glyph and
            # text, then a red glyph on no fill.
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
        row_h = metrics.row_height
        panel_h = timeline_panel_height_px(row_count)
        # The shell's timeline band is the container; the strip fills its width.
        if timeline_rect is None:
            timeline_rect = (0, 0, viewport_width, viewport_height)
        band_x, band_y, band_w, band_h = timeline_rect
        if band_w <= 0 or band_h <= 0:
            return None
        panel_w = band_w
        panel_x = band_x
        panel_y = band_y + band_h - panel_h
        badge_reserve = timeline_badge_reserve_px(
            font_size=self._font_size, padding=self._padding
        )

        font = self._font_get()
        num_sample = font.render(layer_num_prefix(max(row_count, 1)), True, LABEL)
        abbrev_sample = font.render(stem_abbrev_label("drums"), True, LABEL)
        layer_num_width = num_sample.get_width()
        stem_abbrev_width = abbrev_sample.get_width()
        eye_slot_w = visibility_icon_slot_width(row_h)
        prefix_width = row_prefix_width(layer_num_width, stem_abbrev_width, row_h)
        bar_left = self._padding + prefix_width
        bar_width = max(1, panel_w - self._padding * 2 - prefix_width - eye_slot_w)
        timeline_eye_x = panel_w - self._padding - eye_slot_w
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
        self._bar_layout = (bar_left, bar_width, eye_slot_w)

        return _TimelineLayout(
            panel_w=panel_w,
            panel_h=panel_h,
            panel_x=panel_x,
            panel_y=panel_y,
            row_count=row_count,
            row_h=row_h,
            bar_left=bar_left,
            bar_width=bar_width,
            eye_slot_w=eye_slot_w,
            timeline_eye_x=timeline_eye_x,
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
        timeline_eye_x = layout.timeline_eye_x

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
            monitor_eye_x = stem_abbrev_x + layout.stem_abbrev_width

            if focused:
                blit_tint(panel, row_rect, HIGHLIGHT, alpha=SELECTED_WASH_ALPHA)
            if state.hover_label_row == row_index:
                blit_tint(
                    panel,
                    (
                        layer_num_x,
                        row_y,
                        layout.layer_num_width + layout.stem_abbrev_width,
                        row_h,
                    ),
                    NUDGE_HOVER_BG,
                    alpha=NUDGE_HOVER_BG_ALPHA,
                )

            abbrev_rect = pygame.Rect(
                stem_abbrev_x, row_y, layout.stem_abbrev_width, row_h
            )
            # Armed abbrev background and recording monitor flash are live-patched.

            # Shell hover: nudge wash behind, nudge foreground on the label.
            if state.hover_label_row == row_index:
                label_color = NUDGE_HOVER_FG
            elif focused or armed:
                label_color = HIGHLIGHT
            else:
                label_color = LABEL
            num_surf = font.render(layer_num_prefix(layer_num), True, label_color)
            abbrev_surf = font.render(stem_abbrev_label(stem_source), True, label_color)
            num_y = row_y + max(0, (row_h - num_surf.get_height()) // 2)
            abbrev_y = row_y + max(0, (row_h - abbrev_surf.get_height()) // 2)
            panel.blit(num_surf, (layer_num_x, num_y))
            panel.blit(abbrev_surf, (stem_abbrev_x, abbrev_y))

            monitor_enabled = state.monitor_visible.get(slot, True)
            timeline_level = float(state.timeline_level.get(slot, 1.0))
            monitor_override = (
                slot in state.override_slots
                and not (state.recording and armed)
            )
            if not (state.recording and armed):
                monitor_icon = render_visibility_icon(
                    enabled=monitor_enabled,
                    override=monitor_override,
                    line_height=row_h,
                )
                panel.blit(monitor_icon, (monitor_eye_x, row_y))
            timeline_icon = _render_committed_level_icon(
                timeline_level, line_height=row_h
            )
            panel.blit(timeline_icon, (timeline_eye_x, row_y))

            _draw_level_bar(
                panel,
                breakpoints=bar_level_breakpoints_for_row(state, slot),
                bar_left=bar_left,
                bar_width=bar_width,
                view_start_sec=view_start,
                view_end_sec=view_end,
                bar_rect=bar_rect,
            )

            row_cues = bar_cues_for_row(state, slot)
            # Per-slot selection memory stays in selected_cue_t; only the focused
            # row draws the selected marker (settled yellow / flash / badge).
            selected_t = (
                state.selected_cue_t.get(slot)
                if row_index == state.focus_row
                else None
            )
            for cue in row_cues:
                if not time_in_view(cue.t, view_start, view_end):
                    continue
                tick_x = time_to_x(cue.t, bar_left, bar_width, view_start, view_end)
                selected = selected_t is not None and cue.t == selected_t
                if selected:
                    pygame.draw.line(
                        panel,
                        SELECTED_CUE_COLOR,
                        (tick_x, row_y),
                        (tick_x, row_y + row_h - 1),
                        SELECTED_CUE_TICK_WIDTH,
                    )
                else:
                    pygame.draw.line(
                        panel,
                        (*LABEL, CUE_TICK_ALPHA),
                        (tick_x, bar_rect.y),
                        (tick_x, bar_rect.bottom - 1),
                        CUE_TICK_WIDTH,
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

        for marker_i, marker_t in enumerate(state.song_marker_times):
            if not time_in_view(marker_t, view_start, view_end):
                continue
            marker_x = time_to_x(marker_t, bar_left, bar_width, view_start, view_end)
            selected = marker_i == state.selected_song_marker_index
            pygame.draw.line(
                panel,
                SONG_MARKER_SELECTED if selected else SONG_MARKER,
                (marker_x, layout.bar_top),
                (marker_x, layout.bar_bottom - 1),
                4 if selected else 2,
            )

        self._draw_scrollbar(panel, state, layout)
        return panel

    def _draw_scrollbar(
        self,
        panel: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
    ) -> None:
        """Track under the rows; the thumb is the visible share of the song."""
        track_x, track_y, track_w, track_h = layout.scrollbar_rect
        if track_w <= 0 or track_h <= 0:
            return
        view_start, view_end = view_window(state)
        pygame.draw.rect(panel, SCROLLBAR_TRACK, layout.scrollbar_rect)
        thumb_x, thumb_w = scrollbar_thumb_span(
            track_w,
            view_start,
            view_end,
            state.duration_sec,
            min_thumb=timeline_ui_metrics().scrollbar_min_thumb,
        )
        pygame.draw.rect(
            panel, SCROLLBAR_THUMB, (track_x + thumb_x, track_y, thumb_w, track_h)
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
        stem_abbrev_x = self._padding + layout.layer_num_width
        monitor_eye_x = stem_abbrev_x + layout.stem_abbrev_width
        eye_slot_w = visibility_icon_slot_width(row_h)
        dirty: list[tuple[int, int, int, int]] = []

        abbrev_rect = (stem_abbrev_x, upload_y, layout.stem_abbrev_width, row_h)
        self._restore_upload_rect_from_static(
            upload,
            static_panel,
            abbrev_rect,
            panel_y_offset=panel_y_offset,
        )
        if armed_abbrev_bg_visible(
            armed=armed,
            recording=state.recording,
            flash_starts=state.arm_flash_start_ms,
            slot=slot,
        ):
            armed_surf = pygame.Surface(
                (layout.stem_abbrev_width, row_h), pygame.SRCALPHA
            )
            armed_surf.fill((*ARMED_BG, ARMED_BG_ALPHA))
            upload.blit(armed_surf, (stem_abbrev_x, upload_y))
            # Red fill is live-patched over the static glyph; redraw so it stays readable.
            stem_source = state.slot_stems.get(slot, slot)
            abbrev_surf = self._font_get().render(
                stem_abbrev_label(stem_source), True, HIGHLIGHT
            )
            abbrev_y = upload_y + max(0, (row_h - abbrev_surf.get_height()) // 2)
            upload.blit(abbrev_surf, (stem_abbrev_x, abbrev_y))
        dirty.append(abbrev_rect)

        monitor_rect = (monitor_eye_x, upload_y, eye_slot_w, row_h)
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
            line_height=row_h,
        )
        upload.blit(monitor_icon, (monitor_eye_x, upload_y))
        dirty.append(monitor_rect)

        selected_t = (
            state.selected_cue_t.get(slot) if row_index == state.focus_row else None
        )
        view_start, view_end = view_window(state)
        if (
            selected_t is not None
            and time_in_view(selected_t, view_start, view_end)
            and selected_cue_flash_active(state.selected_cue_flash_start_ms)
        ):
            tick_x = time_to_x(
                selected_t, layout.bar_left, layout.bar_width, view_start, view_end
            )
            half_w = SELECTED_CUE_FLASH_TICK_WIDTH // 2 + 1
            tick_rect = (
                max(layout.bar_left, tick_x - half_w),
                upload_y,
                min(layout.bar_width, half_w * 2 + 1),
                row_h,
            )
            # Clamp width if tick sits near the bar edge.
            tick_rect = (
                tick_rect[0],
                tick_rect[1],
                min(tick_rect[2], layout.bar_left + layout.bar_width - tick_rect[0]),
                tick_rect[3],
            )
            if tick_rect[2] > 0:
                self._restore_upload_rect_from_static(
                    upload,
                    static_panel,
                    tick_rect,
                    panel_y_offset=panel_y_offset,
                )
                pygame.draw.line(
                    upload,
                    selected_cue_tick_color(state.selected_cue_flash_start_ms),
                    (tick_x, upload_y),
                    (tick_x, upload_y + row_h - 1),
                    SELECTED_CUE_FLASH_TICK_WIDTH,
                )
                dirty.append(tick_rect)
        return dirty

    def _live_flash_row_indices(self, state: TimelineViewState) -> tuple[int, ...]:
        indices: list[int] = []
        cue_flash = selected_cue_flash_active(state.selected_cue_flash_start_ms)
        for row_index, slot in enumerate(state.layer_z_order):
            armed = slot in state.armed_slots
            if arm_abbrev_flash_active(state.arm_flash_start_ms, slot):
                indices.append(row_index)
            elif state.recording and armed:
                indices.append(row_index)
            elif armed and not state.recording:
                indices.append(row_index)
            elif (
                cue_flash
                and row_index == state.focus_row
                and slot in state.selected_cue_t
            ):
                indices.append(row_index)
        return tuple(indices)

    def _live_flash_signature(self, state: TimelineViewState) -> tuple:
        parts: list[tuple] = []
        cue_flash_bright = (
            selected_cue_flash_bright(state.selected_cue_flash_start_ms)
            if selected_cue_flash_active(state.selected_cue_flash_start_ms)
            else None
        )
        for row_index in self._live_flash_row_indices(state):
            slot = state.layer_z_order[row_index]
            armed = slot in state.armed_slots
            parts.append(
                (
                    slot,
                    armed_abbrev_bg_visible(
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
                        state.selected_cue_t.get(slot)
                        if cue_flash_bright is not None
                        and row_index == state.focus_row
                        else None
                    ),
                    (
                        cue_flash_bright
                        if row_index == state.focus_row and slot in state.selected_cue_t
                        else None
                    ),
                )
            )
        return tuple(parts)

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

    def _draw_header_badges_on_surface(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        layout: _TimelineLayout,
        recording: bool,
        *,
        y_offset: int = 0,
    ) -> tuple[int, int, int, int] | None:
        """REC badge on the right, above the strip.

        It starts where the ruler ends and runs to the strip's right edge,
        over the committed-level icon column; the text is centred.
        """
        metrics = timeline_ui_metrics()
        pad_y = metrics.rec_badge_pad_y
        badge_y = y_offset
        badge_h = font.get_height() + pad_y * 2
        rects: list[tuple[int, int, int, int]] = []

        if recording:
            rec_surf = font.render(REC_BUTTON_TEXT, True, VALUE)
            rec_x = layout.bar_left + layout.bar_width
            rec_w = max(1, layout.panel_w - rec_x)
            if rec_flash_visible():
                pygame.draw.rect(
                    surface, REC_BG, rec_fill_rect((rec_x, badge_y, rec_w, badge_h))
                )
            surface.blit(
                rec_surf,
                (rec_x + (rec_w - rec_surf.get_width()) // 2, badge_y + pad_y),
            )
            rects.append((rec_x, badge_y, rec_w, badge_h))

        if not rects:
            return None
        left = min(r[0] for r in rects)
        right = max(r[0] + r[2] for r in rects)
        return (left, badge_y, right - left, badge_h)

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
        font = self._font_get()

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

        # The REC badge sits level with the corner buttons, the same drop
        # below the top of the band, over the strip's top padding.
        badge_top = TRANSPORT_BUTTON_DROP_PX
        if incremental and cache.last_badge_rect is not None:
            upload.fill((0, 0, 0, 0), cache.last_badge_rect)
            self._restore_upload_rect_from_static(
                upload,
                static_panel,
                cache.last_badge_rect,
                panel_y_offset=panel_y_offset,
            )
            if self._ruler is not None:
                bx, by, bw, bh = cache.last_badge_rect
                upload.blit(self._ruler, (bx, by), (bx, by, bw, bh))

        badge_rect = self._draw_header_badges_on_surface(
            upload,
            font,
            layout,
            state.recording,
            y_offset=badge_top,
        )
        cache.last_badge_rect = badge_rect

        flash_dirty: list[tuple[int, int, int, int]] = []
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
        self._header_badge_rect = None
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
            cache.last_badge_rect = None
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
        prev_badge = cache.last_badge_rect
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
        sx, sy, sw, sh = screen_bounds
        panel_screen_y = layout.panel_y
        self._panel_rect = clip_rect_to_bounds(
            (layout.panel_x, panel_screen_y, panel_w, panel_h),
            viewport_width,
            viewport_height,
        )
        badge_screen_y = panel_screen_y - layout.badge_reserve
        badge_local = cache.last_badge_rect
        if badge_local is not None:
            bx, by, bw, bh = badge_local
            self._header_badge_rect = clip_rect_to_bounds(
                (layout.panel_x + bx, badge_screen_y + by, bw, bh),
                viewport_width,
                viewport_height,
            )

        capacity = timeline_panel_max_dimensions(viewport_width)
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
                prev_badge,
                cache.last_badge_rect,
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
            self._header_badge_rect = None
            self._bar_layout = None
            self._row_layout = []
            return
        sx, sy, sw, sh = composed.screen_rect
        src_x, src_y = self._blit_src
        surface.blit(composed.upload_surface, (sx, sy), (src_x, src_y, sw, sh))
