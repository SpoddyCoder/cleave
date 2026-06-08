"""Tests for cleave.viz.text_fit."""

from __future__ import annotations

from cleave.viz.text_fit import (
    fit_counter_label_to_width,
    fit_path_label_to_width,
    fit_text_to_width,
)
from tests.support.viz import overlay_font


def test_fit_text_to_width_fits_as_is() -> None:
    font = overlay_font()
    text = "short"
    width = font.size(text)[0] + 20
    assert fit_text_to_width(font, text, width) == text


def test_fit_text_to_width_ellipsis() -> None:
    font = overlay_font()
    text = "abcdefghijklmnopqrstuvwxyz"
    width = font.size("abc…")[0]
    fitted = fit_text_to_width(font, text, width)
    assert fitted.endswith("…")
    assert font.size(fitted)[0] <= width
    assert len(fitted) < len(text)


def test_fit_text_to_width_zero_width() -> None:
    font = overlay_font()
    assert fit_text_to_width(font, "anything", 0) == ""
    assert fit_text_to_width(font, "anything", -10) == ""


def test_fit_path_label_preserves_tail() -> None:
    font = overlay_font()
    label = "presets/drums/subdir/anchor.milk"
    tail = "subdir/anchor.milk"
    width = font.size("…" + tail)[0]
    fitted = fit_path_label_to_width(font, label, width)
    assert fitted.endswith(tail)
    assert fitted.startswith("…")
    assert font.size(fitted)[0] <= width


def test_fit_counter_label_preserves_suffix() -> None:
    font = overlay_font()
    label = "presets/vocals/long/path/to/preset.milk (3/12)"
    suffix = " (3/12)"
    suffix_w = font.size(suffix)[0]
    width = suffix_w + font.size("…tail.milk")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.endswith(suffix)
    assert font.size(fitted)[0] <= width
