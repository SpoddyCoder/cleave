"""Headless inspector choice rows: segments, combos, the open list, and steppers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pygame

from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.shell_host import ShellHost
from cleave.viz.value_nudge import centre_pad
from tests.cleave.viz.test_modal_surface import _button, _center, _draw, _host, _motion
from tests.support.viz import keydown, make_controls

_QUALITY = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
_NAV_SIDE = RowDescriptor(RowKind.SETTINGS_NAVIGATOR_SIDE)


@contextmanager
def _inspector(page_id: str) -> Iterator[tuple[object, object]]:
    """A shell drawing the real inspector rows of ``page_id``."""
    controls = make_controls(("layer_1",))
    controls.navigator.open_page(page_id)
    with _host() as host:
        host._controls = controls
        host._draw_inspector = lambda state: ShellHost._draw_inspector(host, state)
        yield host, controls


def _release(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def _frame(host: object, pos: tuple[int, int], *, click: bool = False) -> None:
    host.process_event(_motion(pos))
    if click:
        host.process_event(_button(pos))
    _draw(host)
    if click:
        host.process_event(_release(pos))
        _draw(host)


def test_a_long_list_draws_as_a_combo_and_a_click_opens_it() -> None:
    with _inspector("settings.preview") as (host, controls):
        _frame(host, (0, 0))
        combo = host._choice_rects[_QUALITY]
        _frame(host, _center(combo), click=True)
        view = controls.inline_edit.choice_view
        assert view is not None and view.target == _QUALITY
        assert view.options[view.chosen] == "full-quality"
        assert len(host._choice_list_rows) == 5


def test_a_row_click_in_the_open_list_picks_that_option() -> None:
    with _inspector("settings.preview") as (host, controls):
        _frame(host, (0, 0))
        _frame(host, _center(host._choice_rects[_QUALITY]), click=True)
        _frame(host, _center(host._choice_list_rows[1]), click=True)
        assert controls.inline_edit.choice_view is None
        assert controls.cfg.editor.preview_quality == "performance"


def test_a_click_outside_the_list_closes_it_and_keeps_the_value() -> None:
    with _inspector("settings.preview") as (host, controls):
        _frame(host, (0, 0))
        _frame(host, _center(host._choice_rects[_QUALITY]), click=True)
        _frame(host, (1200, 700), click=True)
        assert controls.inline_edit.choice_view is None
        assert controls.cfg.editor.preview_quality == "full-quality"


def test_a_short_list_draws_as_segments_and_a_click_chooses() -> None:
    with _inspector("settings.ui") as (host, controls):
        _frame(host, (0, 0))
        x, y, w, h = host._choice_rects[_NAV_SIDE]
        assert controls.cfg.editor.navigator_side == "left"
        _frame(host, (x + w - 4, y + h // 2), click=True)
        assert controls.cfg.editor.navigator_side == "right"
        assert controls.inline_edit.choice_view is None


def test_enter_opens_a_combo_row_and_enter_again_picks() -> None:
    controls = make_controls(("layer_1",))
    controls.navigator.open_page("settings.preview")
    controls.shell_focus.inspector_cursor = _QUALITY
    controls.inspector.handle_keydown(keydown(pygame.K_RETURN))
    view = controls.inline_edit.choice_view
    assert view is not None and view.highlighted == view.chosen
    controls.inline_edit.handle_keydown(keydown(pygame.K_UP))
    controls.inline_edit.handle_keydown(keydown(pygame.K_RETURN))
    assert controls.inline_edit.choice_view is None
    assert controls.cfg.editor.preview_quality == "balanced"


def test_escape_closes_the_list_without_a_change() -> None:
    controls = make_controls(("layer_1",))
    controls.navigator.open_page("settings.preview")
    controls.shell_focus.inspector_cursor = _QUALITY
    controls.inspector.handle_keydown(keydown(pygame.K_RETURN))
    controls.inline_edit.handle_keydown(keydown(pygame.K_DOWN))
    controls.inline_edit.handle_keydown(keydown(pygame.K_ESCAPE))
    assert controls.inline_edit.choice_view is None
    assert controls.cfg.editor.preview_quality == "full-quality"


def test_enter_on_a_segment_row_opens_nothing() -> None:
    controls = make_controls(("layer_1",))
    controls.navigator.open_page("settings.ui")
    controls.shell_focus.inspector_cursor = _NAV_SIDE
    controls.inspector.handle_keydown(keydown(pygame.K_RETURN))
    assert controls.inline_edit.choice_view is None


def test_a_jump_pick_changes_the_stem_once() -> None:
    controls = make_controls(("layer_1",))
    changes: list[str] = []
    controls._layer_bindings = None
    original = controls.layer_mutations.step_stem

    def counted(slot: str, *, delta: int) -> None:
        changes.append(slot)
        original(slot, delta=delta)

    controls.layer_mutations.step_stem = counted
    from cleave.viz.row_spec import apply_field_choice

    stem = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    assert apply_field_choice(controls, stem, 3) is True
    assert changes == ["layer_1"]
    assert controls.session.layers["layer_1"].stem == "other"


def test_centre_pad_fixes_the_width() -> None:
    assert centre_pad("5", 3) == " 5 "
    assert centre_pad("10", 3) == "10 "
    assert centre_pad("1000", 3) == "1000"


def test_a_stepper_keeps_the_widest_width_it_has_shown() -> None:
    with _inspector("settings.preview") as (host, _controls):
        kind = RowKind.SETTINGS_RESIDUAL_LATENCY_MS
        assert host._fixed_width_value(kind, "100 ms") == "100 ms"
        assert host._fixed_width_value(kind, "5 ms") == " 5 ms "
