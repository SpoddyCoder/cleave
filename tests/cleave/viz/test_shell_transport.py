"""Transport readout text for the shell bar."""

from __future__ import annotations

from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.shell_host import (
    TransportReadout,
    border_stroke_outset_px,
    side_panel_seat_px,
    transport_content_pad_y,
    transport_fps_text,
    transport_notice,
    transport_parts,
)
from cleave.viz.theme import ACTION, ERROR_NOTIFICATION, HIGHLIGHT, MUTED, VALUE


def test_transport_parts_while_playing() -> None:
    readout = TransportReadout(
        paused=False,
        position_sec=83.4,
        duration_sec=252.0,
        bar_text="34",
        fps=60.0,
    )
    assert transport_parts(readout) == [
        ("\u25b6 playing", ACTION),
        ("01:23 / 04:12", VALUE),
        ("bar 34", MUTED),
    ]
    assert transport_fps_text(readout) == "60 fps"


def test_transport_parts_while_paused() -> None:
    readout = TransportReadout(
        paused=True,
        position_sec=0.0,
        duration_sec=0.0,
        bar_text="—",
        fps=None,
    )
    assert transport_parts(readout) == [
        ("\u275a\u275a pause", ACTION),
        ("00:00 / 00:00", VALUE),
        ("bar —", MUTED),
    ]
    assert transport_fps_text(readout) == "— fps"


def _active(
    *,
    persistent: str | None = None,
    persistent_elapsed: float = 0.0,
    message: str | None = None,
    elapsed: float = 0.0,
) -> PanelNotificationActive:
    return PanelNotificationActive(
        persistent_message=persistent,
        persistent_elapsed_sec=persistent_elapsed,
        message=message,
        remaining_sec=2.0 if message is not None else 0.0,
        elapsed_sec=elapsed,
    )


def test_transport_notice_prefers_the_timed_warning() -> None:
    warning = transport_notice(_active(message="Saved", elapsed=0.1))
    assert warning is not None
    assert warning.text == "Saved"
    assert warning.accent == HIGHLIGHT
    assert warning.timed is True
    assert warning.elapsed_sec == 0.1

    both = transport_notice(
        _active(persistent="Missing stem", message="Saved", elapsed=0.2)
    )
    assert both is not None
    assert both.text == "Saved"
    assert both.timed is True


def test_transport_notice_uses_the_persistent_error_when_no_warning() -> None:
    error = transport_notice(
        _active(persistent="Missing stem", persistent_elapsed=3.0)
    )
    assert error is not None
    assert error.text == "Missing stem"
    assert error.accent == ERROR_NOTIFICATION
    assert error.timed is False
    assert error.elapsed_sec == 3.0
    assert transport_notice(_active()) is None


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
