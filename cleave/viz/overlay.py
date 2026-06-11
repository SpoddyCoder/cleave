"""Live tuning tree overlay for the Cleave visualizer.

Row typography: LABEL prefixes, VALUE defaults, DISABLED/LOCKED state overrides.
See cleave/viz/theme.py and .cursor/rules/live-tuning-ui.mdc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Literal

import pygame

from cleave.config import RenderOverlayPosition
from cleave.effects.registry import effect_roster
from cleave.viz.confirm import ConfirmDialog
from cleave.viz.text_fit import (
    fit_counter_label_to_width,
    fit_path_label_to_width,
    fit_text_to_width,
)
from cleave.viz.playback import format_mmss
from cleave.viz.material_icons import (
    FILE_GLYPH,
    FOLDER_GLYPH,
    LOCK_GLYPH,
    VISIBILITY_GLYPH,
    VISIBILITY_OFF_GLYPH,
    VISIBILITY_ICON_PAD_X,
    render_glyph,
    render_transport_icons,
    row_icon_prefix_width,
    track_header_lock_suffix_width,
    visibility_icon_slot_width,
)
from cleave.viz.theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    DISABLED,
    FADE_DURATION_SEC,
    HIGHLIGHT,
    HOLD_IDLE_SEC,
    LABEL,
    LOCKED,
    LOCK_ICON,
    MOVE_MODE,
    PANEL_CONTENT_MAX_WIDTH,
    PRESET_FILE_ICON,
    PRESET_ICON,
    SOLO_BG,
    VALUE,
)

Anchor = Literal["topleft", "bottomleft"]

FOOTER_ROWS_WITH_OVERWRITE = 4
FOOTER_ROWS_WITHOUT_OVERWRITE = 3
TREE_INDENT = 16
ROW_ICON_SUFFIX_GAP = 4


class RowKind(Enum):
    TRACK_HEADER = auto()
    TRACK_PRESET_DIR = auto()
    TRACK_PRESET = auto()
    TRACK_BLEND = auto()
    TRACK_OPACITY = auto()
    TRACK_BEAT = auto()
    TRACK_EFFECTS_HEADER = auto()
    TRACK_EFFECT = auto()
    RENDER_OVERLAY_HEADER = auto()
    RENDER_OVERLAY_POSITION = auto()
    RENDER_OVERLAY_FONT_SIZE = auto()
    RENDER_OVERLAY_OPACITY = auto()
    RENDER_OVERLAY_BORDER_WIDTH = auto()
    RENDER_OVERLAY_START = auto()
    RENDER_OVERLAY_DISPLAY_TIME = auto()
    CONFIG_HEADER = auto()
    TRANSPORT = auto()
    SAVE_AS_NEW_CONFIG = auto()
    OVERWRITE_CONFIG = auto()


@dataclass(frozen=True)
class RowDescriptor:
    kind: RowKind
    stem: str | None = None
    effect_id: str | None = None
    driver_slug: str | None = None


@dataclass
class TrackBlock:
    stem: str
    preset_dir_label: str
    preset_label: str
    blend_mode: str
    opacity_pct: int
    beat_sensitivity: float
    effects: dict[str, dict[str, int]]
    effects_expanded: bool = False
    enabled: bool = True
    expanded: bool = False
    locked: bool = False
    preset_empty: bool = False


@dataclass
class RenderOverlayBlock:
    enabled: bool = True
    expanded: bool = False
    position: RenderOverlayPosition = "bottom-left"
    font_size: int = 10
    opacity_pct: int = 100
    border_width: int = 2
    start: float = 10.0
    display_time: float = 30.0
    solo: bool = False


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
    active_config_label: str = "cleave-viz.yaml"
    solo_stem: str | None = None
    solo_active: bool = False
    render_overlay: RenderOverlayBlock = field(default_factory=RenderOverlayBlock)


def footer_row_count(state: TuningViewState) -> int:
    return (
        FOOTER_ROWS_WITH_OVERWRITE
        if state.allow_overwrite
        else FOOTER_ROWS_WITHOUT_OVERWRITE
    )


_FOOTER_ROW_KINDS = frozenset(
    {
        RowKind.CONFIG_HEADER,
        RowKind.TRANSPORT,
        RowKind.SAVE_AS_NEW_CONFIG,
        RowKind.OVERWRITE_CONFIG,
    }
)


def build_row_layout(state: TuningViewState) -> list[RowDescriptor]:
    rows: list[RowDescriptor] = []
    for stem in state.layer_z_order:
        rows.append(RowDescriptor(RowKind.TRACK_HEADER, stem=stem))
        rows.append(RowDescriptor(RowKind.TRACK_PRESET_DIR, stem=stem))
        rows.append(RowDescriptor(RowKind.TRACK_PRESET, stem=stem))
        rows.append(RowDescriptor(RowKind.TRACK_BLEND, stem=stem))
        rows.append(RowDescriptor(RowKind.TRACK_OPACITY, stem=stem))
        rows.append(RowDescriptor(RowKind.TRACK_BEAT, stem=stem))
        rows.append(RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, stem=stem))
        block = state.tracks[stem]
        if block.effects_expanded:
            for effect_def in effect_roster(stem):
                rows.append(
                    RowDescriptor(
                        RowKind.TRACK_EFFECT,
                        stem=stem,
                        effect_id=effect_def.effect_id,
                        driver_slug=effect_def.driver_slug,
                    )
                )
    rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_HEADER))
    if state.render_overlay.expanded:
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_POSITION))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_FONT_SIZE))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_BORDER_WIDTH))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_START))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_DISPLAY_TIME))
    rows.append(RowDescriptor(RowKind.CONFIG_HEADER))
    rows.append(RowDescriptor(RowKind.TRANSPORT))
    rows.append(RowDescriptor(RowKind.SAVE_AS_NEW_CONFIG))
    if state.allow_overwrite:
        rows.append(RowDescriptor(RowKind.OVERWRITE_CONFIG))
    return rows


def track_row_count(state: TuningViewState) -> int:
    return sum(
        1
        for row in build_row_layout(state)
        if row.kind not in _FOOTER_ROW_KINDS
    )


def row_descriptor(state: TuningViewState, index: int) -> RowDescriptor:
    layout = build_row_layout(state)
    if index < 0 or index >= len(layout):
        raise IndexError(index)
    return layout[index]


def find_row(
    state: TuningViewState,
    stem: str,
    kind: RowKind,
    *,
    effect_id: str | None = None,
    driver_slug: str | None = None,
) -> int:
    for index, desc in enumerate(build_row_layout(state)):
        if desc.kind != kind or desc.stem != stem:
            continue
        if kind == RowKind.TRACK_EFFECT:
            if desc.effect_id != effect_id or desc.driver_slug != driver_slug:
                continue
        return index
    raise ValueError(f"no row for stem={stem!r} kind={kind!r}")


def find_row_by_kind(state: TuningViewState, kind: RowKind) -> int:
    for index, desc in enumerate(build_row_layout(state)):
        if desc.kind == kind:
            return index
    raise ValueError(f"no row for kind={kind!r}")


def row_count(state: TuningViewState) -> int:
    return len(build_row_layout(state))


_SUB_ROW_KINDS = frozenset(
    {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.TRACK_EFFECT,
    }
)

_EFFECT_SUB_ROW_KINDS = frozenset({RowKind.TRACK_EFFECT})

_RENDER_OVERLAY_SUB_ROW_KINDS = frozenset(
    {
        RowKind.RENDER_OVERLAY_POSITION,
        RowKind.RENDER_OVERLAY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_OPACITY,
        RowKind.RENDER_OVERLAY_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_START,
        RowKind.RENDER_OVERLAY_DISPLAY_TIME,
    }
)

_LOCKED_NAVIGABLE_SUB_ROW_KINDS = frozenset({RowKind.TRACK_EFFECTS_HEADER})

_LABELED_SUB_ROW_KINDS = frozenset(
    {
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECT,
        RowKind.RENDER_OVERLAY_POSITION,
        RowKind.RENDER_OVERLAY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_OPACITY,
        RowKind.RENDER_OVERLAY_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_START,
        RowKind.RENDER_OVERLAY_DISPLAY_TIME,
    }
)


def track_sub_rows_visible(state: TuningViewState, stem: str) -> bool:
    return state.tracks[stem].expanded


def track_sub_rows_navigable(state: TuningViewState, stem: str) -> bool:
    block = state.tracks[stem]
    return block.expanded and not block.locked


def _sub_row_visible(state: TuningViewState, index: int) -> bool:
    desc = row_descriptor(state, index)
    if desc.kind in _RENDER_OVERLAY_SUB_ROW_KINDS:
        return state.render_overlay.expanded
    stem = desc.stem
    if stem is None or desc.kind not in _SUB_ROW_KINDS:
        return True
    block = state.tracks[stem]
    if not block.expanded:
        return False
    if desc.kind in _EFFECT_SUB_ROW_KINDS:
        return block.effects_expanded
    return True


def row_visible(state: TuningViewState, index: int) -> bool:
    return _sub_row_visible(state, index)


def visible_row_indices(state: TuningViewState) -> list[int]:
    """Row indices drawn in the panel (sub-rows hidden when collapsed)."""
    return [index for index in range(row_count(state)) if row_visible(state, index)]


def navigable_row_indices(state: TuningViewState) -> list[int]:
    """Row indices reachable via Up/Down (sub-rows skipped when collapsed)."""
    indices: list[int] = []
    for index in range(row_count(state)):
        desc = row_descriptor(state, index)
        if desc.kind == RowKind.CONFIG_HEADER:
            continue
        if desc.kind in _RENDER_OVERLAY_SUB_ROW_KINDS:
            if not state.render_overlay.expanded:
                continue
        elif desc.kind in _SUB_ROW_KINDS:
            stem = desc.stem
            assert stem is not None
            block = state.tracks[stem]
            if not block.expanded:
                continue
            if block.locked and desc.kind not in _LOCKED_NAVIGABLE_SUB_ROW_KINDS:
                continue
            if desc.kind in _EFFECT_SUB_ROW_KINDS and not block.effects_expanded:
                continue
        indices.append(index)
    return indices


def quick_nav_row_indices(state: TuningViewState) -> list[int]:
    """Row indices for Ctrl+Up/Down: layer headers and transport only."""
    indices: list[int] = []
    for index in range(row_count(state)):
        kind = row_kind(state, index)
        if kind in (
            RowKind.TRACK_HEADER,
            RowKind.RENDER_OVERLAY_HEADER,
            RowKind.TRANSPORT,
        ):
            indices.append(index)
    return indices


def row_stem(state: TuningViewState, index: int) -> str | None:
    return row_descriptor(state, index).stem


def row_kind(state: TuningViewState, index: int) -> RowKind:
    return row_descriptor(state, index).kind


def row_effect(
    state: TuningViewState, index: int
) -> tuple[str, str] | None:
    desc = row_descriptor(state, index)
    if desc.kind != RowKind.TRACK_EFFECT:
        return None
    assert desc.effect_id is not None and desc.driver_slug is not None
    return desc.effect_id, desc.driver_slug


def _effect_pct(block: TrackBlock, effect_id: str, driver_slug: str) -> int:
    return block.effects.get(effect_id, {}).get(driver_slug, 0)


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

    if kind == RowKind.RENDER_OVERLAY_HEADER:
        arrow = "▼" if state.render_overlay.expanded else "▶"
        return f"Render: OVERLAY {arrow}"

    block_ro = state.render_overlay
    if kind == RowKind.RENDER_OVERLAY_POSITION:
        return f"└─ position: {block_ro.position}"
    if kind == RowKind.RENDER_OVERLAY_FONT_SIZE:
        return f"└─ font size: {block_ro.font_size}"
    if kind == RowKind.RENDER_OVERLAY_OPACITY:
        return f"└─ background opacity: {block_ro.opacity_pct}%"
    if kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
        return f"└─ border width: {block_ro.border_width}"
    if kind == RowKind.RENDER_OVERLAY_START:
        return f"└─ start time: {block_ro.start:.1f}"
    if kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
        return f"└─ display time: {block_ro.display_time:.1f}"

    stem = row_stem(state, index)
    assert stem is not None
    block = state.tracks[stem]
    if kind == RowKind.TRACK_HEADER:
        layer_num = state.layer_z_order.index(stem) + 1
        arrow = "▼" if block.expanded else "▶"
        return f"Layer {layer_num}: {stem.upper()} {arrow}"
    if kind == RowKind.TRACK_PRESET_DIR:
        return block.preset_dir_label
    if kind == RowKind.TRACK_PRESET:
        return block.preset_label
    if kind == RowKind.TRACK_BLEND:
        return f"└─ blend mode: {block.blend_mode}"
    if kind == RowKind.TRACK_OPACITY:
        return f"└─ opacity: {block.opacity_pct}%"
    if kind == RowKind.TRACK_BEAT:
        return f"└─ beat sensitivity: {block.beat_sensitivity:.2f}"
    if kind == RowKind.TRACK_EFFECTS_HEADER:
        arrow = "▼" if block.effects_expanded else "▶"
        return f"└─ cleave effects {arrow}"
    assert kind == RowKind.TRACK_EFFECT
    effect = row_effect(state, index)
    assert effect is not None
    effect_id, driver_slug = effect
    pct = _effect_pct(block, effect_id, driver_slug)
    return f"└─ {effect_id} ({driver_slug}): {pct}%"


def _labeled_sub_row_prefix(state: TuningViewState, index: int) -> str:
    kind = row_kind(state, index)
    if kind == RowKind.TRACK_BLEND:
        return "└─ blend mode: "
    if kind == RowKind.TRACK_OPACITY:
        return "└─ opacity: "
    if kind == RowKind.TRACK_BEAT:
        return "└─ beat sensitivity: "
    if kind == RowKind.RENDER_OVERLAY_POSITION:
        return "└─ position: "
    if kind == RowKind.RENDER_OVERLAY_FONT_SIZE:
        return "└─ font size: "
    if kind == RowKind.RENDER_OVERLAY_OPACITY:
        return "└─ background opacity: "
    if kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
        return "└─ border width: "
    if kind == RowKind.RENDER_OVERLAY_START:
        return "└─ start time: "
    if kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
        return "└─ display time: "
    assert kind == RowKind.TRACK_EFFECT
    effect = row_effect(state, index)
    assert effect is not None
    effect_id, driver_slug = effect
    return f"└─ {effect_id} ({driver_slug}): "


def _labeled_sub_row_value(state: TuningViewState, index: int) -> str:
    kind = row_kind(state, index)
    block_ro = state.render_overlay
    if kind == RowKind.RENDER_OVERLAY_POSITION:
        return block_ro.position
    if kind == RowKind.RENDER_OVERLAY_FONT_SIZE:
        return str(block_ro.font_size)
    if kind == RowKind.RENDER_OVERLAY_OPACITY:
        return f"{block_ro.opacity_pct}%"
    if kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
        return str(block_ro.border_width)
    if kind == RowKind.RENDER_OVERLAY_START:
        return f"{block_ro.start:.1f}"
    if kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
        return f"{block_ro.display_time:.1f}"
    stem = row_stem(state, index)
    assert stem is not None
    block = state.tracks[stem]
    if kind == RowKind.TRACK_BLEND:
        return block.blend_mode
    if kind == RowKind.TRACK_OPACITY:
        return f"{block.opacity_pct}%"
    if kind == RowKind.TRACK_BEAT:
        return f"{block.beat_sensitivity:.2f}"
    assert kind == RowKind.TRACK_EFFECT
    effect = row_effect(state, index)
    assert effect is not None
    effect_id, driver_slug = effect
    return f"{_effect_pct(block, effect_id, driver_slug)}%"


def _fit_labeled_sub_row_value(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> str:
    budget = max_content_width - _row_indent(state, index)
    budget -= font.size(_labeled_sub_row_prefix(state, index))[0]
    return fit_text_to_width(font, _labeled_sub_row_value(state, index), budget)


def _render_label_value_row(
    font: pygame.font.Font,
    *,
    prefix: str,
    value: str,
    value_color: tuple[int, int, int],
    line_height: int,
    suffix_surf: pygame.Surface | None = None,
    suffix_gap: int = 0,
) -> pygame.Surface:
    prefix_surf = font.render(prefix, True, LABEL)
    value_surf = font.render(value, True, value_color)
    label_w = prefix_surf.get_width() + value_surf.get_width()
    if suffix_surf is not None:
        label_w += suffix_gap + suffix_surf.get_width()

    label_surf = pygame.Surface((label_w, line_height), pygame.SRCALPHA)
    x = 0
    label_surf.blit(prefix_surf, (x, 0))
    x += prefix_surf.get_width()
    label_surf.blit(value_surf, (x, 0))
    if suffix_surf is not None:
        x += value_surf.get_width() + suffix_gap
        label_surf.blit(suffix_surf, (x, 0))
    return label_surf


def _track_header_layer_prefix(state: TuningViewState, index: int) -> str:
    stem = row_stem(state, index)
    assert stem is not None
    layer_num = state.layer_z_order.index(stem) + 1
    return f"Layer {layer_num}: "


def _track_header_expand_suffix(expanded: bool) -> str:
    arrow = "▼" if expanded else "▶"
    return f" {arrow}"


def _render_overlay_header_prefix() -> str:
    return "Render: "


def render_visibility_icon(
    *,
    enabled: bool,
    solo: bool,
    line_height: int,
) -> pygame.Surface:
    glyph = VISIBILITY_GLYPH if enabled else VISIBILITY_OFF_GLYPH
    color = VALUE if (enabled or solo) else DISABLED
    glyph_surf = render_glyph(glyph, color=color, line_height=line_height)
    slot_w = visibility_icon_slot_width(line_height)
    surf = pygame.Surface((slot_w, line_height), pygame.SRCALPHA)
    if solo:
        pygame.draw.rect(surf, SOLO_BG, (0, 0, slot_w, line_height))
    surf.blit(glyph_surf, (VISIBILITY_ICON_PAD_X, 0))
    return surf


def track_header_prefix_width(font: pygame.font.Font) -> int:
    line_h = font.get_linesize()
    icon_w = render_visibility_icon(
        enabled=True, solo=False, line_height=line_h
    ).get_width()
    return icon_w + ROW_ICON_SUFFIX_GAP


def _effects_header_prefix() -> str:
    return "└─ cleave effects "


def _effects_header_expand_value(expanded: bool) -> str:
    return "▼" if expanded else "▶"


def _fit_track_header_stem(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> str:
    stem = row_stem(state, index)
    assert stem is not None
    block = state.tracks[stem]
    locked = block.locked
    budget = max_content_width - _row_indent(state, index)
    budget -= track_header_prefix_width(font)
    budget -= font.size(_track_header_layer_prefix(state, index))[0]
    budget -= font.size(_track_header_expand_suffix(block.expanded))[0]
    if locked:
        budget -= track_header_lock_suffix_width(font.get_linesize())
    return fit_text_to_width(font, stem.upper(), budget)


def _render_track_header_label(
    font: pygame.font.Font,
    *,
    layer_prefix: str,
    stem_text: str,
    value_color: tuple[int, int, int],
    expanded: bool,
    locked: bool,
    line_height: int,
) -> pygame.Surface:
    arrow = _track_header_expand_suffix(expanded)
    prefix_surf = font.render(layer_prefix, True, LABEL)
    stem_surf = font.render(stem_text, True, value_color)
    arrow_surf = font.render(arrow, True, value_color)
    lock_surf = (
        render_glyph(LOCK_GLYPH, color=LOCK_ICON, line_height=line_height)
        if locked
        else None
    )

    label_w = prefix_surf.get_width() + stem_surf.get_width() + arrow_surf.get_width()
    if lock_surf is not None:
        label_w += ROW_ICON_SUFFIX_GAP + lock_surf.get_width()

    label_surf = pygame.Surface((label_w, line_height), pygame.SRCALPHA)
    x = 0
    label_surf.blit(prefix_surf, (x, 0))
    x += prefix_surf.get_width()
    label_surf.blit(stem_surf, (x, 0))
    x += stem_surf.get_width()
    label_surf.blit(arrow_surf, (x, 0))
    if lock_surf is not None:
        x += arrow_surf.get_width() + ROW_ICON_SUFFIX_GAP
        label_surf.blit(lock_surf, (x, 0))
    return label_surf


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

    if kind in {RowKind.CONFIG_HEADER, RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET}:
        icon_w = row_icon_prefix_width(font.get_linesize())
        if kind == RowKind.CONFIG_HEADER:
            return fit_path_label_to_width(font, text, budget - icon_w)
        return fit_counter_label_to_width(font, text, budget - icon_w)
    if kind == RowKind.TRACK_HEADER:
        stem = row_stem(state, index)
        assert stem is not None
        expanded = state.tracks[stem].expanded
        return (
            _track_header_layer_prefix(state, index)
            + _fit_track_header_stem(
                font, state, index, max_content_width=max_content_width
            )
            + _track_header_expand_suffix(expanded)
        )
    if kind == RowKind.RENDER_OVERLAY_HEADER:
        expanded = state.render_overlay.expanded
        return (
            _render_overlay_header_prefix()
            + "OVERLAY"
            + _track_header_expand_suffix(expanded)
        )
    if kind in _LABELED_SUB_ROW_KINDS:
        return _labeled_sub_row_prefix(state, index) + _fit_labeled_sub_row_value(
            font, state, index, max_content_width=max_content_width
        )
    return fit_text_to_width(font, text, budget)


def _row_indent(state: TuningViewState, index: int) -> int:
    kind = row_kind(state, index)
    if kind in {RowKind.TRACK_HEADER, RowKind.RENDER_OVERLAY_HEADER}:
        return 0
    if kind == RowKind.TRACK_EFFECT:
        return TREE_INDENT * 2
    if kind in {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECTS_HEADER,
    } | _RENDER_OVERLAY_SUB_ROW_KINDS:
        return TREE_INDENT
    return 0


def _track_disabled(state: TuningViewState, stem: str) -> bool:
    return not state.tracks[stem].enabled


def _row_value_color(state: TuningViewState, index: int) -> tuple[int, int, int]:
    """Return the VALUE-role color for a row (before label/value split rendering)."""
    kind = row_kind(state, index)
    stem = row_stem(state, index)
    if kind == RowKind.CONFIG_HEADER:
        return LABEL

    if kind in {RowKind.RENDER_OVERLAY_HEADER, *_RENDER_OVERLAY_SUB_ROW_KINDS}:
        if not state.render_overlay.enabled:
            return DISABLED

    if state.solo_active and kind in (
        RowKind.SAVE_AS_NEW_CONFIG,
        RowKind.OVERWRITE_CONFIG,
    ):
        return DISABLED

    if (
        kind == RowKind.TRACK_PRESET
        and stem is not None
        and state.tracks[stem].preset_empty
    ):
        return DISABLED

    if stem is not None and state.move_mode_stem == stem:
        return MOVE_MODE

    if index == state.focus_index:
        return HIGHLIGHT

    if stem is not None and _track_disabled(state, stem):
        return DISABLED

    if (
        stem is not None
        and state.tracks[stem].locked
        and kind in _SUB_ROW_KINDS
    ):
        return LOCKED

    return VALUE


def _row_bg_color(state: TuningViewState, index: int) -> tuple[int, int, int] | None:
    stem = row_stem(state, index)
    if stem is not None and state.move_mode_stem == stem:
        return MOVE_MODE
    if index == state.focus_index:
        return HIGHLIGHT
    return None


def _clip_rect_to_surface(
    rect: tuple[int, int, int, int],
    surface: pygame.Surface,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with surface bounds (for subsurface-safe panel_rect)."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    sw, sh = surface.get_width(), surface.get_height()
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + w, sw)
    bottom = min(y + h, sh)
    clip_w = right - left
    clip_h = bottom - top
    if clip_w <= 0 or clip_h <= 0:
        return None
    return (left, top, clip_w, clip_h)


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
        track_rows_boundary = track_row_count(state)
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
            color = _row_value_color(state, index)

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
            elif kind == RowKind.TRACK_HEADER:
                stem = row_stem(state, index)
                block = state.tracks[stem] if stem is not None else None
                enabled = block.enabled if block is not None else True
                solo = stem is not None and state.solo_stem == stem
                locked = block.locked if block is not None else False
                prefix_surf = render_visibility_icon(
                    enabled=enabled, solo=solo, line_height=line_h
                )
                layer_prefix = _track_header_layer_prefix(state, index)
                stem_text = _fit_track_header_stem(font, state, index)
                expanded = block.expanded if block is not None else False
                label_surf = _render_track_header_label(
                    font,
                    layer_prefix=layer_prefix,
                    stem_text=stem_text,
                    value_color=color,
                    expanded=expanded,
                    locked=locked,
                    line_height=line_h,
                )
                row_surfaces.append(prefix_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + prefix_surf.get_width() + label_surf.get_width()
                )
            elif kind == RowKind.RENDER_OVERLAY_HEADER:
                block_ro = state.render_overlay
                prefix_surf = render_visibility_icon(
                    enabled=block_ro.enabled,
                    solo=block_ro.solo,
                    line_height=line_h,
                )
                label_surf = _render_track_header_label(
                    font,
                    layer_prefix=_render_overlay_header_prefix(),
                    stem_text="OVERLAY",
                    value_color=color,
                    expanded=block_ro.expanded,
                    locked=False,
                    line_height=line_h,
                )
                row_surfaces.append(prefix_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + prefix_surf.get_width() + label_surf.get_width()
                )
            elif kind in {
                RowKind.CONFIG_HEADER,
                RowKind.TRACK_PRESET_DIR,
                RowKind.TRACK_PRESET,
            }:
                if kind == RowKind.TRACK_PRESET_DIR:
                    glyph = FOLDER_GLYPH
                    icon_color = PRESET_ICON
                else:
                    glyph = FILE_GLYPH
                    icon_color = PRESET_FILE_ICON
                icon_surf = render_glyph(glyph, color=icon_color, line_height=line_h)
                label = fit_row_text(font, state, index)
                label_surf = font.render(label, True, color)
                row_surfaces.append(icon_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + icon_surf.get_width() + label_surf.get_width()
                )
            elif kind == RowKind.TRACK_EFFECTS_HEADER:
                stem = row_stem(state, index)
                assert stem is not None
                block = state.tracks[stem]
                surf = _render_label_value_row(
                    font,
                    prefix=_effects_header_prefix(),
                    value=_effects_header_expand_value(block.effects_expanded),
                    value_color=color,
                    line_height=line_h,
                )
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())
            elif kind in _LABELED_SUB_ROW_KINDS:
                prefix = _labeled_sub_row_prefix(state, index)
                value = _fit_labeled_sub_row_value(font, state, index)
                surf = _render_label_value_row(
                    font,
                    prefix=prefix,
                    value=value,
                    value_color=color,
                    line_height=line_h,
                )
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())
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
            toast_surf = font.render(toast_text, True, DISABLED)

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
        self._panel_rect = _clip_rect_to_surface(
            (pos[0], pos[1], panel_w, panel_h),
            surface,
        )
