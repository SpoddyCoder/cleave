"""Unit tests for strips pattern mask generator and config round-trip."""

from __future__ import annotations

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
    DEFAULT_RENDER_PATTERN_MASK_TYPE,
    PersistCtx,
    parse_render_section,
    persist_render,
)
from cleave.pattern_mask import (
    DEFAULT_TIMELINE_PRESET_PATTERN_MASK,
    cycle_timeline_preset_pattern_mask,
    generate_strips_mask,
    timeline_preset_pattern_mask_display,
)
from cleave.viz.session import (
    TuningSession,
    default_render_pattern_mask_runtime,
    render_pattern_mask_runtime_from_cfg,
)


def test_generate_strips_mask_shape_and_dtype() -> None:
    mask = generate_strips_mask(128, layer_count=4, density=0.5, invert=False)
    assert mask.shape == (128,)
    assert mask.dtype == np.uint8
    assert int(mask.min()) >= 0
    assert int(mask.max()) <= 3


def test_generate_strips_mask_density_controls_strip_count() -> None:
    low = generate_strips_mask(100, layer_count=4, density=0.0)
    high = generate_strips_mask(100, layer_count=4, density=1.0)
    # density=0 -> strip_count = layer_count = 4; density=1 -> strip_count = 16
    assert len(np.unique(low)) == 4
    assert len(np.unique(high)) == 4
    # More strips at higher density means more transitions along x.
    low_transitions = int(np.sum(low[1:] != low[:-1]))
    high_transitions = int(np.sum(high[1:] != high[:-1]))
    assert high_transitions > low_transitions


def test_generate_strips_mask_invert_reverses_assignment() -> None:
    base = generate_strips_mask(64, layer_count=4, density=0.5, invert=False)
    inverted = generate_strips_mask(64, layer_count=4, density=0.5, invert=True)
    assert np.array_equal(inverted, (3 - base.astype(np.int64)).astype(np.uint8))


def test_generate_strips_mask_rejects_invalid_args() -> None:
    with pytest.raises(ValueError, match="width"):
        generate_strips_mask(0, layer_count=2)
    with pytest.raises(ValueError, match="layer_count"):
        generate_strips_mask(16, layer_count=0)


def test_parse_render_pattern_mask_defaults() -> None:
    render = parse_render_section({"render": {"pattern_mask": {}}})
    assert render is not None
    assert render.pattern_mask is not None
    assert render.pattern_mask.enabled is DEFAULT_RENDER_PATTERN_MASK_ENABLED
    assert render.pattern_mask.type == DEFAULT_RENDER_PATTERN_MASK_TYPE
    assert render.pattern_mask.density == DEFAULT_RENDER_PATTERN_MASK_DENSITY
    assert render.pattern_mask.invert is DEFAULT_RENDER_PATTERN_MASK_INVERT
    assert render.pattern_mask.locked is False


def test_parse_render_pattern_mask_explicit() -> None:
    render = parse_render_section(
        {
            "render": {
                "pattern_mask": {
                    "enabled": True,
                    "type": "strips",
                    "density": 0.75,
                    "invert": True,
                    "locked": True,
                }
            }
        }
    )
    assert render is not None
    assert render.pattern_mask is not None
    assert render.pattern_mask.enabled is True
    assert render.pattern_mask.type == "strips"
    assert render.pattern_mask.density == 0.75
    assert render.pattern_mask.invert is True
    assert render.pattern_mask.locked is True


def test_parse_render_pattern_mask_clamps_density() -> None:
    render = parse_render_section(
        {"render": {"pattern_mask": {"density": 2.5}}}
    )
    assert render is not None
    assert render.pattern_mask is not None
    assert render.pattern_mask.density == 1.0


def test_parse_render_pattern_mask_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="pattern_mask.type"):
        parse_render_section({"render": {"pattern_mask": {"type": "radial"}}})


def test_persist_render_pattern_mask_round_trip() -> None:
    render = parse_render_section(
        {
            "render": {
                "fps": 24,
                "pattern_mask": {
                    "enabled": True,
                    "type": "strips",
                    "density": 0.25,
                    "invert": True,
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
        "type": "strips",
        "density": 0.25,
        "invert": True,
    }
    round_trip = parse_render_section({"render": payload})
    assert round_trip is not None
    assert round_trip.pattern_mask == RenderPatternMaskConfig(
        enabled=True,
        type="strips",
        density=0.25,
        invert=True,
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
    assert runtime.expanded is False


def test_timeline_preset_pattern_mask_cycle_and_display() -> None:
    assert DEFAULT_TIMELINE_PRESET_PATTERN_MASK is False
    assert timeline_preset_pattern_mask_display(False) == "off"
    assert timeline_preset_pattern_mask_display(True) == "on"
    assert cycle_timeline_preset_pattern_mask(False, forward=True) is True
    assert cycle_timeline_preset_pattern_mask(True, forward=True) is False
    assert cycle_timeline_preset_pattern_mask(False, forward=False) is True
    assert cycle_timeline_preset_pattern_mask(True, forward=False) is False
