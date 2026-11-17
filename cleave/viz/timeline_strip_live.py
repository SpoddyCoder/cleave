"""Timeline strip live layer, patched over the cached static panel each frame.

Song markers, the transport buttons, the playhead, per-row flashes (arm, the
recording eye, the selected clip) and the XOR role glyphs. Each draw returns
the rects it touched so the next frame can restore them from ``StaticLayers``
and the upload can send only what changed.
"""

from __future__ import annotations

from typing import Literal

import pygame

from cleave.cue_roles import CueRole
from cleave.timeline import LEVEL_EPS, TimelineLane, lane_level_at
from cleave.viz.material_icons import (
    PAUSE_GLYPH,
    PLAY_GLYPH,
    RECORD_GLYPH,
    material_font,
)
from cleave.viz.row_present_renderers import (
    render_header_toggle,
    render_visibility_icon,
)
from cleave.viz.theme import palette, timeline_ui_metrics
from cleave.viz.timeline_panel_cache import TimelinePanelCache
from cleave.viz.timeline_strip_flash import (
    arm_button_lit,
    arm_flash_active,
    playhead_color,
    playhead_flash_bright,
    rec_flash_visible,
    selected_clip_flash_active,
    selected_clip_flash_bright,
    selected_clip_flash_color,
)
from cleave.viz.timeline_strip_layout import (
    StripLayout,
    clip_bar_span,
    time_in_view,
    time_to_x,
)
from cleave.viz.timeline_strip_state import (
    TimelineViewState,
    bar_cues_for_row,
    glyph_lane_for_cue,
    row_clips_for_view,
    view_window,
)
from cleave.viz.timeline_strip_static import StaticLayers
from cleave.viz.ui_tint import blit_hover

Rect = tuple[int, int, int, int]

ARMED_BG_ALPHA: int = 220
SELECTED_CLIP_FLASH_OUTLINE_WIDTH: int = 3
# Thick width of a selected song marker while its flash is active.
SELECTED_CLIP_FLASH_TICK_WIDTH: int = 7
# Clear half the flash tick plus 1px so glyphs sit beside the thick marker.
ROLE_GLYPH_TICK_GAP: int = SELECTED_CLIP_FLASH_TICK_WIDTH // 2 + 1
ROLE_GLYPH_BOTTOM_PAD: int = 1
# Song markers span the ruler and every row. The selected one flashes like a
# selected cue (SELECTED_CLIP_FLASH_TICK_WIDTH), then settles at its own width.
SONG_MARKER_WIDTH: int = 3
SONG_MARKER_SELECTED_WIDTH: int = 5
_ROLE_GLYPH: dict[CueRole, str] = {
    "bed": "B",
    "pulse": "P",
    "lead": "L",
    "accent": "A",
}
REC_BUTTON_TEXT: str = "REC"
# The flashing red REC fill stops this far short of the button's top and bottom.
REC_FILL_INSET_Y_PX: int = 2


def rec_fill_rect(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """*rect* inset top and bottom by ``REC_FILL_INSET_Y_PX``."""
    x, y, w, h = rect
    inset = min(REC_FILL_INSET_Y_PX, max(0, (h - 1) // 2))
    return (x, y + inset, w, h - inset * 2)


def transport_live_signature(state: TimelineViewState, ticks_ms: int) -> tuple:
    return (
        state.paused,
        state.locked,
        state.hover_button,
        bool(state.armed_slots),
        rec_flash_visible(ticks_ms) if state.recording else None,
    )


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


def patch_live_overlay(
    upload: pygame.Surface,
    static: StaticLayers,
    state: TimelineViewState,
    layout: StripLayout,
    cache: TimelinePanelCache,
    *,
    playhead_px: int | None,
    incremental: bool,
    font: pygame.font.Font,
    bold_font: pygame.font.Font,
) -> list[Rect]:
    """Draw the live layer over the static layers on *upload*.

    With *incremental*, the upload still holds last frame's live layer, and
    the rects recorded in *cache* are restored first. Records this frame's
    rects in *cache* and returns the flash and glyph rects drawn.
    """
    y_offset = static.panel_y_offset

    if incremental:
        # Put back what the last live pass drew before drawing again: the
        # transport tint and role glyphs (XOR) do not survive being drawn twice.
        for rect in (
            cache.last_playhead_rect,
            cache.last_transport_rect,
            *cache.last_flash_rects,
            *cache.last_glyph_rects,
        ):
            if rect is not None:
                static.restore(upload, rect)

    # Markers after the playhead restore (which repaints that column from
    # the static panel) and before the playhead, which stays on top.
    marker_flash_rect = _draw_song_markers(upload, state, layout, y_offset=y_offset)

    # Corner buttons before the playhead, so a red record fill that ends
    # at the ruler never covers the playhead at the song start.
    cache.last_transport_rect = _draw_transport_buttons(upload, state, layout, font)
    cache.last_playhead_rect = _draw_playhead(
        upload, layout, playhead_px, y_offset=y_offset
    )

    flash_dirty: list[Rect] = []
    if marker_flash_rect is not None:
        flash_dirty.append(marker_flash_rect)
    for row_index in live_flash_row_indices(state):
        flash_dirty.extend(
            _draw_row_live_flash(upload, static, state, layout, row_index=row_index)
        )
    cache.last_flash_rects = tuple(flash_dirty)

    # Role glyphs last (after playhead / flash) so XOR letters sit on top.
    glyph_dirty = _draw_role_glyphs(
        upload, state, layout, bold_font, y_offset=y_offset
    )
    cache.last_glyph_rects = tuple(glyph_dirty)
    flash_dirty.extend(glyph_dirty)
    return flash_dirty


def live_flash_row_indices(state: TimelineViewState) -> tuple[int, ...]:
    """Rows whose header or selected clip draws in the live layer this frame."""
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


def _monitor_eye_override(state: TimelineViewState, slot: str) -> bool:
    """The row eye draws yellow: an override, or an armed row's REC blink."""
    armed = slot in state.armed_slots
    return (slot in state.override_slots and not (state.recording and armed)) or (
        state.recording and armed and rec_flash_visible()
    )


def live_flash_signature(state: TimelineViewState) -> tuple:
    """What the per-row flashes and the selected song marker look like now."""
    parts: list[tuple] = []
    cue_flash_bright = (
        selected_clip_flash_bright(state.selected_clip_flash_start_ms)
        if selected_clip_flash_active(state.selected_clip_flash_start_ms)
        else None
    )
    for row_index in live_flash_row_indices(state):
        slot = state.layer_z_order[row_index]
        parts.append(
            (
                slot,
                arm_button_lit(
                    armed=slot in state.armed_slots,
                    recording=state.recording,
                    flash_starts=state.arm_flash_start_ms,
                    slot=slot,
                ),
                _monitor_eye_override(state, slot),
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


def _draw_transport_buttons(
    surface: pygame.Surface,
    state: TimelineViewState,
    layout: StripLayout,
    font: pygame.font.Font,
) -> Rect:
    """Play/pause and record glyphs in the corner (upload coordinates)."""
    play_rect, record_rect = layout.transport_rects()
    rec_text_color = palette().value
    if state.recording:
        # Flash: red fill with white glyph and text, then a red glyph on
        # no fill.
        if rec_flash_visible():
            pygame.draw.rect(surface, palette().rec_bg, rec_fill_rect(record_rect))
            record_color = palette().value
        else:
            record_color = palette().rec_bg
    elif state.locked:
        record_color = palette().muted
    elif state.armed_slots:
        record_color = palette().armed_bg
    else:
        record_color = palette().value
    play_color = palette().value
    # Shell hover: violet wash behind, hover yellow on glyph and text.
    if state.hover_button == "play":
        blit_hover(surface, play_rect)
        play_color = palette().icon_hover_fg
    # Recording wins over hover, so a click on record flashes at once.
    if state.hover_button == "record" and not state.recording:
        blit_hover(surface, record_rect)
        record_color = rec_text_color = palette().icon_hover_fg

    icon_size = layout.transport_icon_size()
    icon_font = material_font(icon_size)
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
    text_gap = timeline_ui_metrics().rec_badge_gap // 2
    record_surf = icon_font.render(RECORD_GLYPH, True, record_color)
    text_surf = font.render(REC_BUTTON_TEXT, True, rec_text_color)
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


def _draw_row_live_flash(
    upload: pygame.Surface,
    static: StaticLayers,
    state: TimelineViewState,
    layout: StripLayout,
    *,
    row_index: int,
) -> list[Rect]:
    slot = state.layer_z_order[row_index]
    row_h = layout.row_h
    upload_y = static.panel_y_offset + layout.row_y(row_index)
    arm_x = layout.header_button_x("arm")
    monitor_eye_x = layout.header_button_x("eye")
    slot_w = layout.slot_w
    icon_y = layout.icon_y(upload_y)
    dirty: list[Rect] = []

    arm_rect = (arm_x, upload_y, slot_w, row_h)
    static.restore(upload, arm_rect)
    if arm_button_lit(
        armed=slot in state.armed_slots,
        recording=state.recording,
        flash_starts=state.arm_flash_start_ms,
        slot=slot,
    ):
        # The same square box as every header button's fill and hover.
        armed_surf = pygame.Surface((slot_w, slot_w), pygame.SRCALPHA)
        armed_surf.fill((*palette().armed_bg, ARMED_BG_ALPHA))
        upload.blit(armed_surf, (arm_x, icon_y))
        upload.blit(
            render_header_toggle(RECORD_GLYPH, color=palette().value, line_height=layout.icon_h),
            (arm_x, icon_y),
        )
    dirty.append(arm_rect)

    monitor_rect = (monitor_eye_x, upload_y, slot_w, row_h)
    static.restore(upload, monitor_rect)
    monitor_icon = render_visibility_icon(
        enabled=state.monitor_visible.get(slot, True),
        override=_monitor_eye_override(state, slot),
        line_height=layout.icon_h,
    )
    upload.blit(monitor_icon, (monitor_eye_x, icon_y))
    dirty.append(monitor_rect)

    selected_t = (
        state.selected_clip_t.get(slot)
        if row_index == state.focus_row and not state.recording
        else None
    )
    if selected_t is None or not selected_clip_flash_active(
        state.selected_clip_flash_start_ms
    ):
        return dirty
    clip = next(
        (clip for clip in row_clips_for_view(state, slot) if clip.start == selected_t),
        None,
    )
    if clip is None:
        return dirty
    view_start, view_end = view_window(state)
    span = clip_bar_span(
        clip,
        bar_left=layout.bar_left,
        bar_width=layout.bar_width,
        view_start_sec=view_start,
        view_end_sec=view_end,
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


def _draw_song_markers(
    upload: pygame.Surface,
    state: TimelineViewState,
    layout: StripLayout,
    *,
    y_offset: int,
) -> Rect | None:
    """Draw song markers through the ruler and rows.

    Returns the selected marker's column while it flashes, so the upload
    repaints it each blink and once more when it settles; else None.
    """
    view_start, view_end = view_window(state)
    y0 = layout.playhead_top_y(y_offset=y_offset)
    y1 = y_offset + layout.bar_bottom - 1
    bar_right = layout.bar_left + layout.bar_width - 1
    flash_rect: Rect | None = None
    selected_index = state.selected_song_marker_index
    selected_x: int | None = None
    for marker_i, marker_t in enumerate(state.song_marker_times):
        if not time_in_view(marker_t, view_start, view_end):
            continue
        marker_x = min(
            bar_right,
            time_to_x(marker_t, layout.bar_left, layout.bar_width, view_start, view_end),
        )
        if marker_i == selected_index:
            selected_x = marker_x
            continue
        pygame.draw.line(
            upload, palette().song_marker, (marker_x, y0), (marker_x, y1), SONG_MARKER_WIDTH
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
            color = palette().song_marker_selected
            width = SONG_MARKER_SELECTED_WIDTH
        pygame.draw.line(upload, color, (selected_x, y0), (selected_x, y1), width)
    return flash_rect


def _draw_playhead(
    surface: pygame.Surface,
    layout: StripLayout,
    playhead_px: int | None,
    *,
    y_offset: int,
) -> Rect | None:
    """Draw the playhead. None when it is outside the visible window."""
    if playhead_px is None:
        return None
    playhead_left = max(
        layout.bar_left,
        min(layout.bar_left + layout.bar_width - 1, playhead_px),
    )
    y0 = layout.playhead_top_y(y_offset=y_offset)
    y1 = y_offset + layout.bar_bottom - 1
    pygame.draw.line(
        surface,
        playhead_color(),
        (playhead_left, y0),
        (playhead_left, y1),
        timeline_ui_metrics().playhead_width,
    )
    return layout.playhead_strip_rect(playhead_px, y_offset=y_offset)


def _draw_role_glyphs(
    surface: pygame.Surface,
    state: TimelineViewState,
    layout: StripLayout,
    bold_font: pygame.font.Font,
    *,
    y_offset: int,
) -> list[Rect]:
    """XOR role letters after bars/ticks/markers/playhead so they stay on top."""
    dirty: list[Rect] = []
    view_start, view_end = view_window(state)
    for display_i, slot in enumerate(state.layer_z_order):
        bar_rect = layout.bar_rect(layout.row_y(display_i))
        for cue in bar_cues_for_row(state, slot):
            if cue.role is None or cue.level <= LEVEL_EPS:
                continue
            if not time_in_view(cue.t, view_start, view_end):
                continue
            letter = _ROLE_GLYPH.get(cue.role)
            if letter is None:
                continue
            lane, inherit = glyph_lane_for_cue(state, slot, cue.t)
            previous = role_glyph_previous_level(lane, cue.t, inherit=inherit)
            side = role_glyph_side(previous_level=previous, cue_level=cue.level)
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
