"""Tests for render overlay system font discovery."""

from __future__ import annotations

from unittest.mock import patch

from cleave.viz.fonts import (
    cycle_render_overlay_font,
    render_overlay_font_display,
)


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=("alpha", "bravo", "charlie"),
)
def test_render_overlay_font_display_in_list(_mock_fonts) -> None:
    assert render_overlay_font_display("bravo") == "bravo (2/3)"


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=("alpha", "bravo", "charlie"),
)
def test_render_overlay_font_display_unknown_omits_counter(_mock_fonts) -> None:
    assert render_overlay_font_display("missing") == "missing"


@patch("cleave.viz.fonts.pygame.font.SysFont")
@patch(
    "cleave.viz.fonts.pygame.font.get_fonts",
    return_value=["good", "bad", "also-good"],
)
def test_render_overlay_system_fonts_filters_non_latin(get_fonts, sys_font) -> None:
    from cleave.viz import fonts as fonts_mod

    fonts_mod._font_names_cache = None

    def metrics_side_effect(char):
        if char == "A":
            return [(0, 10, 0, 12, 10)]
        if char == "i":
            return [(0, 4, 0, 12, 4)]
        return [(0, 10, 0, 12, 10)]

    tofu_metrics = [(2, 12, 0, 18, 14)]

    def sys_font_factory(name, size):
        font = sys_font.return_value
        if name == "bad":

            def bad_metrics(ch):
                return tofu_metrics

            font.metrics.side_effect = bad_metrics
        else:
            font.metrics.side_effect = metrics_side_effect
        return font

    sys_font.side_effect = sys_font_factory
    assert fonts_mod.render_overlay_system_fonts() == ("also-good", "good")
    fonts_mod._font_names_cache = None


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=("alpha", "bravo", "charlie"),
)
def test_cycle_render_overlay_font_forward(_mock_fonts) -> None:
    assert cycle_render_overlay_font("bravo", forward=True) == "charlie"
    assert cycle_render_overlay_font("charlie", forward=True) == "alpha"


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=("alpha", "bravo", "charlie"),
)
def test_cycle_render_overlay_font_backward(_mock_fonts) -> None:
    assert cycle_render_overlay_font("bravo", forward=False) == "alpha"
    assert cycle_render_overlay_font("alpha", forward=False) == "charlie"


@patch(
    "cleave.viz.fonts.render_overlay_system_fonts",
    return_value=("alpha", "bravo", "charlie"),
)
def test_cycle_render_overlay_font_unknown_starts_at_first(_mock_fonts) -> None:
    assert cycle_render_overlay_font("missing", forward=True) == "bravo"


@patch("cleave.viz.fonts.render_overlay_system_fonts", return_value=())
def test_cycle_render_overlay_font_empty_list_keeps_current(_mock_fonts) -> None:
    assert cycle_render_overlay_font("monospace", forward=True) == "monospace"
