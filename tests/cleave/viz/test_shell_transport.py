"""Transport readout text for the shell bar."""

from __future__ import annotations

from cleave.viz.shell_host import (
    TransportReadout,
    border_stroke_outset_px,
    side_panel_seat_px,
    transport_content_pad_y,
    transport_parts,
)
from cleave.viz.theme import ACTION, MUTED, VALUE


def test_transport_parts_while_playing() -> None:
    readout = TransportReadout(
        paused=False,
        position_sec=83.4,
        duration_sec=252.0,
        bar_text="34",
        fps=60.0,
        recording=False,
    )
    assert transport_parts(readout) == [
        ("\u25b6 playing", ACTION),
        ("01:23 / 04:12", VALUE),
        ("bar 34", MUTED),
        ("60 fps", MUTED),
        ("rec off", MUTED),
    ]


def test_transport_parts_while_paused_and_recording() -> None:
    readout = TransportReadout(
        paused=True,
        position_sec=0.0,
        duration_sec=0.0,
        bar_text="—",
        fps=None,
        recording=True,
    )
    assert transport_parts(readout) == [
        ("\u275a\u275a pause", ACTION),
        ("00:00 / 00:00", VALUE),
        ("bar —", MUTED),
        ("— fps", MUTED),
        ("rec on", MUTED),
    ]


def test_border_stroke_outset_matches_imgui_rect() -> None:
    # AddRect path is inset 0.5px. AA adds a 1px fringe past half the thickness.
    assert border_stroke_outset_px(1.0, anti_aliased_lines=True) == 1.0
    assert border_stroke_outset_px(2.0, anti_aliased_lines=True) == 1.5
    assert border_stroke_outset_px(1.0, anti_aliased_lines=False) == 0.0
    assert border_stroke_outset_px(2.0, anti_aliased_lines=False) == 0.5
    assert border_stroke_outset_px(0.0, anti_aliased_lines=True) == 0.0


def test_side_panel_seat_clears_the_stroke() -> None:
    assert side_panel_seat_px(1.0, anti_aliased_lines=True) == 1
    assert side_panel_seat_px(2.0, anti_aliased_lines=True) == 2
    assert side_panel_seat_px(1.0, anti_aliased_lines=False) == 0
    assert side_panel_seat_px(2.0, anti_aliased_lines=False) == 1


def test_transport_content_pad_centers_one_line() -> None:
    assert transport_content_pad_y(23.0, 17.0) == 3.0
    assert transport_content_pad_y(10.0, 17.0) == 0.0
