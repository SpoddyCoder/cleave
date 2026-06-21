"""Context-sensitive help panel for the Cleave visualizer."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.viz.row_semantics import RowAffordance, RowKind, row_behavior
from cleave.viz.overlay import clip_rect_to_surface
from cleave.viz.theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    DISABLED,
    HIGHLIGHT,
    LABEL,
    VALUE,
    tuning_ui_metrics,
)


@dataclass(frozen=True)
class HelpSection:
    title: str
    entries: tuple[tuple[str, str], ...]


NAVIGATION_SECTION = HelpSection(
    "Navigation",
    (
        ("Up/Down", "move row"),
        ("Ctrl + Up/Down", "jump section"),
        ("ESC", "hide UI"),
        ("Ctrl + Q", "quit"),
    ),
)

_TRANSPORT_SECTION = HelpSection(
    "Transport Controls",
    (
        ("Enter", "play/pause"),
        ("Left/Right", "skip 10s"),
        ("Ctrl + Left/Right", "skip 30s"),
    ),
)

_LAYER_SECTION_BASE: tuple[tuple[str, str], ...] = (
    ("Enter", "move z-order"),
    ("Ctrl + Enter", "lock/unlock layer"),
    ("Shift + Left/Right", "solo layer"),
    ("Left/Right", "expand/collapse"),
)

_LAYER_VISIBILITY_ENTRY = ("Ctrl + Left/Right", "enable/disable layer")


def _layer_section(*, timeline_enabled: bool) -> HelpSection:
    entries = list(_LAYER_SECTION_BASE)
    if not timeline_enabled:
        entries.append(_LAYER_VISIBILITY_ENTRY)
    return HelpSection("Layer", tuple(entries))


_EDIT_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "adjust value"),
        ("Ctrl + Left/Right", "large step"),
    ),
)

_PRESET_DIR_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous directory"),
        ("Ctrl + Left/Right", "up/down directory tree"),
    ),
)

_PRESET_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous preset"),
        ("Ctrl + Left/Right", "next/previous large step"),
    ),
)

_STEM_SECTION = HelpSection(
    "Stem",
    (("Left/Right", "cycle stem source; effects reset on change"),),
)


_RENDER_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("Ctrl + Left/Right", "enable/disable"),
        ("Shift + Left/Right", "always on"),
    ),
)

_RENDER_TIMELINE_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("Ctrl + Left/Right", "enable/disable"),
    ),
)

def _timeline_strip_section(
    *,
    paused: bool,
    recording: bool,
    override_active: bool,
) -> HelpSection:
    entries: list[tuple[str, str]] = [("Enter", "toggle arm track")]

    if not recording:
        entries.append(("Shift + Enter", "toggle override"))
        if paused or override_active:
            entries.append(("1-4", "toggle layer visibility"))

    if recording:
        entries.append(("1-4", "toggle layer visibility"))

    if recording:
        entries.append(("r", "stop record"))
        entries.append(("Ctrl + Space / Space", "stop record and pause"))
    else:
        entries.append(("Ctrl + Space / r", "start record"))
        if paused:
            entries.append(("Space", "play"))
        else:
            entries.append(("Space", "pause"))

    if not recording:
        entries.extend(
            (
                ("Left/Right", "skip 10s"),
                ("Ctrl + Left/Right", "skip 30s"),
            )
        )

    entries.extend(
        (
            ("Backspace", "delete cue"),
            ("Esc", "close timeline"),
        )
    )
    return HelpSection("Timeline", tuple(entries))

_SAVE_SECTION = HelpSection(
    "Save",
    (("Enter", "save config"),),
)


def _value_step_section(row_kind: RowKind) -> HelpSection:
    behavior = row_behavior(row_kind)
    if row_kind == RowKind.TRACK_EFFECT:
        entries = (
            ("Left/Right", "adjust depth"),
            ("Ctrl + Left/Right", "large step"),
        )
    else:
        entries = _EDIT_SECTION.entries
    return HelpSection(behavior.help_title or "Edit", entries)


def _sections_for(
    row_kind: RowKind,
    *,
    timeline_enabled: bool = False,
    timeline_submenu_focused: bool = False,
    paused: bool = False,
    timeline_recording: bool = False,
    timeline_override_active: bool = False,
) -> tuple[HelpSection, ...]:
    if timeline_submenu_focused:
        return (
            _timeline_strip_section(
                paused=paused,
                recording=timeline_recording,
                override_active=timeline_override_active,
            ),
            NAVIGATION_SECTION,
        )

    behavior = row_behavior(row_kind)

    if not behavior.navigable or behavior.affordance == RowAffordance.DISPLAY:
        return (NAVIGATION_SECTION,)

    primary: HelpSection | None = None

    if behavior.affordance == RowAffordance.EXPAND:
        if behavior.is_sub_header:
            primary = HelpSection(
                behavior.help_title or "Edit",
                (("Left/Right", "expand/collapse"),),
            )
        elif behavior.can_enter_move_mode:
            primary = _layer_section(timeline_enabled=timeline_enabled)
        elif behavior.can_enable_disable and behavior.can_solo:
            primary = _RENDER_SECTION
        elif behavior.can_enable_disable:
            primary = _RENDER_TIMELINE_SECTION
    elif row_kind == RowKind.TRACK_STEM:
        primary = _STEM_SECTION
    elif behavior.affordance == RowAffordance.VALUE_STEP:
        primary = _value_step_section(row_kind)
    elif behavior.affordance == RowAffordance.PATH_DIR:
        primary = _PRESET_DIR_SECTION
    elif behavior.affordance == RowAffordance.PATH_PRESET:
        primary = _PRESET_SECTION
    elif behavior.affordance == RowAffordance.SEEK:
        primary = _TRANSPORT_SECTION
    elif row_kind == RowKind.LAYER_MANAGEMENT_ADD:
        primary = HelpSection(
            behavior.help_title or "Add new layer",
            (("Enter", "confirm add"),),
        )
    elif row_kind == RowKind.LAYER_MANAGEMENT_DELETE:
        primary = HelpSection(
            behavior.help_title or "Delete layer",
            (
                ("Enter", "confirm delete"),
                ("", "at least 1 layer required"),
            ),
        )
    elif behavior.affordance == RowAffordance.ACTION:
        primary = _SAVE_SECTION

    if primary is None:
        return (NAVIGATION_SECTION,)

    return (primary, NAVIGATION_SECTION)


class HelpOverlay:
    """Read-only help panel anchored top-right; visibility from session state."""

    def __init__(
        self,
        *,
        margin: tuple[int, int] | None = None,
        padding: int | None = None,
        line_gap: int | None = None,
        font_size: int | None = None,
    ) -> None:
        metrics = tuning_ui_metrics()
        if margin is None:
            margin = (metrics.margin, metrics.margin)
        if padding is None:
            padding = metrics.padding
        if line_gap is None:
            line_gap = metrics.line_gap
        if font_size is None:
            font_size = metrics.font_size
        self._margin = margin
        self._padding = padding
        self._line_gap = line_gap
        self._font_size = font_size
        self._font: pygame.font.Font | None = None
        self._panel_rect: tuple[int, int, int, int] | None = None

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        return self._panel_rect

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    def _entry_gap(self, font: pygame.font.Font) -> int:
        return font.size("  ")[0]

    def _max_key_width(
        self, font: pygame.font.Font, sections: tuple[HelpSection, ...]
    ) -> int:
        return max(
            (
                font.render(key, True, LABEL).get_width()
                for section in sections
                for key, _ in section.entries
            ),
            default=0,
        )

    def _entry_width(
        self,
        font: pygame.font.Font,
        key: str,
        description: str,
        *,
        key_column_width: int,
        entry_gap: int,
    ) -> int:
        desc_w = font.render(description, True, VALUE).get_width()
        return key_column_width + entry_gap + desc_w

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
        *,
        key_column_width: int,
        entry_gap: int,
    ) -> None:
        key_surf = font.render(key, True, LABEL)
        desc_surf = font.render(description, True, VALUE)
        target.blit(key_surf, (x, y))
        target.blit(desc_surf, (x + key_column_width + entry_gap, y))

    def draw(
        self,
        surface: pygame.Surface,
        row_kind: RowKind,
        *,
        timeline_enabled: bool = False,
        timeline_submenu_focused: bool = False,
        paused: bool = False,
        timeline_recording: bool = False,
        timeline_override_active: bool = False,
    ) -> None:
        self._panel_rect = None
        font = self._font_get()
        line_h = font.get_linesize()
        sections = _sections_for(
            row_kind,
            timeline_enabled=timeline_enabled,
            timeline_submenu_focused=timeline_submenu_focused,
            paused=paused,
            timeline_recording=timeline_recording,
            timeline_override_active=timeline_override_active,
        )

        entry_gap = self._entry_gap(font)
        key_column_width = self._max_key_width(font, sections)

        content_w = 0
        for section in sections:
            title_w = font.render(section.title, True, HIGHLIGHT).get_width()
            content_w = max(content_w, title_w)
            for key, description in section.entries:
                content_w = max(
                    content_w,
                    self._entry_width(
                        font,
                        key,
                        description,
                        key_column_width=key_column_width,
                        entry_gap=entry_gap,
                    ),
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
            title_surf = font.render(section.title, True, HIGHLIGHT)
            panel.blit(title_surf, (self._padding, y))
            y += row_stride

            sep_surf = self._dash_separator(font, content_w)
            panel.blit(sep_surf, (self._padding, y))
            y += row_stride

            for key, description in section.entries:
                self._blit_entry(
                    panel,
                    font,
                    key,
                    description,
                    self._padding,
                    y,
                    key_column_width=key_column_width,
                    entry_gap=entry_gap,
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
        self._panel_rect = clip_rect_to_surface(
            (pos[0], pos[1], panel_w, panel_h),
            surface,
        )
