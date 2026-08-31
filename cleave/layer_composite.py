"""Shared layer-composite contract for both GPU compositors.

``LayerFramePipeline.composite`` is the layer choke point: it builds one
``LayerCompositeRequest`` and selects ``GlCompositor`` or ``GlMaskedCompositor``.
Layers are in session z-order (first = topmost). Each implementation chooses
its own draw direction.

``mask`` is ``None`` on the unmasked path. Wipes are an explicit
``MaskTransition`` on the request; compositors do not infer them from slot diffs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from cleave.gl_color_format import GlColorFormat
from cleave.pattern_mask import PatternMaskParams
from cleave.pattern_mask_transition import MaskTransition

if TYPE_CHECKING:
    from cleave.gl_compositor import LayerFbo


@dataclass(frozen=True)
class LayerCompositeRequest:
    """One stack composite into a content FBO.

    ``layers`` are in z-order (first = topmost, matching ``session.layer_z_order``).
    ``mask`` is ``None`` for the unmasked path. ``transition`` is set only when
    the active slot set changed; an in-flight wipe continues from stored state
    and ``song_time_sec``.
    """

    target_fbo_id: int
    layers: Sequence[LayerFbo]
    color_format: GlColorFormat
    mask: PatternMaskParams | None = None
    active_slots: tuple[bool, ...] | None = None
    song_time_sec: float = 0.0
    transition: MaskTransition | None = None


@runtime_checkable
class LayerCompositor(Protocol):
    def composite(self, request: LayerCompositeRequest) -> None:
        """Clear the target and stack ``request.layers``."""

    def set_color_format(self, color_format: GlColorFormat) -> None:
        """Switch attachment format; raise if RGBA16F is unsupported."""


def apply_color_format(
    color_format: GlColorFormat,
    *targets: object,
) -> None:
    """Call ``set_color_format`` on each non-None target."""
    for target in targets:
        if target is None:
            continue
        setter = getattr(target, "set_color_format", None)
        if setter is None:
            raise TypeError(f"{type(target).__name__} has no set_color_format")
        setter(color_format)
