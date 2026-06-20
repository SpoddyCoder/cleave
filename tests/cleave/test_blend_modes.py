"""Tests for compositor blend mode registry and config parsing."""

from __future__ import annotations

from cleave.config_schema import parse_blend_mode
from cleave.blend_modes import BLEND_MODES
from tests.support.viz import make_controls


def test_blend_modes_cycle_order() -> None:
    assert BLEND_MODES == (
        "black-key",
        "add",
        "multiply",
        "screen",
        "subtract",
        "difference",
        "exclusion",
        "max",
        "pure-add",
    )


def test_parse_blend_mode_accepts_all_modes() -> None:
    for mode in BLEND_MODES:
        assert parse_blend_mode("layer_1", "drums", {"blend_mode": mode}) == mode


def test_parse_blend_mode_rejects_unknown() -> None:
    try:
        parse_blend_mode("layer_1", "drums", {"blend_mode": "overlay"})
    except ValueError as exc:
        assert "blend_mode must be one of" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown blend mode")


def test_cycle_blend_wraps_forward() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.blend_mode = "pure-add"

    controls._cycle_blend("layer_1", forward=True)
    assert layer.blend_mode == "black-key"


def test_cycle_blend_steps_backward() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.blend_mode = "add"

    controls._cycle_blend("layer_1", forward=False)
    assert layer.blend_mode == "black-key"


def test_cycle_blend_recovers_from_unknown_mode() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.blend_mode = "legacy"  # type: ignore[assignment]

    controls._cycle_blend("layer_1", forward=True)
    assert layer.blend_mode == "add"
