"""Tests for the live colour palette in cleave.viz.theme."""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from imgui_bundle import imgui

from cleave.viz.button_paint import ButtonState, ButtonTone, button_look
from cleave.viz.imgui_theme import imgui_color_roles, lighten
from cleave.viz.theme import (
    BUILTIN_PALETTES,
    CHOCOLATE,
    DAYLIGHT,
    MINT,
    ULTRAVIOLET,
    Palette,
    palette,
    palette_generation,
    set_palette,
)
from cleave.viz.timeline_panel_cache import timeline_static_signature
from cleave.viz.timeline_strip_flash import selected_clip_flash_color
from tests.support.timeline import strip_view_state

_SOURCE_ROOT = Path(__file__).resolve().parents[3] / "cleave"


@contextmanager
def _live(value: Palette) -> Iterator[None]:
    previous = palette()
    set_palette(value)
    try:
        yield
    finally:
        set_palette(previous)


def _variant() -> Palette:
    return dataclasses.replace(
        ULTRAVIOLET,
        id="test",
        name="Test",
        value=(1, 2, 3),
        button_bg=(4, 5, 6),
        highlight=(7, 8, 9),
    )


def test_builtin_themes_in_setting_order() -> None:
    assert palette() is ULTRAVIOLET
    assert BUILTIN_PALETTES == (ULTRAVIOLET, CHOCOLATE, MINT, DAYLIGHT)
    assert [(p.id, p.name) for p in BUILTIN_PALETTES] == [
        ("ultraviolet", "Ultraviolet"),
        ("chocolate", "Chocolate"),
        ("mint", "Mint"),
        ("daylight", "Daylight"),
    ]


def test_set_palette_bumps_generation_only_on_change() -> None:
    generation = palette_generation()
    set_palette(palette())
    assert palette_generation() == generation
    with _live(_variant()):
        assert palette_generation() == generation + 1
    assert palette_generation() == generation + 2
    assert palette() is ULTRAVIOLET


def test_draw_helpers_follow_the_live_palette() -> None:
    variant = _variant()
    with _live(variant):
        assert imgui_color_roles()[imgui.Col_.text] == ((1, 2, 3), 1.0)
        assert imgui_color_roles()[imgui.Col_.button] == ((4, 5, 6), 1.0)
        assert imgui_color_roles()[imgui.Col_.modal_window_dim_bg][0] == variant.modal_scrim
        rest = button_look(ButtonTone.PLAIN, ButtonState.REST)
        assert rest.top == lighten((4, 5, 6), variant.button_sheen)
        assert selected_clip_flash_color(None) == (7, 8, 9)
    assert imgui_color_roles()[imgui.Col_.text] == (ULTRAVIOLET.value, 1.0)


def test_timeline_static_signature_changes_with_palette() -> None:
    state = strip_view_state()
    before = timeline_static_signature(state, panel_w=800, panel_h=120, visibility=1.0)
    with _live(_variant()):
        during = timeline_static_signature(state, panel_w=800, panel_h=120, visibility=1.0)
    assert before != during


def _calls_palette(node: ast.AST) -> bool:
    return any(
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Name)
        and sub.func.id == "palette"
        for sub in ast.walk(node)
    )


def _import_time_reads(body: list[ast.stmt]) -> Iterator[int]:
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for default in [*args.defaults, *(d for d in args.kw_defaults if d)]:
                if _calls_palette(default):
                    yield default.lineno
            for decorator in node.decorator_list:
                if _calls_palette(decorator):
                    yield decorator.lineno
        elif isinstance(node, ast.ClassDef):
            yield from _import_time_reads(node.body)
        elif _calls_palette(node):
            yield node.lineno


def test_no_module_reads_the_palette_at_import() -> None:
    """A colour bound at import would miss a theme change."""
    offenders = [
        f"{path.relative_to(_SOURCE_ROOT.parent)}:{line}"
        for path in sorted(_SOURCE_ROOT.rglob("*.py"))
        for line in _import_time_reads(ast.parse(path.read_text(encoding="utf-8")).body)
    ]
    assert offenders == []


def test_default_theme_is_ultraviolet_and_unknown_ids_fall_back() -> None:
    from cleave.config_schema.editor import DEFAULT_THEME
    from cleave.viz.theme import palette_for_theme, theme_ids, theme_label

    assert DEFAULT_THEME == ULTRAVIOLET.id
    assert theme_ids() == ("ultraviolet", "chocolate", "mint", "daylight")
    assert palette_for_theme("ultraviolet") is ULTRAVIOLET
    assert palette_for_theme("deleted-user-theme") is ULTRAVIOLET
    assert theme_label("ultraviolet") == "Ultraviolet"


def test_theme_row_steps_live_palette_and_writes_user_config(
    tmp_path: Path, monkeypatch
) -> None:
    import pygame

    from cleave import user_config
    from cleave.viz import theme
    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from tests.support.viz import keydown, make_controls, press_main_row

    variant = _variant()
    monkeypatch.setattr(theme, "BUILTIN_PALETTES", (ULTRAVIOLET, variant))
    user_path = tmp_path / "config.yaml"
    controls = make_controls()
    controls.cfg.user_config_path = user_path
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_THEME)
    with _live(ULTRAVIOLET):
        press_main_row(controls, keydown(pygame.K_RIGHT))
        assert controls.cfg.editor.theme == "test"
        assert palette() is variant
        assert user_config.load_user_config(user_path).editor.theme == "test"
        press_main_row(controls, keydown(pygame.K_RIGHT))
        assert palette() is variant
        press_main_row(controls, keydown(pygame.K_LEFT))
        assert controls.cfg.editor.theme == "ultraviolet"
        assert palette() is ULTRAVIOLET


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two colours."""

    def channel(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb: tuple[int, int, int]) -> float:
        r, g, b = (channel(v) for v in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _text_pairs(p: Palette) -> list[tuple[str, str, float]]:
    """(text role, fill role, minimum contrast) every built-in theme must meet."""
    body = 4.5
    # Labels on fills are short and bold enough for the WCAG UI floor.
    fill = 3.0
    return [
        ("value", "background", body),
        ("value", "surface_bg", body),
        ("label", "background", body),
        ("label", "surface_bg", body),
        ("highlight", "background", body),
        ("surface_text", "surface_bg", body),
        ("muted", "background", 3.0),
        ("disabled", "background", 3.0),
        ("on_hover", "button_hover_bg", fill),
        ("on_hover", "button_active_bg", fill),
        ("on_primary", "button_primary_bg", fill),
        ("on_primary", "button_primary_hover_bg", fill),
        ("on_danger", "button_danger_bg", fill),
        ("on_danger", "button_danger_hover_bg", fill),
        ("on_accent", "accent_from", fill),
        ("on_accent", "accent_to", fill),
        ("on_lit_icon", "nav_on_bg", fill),
        ("on_lit_icon", "solo_bg", fill),
        ("on_lit_icon", "rec_bg", fill),
        ("nav_lock_glyph", "nav_lock_bg", fill),
        ("override_glyph", "override_bg", fill),
        ("off_control_text", "button_off_bg", body),
    ]


def test_every_builtin_theme_keeps_its_text_readable() -> None:
    failures = [
        f"{p.id}: {text} on {fill} is {_contrast(getattr(p, text), getattr(p, fill)):.2f}"
        for p in BUILTIN_PALETTES
        for text, fill, floor in _text_pairs(p)
        if _contrast(getattr(p, text), getattr(p, fill)) < floor
    ]
    assert failures == []


def test_ultraviolet_on_fill_roles_match_its_panel_text() -> None:
    """Ultraviolet's split roles keep the look it had with one text colour."""
    for role in ("on_hover", "on_primary", "on_danger", "on_accent", "on_lit_icon"):
        assert getattr(ULTRAVIOLET, role) == ULTRAVIOLET.value
    assert ULTRAVIOLET.on_hover_muted == ULTRAVIOLET.surface_text
    assert ULTRAVIOLET.modal_scrim == (0, 0, 0)
