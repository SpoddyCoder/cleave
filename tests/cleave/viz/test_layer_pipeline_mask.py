"""Unit tests for LayerFramePipeline pattern-mask composite branch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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
    session.render_pattern_mask.feather_pct = 0
    session.render_pattern_mask.type = "radial"
    session.render_pattern_mask.density = 2.5
    session.render_pattern_mask.invert = True
    session.render_pattern_mask.seed = 11
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

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
    )

    compositor.composite.assert_not_called()
    masked.set_content_size.assert_called_once_with(1280, 720)
    masked.set_color_format.assert_called_once_with(compositor.color_format)
    masked.composite.assert_called_once()
    call = masked.composite.call_args
    assert call.args[0] == 7
    assert call.kwargs["mask_type"] == "radial"
    assert call.kwargs["feather_pct"] == 0
    assert call.kwargs["density"] == 2.5
    assert call.kwargs["invert"] is True
    assert call.kwargs["seed"] == 11
    assert call.kwargs["slot_names"] == ["layer_1", "layer_2"]
    assert call.kwargs["active_slots"] == [True, True]
    assert call.kwargs["song_time_sec"] == 0.0
    assert call.kwargs["transition_duration"] == 0.0


def test_composite_passes_transition_and_inactive_slots() -> None:
    session = _session(("layer_1", "layer_2", "layer_3"))
    session.render_pattern_mask.enabled = True
    session.render_pattern_mask.transition = 1.2
    layers_by_slot = {
        "layer_1": _stem_layer("layer_1"),
        "layer_2": _stem_layer("layer_2", enabled=False),
        "layer_3": _stem_layer("layer_3", opacity=0.0),
    }
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
        song_time_sec=3.5,
    )

    call = masked.composite.call_args
    assert call.kwargs["slot_names"] == ["layer_1", "layer_2", "layer_3"]
    assert call.kwargs["active_slots"] == [True, False, False]
    assert call.kwargs["song_time_sec"] == 3.5
    assert call.kwargs["transition_duration"] == 1.2


def test_composite_uses_soft_path_when_feather_above_zero() -> None:
    session = _session(("layer_1", "layer_2"))
    session.render_pattern_mask.enabled = True
    session.render_pattern_mask.feather_pct = 100
    session.render_pattern_mask.type = "plasma"
    session.render_pattern_mask.density = 2.0
    session.render_pattern_mask.invert = False
    session.render_pattern_mask.seed = 42
    layers_by_slot = {
        "layer_1": _stem_layer("layer_1"),
        "layer_2": _stem_layer("layer_2"),
    }
    compositor = MagicMock()
    compositor.content_width = 64
    compositor.content_height = 48
    compositor.content_fbo_id = 9
    compositor.color_format = object()
    masked = MagicMock()

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
    )

    compositor.composite.assert_not_called()
    masked.composite.assert_called_once()
    call = masked.composite.call_args
    assert call.args[0] == 9
    assert call.kwargs["mask_type"] == "plasma"
    assert call.kwargs["feather_pct"] == 100
    assert call.kwargs["seed"] == 42


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
    masked.composite.assert_not_called()


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

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
    )

    compositor.composite.assert_called_once()
    masked.composite.assert_not_called()


def test_composite_skips_mask_in_preset_curation_mode() -> None:
    session = _session(("layer_1",))
    session.render_pattern_mask.enabled = True
    session.settings.editor_mode = "preset_curation"
    layers_by_slot = {"layer_1": _stem_layer("layer_1")}
    compositor = MagicMock()
    masked = MagicMock()

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
    )

    compositor.composite.assert_called_once()
    masked.composite.assert_not_called()
