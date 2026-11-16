"""Bottom timeline strip: composes the cached static panel and the live layer.

The strip's parts live in their own modules: view state and per-row data in
``timeline_strip_state``, geometry in ``timeline_strip_layout``, the static
panel in ``timeline_strip_static``, the live layer in ``timeline_strip_live``,
blink timing in ``timeline_strip_flash``, and hit testing in
``timeline_strip_hit``. ``TimelineOverlay`` owns the caches and the upload.
"""

from __future__ import annotations

import pygame

from cleave.viz.overlay_primitives import (
    ComposedPanel,
    clip_rect_to_bounds,
    overlay_font,
)
from cleave.viz.overlay_upload import (
    clip_dirty_rects,
    dirty_rects_for_clip_rect,
    upload_plan_for_signature,
)
from cleave.viz.theme import timeline_ui_metrics
from cleave.viz.timeline_panel_cache import (
    TimelinePanelCache,
    timeline_panel_max_dimensions,
    timeline_static_signature,
    timeline_upload_signature,
)
from cleave.viz.timeline_strip_hit import StripHit, StripHitMap
from cleave.viz.timeline_strip_layout import (
    StripLayout,
    compute_strip_layout,
    playhead_x,
    time_in_view,
)
from cleave.viz.timeline_strip_live import (
    live_flash_signature,
    patch_live_overlay,
    timeline_live_signature,
)
from cleave.viz.timeline_strip_state import (
    TimelineViewState,
    row_clips_for_view,
    view_window,
)
from cleave.viz.timeline_strip_static import (
    RowLayoutEntry,
    StaticLayers,
    build_ruler,
    build_static_panel,
)


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
        self._bar_layout: tuple[int, int] | None = None
        self._row_layout: list[RowLayoutEntry] = []
        self._cache = TimelinePanelCache()
        self._visibility = 1.0
        self._upload_scratch: pygame.Surface | None = None
        self._ruler: pygame.Surface | None = None
        self._blit_src: tuple[int, int] = (0, 0)
        self._hits: StripHitMap | None = None

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
    def row_layout(self) -> list[RowLayoutEntry]:
        """Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates."""
        return list(self._row_layout)

    @property
    def layout(self) -> StripLayout | None:
        """The layout of the last compose that reached the screen."""
        return None if self._hits is None else self._hits.layout

    def hit_at(self, x: float, y: float) -> StripHit | None:
        """Ruler or layer row under a screen point, from the last compose."""
        return None if self._hits is None else self._hits.hit_at(x, y)

    def row_label_rect(self, row: int) -> tuple[int, int, int, int] | None:
        """Screen rect of *row*'s label (number and stem), from the last compose."""
        return None if self._hits is None else self._hits.row_label_rect(row)

    def time_at_x(self, x: float) -> float | None:
        """Song time under screen *x*, clamped to the bar. None before a compose."""
        return None if self._hits is None else self._hits.time_at_x(x)

    def view_sec_per_px(self) -> float:
        """Song seconds one bar pixel spans in the visible window. 0 before a compose."""
        return 0.0 if self._hits is None else self._hits.view_sec_per_px()

    def scrollbar_time_at_x(self, x: float) -> float | None:
        """Song time at screen *x* along the scrollbar track (the whole song)."""
        return None if self._hits is None else self._hits.scrollbar_time_at_x(x)

    def scrollbar_sec_per_px(self) -> float:
        """Seconds the window start moves per pixel of thumb travel. 0 when it cannot move."""
        return 0.0 if self._hits is None else self._hits.scrollbar_sec_per_px()

    def _ensure_upload_scratch(
        self,
        upload_w: int,
        upload_h: int,
    ) -> tuple[pygame.Surface, bool]:
        """The upload surface, and whether it was just allocated (and so blank)."""
        scratch = self._upload_scratch
        if (
            scratch is not None
            and scratch.get_width() == upload_w
            and scratch.get_height() == upload_h
        ):
            return scratch, False
        scratch = pygame.Surface((upload_w, upload_h), pygame.SRCALPHA)
        self._upload_scratch = scratch
        return scratch, True

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
        self._hits = None
        if visibility <= 0.01:
            return None

        layout = compute_strip_layout(
            len(state.layer_z_order),
            font=overlay_font(self._font_size),
            font_size=self._font_size,
            padding=self._padding,
            row_gap=self._row_gap,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            timeline_rect=timeline_rect,
        )
        if layout is None:
            return None
        self._layer_num_width = layout.layer_num_width
        self._stem_abbrev_width = layout.stem_abbrev_width
        self._bar_layout = (layout.bar_left, layout.bar_width)

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
            static_panel, self._row_layout = build_static_panel(
                state, layout, overlay_font(self._font_size)
            )
            self._ruler = build_ruler(state, layout, font_size=self._font_size)
            cache.panel = static_panel
            cache.static_signature = static_sig
            cache.panel_size = (panel_w, panel_h)
            cache.last_playhead_rect = None
            cache.last_flash_rects = ()
            cache.last_glyph_rects = ()
            cache.last_live_signature = None
            incremental = False
        static = StaticLayers(
            panel=static_panel, ruler=self._ruler, panel_y_offset=layout.badge_reserve
        )

        upload_w = panel_w
        upload_h = panel_h + layout.badge_reserve
        upload, upload_fresh = self._ensure_upload_scratch(upload_w, upload_h)
        if upload_fresh:
            incremental = False
            cache.last_live_signature = None
        if not incremental:
            static.lay(upload)

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
        live_sig = timeline_live_signature(
            state,
            playhead_px=playhead_px,
            bar_left=layout.bar_left,
            bar_width=layout.bar_width,
            row_count=layout.row_count,
            row_h=layout.row_h,
            flash_sig=live_flash_signature(state),
        )
        live_unchanged = incremental and live_sig == cache.last_live_signature
        prev_playhead = cache.last_playhead_rect
        prev_transport = cache.last_transport_rect
        prev_flash = cache.last_flash_rects
        prev_glyphs = cache.last_glyph_rects
        flash_dirty: list[tuple[int, int, int, int]] = []
        if not live_unchanged:
            flash_dirty = patch_live_overlay(
                upload,
                static,
                state,
                layout,
                cache,
                playhead_px=playhead_px,
                incremental=incremental,
                font=overlay_font(self._font_size),
                bold_font=overlay_font(self._font_size, bold=True),
            )

        upload_top_y = layout.panel_y - layout.badge_reserve
        screen_bounds = clip_rect_to_bounds(
            (layout.panel_x, upload_top_y, upload_w, upload_h),
            viewport_width,
            viewport_height,
        )
        if screen_bounds is None:
            return None

        self._hits = StripHitMap(
            layout=layout,
            duration_sec=state.duration_sec,
            view=(view_start, view_end),
            markers=state.song_marker_times,
            clips=tuple(
                tuple(row_clips_for_view(state, slot)) for slot in state.layer_z_order
            ),
        )
        sx, sy, sw, sh = screen_bounds
        self._panel_rect = clip_rect_to_bounds(
            (layout.panel_x, layout.panel_y, panel_w, panel_h),
            viewport_width,
            viewport_height,
        )

        capacity = timeline_panel_max_dimensions(viewport_width, viewport_height)
        upload_signature = timeline_upload_signature(static_sig, screen_bounds, live_sig)

        src_x = sx - layout.panel_x
        src_y = sy - upload_top_y
        if live_unchanged:
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
                prev_transport,
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
