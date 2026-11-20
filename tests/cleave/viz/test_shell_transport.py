"""Transport readout text for the shell bar."""

from __future__ import annotations

from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.shell_transport import (
    TransportPart,
    TransportReadout,
    transport_content_pad_y,
    transport_fps_text,
    transport_notice,
    transport_notice_span,
    transport_parts,
)
from cleave.viz.shell_windows import panel_border_overlap_px
from cleave.viz.theme import palette
from cleave.viz.transport_controls import TransportField


def test_transport_parts_while_playing() -> None:
    readout = TransportReadout(
        paused=False,
        position_sec=83.4,
        duration_sec=252.0,
        bar_text="34",
        fps=60.0,
    )
    assert transport_parts(readout) == [
        TransportPart("PLAYING", palette().value, TransportField.PLAY, icon="\u25b6"),
        TransportPart("01:23", palette().value, TransportField.TIME),
        TransportPart("/ 04:12", palette().value, gap=False),
        TransportPart("BAR 34", palette().value, TransportField.BAR),
    ]
    assert transport_fps_text(readout) == "60 FPS"


def test_transport_parts_while_paused() -> None:
    readout = TransportReadout(
        paused=True,
        position_sec=0.0,
        duration_sec=0.0,
        bar_text="—",
        fps=None,
    )
    assert transport_parts(readout) == [
        TransportPart("PAUSED", palette().value, TransportField.PLAY, icon="\u275a\u275a"),
        TransportPart("00:00", palette().value, TransportField.TIME),
        TransportPart("/ 00:00", palette().value, gap=False),
        TransportPart("BAR —", palette().value),
    ]
    assert transport_fps_text(readout) == "— FPS"


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
    assert warning.accent == palette().highlight
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
    assert error.accent == palette().error_notification
    assert error.timed is False
    assert error.elapsed_sec == 3.0
    assert transport_notice(_active()) is None


def test_panel_border_overlap_shares_one_row() -> None:
    assert panel_border_overlap_px(1.0) == 1
    assert panel_border_overlap_px(2.0) == 2
    assert panel_border_overlap_px(0.0) == 0


def test_transport_content_pad_centers_one_line_above_the_rule() -> None:
    assert transport_content_pad_y(23.0, 17.0, 0.0) == 3.0
    assert transport_content_pad_y(25.0, 17.0, 2.0) == 3.0
    assert transport_content_pad_y(24.0, 17.0, 2.0) == 2.0
    assert transport_content_pad_y(10.0, 17.0, 2.0) == 0.0


def test_transport_notice_span_centres_a_chip_that_fits() -> None:
    assert transport_notice_span(100.0, 0.0, 1000.0, 300.0, 900.0) == (450.0, 100.0)


def test_transport_notice_span_slides_off_centre_to_clear_the_labels() -> None:
    # Centred would start at 350, inside the left labels ending at 400.
    assert transport_notice_span(300.0, 0.0, 1000.0, 400.0, 900.0) == (400.0, 300.0)


def test_transport_notice_span_fills_the_room_when_too_long() -> None:
    assert transport_notice_span(2000.0, 0.0, 1000.0, 400.0, 900.0) == (400.0, 500.0)
    assert transport_notice_span(100.0, 0.0, 1000.0, 600.0, 500.0) == (600.0, 0.0)
