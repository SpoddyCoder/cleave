"""Context-sensitive help panel for the Cleave visualizer."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.viz.overlay import RowKind, _clip_rect_to_surface
from cleave.viz.theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    DISABLED,
    LABEL,
    VALUE,
)


@dataclass(frozen=True)
class HelpSection:
    title: str
    entries: tuple[tuple[str, str], ...]


NAVIGATION_SECTION = HelpSection(
    "Navigation",
    (
        ("Up/Down", "move row"),
        ("Ctrl+Up/Down", "jump section"),
        ("ESC", "hide UI"),
        ("Ctrl+Q", "quit"),
    ),
)

_TRANSPORT_SECTION = HelpSection(
    "Transport Controls",
    (
        ("Enter", "play/pause"),
        ("Left/Right", "skip 10s"),
        ("Ctrl+Left/Right", "skip 30s"),
    ),
)

_LAYER_SECTION_BASE: tuple[tuple[str, str], ...] = (
    ("Enter", "move mode"),
    ("Shift+Left/Right", "solo"),
    ("Left/Right", "expand/collapse"),
)

_LAYER_VISIBILITY_ENTRY = ("Ctrl+Left/Right", "enable/disable")


def _layer_section(*, timeline_enabled: bool) -> HelpSection:
    entries = list(_LAYER_SECTION_BASE)
    if not timeline_enabled:
        entries.append(_LAYER_VISIBILITY_ENTRY)
    return HelpSection("Layer", tuple(entries))


_EDIT_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "adjust value"),
        ("Ctrl+Left/Right", "large step"),
    ),
)

_PRESET_DIR_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous directory"),
        ("Ctrl+Left/Right", "up/down directory tree"),
    ),
)

_PRESET_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous preset"),
        ("Ctrl+Left/Right", "next/previous large step"),
    ),
)


def _cleave_effects_section(row_kind: RowKind) -> HelpSection:
    if row_kind == RowKind.TRACK_EFFECTS_HEADER:
        entries = (("Left/Right", "expand/collapse"),)
    else:
        entries = (
            ("Left/Right", "adjust depth"),
            ("Ctrl+Left/Right", "large step"),
        )
    return HelpSection("Cleave Effects", entries)


_RENDER_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("Ctrl+Left/Right", "enable/disable"),
        ("Shift+Left/Right", "always on"),
    ),
)

_RENDER_TIMELINE_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("Ctrl+Left/Right", "enable/disable"),
    ),
)

_SAVE_SECTION = HelpSection(
    "Save",
    (("Enter", "save config"),),
)

_TRACK_EDIT_KINDS = frozenset(
    {
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
    }
)

_TRACK_EFFECT_KINDS = frozenset(
    {
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.TRACK_EFFECT,
    }
)

_RENDER_HEADER_KINDS = frozenset(
    {
        RowKind.RENDER_OVERLAY_HEADER,
        RowKind.RENDER_POST_FX_HEADER,
    }
)

_RENDER_SUB_ROW_KINDS = frozenset(
    {
        RowKind.RENDER_OVERLAY_POSITION,
        RowKind.RENDER_OVERLAY_TITLE_HEADER,
        RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE,
        RowKind.RENDER_OVERLAY_TITLE_FONT,
        RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        RowKind.RENDER_OVERLAY_BODY_HEADER,
        RowKind.RENDER_OVERLAY_BODY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_BODY_FONT,
        RowKind.RENDER_OVERLAY_OPACITY,
        RowKind.RENDER_OVERLAY_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_START_DELAY,
        RowKind.RENDER_OVERLAY_DISPLAY_TIME,
        RowKind.RENDER_POST_FX_FADE_IN,
        RowKind.RENDER_POST_FX_FADE_OUT,
    }
)

_HELP_BY_KIND: dict[RowKind, tuple[HelpSection, ...]] = {
    RowKind.TRANSPORT: (_TRANSPORT_SECTION, NAVIGATION_SECTION),
    RowKind.SAVE_CONFIG: (_SAVE_SECTION, NAVIGATION_SECTION),
    RowKind.CONFIG_HEADER: (NAVIGATION_SECTION,),
    RowKind.RENDER_TIMELINE_HEADER: (_RENDER_TIMELINE_SECTION, NAVIGATION_SECTION),
}


def _sections_for(
    row_kind: RowKind, *, timeline_enabled: bool = False
) -> tuple[HelpSection, ...]:
    if row_kind == RowKind.TRACK_HEADER:
        return (_layer_section(timeline_enabled=timeline_enabled), NAVIGATION_SECTION)
    if row_kind in _HELP_BY_KIND:
        return _HELP_BY_KIND[row_kind]
    if row_kind == RowKind.TRACK_PRESET_DIR:
        return (_PRESET_DIR_SECTION, NAVIGATION_SECTION)
    if row_kind == RowKind.TRACK_PRESET:
        return (_PRESET_SECTION, NAVIGATION_SECTION)
    if row_kind in _TRACK_EDIT_KINDS:
        return (_EDIT_SECTION, NAVIGATION_SECTION)
    if row_kind in _TRACK_EFFECT_KINDS:
        return (_cleave_effects_section(row_kind), NAVIGATION_SECTION)
    if row_kind in _RENDER_HEADER_KINDS:
        return (_RENDER_SECTION, NAVIGATION_SECTION)
    if row_kind in _RENDER_SUB_ROW_KINDS:
        return (_EDIT_SECTION, NAVIGATION_SECTION)
    return (NAVIGATION_SECTION,)


class HelpOverlay:
    """Read-only help panel anchored top-right; toggled independently of focus."""

    def __init__(
        self,
        *,
        margin: tuple[int, int] = (10, 10),
        padding: int = 8,
        line_gap: int = 3,
        font_size: int = 14,
    ) -> None:
        self._visible = False
        self._margin = margin
        self._padding = padding
        self._line_gap = line_gap
        self._font_size = font_size
        self._font: pygame.font.Font | None = None
        self._panel_rect: tuple[int, int, int, int] | None = None

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        return self._panel_rect

    def toggle(self) -> None:
        self._visible = not self._visible

    def is_visible(self) -> bool:
        return self._visible

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    def _entry_width(self, font: pygame.font.Font, key: str, description: str) -> int:
        key_w = font.render(key, True, VALUE).get_width()
        gap_w = font.size("  ")[0]
        desc_w = font.render(description, True, DISABLED).get_width()
        return key_w + gap_w + desc_w

    def _dash_separator(self, font: pygame.font.Font, width: int) -> pygame.Surface:
        dash_w = font.render("-", True, DISABLED).get_width()
        count = max(1, width // dash_w) if dash_w > 0 else 1
        return font.render("-" * count, True, DISABLED)

    def _blit_entry(
        self,
        target: pygame.Surface,
        font: pygame.font.Font,
        key: str,
        description: str,
        x: int,
        y: int,
    ) -> None:
        key_surf = font.render(key, True, VALUE)
        desc_surf = font.render(description, True, DISABLED)
        gap = font.size("  ")[0]
        target.blit(key_surf, (x, y))
        target.blit(desc_surf, (x + key_surf.get_width() + gap, y))

    def draw(
        self,
        surface: pygame.Surface,
        row_kind: RowKind,
        *,
        timeline_enabled: bool = False,
    ) -> None:
        self._panel_rect = None
        font = self._font_get()
        line_h = font.get_linesize()
        sections = _sections_for(row_kind, timeline_enabled=timeline_enabled)

        content_w = 0
        for section in sections:
            title_w = font.render(section.title, True, LABEL).get_width()
            content_w = max(content_w, title_w)
            for key, description in section.entries:
                content_w = max(
                    content_w, self._entry_width(font, key, description)
                )

        row_stride = line_h + self._line_gap
        line_count = 0
        for section_index, section in enumerate(sections):
            line_count += 1  # title
            line_count += 1  # separator
            line_count += len(section.entries)
            if section_index < len(sections) - 1:
                line_count += 1  # gap between sections

        content_h = line_count * row_stride - self._line_gap
        panel_w = content_w + self._padding * 2
        panel_h = content_h + self._padding * 2

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, BACKGROUND_ALPHA))

        y = self._padding
        for section_index, section in enumerate(sections):
            title_surf = font.render(section.title, True, LABEL)
            panel.blit(title_surf, (self._padding, y))
            y += row_stride

            sep_surf = self._dash_separator(font, content_w)
            panel.blit(sep_surf, (self._padding, y))
            y += row_stride

            for key, description in section.entries:
                self._blit_entry(
                    panel, font, key, description, self._padding, y
                )
                y += row_stride

            if section_index < len(sections) - 1:
                y += row_stride

        if BORDER_WIDTH > 0:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, 255),
                panel.get_rect(),
                width=BORDER_WIDTH,
            )

        mx, my = self._margin
        pos = (surface.get_width() - panel_w - mx, my)
        surface.blit(panel, pos)
        self._panel_rect = _clip_rect_to_surface(
            (pos[0], pos[1], panel_w, panel_h),
            surface,
        )
