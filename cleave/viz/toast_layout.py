"""Toast geometry inside the visualiser. No pygame or ImGui."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.modal_layout import TextMeasure
from cleave.viz.shell_layout import ShellLayout
from cleave.viz.theme import tuning_ui_metrics

Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class ToastGeometry:
    """Window rect plus each line's hit rect, in screen pixels."""

    rect: Rect
    persistent_line: Rect | None
    timed_line: Rect | None


def _clip(rect: Rect, bounds: Rect) -> Rect | None:
    x, y, width, height = rect
    bx, by, bw, bh = bounds
    x1 = max(x, bx)
    y1 = max(y, by)
    x2 = min(x + width, bx + bw)
    y2 = min(y + height, by + bh)
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2 - x1, y2 - y1)


def toast_geometry(
    layout: ShellLayout,
    measure: TextMeasure,
    *,
    persistent: str | None,
    timed: str | None,
) -> ToastGeometry:
    """One window at the visualiser top-left plus the tuning margin.

    Persistent text sits above the timed line. Width is the wider line plus
    padding, and both axes clamp to the visualiser minus the margins. The
    rect stays inside ``layout.visualiser``.
    """
    metrics = tuning_ui_metrics()
    margin = metrics.margin
    pad_x = metrics.padding
    pad_y = metrics.padding
    line_gap = metrics.line_gap
    line_h = measure.get_linesize()
    vx, vy, vw, vh = layout.visualiser
    empty = ToastGeometry((vx, vy, 0, 0), None, None)
    max_w = vw - 2 * margin
    max_h = vh - 2 * margin
    if max_w <= 0 or max_h <= 0:
        return empty

    lines: list[tuple[str, str]] = []
    if persistent is not None:
        lines.append(("persistent", persistent))
    if timed is not None:
        lines.append(("timed", timed))
    if not lines:
        return empty

    text_w = max(measure.size(text)[0] for _role, text in lines)
    width = min(max_w, text_w + pad_x * 2)
    count = len(lines)
    content_h = count * line_h + max(0, count - 1) * line_gap + pad_y * 2
    height = min(max_h, content_h)
    window = (vx + margin, vy + margin, width, height)

    cursor_y = window[1] + pad_y
    persistent_line: Rect | None = None
    timed_line: Rect | None = None
    for index, (role, _text) in enumerate(lines):
        line = _clip((window[0], cursor_y, width, line_h), window)
        if role == "persistent":
            persistent_line = line
        else:
            timed_line = line
        cursor_y += line_h
        if index + 1 < count:
            cursor_y += line_gap
    return ToastGeometry(window, persistent_line, timed_line)
