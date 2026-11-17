from cleave.viz.button_paint import ButtonState, ButtonTone, button_look
from cleave.viz.theme import (
    BUTTON_BORDER,
    BUTTON_DANGER_HOVER_BG,
    BUTTON_HOVER_BORDER,
    BUTTON_OFF_CHOSEN_BG,
)


def _luma(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_rest_has_a_sheen_and_plain_keeps_its_border() -> None:
    look = button_look(ButtonTone.PLAIN, ButtonState.REST)
    assert _luma(look.top) > _luma(look.bottom)
    assert look.border == BUTTON_BORDER
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
    assert button_look(ButtonTone.PLAIN, ButtonState.HOVER).border == BUTTON_HOVER_BORDER
    assert button_look(ButtonTone.DANGER, ButtonState.HOVER).glow == BUTTON_DANGER_HOVER_BG
    assert button_look(ButtonTone.PRIMARY, ButtonState.HOVER).glow is not None


def test_fill_override_borders_in_its_own_shade() -> None:
    look = button_look(ButtonTone.PLAIN, ButtonState.REST, fill=BUTTON_OFF_CHOSEN_BG)
    assert look.border != BUTTON_BORDER
    assert _luma(look.border) > _luma(BUTTON_OFF_CHOSEN_BG)


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


def test_off_control_text_reads_on_its_fills() -> None:
    """Dimmed text stays readable over the whole gradient of a dimmed control."""
    from cleave.viz.theme import (
        LOCKED,
        LOCKED_MUTED,
        OFF_CONTROL_MUTED,
        OFF_CONTROL_TEXT,
    )

    off = button_look(ButtonTone.OFF, ButtonState.REST)
    chosen = button_look(ButtonTone.PLAIN, ButtonState.REST, fill=BUTTON_OFF_CHOSEN_BG)
    for text, look, floor in (
        (OFF_CONTROL_TEXT, off, 4.5),
        (OFF_CONTROL_TEXT, chosen, 3.5),
        (OFF_CONTROL_MUTED, off, 2.6),
        (LOCKED, chosen, 3.5),
        (LOCKED_MUTED, off, 2.5),
    ):
        assert _contrast(text, look.top) >= floor
        assert _contrast(text, look.bottom) >= floor
