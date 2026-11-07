"""Editor window geometry in the user config: restored size and maximised state.

The window owns this section. Settings changes rewrite ``editor:`` and leave
``window:`` alone, so the size the user dragged to survives them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cleave.config_schema.descriptors import (
    FieldDescriptor,
    ParseCtx,
    PersistCtx,
    as_mapping,
    dump_fields,
    dump_scalar,
    parse_field,
    require_non_negative_number,
)

WINDOW_SECTION_KEY = "window"

DEFAULT_WINDOW_WIDTH = 1920
DEFAULT_WINDOW_HEIGHT = 1080
DEFAULT_WINDOW_MAXIMISED = False
# Smallest window at 100% UI scale. Scaled with the UI and capped at the desktop.
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 600
# Gap kept around a saved size that is opened on a smaller desktop.
WINDOW_DESKTOP_MARGIN = 64


@dataclass(frozen=True)
class WindowGeometry:
    """Restored (not maximised) window size, and whether it was maximised."""

    width: int = DEFAULT_WINDOW_WIDTH
    height: int = DEFAULT_WINDOW_HEIGHT
    maximised: bool = DEFAULT_WINDOW_MAXIMISED


def clamp_window_width(value: int | float) -> int:
    return max(WINDOW_MIN_WIDTH, int(round(value)))


def clamp_window_height(value: int | float) -> int:
    return max(WINDOW_MIN_HEIGHT, int(round(value)))


def _parse_bool(raw: Any, _ctx: ParseCtx, label: str) -> bool:
    if not isinstance(raw, bool):
        raise ValueError(f"{label} must be true or false")
    return raw


WINDOW_FIELDS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor(
        "width",
        DEFAULT_WINDOW_WIDTH,
        lambda raw, ctx, label: clamp_window_width(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_window_width(value),
    ),
    FieldDescriptor(
        "height",
        DEFAULT_WINDOW_HEIGHT,
        lambda raw, ctx, label: clamp_window_height(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_window_height(value),
    ),
    FieldDescriptor(
        "maximised",
        DEFAULT_WINDOW_MAXIMISED,
        _parse_bool,
        dump_scalar,
    ),
)


def parse_window_section(data: dict[str, Any]) -> WindowGeometry:
    window = as_mapping(data.get(WINDOW_SECTION_KEY), WINDOW_SECTION_KEY)
    ctx = ParseCtx()
    parsed = {
        field.yaml_key: parse_field(window, field, ctx, WINDOW_SECTION_KEY)
        for field in WINDOW_FIELDS
    }
    return WindowGeometry(
        width=parsed["width"],
        height=parsed["height"],
        maximised=parsed["maximised"],
    )


def dump_window_section(geometry: WindowGeometry) -> dict[str, Any]:
    values = {
        "width": geometry.width,
        "height": geometry.height,
        "maximised": geometry.maximised,
    }
    return dump_fields(WINDOW_FIELDS, values, PersistCtx(cfg=None, session=None))


def fit_window_to_desktop(
    geometry: WindowGeometry,
    desktop: tuple[int, int] | None,
) -> WindowGeometry:
    """Shrink a saved size that does not fit the desktop, and open it maximised.

    No desktop size (headless) keeps the saved geometry.
    """
    if desktop is None:
        return geometry
    desk_w, desk_h = desktop
    max_w = max(1, desk_w - WINDOW_DESKTOP_MARGIN)
    max_h = max(1, desk_h - WINDOW_DESKTOP_MARGIN)
    if geometry.width <= max_w and geometry.height <= max_h:
        return geometry
    return WindowGeometry(
        width=min(geometry.width, max_w),
        height=min(geometry.height, max_h),
        maximised=True,
    )


def window_minimum_size(
    ui_scale: float,
    desktop: tuple[int, int] | None,
) -> tuple[int, int]:
    """Minimum window size at *ui_scale* (1.0 is 100%), capped at the desktop."""
    width = round(WINDOW_MIN_WIDTH * ui_scale)
    height = round(WINDOW_MIN_HEIGHT * ui_scale)
    if desktop is not None:
        width = min(width, desktop[0])
        height = min(height, desktop[1])
    return (max(1, width), max(1, height))
