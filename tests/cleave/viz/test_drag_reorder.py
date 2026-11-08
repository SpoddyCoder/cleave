from __future__ import annotations

from cleave.viz.drag_reorder import DRAG_PRESET, RowDragGesture, drop_index

_ROWS = [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, 40.0)]


def test_drop_index_top_middle_bottom() -> None:
    assert drop_index(_ROWS, 2, -5.0) == 0
    assert drop_index(_ROWS, 0, 16.0) == 1
    assert drop_index(_ROWS, 0, 26.0) == 2
    assert drop_index(_ROWS, 1, 99.0) == 3


def test_drop_index_stays_put_on_the_dragged_row() -> None:
    for y in (10.5, 15.0, 19.5):
        assert drop_index(_ROWS, 1, y) == 1


def test_drop_index_mixed_heights_and_missing_rows() -> None:
    spans = [(0.0, 10.0), (10.0, 60.0), None, (60.0, 70.0)]
    assert drop_index(spans, 0, 30.0) == 0
    assert drop_index(spans, 0, 40.0) == 1
    assert drop_index(spans, 3, 40.0) == 2


def test_gesture_ignores_the_partial_press_frame() -> None:
    # The press on row 2 lands mid-draw: rows 0 and 1 drew before it existed.
    drag = RowDragGesture(DRAG_PRESET, "layer_1", 2)
    drag.record_span(2, 20.0, 30.0)
    drag.record_span(3, 30.0, 40.0)
    assert drag.target(25.0) is None
    drag.clear_spans()
    for index, (top, bottom) in enumerate(_ROWS):
        drag.record_span(index, top, bottom)
    assert drag.target(25.0) == 2


def test_gesture_waits_for_dragged_row_then_clears() -> None:
    drag = RowDragGesture(DRAG_PRESET, "layer_1", 1)
    drag.clear_spans()
    drag.record_span(0, 0.0, 10.0)
    assert drag.target(25.0) is None
    drag.record_span(1, 10.0, 20.0)
    drag.record_span(2, 20.0, 30.0)
    assert drag.target(27.0) == 2
    drag.clear_spans()
    assert drag.target(27.0) is None
