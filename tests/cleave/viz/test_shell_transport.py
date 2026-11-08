"""Transport readout text for the shell bar."""

from __future__ import annotations

from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.shell_host import (
    TransportPart,
    TransportReadout,
    panel_border_overlap_px,
    transport_content_pad_y,
    transport_fps_text,
    transport_notice,
    transport_parts,
)
from cleave.viz.theme import ERROR_NOTIFICATION, HIGHLIGHT, VALUE
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
        TransportPart("PLAYING", VALUE, TransportField.PLAY, icon="\u25b6"),
        TransportPart("01:23", VALUE, TransportField.TIME),
        TransportPart("/ 04:12", VALUE, gap=False),
        TransportPart("BAR 34", VALUE, TransportField.BAR),
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
        TransportPart("PAUSE", VALUE, TransportField.PLAY, icon="\u275a\u275a"),
        TransportPart("00:00", VALUE, TransportField.TIME),
        TransportPart("/ 00:00", VALUE, gap=False),
        TransportPart("BAR —", VALUE),
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


def test_panel_border_overlap_shares_one_row() -> None:
    assert panel_border_overlap_px(1.0) == 1
    assert panel_border_overlap_px(2.0) == 1
    assert panel_border_overlap_px(0.0) == 0


def test_transport_content_pad_centers_one_line() -> None:
    assert transport_content_pad_y(23.0, 17.0) == 3.0
    assert transport_content_pad_y(10.0, 17.0) == 0.0
