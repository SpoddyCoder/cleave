"""Sideways drag on stepped inspector values. No ImGui window."""

from __future__ import annotations

from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import apply_field_horizontal
from cleave.viz.shell_host import (
    _VALUE_DRAG_THRESHOLD_PX,
    apply_value_drag,
    value_drag_steps,
)
from tests.cleave.viz.test_controls import _make_controls

_OPACITY = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")


def _opacity(controls) -> int:
    return controls.session.layers["layer_1"].opacity_pct


def test_value_drag_steps_direction_count_and_remainder() -> None:
    assert value_drag_steps(25.0, 10.0) == (2, 5.0)
    assert value_drag_steps(-25.0, 10.0) == (-2, -5.0)
    assert value_drag_steps(9.0, 10.0) == (0, 9.0)
    assert value_drag_steps(-9.0, 10.0) == (0, -9.0)
    assert value_drag_steps(10.0, 10.0) == (1, 0.0)
    assert value_drag_steps(-10.0, 10.0) == (-1, 0.0)


def test_drag_delta_matches_one_horizontal_step() -> None:
    threshold = _VALUE_DRAG_THRESHOLD_PX
    dragged = _make_controls(("layer_1",))
    keyed = _make_controls(("layer_1",))

    remaining, crossed = apply_value_drag(dragged, _OPACITY, threshold, 0.0)
    apply_field_horizontal(keyed, _OPACITY, True, False)

    assert crossed is True
    assert remaining == 0.0
    assert _opacity(dragged) == _opacity(keyed)

    dragged_back = _make_controls(("layer_1",))
    keyed_back = _make_controls(("layer_1",))
    apply_value_drag(dragged_back, _OPACITY, -threshold, 0.0)
    apply_field_horizontal(keyed_back, _OPACITY, False, False)
    assert _opacity(dragged_back) == _opacity(keyed_back)

    burst = _make_controls(("layer_1",))
    keyed_burst = _make_controls(("layer_1",))
    remaining, crossed = apply_value_drag(
        burst, _OPACITY, threshold * 2 + 5.0, 0.0
    )
    apply_field_horizontal(keyed_burst, _OPACITY, True, False)
    apply_field_horizontal(keyed_burst, _OPACITY, True, False)
    assert crossed is True
    assert remaining == 5.0
    assert _opacity(burst) == _opacity(keyed_burst)

    held = _make_controls(("layer_1",))
    before = _opacity(held)
    remaining, crossed = apply_value_drag(held, _OPACITY, threshold - 1.0, 0.0)
    assert crossed is False
    assert remaining == threshold - 1.0
    assert _opacity(held) == before
    remaining, crossed = apply_value_drag(held, _OPACITY, 1.0, remaining)
    assert crossed is True
    assert remaining == 0.0
    assert _opacity(held) == before + 1


def test_locked_drag_does_not_change_the_value() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    before = _opacity(controls)

    remaining, crossed = apply_value_drag(
        controls, _OPACITY, _VALUE_DRAG_THRESHOLD_PX * 2 + 5.0, 0.0
    )

    assert crossed is True
    assert remaining == 5.0
    assert _opacity(controls) == before
    again, crossed_again = apply_value_drag(controls, _OPACITY, 0.0, remaining)
    assert crossed_again is False
    assert again == 5.0
    assert _opacity(controls) == before
