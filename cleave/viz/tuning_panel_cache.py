"""Retained surfaces and signatures for the live tuning panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

import pygame

from cleave.viz.overlay_profiler import OverlayDrawCounters
from cleave.viz.row_semantics import RowKind
from cleave.viz.tuning_view_state import TuningViewState

TextFitter = Callable[[pygame.font.Font, str, int], str]


class RowBuilder(Protocol):
    def __call__(
        self,
        font: pygame.font.Font,
        state: TuningViewState,
        index: int,
        *,
        max_content_width: int,
        line_h: int,
        counters: OverlayDrawCounters | None = None,
        cache: TuningPanelCache | None = None,
    ) -> tuple[pygame.Surface, pygame.Surface | None, int]: ...


@dataclass(frozen=True)
class RowRenderKey:
    kind: RowKind
    slot: str | None
    display_text: str
    color_state: tuple[int, int, int]
    max_width: int
    line_h: int


@dataclass
class RowRenderEntry:
    primary: pygame.Surface
    secondary: pygame.Surface | None = None
    content_width: int = 0


@dataclass(frozen=True)
class TextFitKey:
    fitter: str
    raw_text: str
    max_width: int
    font_size: int


@dataclass(frozen=True)
class PanelSignature:
    visible_indices: tuple[int, ...]
    focus_index: int
    visibility_bucket: int
    panel_w: int
    panel_h: int
    scroll_y: int
    timeline_panel_open: bool
    config_dirty: bool
    static_row_keys: tuple[tuple, ...]


@dataclass
class TuningPanelCache:
    row_surfaces: dict[RowRenderKey, RowRenderEntry] = field(default_factory=dict)
    text_fit: dict[TextFitKey, str] = field(default_factory=dict)
    panel: pygame.Surface | None = None
    panel_signature: PanelSignature | None = None
    panel_size: tuple[int, int] | None = None
    row_cache_structure: tuple[int, ...] | None = None
    last_fps_rect: tuple[int, int, int, int] | None = None

    def clear_rows(self) -> None:
        self.row_surfaces.clear()
        self.text_fit.clear()
        self.row_cache_structure = None

    def clear_panel(self) -> None:
        self.panel = None
        self.panel_signature = None
        self.panel_size = None
        self.last_fps_rect = None

    def clear_all(self) -> None:
        self.clear_rows()
        self.clear_panel()

    def fit_text_cached(
        self,
        fitter: str,
        fit_fn: TextFitter,
        font: pygame.font.Font,
        text: str,
        max_px: int,
    ) -> str:
        key = TextFitKey(
            fitter=fitter,
            raw_text=text,
            max_width=max_px,
            font_size=font.get_height(),
        )
        cached = self.text_fit.get(key)
        if cached is not None:
            return cached
        result = fit_fn(font, text, max_px)
        self.text_fit[key] = result
        return result


def visibility_bucket(visibility: float) -> int:
    if visibility <= 0.01:
        return 0
    return min(255, int(visibility * 255))


def row_render_key(
    state: TuningViewState,
    index: int,
    font: pygame.font.Font,
    *,
    cache: TuningPanelCache | None = None,
    max_content_width: int,
    line_h: int,
) -> RowRenderKey:
    from cleave.viz.tuning_panel_draw import _row_value_color, fit_row_text

    kind = state.layout.kind(index)
    slot = state.layout.slot(index)
    display_text = fit_row_text(
        font,
        state,
        index,
        max_content_width=max_content_width,
        cache=cache,
    )
    color_state = _row_value_color(state, index)
    return RowRenderKey(
        kind=kind,
        slot=slot,
        display_text=display_text,
        color_state=color_state,
        max_width=max_content_width,
        line_h=line_h,
    )


def static_row_keys(
    state: TuningViewState,
    *,
    font: pygame.font.Font,
    cache: TuningPanelCache,
    visible_indices: tuple[int, ...],
    max_content_width_for_index: Callable[[int], int],
    line_h: int,
) -> tuple[tuple, ...]:
    keys: list[tuple] = []
    for index in visible_indices:
        if state.layout.kind(index) == RowKind.TRANSPORT:
            continue
        max_w = max_content_width_for_index(index)
        key = row_render_key(
            state,
            index,
            font,
            cache=cache,
            max_content_width=max_w,
            line_h=line_h,
        )
        keys.append(
            (
                key.kind,
                key.slot,
                key.display_text,
                key.color_state,
                key.max_width,
                key.line_h,
            )
        )
    return tuple(keys)


def panel_signature(
    state: TuningViewState,
    *,
    visibility: float,
    panel_w: int,
    panel_h: int,
    scroll_y: int,
    timeline_panel_open: bool = False,
    static_row_keys: tuple[tuple, ...] = (),
) -> PanelSignature:
    frame = state.layout_frame
    if frame is not None:
        visible_indices = tuple(frame.visible_indices)
    else:
        visible_indices = tuple(state.layout.visible_indices(state))
    return PanelSignature(
        visible_indices=visible_indices,
        focus_index=state.focus_index,
        visibility_bucket=visibility_bucket(visibility),
        panel_w=panel_w,
        panel_h=panel_h,
        scroll_y=scroll_y,
        timeline_panel_open=timeline_panel_open,
        config_dirty=state.config_dirty,
        static_row_keys=static_row_keys,
    )


def ensure_row_surface(
    cache: TuningPanelCache,
    state: TuningViewState,
    index: int,
    font: pygame.font.Font,
    build_row: RowBuilder,
    *,
    max_content_width: int,
    line_h: int,
    counters: OverlayDrawCounters | None = None,
) -> RowRenderEntry:
    kind = state.layout.kind(index)
    if kind == RowKind.TRANSPORT:
        if counters is not None:
            counters.row_cache_misses += 1
        surf, time_surf, width = build_row(
            font,
            state,
            index,
            max_content_width=max_content_width,
            line_h=line_h,
            counters=counters,
            cache=cache,
        )
        return RowRenderEntry(primary=surf, secondary=time_surf, content_width=width)

    key = row_render_key(
        state,
        index,
        font,
        cache=cache,
        max_content_width=max_content_width,
        line_h=line_h,
    )
    entry = cache.row_surfaces.get(key)
    if entry is not None:
        if counters is not None:
            counters.row_cache_hits += 1
        return entry

    if counters is not None:
        counters.row_cache_misses += 1
    surf, time_surf, width = build_row(
        font,
        state,
        index,
        max_content_width=max_content_width,
        line_h=line_h,
        counters=counters,
        cache=cache,
    )
    entry = RowRenderEntry(primary=surf, secondary=time_surf, content_width=width)
    cache.row_surfaces[key] = entry
    return entry
