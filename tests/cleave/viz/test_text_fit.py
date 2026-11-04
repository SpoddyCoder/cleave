"""Tests for cleave.viz.text_fit."""

from __future__ import annotations

from cleave.viz.text_fit import (
    fit_path_label_to_width,
    fit_path_or_name_to_width,
    fit_text_to_width,
    wrap_text_to_width,
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


def test_fit_path_or_name_keeps_path_tail() -> None:
    font = overlay_font()
    label = "packs/drums/subdir/"
    width = font.size("…subdir/")[0]
    assert fit_path_or_name_to_width(font, label, width) == "…subdir/"


def test_fit_path_or_name_keeps_filename_start() -> None:
    font = overlay_font()
    name = "Geiss - Reaction Diffusion 2 - shared tail.milk"
    width = font.size("Geiss - Reaction…")[0]
    assert fit_path_or_name_to_width(font, name, width) == "Geiss - Reaction…"


def test_wrap_text_to_width_keeps_short_line() -> None:
    font = overlay_font()
    text = "Short title?"
    assert wrap_text_to_width(font, text, font.size(text)[0] + 10) == [text]


def test_wrap_text_to_width_preserves_explicit_newlines() -> None:
    font = overlay_font()
    text = (
        "Apply timeline preset?\n"
        "character: arc\n"
        "density: normal\n"
        "conductor: off"
    )
    max_px = max(font.size(part)[0] for part in text.split("\n")) + 10
    assert wrap_text_to_width(font, text, max_px) == [
        "Apply timeline preset?",
        "character: arc",
        "density: normal",
        "conductor: off",
    ]


def test_wrap_text_to_width_prefers_sentence_breaks() -> None:
    font = overlay_font()
    text = (
        "First sentence ends here. Second sentence continues with more words. "
        "Third sentence wraps as needed."
    )
    # Narrow enough that the full string wraps, but wide enough for each sentence.
    max_px = max(font.size(part)[0] for part in text.split(". ") if part) + font.size(".")[0]
    lines = wrap_text_to_width(font, text, max_px)
    assert len(lines) >= 2
    assert all(font.size(line)[0] <= max_px for line in lines)
    assert lines[0].endswith(".")
    assert " ".join(lines) == " ".join(text.split())
