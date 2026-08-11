"""Unit tests for pattern mask generators and config round-trip."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from cleave.config import (
    CleaveConfig,
    EditorConfig,
    PathsConfig,
    RenderConfig,
    RenderPatternMaskConfig,
)
from cleave.config_schema import (
    DEFAULT_RENDER_PATTERN_MASK_DENSITY,
    DEFAULT_RENDER_PATTERN_MASK_ENABLED,
    DEFAULT_RENDER_PATTERN_MASK_INVERT,
    DEFAULT_RENDER_PATTERN_MASK_MODE,
    DEFAULT_RENDER_PATTERN_MASK_SEED,
    DEFAULT_RENDER_PATTERN_MASK_TYPE,
    PATTERN_MASK_TYPES,
    PersistCtx,
    parse_render_section,
    persist_render,
)
from cleave.pattern_mask import (
    DEFAULT_TIMELINE_PRESET_PATTERN_MASK,
    cycle_timeline_preset_pattern_mask,
    generate_checker_mask,
    generate_checker_weights,
    generate_hard_mask,
    generate_plasma_mask,
    generate_plasma_weights,
    generate_radial_mask,
    generate_radial_weights,
    generate_soft_weights,
    generate_strips_mask,
    generate_strips_weights,
    timeline_preset_pattern_mask_display,
)
from cleave.viz.session import (
    TuningSession,
    default_render_pattern_mask_runtime,
    render_pattern_mask_runtime_from_cfg,
)


def _assert_valid_hard_mask(
    mask: np.ndarray, *, height: int, width: int, layer_count: int
) -> None:
    assert mask.shape == (height, width)
    assert mask.dtype == np.uint8
    assert int(mask.min()) >= 0
    assert int(mask.max()) < layer_count


def test_generate_strips_mask_shape_and_dtype() -> None:
    mask = generate_strips_mask(128, 72, layer_count=4, density=2.0, invert=False)
    _assert_valid_hard_mask(mask, height=72, width=128, layer_count=4)
    # Vertical strips: every row identical.
    assert np.array_equal(mask, np.broadcast_to(mask[0], mask.shape))


def test_generate_strips_mask_density_controls_strip_count() -> None:
    low = generate_strips_mask(100, 40, layer_count=4, density=1.0)
    high = generate_strips_mask(100, 40, layer_count=4, density=10.0)
    assert len(np.unique(low)) == 4
    assert len(np.unique(high)) == 4
    low_transitions = int(np.sum(low[0, 1:] != low[0, :-1]))
    high_transitions = int(np.sum(high[0, 1:] != high[0, :-1]))
    assert high_transitions > low_transitions
    # 1.0x = one segment per layer; 10.0x = ten segments per layer.
    assert low_transitions == 3  # 4 strips -> 3 boundaries
    assert high_transitions == 39  # 40 strips -> 39 boundaries


def test_generate_strips_mask_invert_reverses_assignment() -> None:
    base = generate_strips_mask(64, 32, layer_count=4, density=2.0, invert=False)
    inverted = generate_strips_mask(64, 32, layer_count=4, density=2.0, invert=True)
    assert np.array_equal(inverted, (3 - base.astype(np.int64)).astype(np.uint8))


def test_generate_strips_mask_rejects_invalid_args() -> None:
    with pytest.raises(ValueError, match="width"):
        generate_strips_mask(0, 16, layer_count=2)
    with pytest.raises(ValueError, match="height"):
        generate_strips_mask(16, 0, layer_count=2)
    with pytest.raises(ValueError, match="layer_count"):
        generate_strips_mask(16, 16, layer_count=0)


def test_generate_radial_mask_shape_and_bounds() -> None:
    mask = generate_radial_mask(64, 48, layer_count=4, density=2.0, invert=False)
    _assert_valid_hard_mask(mask, height=48, width=64, layer_count=4)
    assert len(np.unique(mask)) == 4


def test_generate_radial_mask_invert() -> None:
    base = generate_radial_mask(32, 32, layer_count=3, density=1.5, invert=False)
    inverted = generate_radial_mask(32, 32, layer_count=3, density=1.5, invert=True)
    assert np.array_equal(inverted, (2 - base.astype(np.int64)).astype(np.uint8))


def _radial_sample(mask: np.ndarray, *, dx: float, dy: float) -> int:
    """Sample mask at pixel-space offset from center (dy up, row 0 = bottom)."""
    height, width = mask.shape
    col = int(round(width * 0.5 + dx - 0.5))
    row = int(round(height * 0.5 + dy - 0.5))
    return int(mask[row, col])


def test_generate_radial_two_wedges_are_diagonal() -> None:
    """Two wedges use a 45 deg default rotation (not a flat top/bottom split)."""
    mask = generate_radial_mask(128, 128, layer_count=2, density=1.0)
    r = 40.0
    up = _radial_sample(mask, dx=0.0, dy=r)
    down = _radial_sample(mask, dx=0.0, dy=-r)
    left = _radial_sample(mask, dx=-r, dy=0.0)
    right = _radial_sample(mask, dx=r, dy=0.0)
    assert up == right
    assert down == left
    assert up != down


def test_generate_radial_four_wedges_are_diagonal() -> None:
    """Four wedges use a 45 deg default rotation (diamond, not axis-aligned plus)."""
    mask = generate_radial_mask(128, 128, layer_count=4, density=1.0)
    r = 40.0
    up = _radial_sample(mask, dx=0.0, dy=r)
    down = _radial_sample(mask, dx=0.0, dy=-r)
    left = _radial_sample(mask, dx=-r, dy=0.0)
    right = _radial_sample(mask, dx=r, dy=0.0)
    # Cardinals are wedge centers after 45 deg rotation; each owns a distinct layer.
    assert len({up, down, left, right}) == 4
    # Near-45 deg sample sits on the boundary between up and right.
    ne = _radial_sample(
        mask, dx=r * math.cos(math.pi / 4), dy=r * math.sin(math.pi / 4)
    )
    assert ne in (up, right)


def test_generate_radial_screen_angles_aspect_invariant() -> None:
    """Same screen-space ray maps to the same wedge on square and widescreen."""
    for wedge_count in (3, 5):
        square = generate_radial_mask(512, 512, layer_count=wedge_count, density=1.0)
        wide = generate_radial_mask(1280, 720, layer_count=wedge_count, density=1.0)
        for deg in range(5, 360, 10):
            rad = math.radians(deg)
            sq = _radial_sample(
                square, dx=180.0 * math.cos(rad), dy=180.0 * math.sin(rad)
            )
            wd = _radial_sample(
                wide, dx=280.0 * math.cos(rad), dy=280.0 * math.sin(rad)
            )
            assert sq == wd, f"n={wedge_count} deg={deg}: square={sq} wide={wd}"


def test_generate_radial_wedge_spans_equal_on_widescreen() -> None:
    """Each wedge spans ~360/n degrees in screen space on a 16:9 frame."""
    width, height = 1280, 720
    for wedge_count in (3, 5):
        mask = generate_radial_mask(
            width, height, layer_count=wedge_count, density=1.0
        )
        radius = min(width, height) * 0.4
        labels = [
            _radial_sample(
                mask,
                dx=radius * math.cos(math.radians(deg)),
                dy=radius * math.sin(math.radians(deg)),
            )
            for deg in range(360)
        ]
        transitions = [
            i for i in range(360) if labels[i] != labels[(i - 1) % 360]
        ]
        assert len(transitions) == wedge_count, (
            f"n={wedge_count} transitions={transitions}"
        )
        spans = [
            (transitions[(i + 1) % wedge_count] - transitions[i]) % 360
            for i in range(wedge_count)
        ]
        expected = 360 / wedge_count
        for span in spans:
            assert abs(span - expected) <= 2, f"n={wedge_count} spans={spans}"


def test_generate_checker_mask_shape_and_bounds() -> None:
    mask = generate_checker_mask(80, 60, layer_count=4, density=2.0, invert=False)
    _assert_valid_hard_mask(mask, height=60, width=80, layer_count=4)
    assert len(np.unique(mask)) == 4


def test_generate_checker_mask_density_adds_tiles() -> None:
    low = generate_checker_mask(64, 64, layer_count=4, density=1.0)
    high = generate_checker_mask(64, 64, layer_count=4, density=10.0)
    # Higher density should create more spatial transitions.
    low_h = int(np.sum(low[0, 1:] != low[0, :-1]))
    high_h = int(np.sum(high[0, 1:] != high[0, :-1]))
    low_v = int(np.sum(low[1:, 0] != low[:-1, 0]))
    high_v = int(np.sum(high[1:, 0] != high[:-1, 0]))
    assert high_h + high_v > low_h + low_v


def test_generate_checker_mask_has_2d_variation() -> None:
    """Checker must vary in both axes (not vertical strips)."""
    w, h = 1280, 720
    mask = generate_checker_mask(w, h, layer_count=4, density=2.0)
    rows_identical = all(np.array_equal(mask[i], mask[0]) for i in range(h))
    cols_identical = all(np.array_equal(mask[:, i], mask[:, 0]) for i in range(w))
    assert not rows_identical
    assert not cols_identical


def test_generate_checker_mask_density_changes_grid() -> None:
    w, h = 1280, 720
    low = generate_checker_mask(w, h, layer_count=4, density=1.0)
    high = generate_checker_mask(w, h, layer_count=4, density=10.0)
    low_trans = int(np.sum(low[:, 1:] != low[:, :-1])) + int(
        np.sum(low[1:, :] != low[:-1, :])
    )
    high_trans = int(np.sum(high[:, 1:] != high[:, :-1])) + int(
        np.sum(high[1:, :] != high[:-1, :])
    )
    assert high_trans > low_trans


def test_generate_checker_weights_has_2d_variation() -> None:
    w, h = 1280, 720
    weights = generate_checker_weights(w, h, layer_count=4, density=2.0)
    dominant = np.argmax(weights, axis=2)
    rows_identical = all(np.array_equal(dominant[i], dominant[0]) for i in range(h))
    cols_identical = all(
        np.array_equal(dominant[:, i], dominant[:, 0]) for i in range(w)
    )
    assert not rows_identical
    assert not cols_identical


def test_generate_plasma_mask_shape_bounds_and_seed() -> None:
    a = generate_plasma_mask(48, 36, layer_count=4, density=2.0, seed=7, invert=False)
    b = generate_plasma_mask(48, 36, layer_count=4, density=2.0, seed=7, invert=False)
    c = generate_plasma_mask(48, 36, layer_count=4, density=2.0, seed=8, invert=False)
    _assert_valid_hard_mask(a, height=36, width=48, layer_count=4)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert len(np.unique(a)) >= 2


def test_generate_hard_mask_dispatches_types() -> None:
    for mask_type in PATTERN_MASK_TYPES:
        mask = generate_hard_mask(
            mask_type, 32, 24, 3, density=1.5, invert=False, seed=1
        )
        _assert_valid_hard_mask(mask, height=24, width=32, layer_count=3)


def test_generate_hard_mask_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown pattern mask type"):
        generate_hard_mask("spiral", 16, 16, 2)


def _assert_valid_soft_weights(
    weights: np.ndarray, *, height: int, width: int, layer_count: int
) -> None:
    assert weights.shape == (height, width, layer_count)
    assert weights.dtype == np.uint8
    sums = weights.astype(np.int64).sum(axis=2)
    assert int(sums.min()) >= 254
    assert int(sums.max()) <= 256
    assert float(np.mean(np.abs(sums - 255))) < 1.0


def test_generate_strips_weights_shape_and_sum() -> None:
    weights = generate_strips_weights(64, 32, layer_count=4, density=2.0)
    _assert_valid_soft_weights(weights, height=32, width=64, layer_count=4)
    # Vertical strips: every row identical.
    assert np.array_equal(weights, np.broadcast_to(weights[0], weights.shape))


def test_generate_radial_weights_shape_and_sum() -> None:
    weights = generate_radial_weights(48, 36, layer_count=3, density=1.5)
    _assert_valid_soft_weights(weights, height=36, width=48, layer_count=3)


def test_generate_checker_weights_shape_and_sum() -> None:
    weights = generate_checker_weights(40, 40, layer_count=4, density=2.5)
    _assert_valid_soft_weights(weights, height=40, width=40, layer_count=4)


def test_generate_plasma_weights_shape_sum_and_seed() -> None:
    a = generate_plasma_weights(32, 24, layer_count=4, density=2.0, seed=3)
    b = generate_plasma_weights(32, 24, layer_count=4, density=2.0, seed=3)
    c = generate_plasma_weights(32, 24, layer_count=4, density=2.0, seed=4)
    _assert_valid_soft_weights(a, height=24, width=32, layer_count=4)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_generate_soft_weights_dispatches_types() -> None:
    for mask_type in PATTERN_MASK_TYPES:
        weights = generate_soft_weights(
            mask_type, 24, 16, 3, density=1.5, invert=False, seed=2
        )
        _assert_valid_soft_weights(weights, height=16, width=24, layer_count=3)


def test_generate_soft_weights_invert_reverses_layers() -> None:
    base = generate_strips_weights(32, 16, layer_count=4, density=2.0, invert=False)
    inverted = generate_strips_weights(32, 16, layer_count=4, density=2.0, invert=True)
    assert np.array_equal(inverted, base[:, :, ::-1])


def test_generate_soft_weights_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown pattern mask type"):
        generate_soft_weights("spiral", 16, 16, 2)


def test_parse_render_pattern_mask_defaults() -> None:
    render = parse_render_section({"render": {"pattern_mask": {}}})
    assert render is not None
    assert render.pattern_mask is not None
    assert render.pattern_mask.enabled is DEFAULT_RENDER_PATTERN_MASK_ENABLED
    assert render.pattern_mask.type == DEFAULT_RENDER_PATTERN_MASK_TYPE
    assert render.pattern_mask.mode == DEFAULT_RENDER_PATTERN_MASK_MODE
    assert render.pattern_mask.density == DEFAULT_RENDER_PATTERN_MASK_DENSITY
    assert render.pattern_mask.invert is DEFAULT_RENDER_PATTERN_MASK_INVERT
    assert render.pattern_mask.seed == DEFAULT_RENDER_PATTERN_MASK_SEED
    assert render.pattern_mask.locked is False


def test_parse_render_pattern_mask_explicit() -> None:
    render = parse_render_section(
        {
            "render": {
                "pattern_mask": {
                    "enabled": True,
                    "type": "plasma",
                    "mode": "soft",
                    "density": 2.5,
                    "invert": True,
                    "seed": 42,
                    "locked": True,
                }
            }
        }
    )
    assert render is not None
    assert render.pattern_mask is not None
    assert render.pattern_mask.enabled is True
    assert render.pattern_mask.type == "plasma"
    assert render.pattern_mask.mode == "soft"
    assert render.pattern_mask.density == 2.5
    assert render.pattern_mask.invert is True
    assert render.pattern_mask.seed == 42
    assert render.pattern_mask.locked is True


def test_parse_render_pattern_mask_clamps_density() -> None:
    high = parse_render_section(
        {"render": {"pattern_mask": {"density": 12.0}}}
    )
    assert high is not None
    assert high.pattern_mask is not None
    assert high.pattern_mask.density == 10.0
    low = parse_render_section(
        {"render": {"pattern_mask": {"density": 0.5}}}
    )
    assert low is not None
    assert low.pattern_mask is not None
    assert low.pattern_mask.density == 1.0


def test_parse_render_pattern_mask_accepts_all_types() -> None:
    for mask_type in PATTERN_MASK_TYPES:
        render = parse_render_section(
            {"render": {"pattern_mask": {"type": mask_type}}}
        )
        assert render is not None
        assert render.pattern_mask is not None
        assert render.pattern_mask.type == mask_type


def test_parse_render_pattern_mask_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="pattern_mask.type"):
        parse_render_section({"render": {"pattern_mask": {"type": "spiral"}}})


def test_parse_render_pattern_mask_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="pattern_mask.mode"):
        parse_render_section({"render": {"pattern_mask": {"mode": "fuzzy"}}})


def test_persist_render_pattern_mask_round_trip() -> None:
    render = parse_render_section(
        {
            "render": {
                "fps": 24,
                "pattern_mask": {
                    "enabled": True,
                    "type": "radial",
                    "mode": "hard",
                    "density": 2.5,
                    "invert": True,
                    "seed": 99,
                    "locked": True,
                },
            }
        }
    )
    assert render is not None
    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=Path("/tmp"), texture_paths=()),
        layers={},
        editor=EditorConfig(),
        config_path=Path("/tmp/cleave-viz.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
        render=render,
    )
    session = TuningSession(layer_z_order=[])
    session.render_pattern_mask = render_pattern_mask_runtime_from_cfg(cfg)
    payload = persist_render(PersistCtx(cfg=cfg, session=session, cfg_dir=None))
    assert payload["pattern_mask"] == {
        "enabled": True,
        "locked": True,
        "type": "radial",
        "density": 2.5,
        "mode": "hard",
        "invert": True,
        "seed": 99,
    }
    round_trip = parse_render_section({"render": payload})
    assert round_trip is not None
    assert round_trip.pattern_mask == RenderPatternMaskConfig(
        enabled=True,
        type="radial",
        density=2.5,
        mode="hard",
        invert=True,
        seed=99,
        locked=True,
    )


def test_render_pattern_mask_runtime_from_cfg_defaults() -> None:
    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=Path("/tmp"), texture_paths=()),
        layers={},
        editor=EditorConfig(),
        config_path=Path("/tmp/cleave-viz.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
        render=RenderConfig(),
    )
    runtime = render_pattern_mask_runtime_from_cfg(cfg)
    assert runtime == default_render_pattern_mask_runtime()
    assert runtime.enabled is False
    assert runtime.type == "strips"
    assert runtime.mode == "hard"
    assert runtime.density == DEFAULT_RENDER_PATTERN_MASK_DENSITY
    assert runtime.seed == 0
    assert runtime.expanded is False


def test_timeline_preset_pattern_mask_cycle_and_display() -> None:
    assert DEFAULT_TIMELINE_PRESET_PATTERN_MASK is False
    assert timeline_preset_pattern_mask_display(False) == "off"
    assert timeline_preset_pattern_mask_display(True) == "on"
    assert cycle_timeline_preset_pattern_mask(False, forward=True) is True
    assert cycle_timeline_preset_pattern_mask(True, forward=True) is False
    assert cycle_timeline_preset_pattern_mask(False, forward=False) is True
    assert cycle_timeline_preset_pattern_mask(True, forward=False) is False
