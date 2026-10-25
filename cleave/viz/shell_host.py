"""ImGui menu bar on the live pygame OpenGL window.

One context, one font atlas, one frame per editor draw. Keyboard stays in
``input_dispatch``; this host only feeds mouse input.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pygame
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_ARRAY_BUFFER_BINDING,
    GL_BACK,
    GL_CULL_FACE,
    GL_CURRENT_PROGRAM,
    GL_FRONT,
    GL_POLYGON_MODE,
    glBindBuffer,
    glDisable,
    glEnable,
    glGetIntegerv,
    glIsEnabled,
    glPolygonMode,
    glUseProgram,
)
from imgui_bundle import imgui
from imgui_bundle.python_backends.opengl_backend import ProgrammablePipelineRenderer

from cleave.gl_state import restore_gl_state, save_gl_state
from cleave.viz.commands import Command, CommandContext, MenuSeparator, command_by_id
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.frame_rate import format_fps_value
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.inspector_controls import inspector_command_enabled
from cleave.viz.menu_bar import MenuBarState, menus_for_session
from cleave.viz.navigator import NavNode, build_navigator
from cleave.viz.overlay_primitives import overlay_font_path
from cleave.viz.playback import format_mmss
from cleave.viz.row_hotkeys import activate_inspector_chip, node_header_descriptor
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_sections import (
    INSPECTOR_GROUP_EXPANDED,
    inspector_group_glyph,
)
from cleave.viz.row_spec import (
    apply_field_horizontal,
    format_row_value,
    row_lock_section,
    row_panel_label,
    row_spec,
    section_lock_blocks_mutation,
    section_locked,
)
from cleave.viz.session import TuningSession
from cleave.viz.shell_focus import (
    CycleStop,
    InspectorGroupKey,
    ShellRegion,
    inspector_group_is_open,
)
from cleave.viz.shell_layout import (
    ShellLayout,
    splitter_hit,
    splitter_request_width,
)
from cleave.viz.theme import (
    ACTION,
    BACKGROUND,
    BORDER_COLOR,
    DISABLED,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    HOVER,
    HOVER_BG_ALPHA,
    LABEL,
    MENU_ITEM_HOVER_BG_ALPHA,
    LOCK_ICON,
    NAVIGATOR_BORDER,
    TRANSPORT_RULE,
    VALUE,
    tuning_ui_metrics,
)

RENDERER_CLASS = ProgrammablePipelineRenderer

_HIDDEN = 0.01
# Vertical padding for the menu bar and the transport bar, which shares its height.
# Dear ImGui's default FramePadding.y is 3, which leaves both rows cramped.
_MENU_BAR_FRAME_PADDING_Y = 8.0
_INSPECTOR_INDENT = 16.0
_NAV_LOCK_MARK = "[lock]"
_TRANSPORT_GAP = 16.0
# Border pushed onto navigator and inspector windows.
_PANEL_BORDER_PX = 1.0
# ImDrawList::AddRect insets the stroke path by half a pixel.
_BORDER_PATH_INSET_PX = 0.5
# Anti-aliased lines add this fringe beyond half the stroke thickness.
_AA_LINE_FRINGE_PX = 1.0
_PLAY_GLYPH = "\u25b6"
_PAUSE_GLYPH = "\u275a\u275a"
# One Left/Right step per this many pixels of sideways drag.
_VALUE_DRAG_THRESHOLD_PX = 10.0


@dataclass(frozen=True)
class TransportReadout:
    """Transport bar numbers. The shell host does not read the app."""

    paused: bool
    position_sec: float
    duration_sec: float
    bar_text: str
    fps: float | None
    recording: bool


@dataclass(frozen=True)
class InspectorChip:
    """One inspector header toggle.

    ``id`` is ``enabled``, ``solo``, or ``lock``. ``active`` is on, soloed,
    or locked. The lock label is ``locked`` or ``lock``; solo stays ``solo``.
    """

    id: str
    label: str
    active: bool


@dataclass(frozen=True)
class InspectorHeader:
    """Inspector title line and the header chips for the selected node."""

    title: str
    chips: tuple[InspectorChip, ...] = ()
    descriptor: RowDescriptor | None = None


def transport_parts(readout: TransportReadout) -> list[tuple[str, tuple[int, int, int]]]:
    """Play state, clock, and meters for the transport bar.

    Play and pause use the action role. The clock uses the value role.
    Bar, frame rate, and record state use the label role.
    """
    icon = _PAUSE_GLYPH if readout.paused else _PLAY_GLYPH
    word = "pause" if readout.paused else "playing"
    fps = format_fps_value(readout.fps) if readout.fps is not None else "—"
    recording = "rec on" if readout.recording else "rec off"
    clock = (
        f"{format_mmss(readout.position_sec)} / {format_mmss(readout.duration_sec)}"
    )
    return [
        (f"{icon} {word}", ACTION),
        (clock, VALUE),
        (f"bar {readout.bar_text}", LABEL),
        (f"{fps} fps", LABEL),
        (recording, LABEL),
    ]


def navigator_twisty(node: NavNode, expanded: Collection[str]) -> str | None:
    """Disclosure glyph for an expandable navigator node."""
    if not node.expandable:
        return None
    return inspector_group_glyph(node.id in expanded)


def navigator_lock_mark(node: NavNode) -> str | None:
    """Lock mark for a locked navigator node."""
    if not node.locked:
        return None
    return _NAV_LOCK_MARK


def value_drag_steps(accum: float, threshold: float) -> tuple[int, float]:
    """Split a signed pixel accumulator into steps and a sub-threshold remainder.

    Positive *accum* steps forward. ``25`` at ``10`` is ``(2, 5.0)``;
    ``-25`` is ``(-2, -5.0)``; ``9`` is ``(0, 9.0)``.
    """
    steps = math.trunc(accum / threshold)
    if steps == 0:
        return 0, accum
    return steps, accum - steps * threshold


def apply_value_drag(
    controls: Any,
    desc: RowDescriptor,
    delta_x: float,
    accum: float,
    *,
    threshold: float = _VALUE_DRAG_THRESHOLD_PX,
) -> tuple[float, bool]:
    """Apply one Left/Right step per *threshold* pixels of horizontal motion.

    *delta_x* is this frame's mouse delta, added to *accum*. Rightward motion
    is ``forward=True``. ``large`` stays false. A refused mutation still
    consumes its steps so those pixels are not retried later.

    Returns the leftover accumulator and whether this call consumed a step.
    """
    steps, remaining = value_drag_steps(accum + delta_x, threshold)
    if steps == 0:
        return remaining, False
    forward = steps > 0
    for _ in range(abs(steps)):
        apply_field_horizontal(controls, desc, forward, False)
    return remaining, True


def selection_after_nav_toggle(
    visible_ids: Sequence[str],
    selected_id: str,
    toggled_id: str,
    *,
    expanded: bool,
) -> str:
    """Selection after a twisty click.

    Expanding keeps *selected_id*. Collapsing selects *toggled_id* when
    *selected_id* is not in *visible_ids*.
    """
    if expanded or selected_id in visible_ids:
        return selected_id
    return toggled_id


def inspector_header(
    nodes: Sequence[NavNode],
    selected_id: str,
    session: TuningSession,
    *,
    curation: bool,
) -> InspectorHeader:
    """Title for *selected_id*. A layer slot breadcrumbs to its parent.

    Chips follow the node's header ``RowSpec`` and are omitted in preset
    curation. Enabled, solo, then lock.
    """
    node = next((item for item in nodes if item.id == selected_id), None)
    if node is None:
        return InspectorHeader(selected_id)
    title = node.label
    if node.parent_id == "layers":
        parent = next((item for item in nodes if item.id == node.parent_id), None)
        if parent is not None:
            title = f"{parent.label} > {node.label}"
    if curation:
        return InspectorHeader(title)
    descriptor = node_header_descriptor(selected_id)
    if descriptor is None:
        return InspectorHeader(title)
    return InspectorHeader(
        title, _header_chips(session, descriptor), descriptor
    )


def _header_chips(
    session: TuningSession, desc: RowDescriptor
) -> tuple[InspectorChip, ...]:
    spec = row_spec(desc.kind)
    chips: list[InspectorChip] = []
    if spec.toggle_enabled is not None:
        enabled = _header_enabled(session, desc)
        chips.append(
            InspectorChip("enabled", "on" if enabled else "off", enabled)
        )
    if spec.toggle_solo is not None:
        chips.append(InspectorChip("solo", "solo", _header_solo_active(session, desc)))
    if row_lock_section(desc.kind) is not None:
        locked = section_locked(session, desc)
        chips.append(InspectorChip("lock", "locked" if locked else "lock", locked))
    return tuple(chips)


def _header_enabled(session: TuningSession, desc: RowDescriptor) -> bool:
    kind = desc.kind
    if kind == RowKind.TRACK_HEADER:
        slot = desc.slot
        if slot is None:
            return False
        return bool(session.layers[slot].enabled)
    if kind == RowKind.RENDER_OVERLAYS_HEADER:
        overlays = session.render_overlays
        return bool(
            overlays.opening_card.enabled or overlays.closing_card.enabled
        )
    if kind == RowKind.RENDER_OVERLAY_CARD_HEADER:
        if desc.card == "opening_card":
            return bool(session.render_overlays.opening_card.enabled)
        if desc.card == "closing_card":
            return bool(session.render_overlays.closing_card.enabled)
        return False
    if kind == RowKind.RENDER_POST_FX_HEADER:
        return bool(session.render_post_fx.enabled)
    if kind == RowKind.RENDER_PATTERN_MASK_HEADER:
        return bool(session.render_pattern_mask.enabled)
    if kind == RowKind.RENDER_TIMELINE_HEADER:
        return bool(session.timeline.enabled)
    return False


def _header_solo_active(session: TuningSession, desc: RowDescriptor) -> bool:
    if desc.kind == RowKind.TRACK_HEADER:
        return session.solo_slot == desc.slot
    if desc.kind == RowKind.RENDER_OVERLAYS_HEADER:
        return bool(session.render_overlay_solo)
    return False


def inspector_selectable_id(desc: RowDescriptor, *, group: bool) -> str:
    """ImGui id for an inspector group or row.

    Slot, card, effect, and preset index stay in the id so repeated effect
    rows and preset-list items do not collide. Group ids include the slot.
    """
    tag = "grp" if group else "row"
    return (
        f"##{tag}-{desc.kind.name}-{desc.slot}-{desc.card}-"
        f"{desc.effect_id}-{desc.driver_slug}-{desc.preset_index}"
    )


def menu_bar_height_px() -> int:
    """Pixels reserved for the menu bar before the first ImGui layout.

    Safe without a GL context or an ImGui context. ``ShellHost`` replaces
    this with the laid-out bar height after the first frame. The transport
    bar uses the same height.
    """
    font_size = float(tuning_ui_metrics().font_size)
    return max(1, int(round(font_size + _MENU_BAR_FRAME_PADDING_Y * 2.0)))


@contextmanager
def _menu_bar_frame_padding() -> Iterator[None]:
    """Extra vertical padding for the menu bar. Other rows keep the default."""
    style = imgui.get_style()
    imgui.push_style_var(
        imgui.StyleVar_.frame_padding,
        imgui.ImVec2(style.frame_padding.x, _MENU_BAR_FRAME_PADDING_Y),
    )
    try:
        yield
    finally:
        imgui.pop_style_var()


class _HeadlessRenderer:
    """No GL device objects. Used only when ``create`` has no current context."""

    def shutdown(self) -> None:
        return None

    def render(self, _draw_data: Any) -> None:
        return None


_GL_LIBS: list[Any] = []
_ContextGetter = Callable[[], int | None]


def _context_pointer(getter: _ContextGetter) -> int:
    try:
        handle = getter()
    except Exception:
        return 0
    if not handle:
        return 0
    return int(handle)


def _dlopen_mode(*, resident_only: bool) -> int | None:
    lazy = getattr(os, "RTLD_LAZY", None)
    if resident_only:
        noload = getattr(os, "RTLD_NOLOAD", None)
        if lazy is None or noload is None:
            return None
        return lazy | noload
    glob = getattr(os, "RTLD_GLOBAL", None)
    if glob is None:
        return None
    if lazy is None:
        return glob
    return lazy | glob


def _open_gl_lib(name: str, *, resident_only: bool) -> Any | None:
    import ctypes

    mode = _dlopen_mode(resident_only=resident_only)
    if mode is None:
        return None
    try:
        return ctypes.CDLL(name, mode=mode)
    except OSError:
        return None


def _live_getter(names: tuple[str, ...], symbol: str, *, resident_only: bool) -> _ContextGetter | None:
    """Load *symbol* and return it only when it reports a current context."""
    import ctypes

    for name in names:
        lib = _open_gl_lib(name, resident_only=resident_only)
        if lib is None:
            continue
        fn = getattr(lib, symbol, None)
        if fn is None:
            continue
        fn.restype = ctypes.c_void_p
        fn.argtypes = ()
        _GL_LIBS.append(lib)
        if _context_pointer(fn):
            return fn
    return None


def _native_context_getter() -> _ContextGetter | None:
    """``glXGetCurrentContext`` or ``eglGetCurrentContext``, whichever is current.

    ``WAYLAND_DISPLAY`` makes PyOpenGL install ``EGLPlatform``, whose
    ``GetCurrentContext`` is ``eglGetCurrentContext`` and stays null for the
    GLX context pygame already made current. moderngl shares that context but
    does not expose the native pointer. Already-resident libraries are tried
    first so a second ``libGL`` does not hide pygame's context.
    """
    probes = (
        (("libGLX.so.0", "libGL.so.1"), "glXGetCurrentContext"),
        (("libEGL.so.1",), "eglGetCurrentContext"),
    )
    for resident_only in (True, False):
        for names, symbol in probes:
            getter = _live_getter(names, symbol, resident_only=resident_only)
            if getter is not None:
                return getter
    return None


def _install_pyopengl_context(getter: _ContextGetter) -> None:
    """Point PyOpenGL's context lookup at *getter*. OpenGL is already imported."""
    import OpenGL.platform as gl_platform

    gl_platform.GetCurrentContext = getter
    gl_platform.CurrentContextIsValid = getter
    plat = gl_platform.PLATFORM
    if plat is None:
        return
    plat.GetCurrentContext = getter
    plat.CurrentContextIsValid = getter


def _gl_context_current() -> bool:
    """True when PyOpenGL's ``GetCurrentContext`` sees the current context.

    ``glGetString`` is not enough: it skips ``contextdata.getContext``, and
    ``glVertexAttribPointer`` does not.
    """
    import OpenGL.platform as gl_platform

    if _context_pointer(gl_platform.GetCurrentContext):
        return True
    getter = _native_context_getter()
    if getter is None:
        return False
    _install_pyopengl_context(getter)
    return bool(_context_pointer(gl_platform.GetCurrentContext))


def _select_renderer_class() -> type[ProgrammablePipelineRenderer] | type[_HeadlessRenderer]:
    if _gl_context_current():
        return RENDERER_CLASS
    return _HeadlessRenderer


def _ensure_font_atlas() -> None:
    """Build the atlas before ``imgui.new_frame``.

    ``ProgrammablePipelineRenderer`` does this while uploading the font
    texture. The headless renderer never uploads, and ``new_frame`` asserts
    if ``GetTexDataAsRGBA32`` has not run.
    """
    fonts = imgui.get_io().fonts
    if fonts.is_built():
        return
    fonts.get_tex_data_as_rgba32()
    fonts.clear_tex_data()


_IMGUI_BUTTON = {1: 0, 2: 2, 3: 1}
_POPUP_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.always_auto_resize)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
)
_SHELL_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.no_scroll_with_mouse)
)


def shell_window_flags(base: int, *, scrollable: bool) -> int:
    """Shell window flags. Scrollable panels keep the wheel and the scrollbar."""
    flags = int(base)
    if not scrollable:
        return flags
    hidden = (
        int(imgui.WindowFlags_.no_scrollbar)
        | int(imgui.WindowFlags_.no_scroll_with_mouse)
    )
    return flags & ~hidden


def _shell_glyph_ranges() -> list[int]:
    """Default Latin plus the glyphs the shell draws outside that range.

    Dear ImGui stops the default range at U+00FF. Disclosure triangles, the
    transport play and pause marks, and the menu check then rasterize as "?".
    """
    ranges = list(imgui.get_io().fonts.get_glyph_ranges_default())
    if ranges and ranges[-1] == 0:
        ranges = ranges[:-1]
    ranges.extend(
        (
            ord(_PLAY_GLYPH),
            ord(INSPECTOR_GROUP_EXPANDED),
            ord("✓"),
            ord("✓"),
            ord(_PAUSE_GLYPH[0]),
            ord(_PAUSE_GLYPH[0]),
            0,
        )
    )
    return ranges


def _rgba(rgb: tuple[int, int, int], alpha: float = 1.0) -> imgui.ImVec4:
    return imgui.ImVec4(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha)


def _rect_contains(rect: tuple[int, int, int, int], x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def _draw_item_suffix(text: str, color: imgui.ImVec4) -> None:
    _draw_aligned_parts([(text, color)])


def _draw_mnemonic_underline(label: str) -> None:
    """1px underline under the first letter of a top-menu button."""
    letter = label[:1]
    if not letter:
        return
    rect_min = imgui.get_item_rect_min()
    pad = imgui.get_style().frame_padding
    letter_size = imgui.calc_text_size(letter)
    x0 = rect_min.x + pad.x
    y = rect_min.y + pad.y + letter_size.y
    color = imgui.get_color_u32(_rgba(LABEL))
    imgui.get_window_draw_list().add_rect_filled(
        imgui.ImVec2(x0, y),
        imgui.ImVec2(x0 + letter_size.x, y + 1.0),
        color,
    )


def _draw_nav_lock_mark(text_pos: imgui.ImVec2, label: str, mark: str) -> None:
    gap = imgui.get_style().item_spacing.x
    origin = imgui.ImVec2(
        text_pos.x + imgui.calc_text_size(label).x + gap,
        text_pos.y,
    )
    imgui.get_window_draw_list().add_text(
        origin,
        imgui.get_color_u32(_rgba(LOCK_ICON)),
        mark,
    )


def _draw_aligned_parts(parts: list[tuple[str, imgui.ImVec4]]) -> None:
    if not parts:
        return
    widths = [imgui.calc_text_size(text).x for text, _color in parts]
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    pad = imgui.get_style().frame_padding.x
    x = rect_max.x - sum(widths) - pad
    y = rect_min.y
    draw = imgui.get_window_draw_list()
    for (text, color), width in zip(parts, widths):
        draw.add_text(imgui.ImVec2(x, y), imgui.get_color_u32(color), text)
        x += width


def _inspector_row_selected(focus: Any, desc: Any) -> bool:
    return (
        focus.region is ShellRegion.INSPECTOR
        and focus.inspector_command_id is None
        and focus.inspector_cursor == desc
    )


def inspector_row_stepped(state: object, desc: RowDescriptor) -> bool:
    """Whether this inspector row paints side arrows and accepts sideways drag.

    Arrows stay paint-only. Drag uses the row selectable. The section-lock
    rule matches Left/Right.
    """
    return (
        row_spec(desc.kind).apply_horizontal is not None
        and not section_lock_blocks_mutation(state, desc)
    )


def _value_parts(
    value: str, color: imgui.ImVec4, *, stepped: bool
) -> list[tuple[str, imgui.ImVec4]]:
    if not stepped:
        return [(value, color)]
    bracket = _rgba(DISABLED)
    return [("< ", bracket), (value, color), (" >", bracket)]


def border_stroke_outset_px(border_size: float, *, anti_aliased_lines: bool) -> float:
    """How far an ImGui window border extends outside the window rect.

    ``AddRect`` centers the stroke on a path half a pixel inside the edge.
    Anti-aliased lines add a one-pixel fringe beyond half the thickness.
    Window padding is inside the rect and does not move this stroke.
    """
    if border_size <= 0.0:
        return 0.0
    half = float(border_size) * 0.5
    if anti_aliased_lines:
        return half + _AA_LINE_FRINGE_PX - _BORDER_PATH_INSET_PX
    return max(0.0, half - _BORDER_PATH_INSET_PX)


def side_panel_seat_px(border_size: float, *, anti_aliased_lines: bool) -> int:
    """Pixels to drop a side panel so its border clears the transport rule."""
    outset = border_stroke_outset_px(
        border_size, anti_aliased_lines=anti_aliased_lines
    )
    if outset <= 0.0:
        return 0
    return math.ceil(outset - 1e-6)


def transport_content_pad_y(window_height: float, line_height: float) -> float:
    """Vertical padding that centers one text line inside the transport bar."""
    return max(0.0, (float(window_height) - float(line_height)) * 0.5)


def _seat_panel(
    rect: tuple[int, int, int, int], inset: int
) -> tuple[int, int, int, int]:
    """Drop a side panel so its border stroke clears the transport rule."""
    x, y, width, height = rect
    if inset <= 0 or height <= inset:
        return rect
    return (x, y + inset, width, height - inset)


def _stroke_h_rule(
    x0: float,
    x1: float,
    y: float,
    rgb: tuple[int, int, int],
    *,
    foreground: bool = True,
) -> None:
    """Opaque 1px rule on pixel row *y*.

    A stroked line is anti-aliased, so an opaque fill shows through it. A
    filled rectangle is not. The foreground list paints after every window,
    which keeps the menu-bar rule on top of the menu buttons. The transport
    rule stays on its own window so a later menu popup covers it.
    """
    if x1 <= x0:
        return
    color = imgui.get_color_u32(_rgba(rgb))
    rect_min = imgui.ImVec2(x0, y)
    rect_max = imgui.ImVec2(x1, y + 1.0)
    if not foreground:
        imgui.get_window_draw_list().add_rect_filled(rect_min, rect_max, color)
        return
    draw = imgui.get_foreground_draw_list(imgui.get_main_viewport())
    display = imgui.get_io().display_size
    draw.push_clip_rect(imgui.ImVec2(0.0, 0.0), display, False)
    draw.add_rect_filled(rect_min, rect_max, color)
    draw.pop_clip_rect()


def _draw_rect_border(rect: tuple[int, int, int, int]) -> None:
    """1px highlight around the timeline strip.

    Drawn only while the strip has focus. An open menu takes that focus, so
    this outline and the popup are never in the same frame. The foreground
    list keeps the stroke above the side panels that meet the strip.
    """
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    color = imgui.get_color_u32(_rgba(HIGHLIGHT))
    imgui.get_foreground_draw_list().add_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + w), float(y + h)),
        color,
        0.0,
        0,
        1.0,
    )


def _draw_item_focus_ring() -> None:
    """1px highlight outline of the current item on its window.

    The window list is painted with that panel, so a later menu popup covers
    the outline where they overlap. The foreground list would sit above the
    popup.
    """
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    if rect_max.x <= rect_min.x or rect_max.y <= rect_min.y:
        return
    color = imgui.get_color_u32(_rgba(HIGHLIGHT))
    imgui.get_window_draw_list().add_rect(
        rect_min,
        rect_max,
        color,
        0.0,
        0,
        1.0,
    )


def selectable_wash(selected: bool) -> tuple[imgui.ImVec4, imgui.ImVec4]:
    """Hovered and active header colors for one shell selectable.

    A selected row keeps the highlight wash. An unselected row uses the hover
    wash ``_apply_theme`` assigns to ``header_hovered`` and ``header_active``.
    """
    if selected:
        rgb: tuple[int, int, int] = HIGHLIGHT
        alpha = FOCUS_ROW_BG_ALPHA / 255.0
    else:
        rgb = HOVER
        alpha = HOVER_BG_ALPHA / 255.0
    return _rgba(rgb, alpha), _rgba(rgb, alpha)


@contextmanager
def _selected_header_wash(selected: bool) -> Iterator[None]:
    """Push the highlight header wash for a selected selectable, then pop."""
    if selected:
        hovered, active = selectable_wash(True)
        imgui.push_style_color(imgui.Col_.header_hovered, hovered)
        imgui.push_style_color(imgui.Col_.header_active, active)
    try:
        yield
    finally:
        if selected:
            imgui.pop_style_color(2)


def _gl_int(param: int) -> int:
    value = glGetIntegerv(param)
    try:
        return int(value[0])
    except (TypeError, IndexError):
        return int(value)


def _apply_theme() -> None:
    """Map overlay roles onto ImGui, including the hover wash."""
    style = imgui.get_style()
    style.window_rounding = 0.0
    style.frame_rounding = 0.0
    style.popup_rounding = 0.0
    style.scrollbar_rounding = 0.0
    highlight = _rgba(HIGHLIGHT, FOCUS_ROW_BG_ALPHA / 255.0)
    hover = _rgba(HOVER, HOVER_BG_ALPHA / 255.0)
    background = _rgba(BACKGROUND)
    text = _rgba(VALUE)
    disabled = _rgba(DISABLED)
    assignments = {
        imgui.Col_.text: text,
        imgui.Col_.text_disabled: disabled,
        imgui.Col_.window_bg: background,
        imgui.Col_.child_bg: background,
        imgui.Col_.popup_bg: background,
        imgui.Col_.menu_bar_bg: background,
        imgui.Col_.border: _rgba(BORDER_COLOR),
        imgui.Col_.header: highlight,
        imgui.Col_.header_hovered: hover,
        imgui.Col_.header_active: hover,
        imgui.Col_.button: background,
        imgui.Col_.button_hovered: highlight,
        imgui.Col_.button_active: highlight,
        imgui.Col_.frame_bg: background,
        imgui.Col_.title_bg: background,
        imgui.Col_.title_bg_active: background,
        imgui.Col_.title_bg_collapsed: background,
        imgui.Col_.check_mark: text,
        imgui.Col_.separator: disabled,
        imgui.Col_.text_selected_bg: highlight,
        imgui.Col_.nav_highlight: _rgba(HIGHLIGHT),
    }
    for column, color in assignments.items():
        style.set_color_(int(column), color)


def _keep_keyboard_nav_off() -> None:
    nav = int(imgui.ConfigFlags_.nav_enable_keyboard)
    io = imgui.get_io()
    io.config_flags = int(io.config_flags) & ~nav


class _ExtraGlState:
    __slots__ = ("program", "array_buffer", "cull", "polygon_front", "polygon_back")

    def __init__(self) -> None:
        self.program = _gl_int(GL_CURRENT_PROGRAM)
        self.array_buffer = _gl_int(GL_ARRAY_BUFFER_BINDING)
        self.cull = bool(glIsEnabled(GL_CULL_FACE))
        polygon = glGetIntegerv(GL_POLYGON_MODE)
        try:
            self.polygon_front = int(polygon[0])
            self.polygon_back = int(polygon[1])
        except (TypeError, IndexError):
            self.polygon_front = int(polygon)
            self.polygon_back = self.polygon_front

    def restore(self) -> None:
        glUseProgram(self.program)
        glBindBuffer(GL_ARRAY_BUFFER, self.array_buffer)
        if self.cull:
            glEnable(GL_CULL_FACE)
        else:
            glDisable(GL_CULL_FACE)
        glPolygonMode(GL_FRONT, self.polygon_front)
        glPolygonMode(GL_BACK, self.polygon_back)


class ShellHost:
    """Programmable-pipeline ImGui menu bar attached to the current GL context."""

    def __init__(
        self,
        context: Any,
        renderer: ProgrammablePipelineRenderer | _HeadlessRenderer,
        overlay: Any,
        menu_state: MenuBarState,
        controls: Any,
        display_size: tuple[int, int],
        bar_height: int,
    ) -> None:
        self._context = context
        self._renderer = renderer
        self._overlay = overlay
        self._menu_state = menu_state
        self._controls = controls
        self._display_size = display_size
        self._menu_bar_height_px = bar_height
        self._layout: ShellLayout | None = None
        self._mouse_pos: tuple[float, float] | None = None
        self._buttons: list[tuple[int, bool]] = []
        self._held: set[int] = set()
        self._wheel_x = 0.0
        self._wheel_y = 0.0
        self._value_drag_accum = 0.0
        self._value_drag_crossed = False
        # Live drag requests. A completed drag persists both columns, then clears these.
        self._nav_width: int | None = None
        self._insp_width: int | None = None
        self._splitter: str | None = None
        self._splitter_down_x = 0.0
        self._resize_cursor = False

    @classmethod
    def create(cls, overlay: Any, menu_state: MenuBarState, controls: Any) -> ShellHost:
        """Build the context and font atlas once. Call after the live GL window exists."""
        context = imgui.create_context()
        try:
            io = imgui.get_io()
            _keep_keyboard_nav_off()
            io.set_ini_filename(os.devnull)
            font_size = float(tuning_ui_metrics().font_size)
            font = io.fonts.add_font_from_file_ttf(
                str(overlay_font_path()),
                font_size,
                None,
                _shell_glyph_ranges(),
            )
            io.font_default = font
            _apply_theme()
            renderer = _select_renderer_class()()
        except Exception:
            imgui.destroy_context(context)
            raise
        bar_height = menu_bar_height_px()
        surface = pygame.display.get_surface()
        if surface is None:
            display_size = (1, 1)
        else:
            display_size = surface.get_size()
        return cls(
            context,
            renderer,
            overlay,
            menu_state,
            controls,
            display_size,
            bar_height,
        )

    @property
    def menu_bar_height_px(self) -> int:
        return self._menu_bar_height_px

    @property
    def layout(self) -> ShellLayout | None:
        return self._layout

    def set_layout(self, layout: ShellLayout) -> None:
        """Remember the frame's shell rects for the transport, navigator, and inspector."""
        self._layout = layout

    @property
    def nav_width(self) -> int | None:
        """Navigator width requested by an in-progress splitter drag."""
        return self._nav_width

    @property
    def insp_width(self) -> int | None:
        """Inspector width requested by an in-progress splitter drag."""
        return self._insp_width

    def destroy(self) -> None:
        renderer = self._renderer
        self._renderer = None
        if renderer is not None:
            renderer.shutdown()
        context = self._context
        self._context = None
        if context is not None:
            imgui.destroy_context(context)

    def process_event(self, event: pygame.event.Event) -> None:
        """Mouse motion, buttons, and wheel only. Keys stay out of ImGui."""
        if event.type == pygame.MOUSEMOTION:
            x = float(event.pos[0])
            y = float(event.pos[1])
            self._mouse_pos = (x, y)
            self._track_splitter_motion(x, y)
            if (
                self._chrome_contains(x, y)
                or self._splitter is not None
                or self._resize_cursor
            ):
                self._overlay.notify_input()
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            button = _IMGUI_BUTTON.get(getattr(event, "button", 0))
            if button is None:
                return
            down = event.type == pygame.MOUSEBUTTONDOWN
            if down:
                if self._clicks_ignored():
                    self._cancel_splitter_drag()
                    return
                # Swallow the left button so ImGui does not activate a row
                # or start a value drag.
                if button == 0 and self._begin_splitter_drag(event.pos):
                    return
                if button == 0:
                    self._assign_shell_region(
                        float(event.pos[0]), float(event.pos[1])
                    )
                self._held.add(button)
            elif button == 0 and self._splitter is not None:
                if self._clicks_ignored():
                    self._cancel_splitter_drag()
                else:
                    self._end_splitter_drag(event.pos)
                return
            elif button not in self._held:
                return
            else:
                self._held.discard(button)
            self._buttons.append((button, down))
            return
        if event.type == pygame.MOUSEWHEEL:
            if self._clicks_ignored():
                return
            self._wheel_x += float(event.x)
            self._wheel_y += float(event.y)

    def _assign_shell_region(self, x: float, y: float) -> None:
        """Left click chooses navigator, inspector, or the open strip.

        Menu, transport, and the visualiser leave the region alone. A miss
        when no layout is stored does nothing. The strip stays open.
        """
        layout = self._layout
        if layout is None:
            return
        if _rect_contains(layout.navigator, x, y):
            self._controls.set_shell_region(ShellRegion.NAVIGATOR)
            return
        if _rect_contains(layout.inspector, x, y):
            self._controls.set_shell_region(ShellRegion.INSPECTOR)
            return
        if layout.timeline[3] > 0 and _rect_contains(layout.timeline, x, y):
            self._controls.set_shell_region(ShellRegion.TIMELINE)

    def _splitter_at(self, x: float, y: float) -> str | None:
        layout = self._layout
        if layout is None:
            return None
        return splitter_hit(layout, x, y)

    def _assign_splitter_width(self, which: str, pointer_x: float) -> None:
        layout = self._layout
        if layout is None:
            return
        width = splitter_request_width(layout, which, pointer_x)
        if which == "nav":
            self._nav_width = width
        else:
            self._insp_width = width

    def _begin_splitter_drag(self, pos: tuple[float, float]) -> bool:
        which = self._splitter_at(float(pos[0]), float(pos[1]))
        if which is None:
            return False
        self._splitter = which
        self._splitter_down_x = float(pos[0])
        self._set_resize_cursor(True)
        return True

    def _end_splitter_drag(self, pos: tuple[float, float]) -> None:
        which = self._splitter
        x = float(pos[0])
        if which is not None and abs(x - self._splitter_down_x) >= 1.0:
            self._assign_splitter_width(which, x)
            editor = self._controls.cfg.editor
            nav = (
                self._nav_width
                if self._nav_width is not None
                else editor.navigator_width
            )
            insp = (
                self._insp_width
                if self._insp_width is not None
                else editor.inspector_width
            )
            self._controls.settings.set_shell_column_widths(nav, insp)
            self._nav_width = None
            self._insp_width = None
        self._splitter = None
        # Layout catches up after this event. Keep the resize cursor until
        # the next motion, which tests the updated boundaries.
        self._set_resize_cursor(True)

    def _cancel_splitter_drag(self) -> None:
        self._splitter = None
        self._set_resize_cursor(False)

    def _track_splitter_motion(self, x: float, y: float) -> None:
        if self._clicks_ignored():
            self._cancel_splitter_drag()
            return
        if self._splitter is not None:
            self._assign_splitter_width(self._splitter, x)
            self._set_resize_cursor(True)
            return
        self._set_resize_cursor(self._splitter_at(x, y) is not None)

    def _set_resize_cursor(self, resize: bool) -> None:
        if resize == self._resize_cursor:
            return
        cursor = (
            pygame.SYSTEM_CURSOR_SIZEWE
            if resize
            else pygame.SYSTEM_CURSOR_ARROW
        )
        pygame.mouse.set_cursor(cursor)
        self._resize_cursor = resize

    def draw(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        visibility: float,
        dt: float,
        readout: TransportReadout | None = None,
    ) -> None:
        """One ImGui frame. Skip it when the shell is hidden and no menu is open."""
        if visibility <= _HIDDEN and not menu_state.dropdown_open:
            self._buttons.clear()
            self._held.clear()
            self._wheel_x = 0.0
            self._wheel_y = 0.0
            self._clear_value_drag()
            self._cancel_splitter_drag()
            return
        self._submit_input(dt)
        _keep_keyboard_nav_off()
        _ensure_font_atlas()
        imgui.new_frame()
        try:
            alpha = 1.0 if menu_state.dropdown_open else max(0.0, min(1.0, visibility))
            imgui.get_style().alpha = alpha
            with _menu_bar_frame_padding():
                self._menu_bar_height_px = max(
                    1, int(round(imgui.get_frame_height()))
                )
                rule_y, anchors, menus = self._draw_bar(menu_state)
            if self._layout is not None:
                self._draw_shell(menu_state, readout)
            popup_hovered = False
            if menu_state.dropdown_open and menus:
                popup_hovered = self._draw_dropdown(
                    menu_state, command_ctx, menus, anchors
                )
            if rule_y is not None:
                _stroke_h_rule(
                    0.0,
                    imgui.get_io().display_size.x,
                    rule_y,
                    BORDER_COLOR,
                )
            if imgui.is_mouse_clicked(0) and not popup_hovered:
                mouse = imgui.get_mouse_pos()
                in_bar = 0.0 <= mouse.y < float(self._menu_bar_height_px)
                if not in_bar:
                    menu_state.blur()
            self._release_value_drag()
        finally:
            imgui.render()
            self._render_draw_data()

    def _chrome_contains(self, x: float, y: float) -> bool:
        if y < self._menu_bar_height_px:
            return True
        layout = self._layout
        if layout is None:
            return False
        return any(
            _rect_contains(rect, x, y)
            for rect in (layout.transport, layout.navigator, layout.inspector)
        )

    def _strip_has_scope(self) -> bool:
        return (
            self._controls.shell_focus.region is ShellRegion.TIMELINE
            and self._controls.session.timeline.panel_open
        )

    def _cycle_stop(self, menu_state: MenuBarState) -> CycleStop:
        if menu_state.focused:
            return CycleStop.MENU
        if self._strip_has_scope():
            return CycleStop.TIMELINE
        if self._controls.shell_focus.region is ShellRegion.INSPECTOR:
            return CycleStop.INSPECTOR
        return CycleStop.NAVIGATOR

    def _scope_label(self, menu_state: MenuBarState) -> str:
        if menu_state.focused:
            return "menu bar"
        if self._strip_has_scope():
            return "timeline strip"
        region = self._controls.shell_focus.region
        if region is ShellRegion.INSPECTOR:
            return "inspector"
        return "navigator"

    def _draw_shell(
        self, menu_state: MenuBarState, readout: TransportReadout | None
    ) -> None:
        layout = self._layout
        if layout is None:
            return
        if readout is None:
            readout = TransportReadout(False, 0.0, 0.0, "—", None, False)
        state = self._controls.build_view_state(
            paused=readout.paused,
            position_sec=readout.position_sec,
            fps=readout.fps,
        )
        stop = self._cycle_stop(menu_state)
        style = imgui.get_style()
        # Default WindowMinSize is 32px, taller than this one-line bar, so the
        # transport was painted through its own text and over the side panels.
        saved_min_x = float(style.window_min_size.x)
        saved_min_y = float(style.window_min_size.y)
        style.window_min_size = imgui.ImVec2(1.0, 1.0)
        seat = side_panel_seat_px(
            _PANEL_BORDER_PX,
            anti_aliased_lines=bool(style.anti_aliased_lines),
        )
        try:
            pad_y = transport_content_pad_y(
                layout.transport[3], imgui.get_text_line_height()
            )
            imgui.push_style_var(
                imgui.StyleVar_.window_padding,
                imgui.ImVec2(style.window_padding.x, pad_y),
            )
            try:
                self._draw_fixed_window(
                    "##shell-transport",
                    layout.transport,
                    active=False,
                    body=lambda: self._draw_transport(readout, menu_state),
                )
            finally:
                imgui.pop_style_var()
            self._draw_fixed_window(
                "##shell-navigator",
                _seat_panel(layout.navigator, seat),
                active=stop is CycleStop.NAVIGATOR,
                idle_border=NAVIGATOR_BORDER,
                body=lambda: self._draw_navigator(),
                scrollable=True,
            )
            self._draw_fixed_window(
                "##shell-inspector",
                _seat_panel(layout.inspector, seat),
                active=stop is CycleStop.INSPECTOR,
                body=lambda: self._draw_inspector(state),
                scrollable=True,
            )
        finally:
            style.window_min_size = imgui.ImVec2(saved_min_x, saved_min_y)
        if stop is CycleStop.TIMELINE:
            _draw_rect_border(layout.timeline)

    def _draw_fixed_window(
        self,
        title: str,
        rect: tuple[int, int, int, int],
        *,
        active: bool,
        body: Callable[[], None],
        idle_border: tuple[int, int, int] | None = None,
        scrollable: bool = False,
    ) -> None:
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return
        border = HIGHLIGHT if active else idle_border
        imgui.set_next_window_pos(
            imgui.ImVec2(float(x), float(y)), imgui.Cond_.always
        )
        imgui.set_next_window_size(
            imgui.ImVec2(float(w), float(h)), imgui.Cond_.always
        )
        imgui.push_style_var(
            imgui.StyleVar_.window_border_size,
            _PANEL_BORDER_PX if border is not None else 0.0,
        )
        if border is not None:
            imgui.push_style_color(imgui.Col_.border, _rgba(border))
        try:
            _visible, _opened = imgui.begin(
                title,
                None,
                shell_window_flags(_SHELL_FLAGS, scrollable=scrollable),
            )
            try:
                body()
            finally:
                imgui.end()
        finally:
            if border is not None:
                imgui.pop_style_color()
            imgui.pop_style_var()

    def _draw_transport(
        self, readout: TransportReadout, menu_state: MenuBarState
    ) -> None:
        for index, (text, color) in enumerate(transport_parts(readout)):
            if index:
                imgui.same_line(0.0, _TRANSPORT_GAP)
            imgui.text_colored(_rgba(color), text)
        scope = f"scope: {self._scope_label(menu_state)}"
        width = imgui.calc_text_size(scope).x
        avail = imgui.get_window_width()
        pad = imgui.get_style().window_padding.x
        imgui.same_line(max(imgui.get_cursor_pos_x(), avail - width - pad))
        imgui.text(scope)
        origin = imgui.get_window_pos()
        size = imgui.get_window_size()
        _stroke_h_rule(
            origin.x,
            origin.x + size.x,
            origin.y + size.y - 1.0,
            TRANSPORT_RULE,
            foreground=False,
        )

    def _draw_navigator(self) -> None:
        focus = self._controls.shell_focus
        imgui.push_style_color(imgui.Col_.text, _rgba(LABEL))
        try:
            for node in build_navigator(
                self._controls.session,
                focus.nav_expanded,
            ):
                self._draw_nav_node(node)
        finally:
            imgui.pop_style_color()

    def _draw_nav_node(self, node: NavNode) -> None:
        focus = self._controls.shell_focus
        indent = node.depth * _INSPECTOR_INDENT
        if indent:
            imgui.indent(indent)
        try:
            selected = node.id == focus.selected_id
            twisty_clicked = False
            with _selected_header_wash(selected):
                twisty = navigator_twisty(node, focus.nav_expanded)
                if twisty is not None:
                    width = imgui.calc_text_size(twisty).x
                    twisty_clicked, _selected = imgui.selectable(
                        f"{twisty}##nav-twisty-{node.id}",
                        selected,
                        0,
                        imgui.ImVec2(width, 0.0),
                    )
                    imgui.same_line()
                text_pos = imgui.get_cursor_screen_pos()
                clicked, _selected = imgui.selectable(
                    f"{node.label}##nav-{node.id}",
                    selected,
                )
                if selected:
                    _draw_item_focus_ring()
            mark = navigator_lock_mark(node)
            if mark is not None:
                _draw_nav_lock_mark(text_pos, node.label, mark)
            if node.badge:
                _draw_item_suffix(node.badge, _rgba(LABEL))
            if twisty_clicked:
                self._toggle_nav_expanded(node.id)
            elif clicked:
                self._controls.navigator.select(node.id)
        finally:
            if indent:
                imgui.unindent(indent)

    def _toggle_nav_expanded(self, node_id: str) -> None:
        focus = self._controls.shell_focus
        expanded = node_id not in focus.nav_expanded
        if expanded:
            focus.nav_expanded.add(node_id)
        else:
            focus.nav_expanded.discard(node_id)
        visible = tuple(
            node.id
            for node in build_navigator(
                self._controls.session, focus.nav_expanded
            )
        )
        focus.selected_id = selection_after_nav_toggle(
            visible,
            focus.selected_id,
            node_id,
            expanded=expanded,
        )

    def _draw_inspector(self, state: Any) -> None:
        focus = self._controls.shell_focus
        nodes = build_navigator(
            self._controls.session,
            focus.nav_expanded,
        )
        header = inspector_header(
            nodes,
            focus.selected_id,
            self._controls.session,
            curation=is_preset_curation_mode(
                self._controls.session.settings.editor_mode
            ),
        )
        if header.chips:
            imgui.align_text_to_frame_padding()
        imgui.text(header.title)
        if header.chips:
            self._draw_inspector_chips(header)
        rows = build_inspector_rows(
            state, focus.selected_id, focus.collapsed, focus.opened
        )
        if not rows:
            imgui.text_colored(_rgba(DISABLED), "Edited on the panel")
            return
        for row in rows:
            self._draw_inspector_row(state, row)

    def _draw_inspector_row(self, state: Any, row: Any) -> None:
        focus = self._controls.shell_focus
        indent = row.depth * _INSPECTOR_INDENT
        if indent:
            imgui.indent(indent)
        try:
            if row.command_id is not None:
                self._draw_command_row(row)
                return
            desc = row.descriptor
            kind = desc.kind
            spec = row_spec(kind)
            label = row_panel_label(kind, desc)
            selected = _inspector_row_selected(focus, desc)
            if row.is_group:
                key = InspectorGroupKey(kind, desc.slot, desc.card)
                glyph = inspector_group_glyph(
                    inspector_group_is_open(key, focus.collapsed, focus.opened)
                )
                with _selected_header_wash(selected):
                    clicked, _selected = imgui.selectable(
                        f"{glyph} {label}{inspector_selectable_id(desc, group=True)}",
                        selected,
                    )
                    if selected:
                        _draw_item_focus_ring()
                if clicked:
                    self._controls.inspector.focus_row(row)
                    self._controls.inspector.activate(row)
                return
            label_color, value_color = inspector_field_colors(state, desc)
            imgui.push_style_color(imgui.Col_.text, _rgba(label_color))
            try:
                with _selected_header_wash(selected):
                    clicked, _selected = imgui.selectable(
                        f"{label}{inspector_selectable_id(desc, group=False)}",
                        selected,
                    )
                    # Item flags are only valid while this selectable is current.
                    # Release clears the active id inside the widget, so the
                    # frame the button comes up is deactivated, not active.
                    activated = imgui.is_item_activated()
                    active = imgui.is_item_active()
                    released = imgui.is_item_deactivated()
                    if selected:
                        _draw_item_focus_ring()
            finally:
                imgui.pop_style_color()
            value = format_row_value(state, desc) if spec.format_value else ""
            stepped = inspector_row_stepped(state, desc)
            if spec.shows_dirty_suffix and state.config_dirty:
                value = f"{value}*" if value else "*"
            if value:
                _draw_aligned_parts(
                    _value_parts(
                        value,
                        _rgba(value_color),
                        stepped=stepped,
                    )
                )
            if stepped:
                self._track_value_drag(
                    row,
                    desc,
                    activated=activated,
                    active=active or released,
                )
            # A release still over the row reports clicked. A gesture that
            # already stepped is a drag, so it must not run the row action.
            if clicked and not self._value_drag_crossed:
                self._controls.inspector.focus_row(row)
                self._controls.inspector.activate(row)
        finally:
            if indent:
                imgui.unindent(indent)

    def _track_value_drag(
        self,
        row: Any,
        desc: RowDescriptor,
        *,
        activated: bool,
        active: bool,
    ) -> None:
        """Step a held inspector value from this frame's horizontal mouse delta."""
        if not active:
            return
        if activated:
            self._value_drag_accum = 0.0
            self._value_drag_crossed = False
        delta_x = float(imgui.get_io().mouse_delta.x)
        remaining, crossed = apply_value_drag(
            self._controls,
            desc,
            delta_x,
            self._value_drag_accum,
        )
        self._value_drag_accum = remaining
        if not crossed:
            return
        self._value_drag_crossed = True
        self._controls.inspector.focus_row(row)

    def _clear_value_drag(self) -> None:
        self._value_drag_accum = 0.0
        self._value_drag_crossed = False

    def _release_value_drag(self) -> None:
        if not imgui.is_mouse_down(0):
            self._clear_value_drag()

    def _draw_command_row(self, row: Any) -> None:
        command = command_by_id(row.command_id)
        enabled = inspector_command_enabled(self._controls, row.command_id)
        focus = self._controls.shell_focus
        selected = (
            focus.region is ShellRegion.INSPECTOR
            and focus.inspector_command_id == row.command_id
        )
        color = ACTION if enabled else DISABLED
        imgui.push_style_color(imgui.Col_.text, _rgba(color))
        try:
            with _selected_header_wash(selected):
                clicked, _selected = imgui.selectable(
                    f"{command.label}##cmd-{row.command_id}",
                    selected,
                )
                if selected:
                    _draw_item_focus_ring()
        finally:
            imgui.pop_style_color()
        if clicked:
            self._controls.inspector.focus_row(row)
            if enabled:
                self._controls.inspector.activate(row)

    def _draw_inspector_chips(self, header: InspectorHeader) -> None:
        chips = header.chips
        descriptor = header.descriptor
        if descriptor is None or not chips:
            return
        style = imgui.get_style()
        gap = style.item_spacing.x
        pad = style.frame_padding.x
        widths = [
            imgui.calc_text_size(chip.label).x + pad * 2.0 for chip in chips
        ]
        total = sum(widths) + gap * (len(chips) - 1)
        avail = imgui.get_window_width()
        imgui.same_line(
            max(
                imgui.get_cursor_pos_x(),
                avail - total - style.window_padding.x,
            )
        )
        for index, chip in enumerate(chips):
            if index:
                imgui.same_line(0.0, gap)
            color = LOCK_ICON if chip.id == "lock" else (
                ACTION if chip.active else LABEL
            )
            imgui.push_style_color(imgui.Col_.text, _rgba(color))
            try:
                clicked, _selected = imgui.selectable(
                    f"{chip.label}##insp-chip-{chip.id}",
                    False,
                    0,
                    imgui.ImVec2(widths[index], 0.0),
                )
            finally:
                imgui.pop_style_color()
            if clicked:
                activate_inspector_chip(self._controls, chip.id, descriptor)

    def _clicks_ignored(self) -> bool:
        return (
            self._overlay.visibility <= _HIDDEN
            and not self._menu_state.dropdown_open
        )

    def _mouse_xy(self) -> tuple[float, float]:
        if self._mouse_pos is not None:
            return self._mouse_pos
        pos = pygame.mouse.get_pos()
        return (float(pos[0]), float(pos[1]))

    def _submit_input(self, dt: float) -> None:
        io = imgui.get_io()
        width, height = self._display_size
        surface = pygame.display.get_surface()
        if surface is not None:
            width, height = surface.get_size()
            self._display_size = (width, height)
        io.display_size = imgui.ImVec2(float(width), float(height))
        io.display_framebuffer_scale = imgui.ImVec2(1.0, 1.0)
        io.delta_time = dt if dt > 0.0 else 1.0 / 60.0
        mouse_x, mouse_y = self._mouse_xy()
        io.add_mouse_pos_event(mouse_x, mouse_y)
        for button, down in self._buttons:
            io.add_mouse_button_event(button, down)
        self._buttons.clear()
        if self._wheel_x or self._wheel_y:
            io.add_mouse_wheel_event(self._wheel_x, self._wheel_y)
            self._wheel_x = 0.0
            self._wheel_y = 0.0

    def _draw_bar(
        self, menu_state: MenuBarState
    ) -> tuple[float | None, dict[int, tuple[float, float]], tuple[Any, ...]]:
        menus = menus_for_session(self._controls.session)
        anchors: dict[int, tuple[float, float]] = {}
        highlight = _rgba(HIGHLIGHT, FOCUS_ROW_BG_ALPHA / 255.0)
        imgui.push_style_color(imgui.Col_.text, _rgba(LABEL))
        # The bar's own border is covered by opaque menu buttons except where
        # the highlight is translucent. The white rule is drawn later, on top.
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        bar_open = imgui.begin_main_menu_bar()
        rule_y: float | None = None
        try:
            if bar_open:
                bar_bottom = imgui.get_window_pos().y + imgui.get_window_height()
                self._menu_bar_height_px = max(1, int(round(bar_bottom)))
                rule_y = bar_bottom - 1.0
                for index, menu in enumerate(menus):
                    active = menu_state.focused and menu_state.menu_index == index
                    if active:
                        imgui.push_style_color(imgui.Col_.button, highlight)
                        imgui.push_style_color(imgui.Col_.button_hovered, highlight)
                        imgui.push_style_color(imgui.Col_.button_active, highlight)
                    clicked = imgui.button(menu.label)
                    if active:
                        imgui.pop_style_color(3)
                    _draw_mnemonic_underline(menu.label)
                    rect_min = imgui.get_item_rect_min()
                    rect_max = imgui.get_item_rect_max()
                    anchors[index] = (rect_min.x, rect_max.y)
                    if clicked:
                        menu_state.click_top(index, menus)
        finally:
            if bar_open:
                imgui.end_main_menu_bar()
            imgui.pop_style_var()
            imgui.pop_style_color()
        return rule_y, anchors, menus

    def _draw_dropdown(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        menus: tuple[Any, ...],
        anchors: dict[int, tuple[float, float]],
    ) -> bool:
        index = menu_state.menu_index % len(menus)
        menu = menus[index]
        anchor = anchors.get(index)
        if anchor is None:
            origin_x = 0.0
            origin_y = float(self._menu_bar_height_px)
        else:
            origin_x, origin_y = anchor
        imgui.set_next_window_pos(
            imgui.ImVec2(origin_x, origin_y), imgui.Cond_.always
        )
        # Begun after the shell panels, and those panels do not raise themselves,
        # so this window stays at the front of the display stack. Do not focus
        # it: FocusWindow clears the menu-bar button's ActiveId, and a later
        # click on another top label never completes.
        visible, _open = imgui.begin("##cleave-menu", None, _POPUP_FLAGS)
        try:
            if not visible:
                return False
            hit = self._draw_rows(menu_state, command_ctx, menus, index, menu)
            return hit or _mouse_in_current_window()
        finally:
            imgui.end()

    def _draw_rows(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        menus: tuple[Any, ...],
        menu_index: int,
        menu: Any,
    ) -> bool:
        hit = False
        style = imgui.get_style()
        pad_x = style.frame_padding.x
        pad_y = style.frame_padding.y
        check_w = imgui.calc_text_size("✓").x
        gap = max(imgui.calc_text_size("  ").x, 16.0)
        label_w = 0.0
        shortcut_w = 0.0
        for item in menu.items:
            if isinstance(item, MenuSeparator):
                continue
            label_w = max(label_w, imgui.calc_text_size(item.label).x)
            if item.shortcut:
                shortcut_w = max(shortcut_w, imgui.calc_text_size(item.shortcut).x)
        row_w = pad_x * 2.0 + check_w + gap + label_w + gap + shortcut_w + pad_x
        draw_list = imgui.get_window_draw_list()
        hover = _rgba(HOVER, MENU_ITEM_HOVER_BG_ALPHA / 255.0)
        imgui.push_style_color(imgui.Col_.header_hovered, hover)
        imgui.push_style_color(imgui.Col_.header_active, hover)
        try:
            for item_index, item in enumerate(menu.items):
                if isinstance(item, MenuSeparator):
                    imgui.separator()
                    continue
                enabled = bool(item.enabled(command_ctx))
                highlighted = menu_state.item_index == item_index
                pos = imgui.get_cursor_screen_pos()
                with _selected_header_wash(highlighted):
                    clicked, _selected = imgui.selectable(
                        f"##{item.id}",
                        highlighted,
                        0,
                        imgui.ImVec2(row_w, 0.0),
                    )
                color = _row_color(item, command_ctx, enabled)
                packed = imgui.get_color_u32(color)
                text_y = pos.y + pad_y
                text_x = pos.x + pad_x
                if (
                    item.kind == "check"
                    and item.checked is not None
                    and item.checked(command_ctx)
                ):
                    draw_list.add_text(imgui.ImVec2(text_x, text_y), packed, "✓")
                draw_list.add_text(
                    imgui.ImVec2(text_x + check_w + gap, text_y),
                    packed,
                    item.label,
                )
                if item.shortcut:
                    shortcut_width = imgui.calc_text_size(item.shortcut).x
                    draw_list.add_text(
                        imgui.ImVec2(pos.x + row_w - pad_x - shortcut_width, text_y),
                        packed,
                        item.shortcut,
                    )
                if clicked:
                    hit = True
                    menu_state.click_item(
                        menu_index,
                        item_index,
                        menus,
                        command_ctx,
                        self._controls,
                    )
        finally:
            imgui.pop_style_color(2)
        return hit

    def _render_draw_data(self) -> None:
        renderer = self._renderer
        if not isinstance(renderer, ProgrammablePipelineRenderer):
            return
        saved = save_gl_state()
        extra = _ExtraGlState()
        try:
            renderer.render(imgui.get_draw_data())
        finally:
            restore_gl_state(saved)
            extra.restore()


def _mouse_in_current_window() -> bool:
    origin = imgui.get_window_pos()
    size = imgui.get_window_size()
    mouse = imgui.get_mouse_pos()
    return (
        origin.x <= mouse.x < origin.x + size.x
        and origin.y <= mouse.y < origin.y + size.y
    )


def _row_color(command: Command, ctx: CommandContext, enabled: bool) -> imgui.ImVec4:
    if not enabled:
        return _rgba(DISABLED)
    if command.label_role is not None:
        return _rgba(command.label_role(ctx))
    return _rgba(VALUE)
