"""Tests for compositor blend mode registry and config parsing."""

from __future__ import annotations

from cleave.config import _parse_blend_mode
from cleave.gl_compositor import BLEND_MODES
from tests.test_viz_tuning_controls import _make_controls


def test_blend_modes_cycle_order() -> None:
    assert BLEND_MODES == (
        "alpha",
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
        assert _parse_blend_mode("drums", {"blend_mode": mode}) == mode


def test_parse_blend_mode_rejects_unknown() -> None:
    try:
        _parse_blend_mode("drums", {"blend_mode": "overlay"})
    except ValueError as exc:
        assert "blend_mode must be one of" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown blend mode")


def test_cycle_blend_wraps_forward() -> None:
    controls = _make_controls(("drums",))
    layer = controls.session.layers["drums"]
    layer.blend_mode = "pure-add"

    controls._cycle_blend("drums", forward=True)
    assert layer.blend_mode == "alpha"


def test_cycle_blend_steps_backward() -> None:
    controls = _make_controls(("drums",))
    layer = controls.session.layers["drums"]
    layer.blend_mode = "add"

    controls._cycle_blend("drums", forward=False)
    assert layer.blend_mode == "alpha"


def test_cycle_blend_recovers_from_unknown_mode() -> None:
    controls = _make_controls(("drums",))
    layer = controls.session.layers["drums"]
    layer.blend_mode = "legacy"  # type: ignore[assignment]

    controls._cycle_blend("drums", forward=True)
    assert layer.blend_mode == "add"


def main() -> int:
    tests = [
        test_blend_modes_cycle_order,
        test_parse_blend_mode_accepts_all_modes,
        test_parse_blend_mode_rejects_unknown,
        test_cycle_blend_wraps_forward,
        test_cycle_blend_steps_backward,
        test_cycle_blend_recovers_from_unknown_mode,
    ]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
