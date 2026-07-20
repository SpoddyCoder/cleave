"""Tests for cleave.viz.text_fit."""

from __future__ import annotations

from cleave.viz.text_fit import (
    fit_counter_label_to_width,
    fit_path_label_to_width,
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


def test_fit_counter_label_preserves_suffix() -> None:
    font = overlay_font()
    label = "presets/vocals/long/path/to/preset.milk (3/12)"
    suffix = " (3/12)"
    suffix_w = font.size(suffix)[0]
    width = suffix_w + font.size("…tail.milk")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.endswith(suffix)
    assert font.size(fitted)[0] <= width


def test_fit_counter_label_preserves_curation_marker() -> None:
    font = overlay_font()
    label = (
        "Slow transition to black - gas effect + zoom in + orange filter "
        "=== Tripgnosis - FlameOrb --- Isosceles edit.milk (2/5) [B]"
    )
    suffix = " (2/5) [B]"
    # Narrow enough that a naive path fitter would latch onto the "/" in (2/5).
    width = font.size(suffix)[0] + font.size("Slow transition to black…")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.endswith(suffix)
    assert fitted.startswith("Slow")
    assert "…/" not in fitted
    assert font.size(fitted)[0] <= width


def test_fit_counter_label_preserves_favourite_and_blacklist_markers() -> None:
    font = overlay_font()
    label = "long-name-without-much-room-left.milk (1/9) [FB]"
    suffix = " (1/9) [FB]"
    width = font.size(suffix)[0] + font.size("long-name…")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.endswith(suffix)
    assert font.size(fitted)[0] <= width


def test_fit_counter_label_preserves_user_defined_marker() -> None:
    font = overlay_font()
    label = "long-name-without-much-room-left.milk (1/9) [FU]"
    suffix = " (1/9) [FU]"
    width = font.size(suffix)[0] + font.size("long-name…")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.endswith(suffix)
    assert font.size(fitted)[0] <= width


def test_fit_counter_label_preserves_full_fbu_marker() -> None:
    font = overlay_font()
    label = "long-name-without-much-room-left.milk (2/8) [FBU]"
    suffix = " (2/8) [FBU]"
    width = font.size(suffix)[0] + font.size("long-name…")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.endswith(suffix)
    assert font.size(fitted)[0] <= width


def test_fit_counter_label_marker_only_user_preset() -> None:
    font = overlay_font()
    label = "very-long-user-preset-filename-that-needs-truncation.milk [B]"
    suffix = " [B]"
    width = font.size(suffix)[0] + font.size("very-long-user…")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.endswith(suffix)
    assert fitted.startswith("very")
    assert font.size(fitted)[0] <= width


def test_fit_counter_label_filename_keeps_start_not_shared_tail() -> None:
    font = overlay_font()
    a = (
        "Slow transition to black - gas effect + zoom in === "
        "Tripgnosis - FlameOrb --- Isosceles edit.milk (3/5) [B]"
    )
    b = (
        "Slow transition to black - gas effect + zoom out === "
        "amandio c - magnetosphere --- Isosceles edit.milk (4/5) [B]"
    )
    width = font.size(" (3/5) [B]")[0] + font.size(
        "Slow transition to black - gas effect + zoom i…"
    )[0]
    fitted_a = fit_counter_label_to_width(font, a, width)
    fitted_b = fit_counter_label_to_width(font, b, width)
    assert fitted_a.endswith(" (3/5) [B]")
    assert fitted_b.endswith(" (4/5) [B]")
    assert fitted_a.startswith("Slow")
    assert fitted_b.startswith("Slow")
    # Path-style tail keep would collapse both to "…Isosceles edit.milk".
    assert "Isosceles" not in fitted_a
    assert "Isosceles" not in fitted_b
    assert "zoom i" in fitted_a
    assert "zoom o" in fitted_b
    assert fitted_a != fitted_b


def test_fit_counter_label_suffix_only_when_budget_tiny() -> None:
    font = overlay_font()
    label = "anything.milk (1/2) [B]"
    suffix = " (1/2) [B]"
    fitted = fit_counter_label_to_width(font, label, font.size(suffix)[0] - 1)
    assert fitted == suffix


def test_fit_counter_label_preserves_directory_tree_marker() -> None:
    font = overlay_font()
    for marker in ("[▲]", "[▼]", "[▲▼]"):
        label = f"{marker}presets/very/long/directory/path/for/testing/ (12/99)"
        suffix = " (12/99)"
        reserved = f"{marker}{suffix}"
        width = font.size(reserved)[0] + font.size("…testing/")[0]
        fitted = fit_counter_label_to_width(font, label, width)
        assert fitted.startswith(marker)
        assert fitted.endswith(suffix)
        assert font.size(fitted)[0] <= width


def test_fit_counter_label_both_tree_markers_reserve_full_width() -> None:
    """Both-direction prefix is longer; truncation must keep the whole marker."""
    font = overlay_font()
    label = "[▲▼]presets/very/long/directory/path/for/testing/ (3/9)"
    reserved = "[▲▼] (3/9)"
    single = "[▲] (3/9)"
    # Budget fits both arrows + counter + a short head; if the fitter reserved
    # only a single-arrow width, the second triangle would be truncated away.
    width = font.size(reserved)[0] + font.size("…testing/")[0]
    fitted = fit_counter_label_to_width(font, label, width)
    assert fitted.startswith("[▲▼]")
    assert fitted.endswith(" (3/9)")
    assert font.size(fitted)[0] <= width
    tiny = fit_counter_label_to_width(font, label, font.size(reserved)[0] - 1)
    assert tiny == reserved
    assert tiny != single


def test_wrap_text_to_width_keeps_short_line() -> None:
    font = overlay_font()
    text = "Short title?"
    assert wrap_text_to_width(font, text, font.size(text)[0] + 10) == [text]


def test_wrap_text_to_width_preserves_explicit_newlines() -> None:
    font = overlay_font()
    text = "Apply timeline preset?\ncharacter: arc\ncrescendo: no\ndensity: normal"
    max_px = max(font.size(part)[0] for part in text.split("\n")) + 10
    assert wrap_text_to_width(font, text, max_px) == [
        "Apply timeline preset?",
        "character: arc",
        "crescendo: no",
        "density: normal",
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
