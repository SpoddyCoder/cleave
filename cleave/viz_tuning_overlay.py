"""Live tuning tree overlay for Milkdrop visualizer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

import pygame

from cleave.viz_confirm import ConfirmDialog
from cleave.viz_overlay import (
    fit_counter_label_to_width,
    fit_path_label_to_width,
    fit_text_to_width,
)
from cleave.viz_playback import format_mmss
from cleave.viz_transport_icons import render_transport_icons
from cleave.viz_theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    FADE_DURATION_SEC,
    HIGHLIGHT,
    HOLD_IDLE_SEC,
    MOVE_MODE,
    PANEL_CONTENT_MAX_WIDTH,
    TEXT,
    TEXT_DIM,
)

Anchor = Literal["topleft", "bottomleft"]

ROWS_PER_TRACK = 6
FOOTER_ROWS_WITH_OVERWRITE = 4
FOOTER_ROWS_WITHOUT_OVERWRITE = 3
TREE_INDENT = 16
_TREE_PREFIX = "└─ "


class RowKind(Enum):
    TRACK_HEADER = auto()
    TRACK_PRESET_DIR = auto()
    TRACK_PRESET = auto()
    TRACK_BLEND = auto()
    TRACK_OPACITY = auto()
    TRACK_BEAT = auto()
    CONFIG_HEADER = auto()
    TRANSPORT = auto()
    SAVE_AS_NEW_CONFIG = auto()
    OVERWRITE_CONFIG = auto()


@dataclass
class TrackBlock:
    stem: str
    preset_dir_label: str
    preset_label: str
    blend_mode: str
    opacity_pct: int
    beat_sensitivity: float
    enabled: bool = True
    expanded: bool = True
    preset_empty: bool = False


@dataclass
class TuningViewState:
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    paused: bool
    position_sec: float
    focus_index: int
    move_mode_stem: str | None
    toast_message: str | None
    toast_remaining_sec: float
    confirm_message: str | None = None
    confirm_focus_yes: bool = True
    allow_overwrite: bool = True
    active_config_label: str = "cleave.config.yaml"


def footer_row_count(state: TuningViewState) -> int:
    return (
        FOOTER_ROWS_WITH_OVERWRITE
        if state.allow_overwrite
        else FOOTER_ROWS_WITHOUT_OVERWRITE
    )


def row_count(state: TuningViewState) -> int:
    return len(state.layer_z_order) * ROWS_PER_TRACK + footer_row_count(state)


_SUB_ROW_KINDS = frozenset(
    {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
    }
)


def track_sub_rows_visible(state: TuningViewState, stem: str) -> bool:
    return state.tracks[stem].expanded


def row_visible(state: TuningViewState, index: int) -> bool:
    kind = row_kind(state, index)
    if kind in _SUB_ROW_KINDS:
        stem = row_stem(state, index)
        if stem is not None and not track_sub_rows_visible(state, stem):
            return False
    return True


def visible_row_indices(state: TuningViewState) -> list[int]:
    """Row indices drawn in the panel (sub-rows hidden when collapsed)."""
    return [index for index in range(row_count(state)) if row_visible(state, index)]


def navigable_row_indices(state: TuningViewState) -> list[int]:
    """Row indices reachable via Up/Down (sub-rows skipped when collapsed)."""
    indices: list[int] = []
    for index in range(row_count(state)):
        kind = row_kind(state, index)
        if kind == RowKind.CONFIG_HEADER:
            continue
        if kind in _SUB_ROW_KINDS:
            stem = row_stem(state, index)
            if stem is not None and not track_sub_rows_visible(state, stem):
                continue
        indices.append(index)
    return indices


def quick_nav_row_indices(state: TuningViewState) -> list[int]:
    """Row indices for Ctrl+Up/Down: layer headers and transport only."""
    indices: list[int] = []
    for index in range(row_count(state)):
        kind = row_kind(state, index)
        if kind in (RowKind.TRACK_HEADER, RowKind.TRANSPORT):
            indices.append(index)
    return indices


def row_stem(state: TuningViewState, index: int) -> str | None:
    track_rows = len(state.layer_z_order) * ROWS_PER_TRACK
    if index >= track_rows:
        return None
    return state.layer_z_order[index // ROWS_PER_TRACK]


def row_kind(state: TuningViewState, index: int) -> RowKind:
    track_rows = len(state.layer_z_order) * ROWS_PER_TRACK
    if index < 0 or index >= row_count(state):
        raise IndexError(index)
    if index < track_rows:
        return (
            RowKind.TRACK_HEADER,
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_BLEND,
            RowKind.TRACK_OPACITY,
            RowKind.TRACK_BEAT,
        )[index % ROWS_PER_TRACK]
    footer_index = index - track_rows
    if footer_index == 0:
        return RowKind.CONFIG_HEADER
    if footer_index == 1:
        return RowKind.TRANSPORT
    if footer_index == 2:
        return RowKind.SAVE_AS_NEW_CONFIG
    return RowKind.OVERWRITE_CONFIG


def _row_text(state: TuningViewState, index: int) -> str:
    kind = row_kind(state, index)
    if kind == RowKind.CONFIG_HEADER:
        return state.active_config_label
    if kind == RowKind.TRANSPORT:
        return ""
    if kind == RowKind.SAVE_AS_NEW_CONFIG:
        return "SAVE AS NEW CONFIG"
    if kind == RowKind.OVERWRITE_CONFIG:
        return "OVERWRITE CONFIG"

    stem = row_stem(state, index)
    assert stem is not None
    block = state.tracks[stem]
    if kind == RowKind.TRACK_HEADER:
        layer_num = state.layer_z_order.index(stem) + 1
        status = "enabled" if block.enabled else "disabled"
        return f"Layer {layer_num}: {stem.upper()} ({status})"
    if kind == RowKind.TRACK_PRESET_DIR:
        return f"{_TREE_PREFIX}{block.preset_dir_label}"
    if kind == RowKind.TRACK_PRESET:
        return f"{_TREE_PREFIX}{block.preset_label}"
    if kind == RowKind.TRACK_BLEND:
        return f"└─ blend mode: {block.blend_mode}"
    if kind == RowKind.TRACK_OPACITY:
        return f"└─ opacity: {block.opacity_pct}%"
    return f"└─ beat sensitivity: {block.beat_sensitivity:.2f}"


def fit_row_text(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> str:
    """Fit row label to the shared panel content width (pixels)."""
    kind = row_kind(state, index)
    indent = _row_indent(state, index)
    budget = max_content_width - indent
    text = _row_text(state, index)

    if kind == RowKind.CONFIG_HEADER:
        return fit_path_label_to_width(font, text, budget)
    if kind in {RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET}:
        prefix_w = font.size(_TREE_PREFIX)[0]
        label = text[len(_TREE_PREFIX) :]
        fitted = fit_counter_label_to_width(font, label, budget - prefix_w)
        return _TREE_PREFIX + fitted
    return fit_text_to_width(font, text, budget)


def _row_indent(state: TuningViewState, index: int) -> int:
    kind = row_kind(state, index)
    if kind == RowKind.TRACK_HEADER:
        return 0
    if kind in {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
    }:
        return TREE_INDENT
    return 0


def _track_disabled(state: TuningViewState, stem: str) -> bool:
    return not state.tracks[stem].enabled


def _row_text_color(state: TuningViewState, index: int) -> tuple[int, int, int]:
    kind = row_kind(state, index)
    stem = row_stem(state, index)
    if kind == RowKind.CONFIG_HEADER:
        return TEXT_DIM

    if (
        kind == RowKind.TRACK_PRESET
        and stem is not None
        and state.tracks[stem].preset_empty
    ):
        return TEXT_DIM

    if stem is not None and state.move_mode_stem == stem:
        return MOVE_MODE

    if index == state.focus_index:
        return HIGHLIGHT

    if stem is not None and _track_disabled(state, stem):
        return TEXT_DIM

    return TEXT


def _row_bg_color(state: TuningViewState, index: int) -> tuple[int, int, int] | None:
    stem = row_stem(state, index)
    if stem is not None and state.move_mode_stem == stem:
        return MOVE_MODE
    if index == state.focus_index:
        return HIGHLIGHT
    return None


class TuningOverlay:
    """Tree-style live tuning panel; holds visible after input, then fades out."""

    def __init__(
        self,
        *,
        anchor: Anchor = "topleft",
        margin: tuple[int, int] = (10, 10),
        font_size: int = 14,
        padding: int = 8,
        line_gap: int = 3,
    ) -> None:
        self._anchor = anchor
        self._margin = margin
        self._font_size = font_size
        self._padding = padding
        self._line_gap = line_gap
        self._hold_idle_sec = HOLD_IDLE_SEC
        self._fade_duration_sec = FADE_DURATION_SEC
        self._idle_sec = 0.0
        self._visibility = 1.0
        self._font: pygame.font.Font | None = None
        self._panel_rect: tuple[int, int, int, int] | None = None
        self._confirm = ConfirmDialog()

    def notify_input(self) -> None:
        self._idle_sec = 0.0
        self._visibility = 1.0

    def update(self, dt_sec: float) -> None:
        self._idle_sec += dt_sec
        if self._idle_sec <= self._hold_idle_sec:
            self._visibility = 1.0
        elif self._fade_duration_sec <= 0:
            self._visibility = 0.0
        elif self._idle_sec <= self._hold_idle_sec + self._fade_duration_sec:
            fade_t = (self._idle_sec - self._hold_idle_sec) / self._fade_duration_sec
            self._visibility = 1.0 - fade_t
        else:
            self._visibility = 0.0

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        """Top-left x, y, width, height of the last drawn panel, if any."""
        return self._panel_rect

    def draw(self, surface: pygame.Surface, state: TuningViewState) -> None:
        self._panel_rect = None
        if self._visibility <= 0.01 or row_count(state) == 0:
            return

        font = self._font_get()
        line_h = font.get_linesize()
        visible_indices = visible_row_indices(state)
        visible_count = len(visible_indices)
        track_rows_boundary = len(state.layer_z_order) * ROWS_PER_TRACK
        first_footer_visible = next(
            (index for index in visible_indices if index >= track_rows_boundary),
            None,
        )
        toast_active = bool(state.toast_message and state.toast_remaining_sec > 0)
        confirm_active = state.confirm_message is not None

        row_surfaces: list[pygame.Surface] = []
        row_time_surfaces: list[pygame.Surface | None] = []
        row_widths: list[int] = []
        for index in visible_indices:
            kind = row_kind(state, index)
            indent = self._padding + _row_indent(state, index)
            color = _row_text_color(state, index)

            if kind == RowKind.TRANSPORT:
                icons_surf = render_transport_icons(
                    color=color,
                    line_height=line_h,
                    paused=state.paused,
                )
                time_text = f" [{format_mmss(state.position_sec)}]"
                time_surf = font.render(time_text, True, color)
                row_surfaces.append(icons_surf)
                row_time_surfaces.append(time_surf)
                row_widths.append(
                    indent + icons_surf.get_width() + time_surf.get_width()
                )
            else:
                text = fit_row_text(font, state, index)
                surf = font.render(text, True, color)
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())

        toast_surf: pygame.Surface | None = None
        if toast_active:
            assert state.toast_message is not None
            toast_text = fit_text_to_width(
                font, state.toast_message, PANEL_CONTENT_MAX_WIDTH
            )
            toast_surf = font.render(toast_text, True, TEXT_DIM)

        confirm_h = 0
        confirm_w = 0
        if confirm_active:
            assert state.confirm_message is not None
            confirm_h = self._confirm.measure_height(
                font,
                state.confirm_message,
                line_gap=self._line_gap,
            )
            confirm_w = self._confirm.measure_width(font, state.confirm_message)

        content_w = max(row_widths) if row_widths else 0
        if toast_surf is not None:
            content_w = max(content_w, toast_surf.get_width())
        if confirm_active:
            content_w = max(content_w, confirm_w)
        content_w = min(content_w, PANEL_CONTENT_MAX_WIDTH)
        panel_w = content_w + self._padding * 2
        footer_gap = line_h + self._line_gap
        panel_h = (
            visible_count * line_h
            + max(0, visible_count - 1) * self._line_gap
            + (footer_gap if first_footer_visible is not None else 0)
            + self._padding * 2
        )
        if confirm_active:
            panel_h += self._line_gap + confirm_h
        if toast_surf is not None:
            panel_h += self._line_gap + line_h

        alpha = int(BACKGROUND_ALPHA * self._visibility)
        if alpha < 2:
            return

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, alpha))

        text_alpha = int(255 * self._visibility)
        y = self._padding
        for draw_index, index in enumerate(visible_indices):
            if index == first_footer_visible:
                y += footer_gap
            surf = row_surfaces[draw_index]
            assert surf is not None
            bg = _row_bg_color(state, index)
            if bg is not None:
                bg_alpha = int(50 * self._visibility)
                if bg_alpha >= 2:
                    bg_surf = pygame.Surface((panel_w - self._padding * 2, line_h), pygame.SRCALPHA)
                    bg_surf.fill((*bg, bg_alpha))
                    panel.blit(bg_surf, (self._padding, y))

            indent = self._padding + _row_indent(state, index)
            if text_alpha >= 2:
                surf.set_alpha(text_alpha)
                panel.blit(surf, (indent, y))
                time_surf = row_time_surfaces[draw_index]
                if time_surf is not None:
                    time_surf.set_alpha(text_alpha)
                    panel.blit(time_surf, (indent + surf.get_width(), y))
            y += line_h + self._line_gap

        if confirm_active and text_alpha >= 2:
            assert state.confirm_message is not None
            y += self._line_gap
            self._confirm.draw(
                panel,
                font,
                x=self._padding,
                y=y,
                message=state.confirm_message,
                focus_yes=state.confirm_focus_yes,
                text_alpha=text_alpha,
                line_gap=self._line_gap,
            )

        if toast_surf is not None and text_alpha >= 2:
            toast_surf.set_alpha(text_alpha)
            toast_x = self._padding
            toast_y = panel_h - self._padding - line_h
            panel.blit(toast_surf, (toast_x, toast_y))

        border_alpha = int(255 * self._visibility)
        if border_alpha >= 2 and BORDER_WIDTH > 0:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, border_alpha),
                panel.get_rect(),
                width=BORDER_WIDTH,
            )

        mx, my = self._margin
        if self._anchor == "topleft":
            pos = (mx, my)
        else:
            pos = (mx, surface.get_height() - panel_h - my)

        surface.blit(panel, pos)
        self._panel_rect = (pos[0], pos[1], panel_w, panel_h)
