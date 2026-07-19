"""Retained surfaces and signatures for the context-sensitive help panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

import pygame

from cleave.effects.registry import EFFECT_IDS
from cleave.viz.help_content import (
    DescriptionSection,
    HelpContent,
    sections_for,
)
from cleave.viz.overlay_upload import OverlayGpuState, UploadSignature
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.theme import LABEL, VALUE


@dataclass(frozen=True)
class HelpContentSignature:
    """Hashable identity of help content — all inputs to sections_for()."""

    kind: RowKind
    effect_id: str | None
    timeline_enabled: bool
    timeline_submenu_focused: bool
    paused: bool
    timeline_recording: bool
    timeline_override_active: bool
    preset_switching_scope: str | None
    preset_curation: bool = False


@dataclass
class HelpPanelCache:
    panel: pygame.Surface | None = None
    panel_signature: HelpContentSignature | None = None
    panel_size: tuple[int, int] | None = None
    gpu: OverlayGpuState = field(default_factory=OverlayGpuState)


def help_content_signature(
    focus: RowDescriptor,
    *,
    timeline_enabled: bool,
    timeline_submenu_focused: bool,
    paused: bool,
    timeline_recording: bool,
    timeline_override_active: bool,
    preset_switching_scope: str | None,
    preset_curation: bool = False,
) -> HelpContentSignature:
    return HelpContentSignature(
        kind=focus.kind,
        effect_id=focus.effect_id,
        timeline_enabled=timeline_enabled,
        timeline_submenu_focused=timeline_submenu_focused,
        paused=paused,
        timeline_recording=timeline_recording,
        timeline_override_active=timeline_override_active,
        preset_switching_scope=preset_switching_scope,
        preset_curation=preset_curation,
    )


def help_upload_signature(
    content_sig: HelpContentSignature,
    screen_rect: tuple[int, int, int, int],
    panel_size: tuple[int, int],
) -> UploadSignature:
    del panel_size  # active upload region comes from screen placement
    return UploadSignature(
        active_size=(screen_rect[2], screen_rect[3]),
        screen_rect=screen_rect,
        content_hash=(content_sig,),
    )


def _entry_gap(font: pygame.font.Font) -> int:
    return font.size("  ")[0]


def _max_key_width(
    font: pygame.font.Font, sections: tuple[HelpContent, ...]
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
    font: pygame.font.Font,
    key: str,
    description: str,
    *,
    key_column_width: int,
    entry_gap: int,
) -> int:
    desc_w = font.render(description, True, VALUE).get_width()
    return key_column_width + entry_gap + desc_w


def _line_width(font: pygame.font.Font, text: str) -> int:
    return font.render(text, True, VALUE).get_width()


def _section_content_width(
    font: pygame.font.Font,
    section: HelpContent,
    *,
    key_column_width: int,
    entry_gap: int,
) -> int:
    from cleave.viz.theme import HIGHLIGHT

    title_w = font.render(section.title, True, HIGHLIGHT).get_width()
    if isinstance(section, DescriptionSection):
        line_widths = tuple(_line_width(font, line) for line in section.lines)
        entry_widths = tuple(
            _entry_width(
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
        _entry_width(
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


def _section_line_count(section: HelpContent) -> int:
    if isinstance(section, DescriptionSection):
        body_lines = len(section.lines) + len(section.entries)
    else:
        body_lines = len(section.entries)
    return 2 + body_lines


def compute_help_panel_size(
    font: pygame.font.Font,
    sections: tuple[HelpContent, ...],
    *,
    padding: int,
    line_gap: int,
) -> tuple[int, int]:
    """Return (panel_w, panel_h) for a section list."""
    entry_gap = _entry_gap(font)
    key_column_width = _max_key_width(font, sections)
    content_w = max(
        (
            _section_content_width(
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
    row_stride = line_h + line_gap
    line_count = sum(_section_line_count(section) for section in sections)
    line_count += max(0, len(sections) - 1)
    content_h = line_count * row_stride - line_gap
    return content_w + padding * 2, content_h + padding * 2


def _help_flag_variants() -> tuple[dict[str, bool], ...]:
    """Boolean flag combinations that change sections_for() output."""
    keys = (
        "timeline_enabled",
        "timeline_submenu_focused",
        "paused",
        "timeline_recording",
        "timeline_override_active",
    )
    variants: list[dict[str, bool]] = []
    for values in product((False, True), repeat=len(keys)):
        variants.append(dict(zip(keys, values)))
    return tuple(variants)


_CAPACITY_CACHE: dict[tuple[object, ...], tuple[int, int]] = {}


def help_panel_max_dimensions(
    viewport_w: int,
    viewport_h: int,
    *,
    margin: tuple[int, int],
    padding: int,
    line_gap: int,
    font_size: int,
) -> tuple[int, int]:
    """Worst-case help panel size for stable GPU texture capacity.

  Iterates every RowKind (and effect id for TRACK_EFFECT) through
  sections_for() with all boolean flag combinations and both preset
  switching modes. Viewport size is accepted for API symmetry with the
  tuning panel helper; measured content drives capacity so textures are
  never undersized.
    """
    cache_key = (
        viewport_w,
        viewport_h,
        margin,
        padding,
        line_gap,
        font_size,
    )
    cached = _CAPACITY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    font = pygame.font.SysFont("monospace", font_size)
    max_w = 0
    max_h = 0
    for row_kind in RowKind:
        effect_ids: tuple[str | None, ...] = (
            tuple(EFFECT_IDS) if row_kind == RowKind.TRACK_EFFECT else (None,)
        )
        for effect_id in effect_ids:
            for flags in _help_flag_variants():
                for preset_switching_scope in (None, "user_defined"):
                    sections = sections_for(
                        row_kind,
                        effect_id=effect_id,
                        preset_switching_scope=preset_switching_scope,
                        **flags,
                    )
                    panel_w, panel_h = compute_help_panel_size(
                        font,
                        sections,
                        padding=padding,
                        line_gap=line_gap,
                    )
                    max_w = max(max_w, panel_w)
                    max_h = max(max_h, panel_h)
    margin_x, margin_y = margin
    usable_w = max(1, viewport_w - margin_x * 2)
    usable_h = max(1, viewport_h - margin_y * 2)
    result = max(max_w, usable_w), max(max_h, usable_h)
    _CAPACITY_CACHE[cache_key] = result
    return result
