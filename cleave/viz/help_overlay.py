"""Context-sensitive help panel for the Cleave editor."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.viz.help_content import (
    DescriptionSection,
    HelpContent,
    sections_for,
)
from cleave.viz.help_panel_cache import (
    HelpPanelCache,
    compute_help_panel_size,
    help_content_signature,
    help_panel_max_dimensions,
    help_upload_signature,
)
from cleave.viz.overlay_upload import OverlayGpuState, UploadPlan, UploadSignature, upload_plan_for_signature
from cleave.viz.row_semantics import RowDescriptor
from cleave.viz.tuning_panel_draw import clip_rect_to_bounds
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
class ComposedHelpPanel:
    upload_surface: pygame.Surface
    panel_size: tuple[int, int]
    screen_rect: tuple[int, int, int, int]
    upload_plan: UploadPlan
    upload_signature: UploadSignature
    capacity: tuple[int, int]


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
        self._cache = HelpPanelCache()

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        return self._panel_rect

    @property
    def gpu_state(self) -> OverlayGpuState:
        return self._cache.gpu

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    def _entry_gap(self, font: pygame.font.Font) -> int:
        return font.size("  ")[0]

    def _section_entries(self, section: HelpContent) -> tuple[tuple[str, str], ...]:
        return section.entries

    def _max_key_width(
        self, font: pygame.font.Font, sections: tuple[HelpContent, ...]
    ) -> int:
        return max(
            (
                font.render(key, True, LABEL).get_width()
                for section in sections
                for key, _ in self._section_entries(section)
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

    def _line_width(self, font: pygame.font.Font, text: str) -> int:
        return font.render(text, True, VALUE).get_width()

    def _section_content_width(
        self,
        font: pygame.font.Font,
        section: HelpContent,
        *,
        key_column_width: int,
        entry_gap: int,
    ) -> int:
        title_w = font.render(section.title, True, HIGHLIGHT).get_width()
        if isinstance(section, DescriptionSection):
            line_widths = tuple(self._line_width(font, line) for line in section.lines)
            entry_widths = tuple(
                self._entry_width(
                    font,
                    key,
                    description,
                    key_column_width=key_column_width,
                    entry_gap=entry_gap,
                )
                for key, description in section.entries
            )
            content_widths = line_widths + entry_widths
            if not content_widths:
                return title_w
            return max(title_w, *content_widths)
        entry_widths = tuple(
            self._entry_width(
                font,
                key,
                description,
                key_column_width=key_column_width,
                entry_gap=entry_gap,
            )
            for key, description in section.entries
        )
        if not entry_widths:
            return title_w
        return max(title_w, *entry_widths)

    def _section_line_count(self, section: HelpContent) -> int:
        if isinstance(section, DescriptionSection):
            body_lines = len(section.lines) + len(section.entries)
        else:
            body_lines = len(section.entries)
        return 2 + body_lines

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

    def _blit_section(
        self,
        panel: pygame.Surface,
        font: pygame.font.Font,
        section: HelpContent,
        y: int,
        *,
        content_w: int,
        key_column_width: int,
        entry_gap: int,
        row_stride: int,
    ) -> int:
        title_surf = font.render(section.title, True, HIGHLIGHT)
        panel.blit(title_surf, (self._padding, y))
        y += row_stride

        sep_surf = self._dash_separator(font, content_w)
        panel.blit(sep_surf, (self._padding, y))
        y += row_stride

        if isinstance(section, DescriptionSection):
            for line in section.lines:
                line_surf = font.render(line, True, VALUE)
                panel.blit(line_surf, (self._padding, y))
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
            return y

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
        return y

    def _build_panel_surface(
        self,
        font: pygame.font.Font,
        sections: tuple[HelpContent, ...],
        *,
        panel_w: int,
        panel_h: int,
    ) -> pygame.Surface:
        entry_gap = self._entry_gap(font)
        key_column_width = self._max_key_width(font, sections)
        content_w = max(
            (
                self._section_content_width(
                    font,
                    section,
                    key_column_width=key_column_width,
                    entry_gap=entry_gap,
                )
                for section in sections
            ),
            default=0,
        )
        line_h = font.get_linesize()
        row_stride = line_h + self._line_gap

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, BACKGROUND_ALPHA))

        y = self._padding
        for section_index, section in enumerate(sections):
            y = self._blit_section(
                panel,
                font,
                section,
                y,
                content_w=content_w,
                key_column_width=key_column_width,
                entry_gap=entry_gap,
                row_stride=row_stride,
            )
            if section_index < len(sections) - 1:
                y += row_stride

        if BORDER_WIDTH > 0:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, 255),
                panel.get_rect(),
                width=BORDER_WIDTH,
            )
        return panel

    def compose_panel(
        self,
        focus: RowDescriptor,
        *,
        viewport_width: int,
        viewport_height: int,
        timeline_enabled: bool = False,
        timeline_submenu_focused: bool = False,
        paused: bool = False,
        timeline_recording: bool = False,
        timeline_override_active: bool = False,
        preset_switching: str | None = None,
    ) -> ComposedHelpPanel | None:
        self._panel_rect = None
        font = self._font_get()
        content_sig = help_content_signature(
            focus,
            timeline_enabled=timeline_enabled,
            timeline_submenu_focused=timeline_submenu_focused,
            paused=paused,
            timeline_recording=timeline_recording,
            timeline_override_active=timeline_override_active,
            preset_switching=preset_switching,
        )
        sections = sections_for(
            focus.kind,
            effect_id=focus.effect_id,
            timeline_enabled=timeline_enabled,
            timeline_submenu_focused=timeline_submenu_focused,
            paused=paused,
            timeline_recording=timeline_recording,
            timeline_override_active=timeline_override_active,
            preset_switching=preset_switching,
        )
        panel_w, panel_h = compute_help_panel_size(
            font,
            sections,
            padding=self._padding,
            line_gap=self._line_gap,
        )
        panel_size = (panel_w, panel_h)
        cache = self._cache

        if (
            cache.panel is not None
            and content_sig == cache.panel_signature
            and cache.panel_size == panel_size
        ):
            panel = cache.panel
        else:
            panel = self._build_panel_surface(
                font,
                sections,
                panel_w=panel_w,
                panel_h=panel_h,
            )
            cache.panel = panel
            cache.panel_signature = content_sig
            cache.panel_size = panel_size

        mx, my = self._margin
        pos = (viewport_width - panel_w - mx, my)
        bounds = clip_rect_to_bounds(
            (pos[0], pos[1], panel_w, panel_h),
            viewport_width,
            viewport_height,
        )
        if bounds is None:
            return None
        self._panel_rect = bounds

        capacity = help_panel_max_dimensions(
            viewport_width,
            viewport_height,
            margin=self._margin,
            padding=self._padding,
            line_gap=self._line_gap,
            font_size=self._font_size,
        )
        upload_signature = help_upload_signature(content_sig, bounds, panel_size)
        src_x = bounds[0] - pos[0]
        src_y = bounds[1] - pos[1]
        active_w, active_h = bounds[2], bounds[3]
        clip_rect = (
            (src_x, src_y, active_w, active_h)
            if src_x != 0 or src_y != 0 or (active_w, active_h) != panel_size
            else ()
        )
        if clip_rect:
            from cleave.viz.overlay_upload import clip_dirty_rects

            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
                dirty_rects=clip_dirty_rects(clip_rect, panel_w, panel_h),
            )
        else:
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
            )

        return ComposedHelpPanel(
            upload_surface=panel,
            panel_size=panel_size,
            screen_rect=bounds,
            upload_plan=upload_plan,
            upload_signature=upload_signature,
            capacity=capacity,
        )

    def draw(
        self,
        surface: pygame.Surface,
        focus: RowDescriptor,
        *,
        timeline_enabled: bool = False,
        timeline_submenu_focused: bool = False,
        paused: bool = False,
        timeline_recording: bool = False,
        timeline_override_active: bool = False,
        preset_switching: str | None = None,
    ) -> None:
        composed = self.compose_panel(
            focus,
            viewport_width=surface.get_width(),
            viewport_height=surface.get_height(),
            timeline_enabled=timeline_enabled,
            timeline_submenu_focused=timeline_submenu_focused,
            paused=paused,
            timeline_recording=timeline_recording,
            timeline_override_active=timeline_override_active,
            preset_switching=preset_switching,
        )
        if composed is None:
            self._panel_rect = None
            return
        panel = self._cache.panel
        assert panel is not None
        mx, my = self._margin
        pos = (surface.get_width() - panel.get_width() - mx, my)
        surface.blit(panel, pos)
