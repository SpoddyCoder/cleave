"""Non-GL contract tests for the shared layer-composite helpers."""

from __future__ import annotations

import inspect

from cleave.blend_modes import BLEND_MODES
from cleave.gl_compositor import GlCompositor
from cleave.gl_masked_compositor import GlMaskedCompositor
from cleave.layer_blend import opacity_in_alpha
from cleave.layer_composite import LayerCompositor, LayerCompositeRequest
from cleave.pattern_mask_transition import (
    MaskTransition,
    PatternMaskTransitionTracker,
    mask_transition_kind,
)


def test_both_compositors_satisfy_layer_compositor_protocol() -> None:
    for cls in (GlCompositor, GlMaskedCompositor):
        assert issubclass(cls, LayerCompositor)
        params = list(inspect.signature(cls.composite).parameters)
        assert params == ["self", "request"]
        annotation = inspect.signature(cls.composite).parameters["request"].annotation
        assert annotation in (LayerCompositeRequest, "LayerCompositeRequest")


def test_opacity_in_alpha_only_for_add() -> None:
    assert opacity_in_alpha("add") is True
    for mode in BLEND_MODES:
        if mode != "add":
            assert opacity_in_alpha(mode) is False
    assert opacity_in_alpha("legacy") is False


def test_mask_transition_kind_splits_layout_and_weight() -> None:
    assert mask_transition_kind("strips") == "hard_layout"
    assert mask_transition_kind("radial") == "hard_layout"
    assert mask_transition_kind("checker") == "weight_field"
    assert mask_transition_kind("plasma") == "weight_field"


def test_transition_tracker_emits_on_slot_set_change() -> None:
    tracker = PatternMaskTransitionTracker()
    assert tracker.peek((True, False), song_time_sec=1.0, duration=0.5, mask_type="strips") is None
    tracker.commit((True, False))
    wipe = tracker.peek(
        (True, True), song_time_sec=2.0, duration=0.8, mask_type="strips"
    )
    assert wipe == MaskTransition(
        kind="hard_layout",
        start_sec=2.0,
        duration=0.8,
        from_slots=(True, False),
    )
    assert tracker.peek(
        (True, False), song_time_sec=2.0, duration=0.8, mask_type="strips"
    ) is None


def test_transition_tracker_clear_when_duration_zero() -> None:
    tracker = PatternMaskTransitionTracker()
    tracker.commit((True, True))
    wipe = tracker.peek(
        (True, False), song_time_sec=3.0, duration=0.0, mask_type="plasma"
    )
    assert wipe == MaskTransition(
        kind="clear",
        start_sec=3.0,
        duration=0.0,
        from_slots=(True, True),
    )
