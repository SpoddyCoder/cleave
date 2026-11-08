"""Mouse drag-to-reorder gesture for list rows with a drag handle.

The shell records each row's vertical span while it draws, then asks for the
drop target under the pointer. The gesture holds no list data: the owning
controller moves the item, and this only tracks where it is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


def drop_index(
    spans: Sequence[tuple[float, float] | None],
    dragged: int,
    mouse_y: float,
) -> int:
    """Index the dragged row should take for a pointer at *mouse_y*.

    Counts the other rows whose vertical centre lies above the pointer, so rows
    of different heights work and the target does not flip while the pointer
    stays on the dragged row. A ``None`` span (row not drawn) is skipped.
    """
    target = 0
    for index, span in enumerate(spans):
        if index == dragged or span is None:
            continue
        top, bottom = span
        if (top + bottom) * 0.5 < mouse_y:
            target += 1
    return target


DRAG_PRESET = "preset"
DRAG_LAYER = "layer"


@dataclass
class RowDragGesture:
    """One held drag handle and the row spans drawn this frame.

    *kind* is ``DRAG_PRESET`` (a row in *slot*'s preset list) or ``DRAG_LAYER``
    (*slot* in the layer z-order). *index* is the dragged row's current position.

    The press lands partway through drawing the list, so that frame has spans
    only for the rows from the dragged one down. No target is given until the
    spans have been cleared once and a whole frame of rows has recorded.
    """

    kind: str
    slot: str
    index: int
    _spans: dict[int, tuple[float, float]] = field(default_factory=dict)
    _whole_frame: bool = False

    def record_span(self, index: int, top: float, bottom: float) -> None:
        self._spans[index] = (top, bottom)

    def target(self, mouse_y: float) -> int | None:
        """Drop index for *mouse_y*, or None until a whole frame has recorded."""
        if not self._whole_frame or self.index not in self._spans:
            return None
        count = max(self._spans) + 1
        spans = [self._spans.get(index) for index in range(count)]
        return drop_index(spans, self.index, mouse_y)

    def clear_spans(self) -> None:
        """End of frame: forget this frame's spans; the next frame is whole."""
        self._spans.clear()
        self._whole_frame = True
