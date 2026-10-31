"""Side-arrow hit tests and hold-to-repeat. No GL window."""

from __future__ import annotations

from unittest.mock import patch

import pygame

from cleave.viz.key_repeat import (
    ACCEL_AFTER_SEC,
    FAST_INTERVAL_SEC,
    INITIAL_DELAY_SEC,
    SLOW_INTERVAL_SEC,
    KeyRepeatController,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import apply_field_horizontal, row_spec
from cleave.viz.value_nudge import (
    NudgeRect,
    ValueNudgeHold,
    nudge_arrow_rects,
    nudge_hit_at,
    nudge_hover_fill_rect,
    nudge_press_skips_row,
    selectable_text_y,
)
from tests.cleave.viz.test_controls import _make_controls

_OPACITY = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
_SNAP = RowDescriptor(RowKind.TIMELINE_PLACEMENT_SNAP)


def _opacity(controls) -> int:
    return controls.session.layers["layer_1"].opacity_pct


def _rects() -> tuple[NudgeRect, NudgeRect]:
    # Cluster sits on the right of a 200px row, 4px frame pad, widths 10/30/14.
    return nudge_arrow_rects(
        0.0,
        20.0,
        200.0,
        36.0,
        (10.0, 30.0, 14.0),
        frame_pad_x=4.0,
    )


def test_arrow_rects_cover_glyphs_and_not_the_value() -> None:
    back, forward = _rects()
    assert back == NudgeRect(142.0, 20.0, 152.0, 36.0)
    assert forward == NudgeRect(182.0, 20.0, 196.0, 36.0)

    left = nudge_hit_at(145.0, 28.0, back, forward)
    right = nudge_hit_at(190.0, 28.0, back, forward)
    body = nudge_hit_at(167.0, 28.0, back, forward)

    assert left is not None and left.forward is False
    assert right is not None and right.forward is True
    assert body is None
    assert nudge_hit_at(151.9, 20.0, back, forward) == left
    assert nudge_hit_at(152.0, 28.0, back, forward) is None
    assert nudge_hit_at(181.9, 28.0, back, forward) is None
    assert nudge_hit_at(182.0, 20.0, back, forward) == right
    assert nudge_hit_at(196.0, 28.0, back, forward) is None
    assert nudge_hit_at(145.0, 19.9, back, forward) is None
    assert nudge_hit_at(145.0, 36.0, back, forward) is None


def test_hover_fill_centers_on_the_arrow_character() -> None:
    arrow_w = 8.0
    space_w = 4.0
    back, forward = nudge_arrow_rects(
        0.0,
        20.0,
        200.0,
        36.0,
        (arrow_w + space_w, 30.0, space_w + arrow_w),
        frame_pad_x=4.0,
    )
    left = nudge_hover_fill_rect(
        back, forward=False, arrow_width=arrow_w, space_width=space_w
    )
    right = nudge_hover_fill_rect(
        forward, forward=True, arrow_width=arrow_w, space_width=space_w
    )

    assert (left.min_x + left.max_x) / 2 == back.min_x + arrow_w / 2
    assert (right.min_x + right.max_x) / 2 == (
        forward.min_x + space_w + arrow_w / 2
    )
    assert left.max_x - left.min_x == back.max_x - back.min_x
    assert right.max_x - right.min_x == forward.max_x - forward.min_x
    assert (left.min_y, left.max_y) == (back.min_y, back.max_y)
    assert (right.min_y, right.max_y) == (forward.min_y, forward.max_y)

    body = nudge_hit_at(
        (back.max_x + forward.min_x) / 2, 28.0, back, forward
    )
    assert body is None


def test_selectable_text_y_matches_the_label_line() -> None:
    # Dear ImGui defaults: ItemSpacing.y is 4, SelectableTextAlign.y is 0,
    # FramePadding.y is 3. Inspector Selectable uses the default size, so the
    # text box is the line and frame padding is not part of the offset.
    line = 13.0
    assert (
        selectable_text_y(
            20.0,
            4.0,
            selectable_text_align_y=0.0,
            text_box_height=line,
            text_height=line,
        )
        == 22.0
    )
    assert selectable_text_y(10.0, 3.0) == 11.0
    assert selectable_text_y(10.0, 1.0) == 10.0
    # Align drops the line only when the box is taller than the text.
    assert (
        selectable_text_y(
            10.0,
            4.0,
            selectable_text_align_y=0.5,
            text_box_height=18.0,
            text_height=14.0,
        )
        == 14.0
    )
    assert (
        selectable_text_y(
            10.0,
            4.0,
            selectable_text_align_y=1.0,
            text_box_height=line,
            text_height=line,
        )
        == 12.0
    )


def test_arrow_press_steps_and_skips_drag_and_activate() -> None:
    back, forward = _rects()
    left = nudge_hit_at(145.0, 28.0, back, forward)
    right = nudge_hit_at(190.0, 28.0, back, forward)
    body = nudge_hit_at(167.0, 28.0, back, forward)

    assert nudge_press_skips_row(left) is True
    assert nudge_press_skips_row(right) is True
    assert nudge_press_skips_row(body) is False

    controls = _make_controls(("layer_1",))
    start = _opacity(controls)
    assert left is not None and right is not None
    apply_field_horizontal(controls, _OPACITY, left.forward, False)
    assert _opacity(controls) == start - 1
    apply_field_horizontal(controls, _OPACITY, right.forward, False)
    assert _opacity(controls) == start


def _hold_schedule() -> list[float]:
    """Quiet, then the delay boundary, then slow, then fast. Same as keys."""
    dts = [INITIAL_DELAY_SEC - 0.01, 0.01]
    held = INITIAL_DELAY_SEC
    n_slow = int((ACCEL_AFTER_SEC - INITIAL_DELAY_SEC) / SLOW_INTERVAL_SEC)
    for _ in range(n_slow):
        dts.append(SLOW_INTERVAL_SEC)
        held += SLOW_INTERVAL_SEC
    dts.append(ACCEL_AFTER_SEC - held + 0.001)
    dts.append(FAST_INTERVAL_SEC * 0.5)
    dts.append(FAST_INTERVAL_SEC * 0.5)
    return dts


def test_hold_matches_key_repeat_then_stops_on_release() -> None:
    controls = _make_controls(("layer_1",))
    assert row_spec(_OPACITY.kind).repeatable is True
    start = _opacity(controls)
    apply_field_horizontal(controls, _OPACITY, True, False)
    hold = ValueNudgeHold(controls)
    before_press = _opacity(controls)
    hold.press(_OPACITY, True, True)
    assert _opacity(controls) == before_press
    assert hold.armed is True

    keys = KeyRepeatController()
    key_fires: list[int] = []
    keys.on_keydown(
        pygame.K_RIGHT,
        0,
        on_repeat=lambda _key, _mod: key_fires.append(1),
    )

    for dt in _hold_schedule():
        opacity_before = _opacity(controls)
        fires_before = len(key_fires)
        hold.tick(dt)
        keys.tick(dt)
        assert _opacity(controls) - opacity_before == len(key_fires) - fires_before

    assert _opacity(controls) == start + 1 + len(key_fires)
    assert len(key_fires) > 1

    hold.release()
    assert hold.armed is False
    frozen = _opacity(controls)
    hold.tick(SLOW_INTERVAL_SEC)
    hold.tick(FAST_INTERVAL_SEC)
    assert _opacity(controls) == frozen


def test_non_repeatable_spec_steps_once() -> None:
    controls = _make_controls(("layer_1",))
    assert row_spec(_SNAP.kind).repeatable is False
    controls.session.timeline.placement_snap = "off"
    apply_field_horizontal(controls, _SNAP, True, False)
    once = controls.session.timeline.placement_snap
    assert once != "off"

    hold = ValueNudgeHold(controls)
    hold.press(_SNAP, True, False)
    assert hold.armed is True
    hold.tick(INITIAL_DELAY_SEC)
    hold.tick(ACCEL_AFTER_SEC)
    assert controls.session.timeline.placement_snap == once
    assert hold.armed is True
    hold.release()
    assert hold.armed is False


def test_key_repeat_and_nudge_disarm_each_other() -> None:
    controls = _make_controls(("layer_1",))
    controls.arm_key_repeat(pygame.K_RIGHT, 0, on_repeat=lambda _key, _mod: None)
    assert controls.key_repeat_armed is True
    controls.begin_value_nudge(_OPACITY, True, True)
    assert controls.key_repeat_armed is False
    assert controls.value_nudge_armed is True
    assert controls.value_nudge.desc == _OPACITY
    assert controls.value_nudge.forward is True

    controls.arm_key_repeat(pygame.K_LEFT, 0, on_repeat=lambda _key, _mod: None)
    assert controls.key_repeat_armed is True
    assert controls.value_nudge_armed is False


def test_tick_releases_when_the_button_is_up_or_a_modal_is_open() -> None:
    controls = _make_controls(("layer_1",))
    start = _opacity(controls)
    apply_field_horizontal(controls, _OPACITY, True, False)
    controls.begin_value_nudge(_OPACITY, True, True)

    mouse_down = patch(
        "cleave.viz.controls.pygame.mouse.get_pressed",
        return_value=(True, False, False),
    )
    with mouse_down:
        controls.tick(INITIAL_DELAY_SEC - 0.01)
        assert _opacity(controls) == start + 1
        controls.tick(0.01)
        assert _opacity(controls) == start + 2

    controls.tick(SLOW_INTERVAL_SEC)
    assert _opacity(controls) == start + 2
    assert controls.value_nudge_armed is False

    apply_field_horizontal(controls, _OPACITY, True, False)
    controls.begin_value_nudge(_OPACITY, True, True)
    controls._modal_host._request = object()
    with mouse_down:
        controls.tick(INITIAL_DELAY_SEC)
    assert _opacity(controls) == start + 3
    assert controls.value_nudge_armed is False
