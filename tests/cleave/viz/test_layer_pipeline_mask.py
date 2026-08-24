"""Unit tests for LayerFramePipeline pattern-mask composite branch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.pattern_mask_transition import PatternMaskTransitionTracker
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import TEST_LAYER_STEMS, default_render_post_fx_runtime


def _stem_layer(slot: str, *, enabled: bool = True, opacity: float = 1.0) -> StemLayer:
    current_dir = Path(f"/tmp/presets/{slot}")
    fbo = MagicMock()
    fbo.enabled = enabled
    fbo.opacity = opacity
    fbo.width = 1280
    fbo.height = 720
    fbo.bloom_strength = 0.0
    fbo.grit_strength = 0.0
    fbo.aberration_px = 0.0
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
    masked.transitions = PatternMaskTransitionTracker()

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
    )

    compositor.composite.assert_not_called()
    masked.set_content_size.assert_called_once_with(1280, 720)
    masked.composite.assert_called_once()
    request = masked.composite.call_args.args[0]
    assert request.target_fbo_id == 7
    assert request.color_format is compositor.color_format
    assert request.mask is not None
    assert request.mask.mask_type == "radial"
    assert request.mask.feather_pct == 0
    assert request.mask.density == 2.5
    assert request.mask.invert is True
    assert request.mask.seed == 11
    assert request.active_slots == (True, True)
    assert request.song_time_sec == 0.0
    assert request.transition is None
    assert masked.transitions.last_active_slots == (True, True)


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
    masked.transitions = PatternMaskTransitionTracker()
    masked.transitions.commit((True, True, True))

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
        song_time_sec=3.5,
    )

    request = masked.composite.call_args.args[0]
    assert request.active_slots == (True, False, False)
    assert request.song_time_sec == 3.5
    assert request.transition is not None
    assert request.transition.kind == "hard_layout"
    assert request.transition.duration == 1.2
    assert request.transition.from_slots == (True, True, True)
    assert masked.transitions.last_active_slots == (True, False, False)


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
    masked.transitions = PatternMaskTransitionTracker()

    LayerFramePipeline.composite(
        compositor,
        layers_by_slot,
        session,
        masked_compositor=masked,
    )

    compositor.composite.assert_not_called()
    masked.composite.assert_called_once()
    request = masked.composite.call_args.args[0]
    assert request.target_fbo_id == 9
    assert request.mask is not None
    assert request.mask.mask_type == "plasma"
    assert request.mask.feather_pct == 100
    assert request.mask.seed == 42


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


def _effect_runtime_for(slots: tuple[str, ...]) -> MagicMock:
    effect_runtime = MagicMock()
    effect_runtime.modifiers.return_value = {
        slot: MagicMock(
            opacity=1.0,
            flash_alpha=0.0,
            bloom_strength=0.0,
            hue_rgb=(1, 1, 1),
            hue_mix=0.0,
            grit_strength=0.0,
            aberration_px=0.0,
        )
        for slot in slots
    }
    return effect_runtime


def test_render_frame_feeds_pcm_for_live_disabled_slot() -> None:
    session = _session(("layer_1", "layer_2"))
    session.render_pattern_mask.enabled = True
    session.render_pattern_mask.transition = 1.0
    session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    live = _stem_layer("layer_1")
    departing = _stem_layer("layer_2", enabled=False)
    pcm_bank = MagicMock()
    pcm_bank.slice_pcm.return_value = b""
    pcm_bank.channels.return_value = 2
    masked = MagicMock()
    masked.live_slots.return_value = (True, True)

    with (
        patch("cleave.viz.layer_pipeline._render_layer_fbo") as render_fbo,
        patch(
            "cleave.viz.layer_pipeline.pcm_max_samples_per_channel",
            return_value=2048,
        ),
    ):
        LayerFramePipeline.render_frame(
            session,
            [live, departing],
            {"layer_1": live, "layer_2": departing},
            pcm_bank,
            512,
            MagicMock(),
            _effect_runtime_for(("layer_1", "layer_2")),
            None,
            2.5,
            paused=False,
            pm_time_sec=1.0,
            masked_compositor=masked,
        )

    masked.transitions.peek.assert_called_once_with(
        (True, False),
        song_time_sec=2.5,
        duration=1.0,
        mask_type=session.render_pattern_mask.type,
    )
    masked.live_slots.assert_called_once_with(
        (True, False), 2.5, masked.transitions.peek.return_value
    )
    assert pcm_bank.slice_pcm.call_count == 2
    assert render_fbo.call_count == 2
    render_fbo.assert_any_call(departing, departing.pm)


def test_render_frame_skips_disabled_slot_that_is_not_live() -> None:
    session = _session(("layer_1", "layer_2"))
    session.render_pattern_mask.enabled = True
    session.render_pattern_mask.transition = 1.0
    session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    live = _stem_layer("layer_1")
    idle = _stem_layer("layer_2", enabled=False)
    pcm_bank = MagicMock()
    pcm_bank.slice_pcm.return_value = b""
    pcm_bank.channels.return_value = 2
    masked = MagicMock()
    masked.live_slots.return_value = (True, False)

    with (
        patch("cleave.viz.layer_pipeline._render_layer_fbo") as render_fbo,
        patch(
            "cleave.viz.layer_pipeline.pcm_max_samples_per_channel",
            return_value=2048,
        ),
    ):
        LayerFramePipeline.render_frame(
            session,
            [live, idle],
            {"layer_1": live, "layer_2": idle},
            pcm_bank,
            512,
            MagicMock(),
            _effect_runtime_for(("layer_1", "layer_2")),
            None,
            2.5,
            paused=False,
            pm_time_sec=1.0,
            masked_compositor=masked,
        )

    assert pcm_bank.slice_pcm.call_count == 1
    render_fbo.assert_called_once_with(live, live.pm)
