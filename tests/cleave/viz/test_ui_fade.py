"""UiFade hold, linear fade, and disabled hold."""

from __future__ import annotations

from cleave.config_schema.editor import DEFAULT_UI_FADE_SEC
from cleave.viz.ui_fade import UiFade


def test_ui_fade_starts_hidden() -> None:
    fade = UiFade()
    assert fade.is_visible() is False
    assert fade.visibility == 0.0


def test_notify_input_shows_and_hide_immediately_hides() -> None:
    fade = UiFade()
    fade.notify_input()
    assert fade.is_visible() is True
    assert fade.visibility == 1.0
    fade.hide_immediately()
    assert fade.is_visible() is False
    assert fade.visibility == 0.0


def test_hold_then_fade() -> None:
    fade = UiFade()
    fade.notify_input()
    fade.update(DEFAULT_UI_FADE_SEC - 0.1)
    assert fade.visibility == 1.0
    fade.update(0.2)
    assert fade.visibility < 1.0


def test_hold_idle_sec_zero_stays_visible_until_hide() -> None:
    fade = UiFade(hold_idle_sec=0.0)
    fade.notify_input()
    for _ in range(200):
        fade.update(1.0)
    assert fade.is_visible() is True
    fade.hide_immediately()
    assert fade.is_visible() is False
