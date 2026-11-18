from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from cleave.viz.button_paint import ButtonState, ButtonTone, button_look, button_text_role
from cleave.viz.theme import BUILTIN_PALETTES, Palette, palette, set_palette


@contextmanager
def _live(value: Palette) -> Iterator[None]:
    previous = palette()
    set_palette(value)
    try:
        yield
    finally:
        set_palette(previous)


def _luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_rest_has_a_sheen_and_plain_keeps_its_border() -> None:
    look = button_look(ButtonTone.PLAIN, ButtonState.REST)
    assert _luma(look.top) > _luma(look.bottom)
    assert look.border == palette().button_border
    assert look.glow is None


def test_hover_is_brighter_than_rest_for_every_tone() -> None:
    for tone in ButtonTone:
        rest = button_look(tone, ButtonState.REST)
        hover = button_look(tone, ButtonState.HOVER)
        assert _luma(hover.border) > _luma(rest.border)
        assert hover.top != rest.top


def test_pressed_sinks_with_the_shade_on_top() -> None:
    for tone in ButtonTone:
        look = button_look(tone, ButtonState.PRESSED)
        assert _luma(look.top) < _luma(look.bottom)


def test_only_primary_and_danger_glow() -> None:
    assert button_look(ButtonTone.PLAIN, ButtonState.HOVER).glow is None
    assert button_look(ButtonTone.PLAIN, ButtonState.HOVER).border == palette().button_hover_border
    assert button_look(ButtonTone.DANGER, ButtonState.HOVER).glow == palette().button_danger_hover_bg
    assert button_look(ButtonTone.PRIMARY, ButtonState.HOVER).glow is not None


def test_rest_borders_are_their_tones_roles() -> None:
    p = palette()
    for tone, border in (
        (ButtonTone.PLAIN, p.button_border),
        (ButtonTone.OFF, p.button_off_border),
        (ButtonTone.OFF_CHOSEN, p.button_off_chosen_border),
        (ButtonTone.PRIMARY, p.button_primary_border),
        (ButtonTone.DANGER, p.button_danger_border),
    ):
        assert button_look(tone, ButtonState.REST).border == border


def test_text_role_follows_the_fill() -> None:
    p = palette()
    for state in ButtonState:
        assert button_text_role(ButtonTone.PRIMARY, state) == p.on_primary
        assert button_text_role(ButtonTone.DANGER, state) == p.on_danger
    for tone in (ButtonTone.PLAIN, ButtonTone.OFF, ButtonTone.OFF_CHOSEN):
        assert button_text_role(tone, ButtonState.REST) is None
        assert button_text_role(tone, ButtonState.HOVER) == p.on_hover
        assert button_text_role(tone, ButtonState.PRESSED) == p.on_hover


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb: tuple[int, int, int]) -> float:
        r, g, b = (channel(v) for v in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_off_rests_darker_and_lights_like_plain() -> None:
    off = button_look(ButtonTone.OFF, ButtonState.REST)
    plain = button_look(ButtonTone.PLAIN, ButtonState.REST)
    assert _luma(off.top) < _luma(plain.top)
    assert off.glow is None
    for state in (ButtonState.HOVER, ButtonState.PRESSED):
        assert button_look(ButtonTone.OFF, state) == button_look(ButtonTone.PLAIN, state)


@pytest.mark.parametrize("theme", BUILTIN_PALETTES, ids=lambda theme: theme.id)
def test_text_reads_over_every_button_gradient(theme: Palette) -> None:
    """Each fill's text stays readable over the whole gradient, in every state."""
    with _live(theme):
        for tone in ButtonTone:
            for state in ButtonState:
                text = button_text_role(tone, state)
                if text is None:
                    continue
                look = button_look(tone, state)
                assert _contrast(text, look.top) >= 3.0, (tone, state)
                assert _contrast(text, look.bottom) >= 3.0, (tone, state)


@pytest.mark.parametrize("theme", BUILTIN_PALETTES, ids=lambda theme: theme.id)
def test_off_control_text_reads_on_its_fills(theme: Palette) -> None:
    """Dimmed text stays readable over the whole gradient of a dimmed control."""
    with _live(theme):
        _assert_off_control_text_reads()


def _assert_off_control_text_reads() -> None:
    off = button_look(ButtonTone.OFF, ButtonState.REST)
    chosen = button_look(ButtonTone.OFF_CHOSEN, ButtonState.REST)
    for text, look, floor in (
        (palette().off_control_text, off, 4.5),
        (palette().off_control_text, chosen, 3.5),
        (palette().off_control_muted, off, 2.6),
        (palette().locked, chosen, 3.5),
        (palette().locked_muted, off, 2.5),
    ):
        assert _contrast(text, look.top) >= floor
        assert _contrast(text, look.bottom) >= floor
