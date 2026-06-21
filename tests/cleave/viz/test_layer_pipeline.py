"""Unit tests for LayerFramePipeline add/remove helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from cleave.preset_playlist import PresetPlaylist
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline


def _stem_layer(slot: str) -> StemLayer:
    current_dir = Path(f"/tmp/presets/{slot}")
    return StemLayer(
        slot=slot,
        pm=MagicMock(),
        fbo=MagicMock(),
        playlist=PresetPlaylist(
            current_dir=current_dir,
            paths=(current_dir / "preset.milk",),
            index=0,
        ),
    )


def test_destroy_single_tears_down_gl_and_updates_collections() -> None:
    layer = _stem_layer("layer_5")
    layers = [layer]
    layers_by_slot = {"layer_5": layer}
    compositor = MagicMock()

    LayerFramePipeline.destroy_single("layer_5", layers, layers_by_slot, compositor)

    assert layers == []
    assert layers_by_slot == {}
    layer.pm.destroy.assert_called_once()
    compositor.remove_layer_fbo.assert_called_once_with("layer_5")
