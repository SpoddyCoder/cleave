"""Unit tests for LayerFramePipeline pattern-mask composite branch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from cleave.preset_playlist import PresetPlaylist
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import TEST_LAYER_STEMS


def _stem_layer(slot: str, *, enabled: bool = True, opacity: float = 1.0) -> StemLayer:
    current_dir = Path(f"/tmp/presets/{slot}")
    fbo = MagicMock()
    fbo.enabled = enabled
    fbo.opacity = opacity
    fbo.width = 1280
    fbo.height = 720
    return StemLayer(
        slot=slot,
        pm=MagicMock(),
        fbo=fbo,
        playlist=PresetPlaylist(
            current_dir=current_dir,
            paths=(current_dir / "preset.milk",),
            index=0,
        ),
    )


def _session(slots: tuple[str, ...]) -> TuningSession:
    preset_root = Path("/tmp/presets")
    return TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=preset_root / slot,
                    paths=(preset_root / slot / "preset.milk",),
                    index=0,
                ),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
            )
            for slot in slots
        },
    )


def test_composite_uses_masked_path_when_enabled() -> None:
    session = _session(("layer_1", "layer_2"))
    session.render_pattern_mask.enabled = True
    session.render_pattern_mask.density = 0.25
    session.render_pattern_mask.invert = True
    layers_by_slot = {
        "layer_1": _stem_layer("layer_1"),
        "layer_2": _stem_layer("layer_2"),
    }
    compositor = MagicMock()
    compositor.content_width = 1280
    compositor.content_height = 720
    compositor.content_fbo_id = 7
    compositor.color_format = object()
    masked = MagicMock()

    with patch(
        "cleave.viz.layer_pipeline.generate_strips_mask",
        return_value=np.zeros(1280, dtype=np.uint8),
    ) as gen:
        LayerFramePipeline.composite(
            compositor,
            layers_by_slot,
            session,
            masked_compositor=masked,
        )

    compositor.composite.assert_not_called()
    gen.assert_called_once()
    assert gen.call_args.args[0] == 1280
    assert gen.call_args.args[1] == 2
    assert gen.call_args.kwargs["density"] == 0.25
    assert gen.call_args.kwargs["invert"] is True
    masked.composite_masked.assert_called_once()
    assert masked.composite_masked.call_args.args[0] == 7


def test_composite_uses_fixed_path_when_disabled() -> None:
    session = _session(("layer_1",))
    session.render_pattern_mask.enabled = False
    layers_by_slot = {"layer_1": _stem_layer("layer_1")}
    compositor = MagicMock()
    compositor.content_width = 1280
    compositor.content_height = 720
    compositor.content_fbo_id = 7
    compositor.color_format = object()
    masked = MagicMock()

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
    )

    compositor.composite.assert_called_once()
    masked.composite_masked.assert_not_called()


def test_composite_enabled_false_skips_mask_even_with_compositor() -> None:
    session = _session(("layer_1", "layer_2"))
    session.render_pattern_mask.enabled = False
    session.render_pattern_mask.density = 1.0
    layers_by_slot = {
        "layer_1": _stem_layer("layer_1"),
        "layer_2": _stem_layer("layer_2"),
    }
    compositor = MagicMock()
    masked = MagicMock()

    with patch("cleave.viz.layer_pipeline.generate_strips_mask") as gen:
        LayerFramePipeline.composite(
            compositor,
            layers_by_slot,
            session,
            masked_compositor=masked,
        )

    gen.assert_not_called()
    compositor.composite.assert_called_once()
    masked.composite_masked.assert_not_called()


def test_composite_skips_mask_in_preset_curation_mode() -> None:
    session = _session(("layer_1",))
    session.render_pattern_mask.enabled = True
    session.settings.editor_mode = "preset_curation"
    layers_by_slot = {"layer_1": _stem_layer("layer_1")}
    compositor = MagicMock()
    masked = MagicMock()

    with patch("cleave.viz.layer_pipeline.generate_strips_mask") as gen:
        LayerFramePipeline.composite(
            compositor,
            layers_by_slot,
            session,
            masked_compositor=masked,
        )

    gen.assert_not_called()
    compositor.composite.assert_called_once()
    masked.composite_masked.assert_not_called()
