"""Bottom timeline strip overlay for per-stem layer visibility cues."""

from __future__ import annotations

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
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.overlay_primitives import (
    ComposedPanel,
    clip_rect_to_bounds,
    draw_panel_border,
    overlay_font,
    overlay_panel_surface,
)
from cleave.viz.overlay_upload import (
    clip_dirty_rects,
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
from cleave.viz.playback import format_mmss
from cleave.viz.theme import (
    ARMED_BG,
    BACKGROUND,
    BAR_GRID,
    HIGHLIGHT,
    LABEL,
    PLAYHEAD,
    PLAYHEAD_FLASH,
    REC_BG,
    SONG_MARKER,
    SONG_MARKER_SELECTED,
    TIMELINE_BAR_ON,
    VALUE,
    timeline_panel_height_px,
    timeline_ui_metrics,
)
from cleave.viz.ui_tint import blit_tint

_timeline_ui = timeline_ui_metrics()
TIMELINE_PANEL_GAP: int = _timeline_ui.panel_gap
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


def timeline_viewport_reserve_px(row_count: int, *, margin: int | None = None) -> int:
    metrics = timeline_ui_metrics()
    if margin is None:
        margin = metrics.margin
    panel_h = timeline_panel_height_px(row_count)
    return panel_h + margin + metrics.panel_gap


BAR_VERTICAL_INSET: int = _timeline_ui.bar_vertical_inset
ARMED_BG_ALPHA: int = 220
CUE_TICK_ALPHA: int = 120
CUE_TICK_WIDTH: int = 1
# Settled selected tick (thinner than flash; still thicker than a normal cue tick).
SELECTED_CUE_TICK_WIDTH: int = 3
# Thick width while the selection flash is active.
SELECTED_CUE_FLASH_TICK_WIDTH: int = 7
PLAYHEAD_WIDTH: int = _timeline_ui.playhead_width
REC_BADGE_GAP: int = _timeline_ui.rec_badge_gap
REC_BADGE_PAD_X: int = _timeline_ui.rec_badge_pad_x
REC_BADGE_PAD_Y: int = _timeline_ui.rec_badge_pad_y
REC_TIME_GAP: int = _timeline_ui.rec_time_gap
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


def selected_cue_readout_segments(
    cue: SlotCue,
    *,
    show_role: bool = False,
) -> list[tuple[str, tuple[int, int, int]]]:
    """Label/value segments for the selected-cue badge readout."""
    cut = cue.cut if cue.cut is not None else "none"
    segments: list[tuple[str, tuple[int, int, int]]] = [
        (f"[{format_mmss(cue.t)}] ", VALUE),
    ]
    if float(cue.level) <= LEVEL_EPS:
        segments.extend(
            [
                ("cut: ", LABEL),
                (str(cut), VALUE),
            ]
        )
        return segments
    blend = cue.blend if cue.blend is not None else "-"
    opacity_pct = int(round(float(cue.level) * 100.0))
    segments.extend(
        [
            ("opacity: ", LABEL),
            (f"{opacity_pct}% ", VALUE),
            ("cut: ", LABEL),
            (f"{cut} ", VALUE),
            ("blend: ", LABEL),
            (f"{blend}" if not show_role else f"{blend} ", VALUE),
        ]
    )
    if show_role:
        role = cue.role if cue.role is not None else "-"
        segments.extend(
            [
                ("role: ", LABEL),
                (str(role), VALUE),
            ]
        )
    return segments


def selected_cue_readout_text(cue: SlotCue, *, show_role: bool = False) -> str:
    """Plain-text form of the selected-cue badge readout."""
    return "".join(
        text for text, _ in selected_cue_readout_segments(cue, show_role=show_role)
    )


def render_selected_cue_readout(
    font: pygame.font.Font, cue: SlotCue, *, show_role: bool = False
) -> pygame.Surface:
    """Badge-strip surface: LABEL prefixes, VALUE for time and field values."""
    surfs = [
        font.render(text, True, color)
        for text, color in selected_cue_readout_segments(cue, show_role=show_role)
    ]
    width = sum(surf.get_width() for surf in surfs)
    height = max((surf.get_height() for surf in surfs), default=0)
    out = pygame.Surface((width, height), pygame.SRCALPHA)
    x = 0
    for surf in surfs:
        out.blit(surf, (x, 0))
        x += surf.get_width()
    return out


def _selected_cue_for_focus(state: TimelineViewState) -> SlotCue | None:
    if not state.layer_z_order:
        return None
    focus = state.focus_row
    if focus < 0 or focus >= len(state.layer_z_order):
        return None
    slot = state.layer_z_order[focus]
    selected_t = state.selected_cue_t.get(slot)
    if selected_t is None:
        return None
    for cue in bar_cues_for_row(state, slot):
        if cue.t == selected_t:
            return cue
    lane = _lane_for_view(state, slot)
    for cue in lane.cues:
        if cue.t == selected_t:
            return cue
    return None


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
    duration_sec: float,
    bar_rect: pygame.Rect,
) -> None:
    pygame.draw.rect(panel, OFF_SEGMENT_COLOR, bar_rect)
    if duration_sec <= 0.0 or len(breakpoints) < 2:
        return
    bottom = bar_rect.bottom
    for index in range(len(breakpoints) - 1):
        t0, level0 = breakpoints[index]
        t1, level1 = breakpoints[index + 1]
        if t1 <= t0:
            continue
        x0 = time_to_x(t0, bar_left, bar_width, duration_sec)
        x1 = time_to_x(t1, bar_left, bar_width, duration_sec)
        if x1 <= x0:
            continue
        if level0 <= LEVEL_EPS and level1 <= LEVEL_EPS:
            continue
        y0 = bar_level_y(bar_rect, level0)
        y1 = bar_level_y(bar_rect, level1)
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


def time_to_x(t_sec: float, bar_left: int, bar_width: int, duration_sec: float) -> int:
    if duration_sec <= 0:
        return bar_left
    ratio = max(0.0, min(1.0, t_sec / duration_sec))
    return bar_left + int(ratio * bar_width)


def playhead_x(
    position_sec: float,
    bar_left: int,
    bar_width: int,
    duration_sec: float,
) -> int:
    return time_to_x(position_sec, bar_left, bar_width, duration_sec)


def layer_num_prefix(layer_num: int) -> str:
    return f" {layer_num} "


def stem_abbrev_label(stem: str) -> str:
    return f" {stem_abbreviation(stem)} "


def transport_time_text(position_sec: float) -> str:
    return f"[{format_mmss(position_sec)}]"


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
    playhead_px: int,
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
        transport_time_text(state.position_sec),
        rec_flash,
        playhead_flash_bright(ticks_ms),
        flash_sig,
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


class TimelineOverlay:
    """Bottom-anchored timeline panel drawn over the composited frame."""

    def __init__(
        self,
        *,
        margin: int | None = None,
        font_size: int | None = None,
        padding: int | None = None,
        row_gap: int | None = None,
    ) -> None:
        metrics = timeline_ui_metrics()
        if margin is None:
            margin = metrics.margin
        if font_size is None:
            font_size = metrics.font_size
        if padding is None:
            padding = metrics.padding
        if row_gap is None:
            row_gap = metrics.row_gap
        self._margin = margin
        self._font_size = font_size
        self._padding = padding
        self._row_gap = row_gap
        self._panel_rect: tuple[int, int, int, int] | None = None
        self._header_badge_rect: tuple[int, int, int, int] | None = None
        self._layer_num_width: int = 0
        self._stem_abbrev_width: int = 0
        self._bar_layout: tuple[int, int, int] | None = None
        self._row_layout: list[tuple[int, int, int, int, str, int]] = []
        self._cache = TimelinePanelCache()
        self._visibility = 1.0
        self._upload_scratch: pygame.Surface | None = None
        self._blit_src: tuple[int, int] = (0, 0)

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

    def _compute_layout(
        self,
        state: TimelineViewState,
        *,
        viewport_width: int,
        viewport_height: int,
    ) -> _TimelineLayout | None:
        row_count = len(state.layer_z_order)
        if row_count == 0:
            return None

        metrics = timeline_ui_metrics()
        row_h = metrics.row_height
        panel_w = viewport_width - self._margin * 2
        panel_h = timeline_panel_height_px(row_count)
        panel_x = self._margin
        panel_y = viewport_height - panel_h - self._margin
        badge_reserve = timeline_badge_reserve_px(font_size=self._font_size)

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

        panel = overlay_panel_surface((panel_w, panel_h))
        font = self._font_get()
        self._row_layout = []

        if state.show_bar_grid and state.bar_grid_times:
            for t in state.bar_grid_times:
                grid_x = time_to_x(t, bar_left, bar_width, state.duration_sec)
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
                row_y + BAR_VERTICAL_INSET,
                bar_width,
                max(1, row_h - BAR_VERTICAL_INSET * 2),
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
                blit_tint(panel, row_rect, HIGHLIGHT)

            abbrev_rect = pygame.Rect(
                stem_abbrev_x, row_y, layout.stem_abbrev_width, row_h
            )
            # Armed abbrev background and recording monitor flash are live-patched.

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

            bar_column_rect = pygame.Rect(bar_left, row_y, bar_width, row_h)
            if focused:
                blit_tint(panel, bar_column_rect, HIGHLIGHT)

            _draw_level_bar(
                panel,
                breakpoints=bar_level_breakpoints_for_row(state, slot),
                bar_left=bar_left,
                bar_width=bar_width,
                duration_sec=state.duration_sec,
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
                tick_x = time_to_x(cue.t, bar_left, bar_width, state.duration_sec)
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

            if focused and BAR_VERTICAL_INSET > 0:
                blit_tint(
                    panel,
                    pygame.Rect(bar_left, row_y, bar_width, BAR_VERTICAL_INSET),
                    HIGHLIGHT,
                )
                blit_tint(
                    panel,
                    pygame.Rect(
                        bar_left,
                        bar_rect.bottom,
                        bar_width,
                        BAR_VERTICAL_INSET,
                    ),
                    HIGHLIGHT,
                )

        for marker_i, marker_t in enumerate(state.song_marker_times):
            marker_x = time_to_x(marker_t, bar_left, bar_width, state.duration_sec)
            selected = marker_i == state.selected_song_marker_index
            pygame.draw.line(
                panel,
                SONG_MARKER_SELECTED if selected else SONG_MARKER,
                (marker_x, layout.bar_top),
                (marker_x, layout.bar_bottom - 1),
                4 if selected else 2,
            )

        draw_panel_border(panel)
        return panel

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
        for display_i, slot in enumerate(state.layer_z_order):
            row_y = self._row_y(display_i, row_h)
            bar_rect = pygame.Rect(
                layout.bar_left,
                row_y + BAR_VERTICAL_INSET,
                layout.bar_width,
                max(1, row_h - BAR_VERTICAL_INSET * 2),
            )
            for cue in bar_cues_for_row(state, slot):
                if cue.role is None or cue.level <= LEVEL_EPS:
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
                    cue.t, layout.bar_left, layout.bar_width, state.duration_sec
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
        if panel_y < 0 or panel_y >= static_panel.get_height():
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
        if selected_t is not None and selected_cue_flash_active(
            state.selected_cue_flash_start_ms
        ):
            tick_x = time_to_x(
                selected_t, layout.bar_left, layout.bar_width, state.duration_sec
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
        x = playhead_left - max(1, PLAYHEAD_WIDTH)
        y = y_offset + layout.bar_top
        w = max(1, PLAYHEAD_WIDTH) * 2 + 1
        h = layout.bar_bottom - layout.bar_top
        return (x, y, w, h)

    def _draw_playhead(
        self,
        surface: pygame.Surface,
        layout: _TimelineLayout,
        playhead_px: int,
        *,
        y_offset: int,
    ) -> tuple[int, int, int, int]:
        playhead_left = max(
            layout.bar_left,
            min(layout.bar_left + layout.bar_width - 1, playhead_px),
        )
        y0 = y_offset + layout.bar_top
        y1 = y_offset + layout.bar_bottom - 1
        pygame.draw.line(
            surface,
            playhead_color(),
            (playhead_left, y0),
            (playhead_left, y1),
            PLAYHEAD_WIDTH,
        )
        return self._playhead_strip_rect(layout, playhead_px, y_offset=y_offset)

    def _draw_header_badges_on_surface(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        panel_w: int,
        position_sec: float,
        recording: bool,
        *,
        y_offset: int = 0,
        cue_readout: pygame.Surface | None = None,
    ) -> tuple[int, int, int, int]:
        time_surf = font.render(transport_time_text(position_sec), True, VALUE)
        time_w = time_surf.get_width() + REC_BADGE_PAD_X * 2
        time_h = time_surf.get_height() + REC_BADGE_PAD_Y * 2

        rec_w = 0
        rec_surf: pygame.Surface | None = None
        if recording:
            rec_surf = font.render("REC", True, VALUE)
            rec_w = rec_surf.get_width() + REC_BADGE_PAD_X * 2

        badge_h = time_h
        gap = REC_TIME_GAP if recording else 0
        right_w = time_w + gap + rec_w
        time_x = panel_w - time_w
        badge_y = y_offset

        readout_w = 0
        if cue_readout is not None:
            readout_w = cue_readout.get_width() + REC_BADGE_PAD_X * 2
            pygame.draw.rect(
                surface, BACKGROUND, (0, badge_y, readout_w, badge_h)
            )
            surface.blit(
                cue_readout,
                (REC_BADGE_PAD_X, badge_y + REC_BADGE_PAD_Y),
            )

        pygame.draw.rect(surface, BACKGROUND, (time_x, badge_y, time_w, badge_h))
        surface.blit(
            time_surf,
            (time_x + REC_BADGE_PAD_X, badge_y + REC_BADGE_PAD_Y),
        )

        header_x = time_x
        if recording and rec_surf is not None:
            rec_x = time_x - gap - rec_w
            header_x = rec_x
            if rec_flash_visible():
                pygame.draw.rect(surface, REC_BG, (rec_x, badge_y, rec_w, badge_h))
            surface.blit(
                rec_surf,
                (rec_x + REC_BADGE_PAD_X, badge_y + REC_BADGE_PAD_Y),
            )

        if readout_w > 0:
            return (0, badge_y, panel_w, badge_h)
        return (header_x, badge_y, right_w, badge_h)

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
        playhead_px: int,
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

        playhead_rect = self._draw_playhead(
            upload,
            layout,
            playhead_px,
            y_offset=panel_y_offset,
        )
        cache.last_playhead_rect = playhead_rect

        badge_top = panel_y_offset - layout.badge_reserve
        if incremental and cache.last_badge_rect is not None:
            bx, by, bw, bh = cache.last_badge_rect
            upload.fill((0, 0, 0, 0), (bx, by, bw, bh))

        selected_cue = _selected_cue_for_focus(state)
        focused_slot = (
            state.layer_z_order[state.focus_row]
            if 0 <= state.focus_row < len(state.layer_z_order)
            else None
        )
        show_role = focused_slot is not None
        cue_readout = (
            render_selected_cue_readout(font, selected_cue, show_role=show_role)
            if selected_cue is not None
            else None
        )
        badge_rect = self._draw_header_badges_on_surface(
            upload,
            font,
            layout.panel_w,
            state.position_sec,
            state.recording,
            y_offset=badge_top,
            cue_readout=cue_readout,
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
    ) -> ComposedPanel | None:
        self._visibility = visibility
        self._panel_rect = None
        self._header_badge_rect = None
        if visibility <= 0.01:
            return None

        layout = self._compute_layout(
            state,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
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

        playhead_px = playhead_x(
            state.position_sec,
            layout.bar_left,
            layout.bar_width,
            state.duration_sec,
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

        capacity = timeline_panel_max_dimensions(
            viewport_width,
            viewport_height,
            margin=self._margin,
        )
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
                else ()
            )
            if clip_rect:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
                    dirty_rects=clip_dirty_rects(clip_rect, upload_w, upload_h),
                )
            else:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
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
    ) -> None:
        composed = self.compose_panel(
            state,
            viewport_width=surface.get_width(),
            viewport_height=surface.get_height(),
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
