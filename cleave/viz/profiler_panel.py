"""Frame timer panel: the profiler's averages, drawn over the visualiser."""

from __future__ import annotations

from imgui_bundle import imgui

from cleave.viz.imgui_theme import rgba
from cleave.viz.overlay_profiler import FrameReport, report_rows
from cleave.viz.theme import LABEL, VALUE, ui_px

_WINDOW = "##frame-timer"
_INSET_PX = 8
_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.always_auto_resize)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_inputs)
)


def draw_profiler_panel(report: FrameReport | None, origin: tuple[int, int]) -> None:
    """Draw the panel inset from *origin*. It takes no pointer or keys."""
    rows = report_rows(report)
    label_chars = max(len(label) for label, _value in rows)
    value_chars = max(len(value) for _label, value in rows)
    inset = ui_px(_INSET_PX)
    imgui.set_next_window_pos(
        imgui.ImVec2(float(origin[0] + inset), float(origin[1] + inset)),
        imgui.Cond_.always,
    )
    imgui.begin(_WINDOW, None, _FLAGS)
    try:
        imgui.internal.bring_window_to_display_front(
            imgui.internal.find_window_by_name(_WINDOW)
        )
        # The shell font is monospace, so padding lines the columns up.
        for label, value in rows:
            imgui.text_colored(rgba(LABEL), label.ljust(label_chars))
            imgui.same_line()
            imgui.text_colored(rgba(VALUE), value.rjust(value_chars))
    finally:
        imgui.end()
