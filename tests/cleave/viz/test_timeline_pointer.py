"""Mouse gestures on the timeline strip, with fake geometry and actions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cleave.viz.timeline_overlay import StripHit
from cleave.viz.timeline_pointer import MIDDLE_BUTTON, TimelinePointer
from cleave.viz.timeline_view import StripView


class _Geometry:
    def __init__(self, hit: StripHit | None) -> None:
        self.hit = hit

    def hit_at(self, x: float, y: float) -> StripHit | None:
        return self.hit

    def time_at_x(self, x: float) -> float | None:
        return x / 10.0

    def view_sec_per_px(self) -> float:
        return 0.1

    def scrollbar_sec_per_px(self) -> float:
        return 0.5


class _Actions:
    duration_sec = 100.0

    def __init__(self, *, cue_hit: bool = False) -> None:
        self.cue_hit = cue_hit
        self.eye_usable = True
        self.calls: list[tuple] = []

    def focus_row(self, row: int) -> None:
        self.calls.append(("focus", row))

    def select_cue_near(self, slot: str, t_sec: float, tolerance_sec: float) -> bool:
        self.calls.append(("select", slot, t_sec, tolerance_sec))
        return self.cue_hit

    def seek_to(self, t_sec: float) -> None:
        self.calls.append(("seek", t_sec))

    def toggle_transport(self) -> None:
        self.calls.append(("transport",))

    def toggle_record(self) -> None:
        self.calls.append(("record",))

    def toggle_arm_row(self, row: int) -> None:
        self.calls.append(("arm", row))

    def toggle_row_visibility(self, row: int) -> None:
        self.calls.append(("visibility", row))

    def strip_target_pressable(self, target: str, row: int | None) -> bool:
        return target != "eye" or self.eye_usable


def _session(panel_open: bool = True, view: StripView | None = None):
    return SimpleNamespace(
        layer_z_order=["layer_1", "layer_2"],
        timeline=SimpleNamespace(
            panel_open=panel_open,
            strip_hover=None,
            strip_view=view if view is not None else StripView(),
        ),
    )


def _zoomed_view() -> StripView:
    return StripView(start_sec=40.0, span_sec=20.0)


def test_press_on_cue_selects_and_does_not_scrub() -> None:
    actions = _Actions(cue_hit=True)
    pointer = TimelinePointer(_Geometry(StripHit(1, 5.0, 0.2)), actions, _session())
    assert pointer.press(0, 0) is True
    assert actions.calls == [("focus", 1), ("select", "layer_2", 5.0, 0.2)]
    assert not pointer.scrubbing


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_single_press_on_bar_selects_without_seeking() -> None:
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(StripHit(0, 5.0, 0.2)), actions, _session())
    assert pointer.press(0, 0) is True
    assert actions.calls == [("focus", 0), ("select", "layer_1", 5.0, 0.2)]
    assert not pointer.scrubbing
    pointer.motion(100, 0)
    pointer.tick()
    assert all(call[0] != "seek" for call in actions.calls)


def test_double_click_on_row_seeks_and_held_drag_scrubs() -> None:
    clock = _Clock()
    actions = _Actions(cue_hit=True)
    pointer = TimelinePointer(
        _Geometry(StripHit(0, 5.0, 0.2)), actions, _session(), clock=clock
    )
    pointer.press(10, 10)
    pointer.release()
    clock.now += 0.2
    actions.calls.clear()
    pointer.press(12, 11)
    assert actions.calls == [("focus", 0), ("seek", 5.0)]
    assert pointer.scrubbing
    actions.calls.clear()
    pointer.motion(100, 0)
    pointer.motion(120, 0)
    pointer.tick()
    pointer.tick()
    assert actions.calls == [("seek", 12.0)]
    pointer.motion(150, 0)
    pointer.release()
    assert actions.calls[-1] == ("seek", 15.0)
    assert not pointer.scrubbing


def test_slow_far_or_other_row_second_press_is_not_a_double_click() -> None:
    clock = _Clock()
    geometry = _Geometry(StripHit(0, 5.0, 0.2))
    actions = _Actions()
    pointer = TimelinePointer(geometry, actions, _session(), clock=clock)

    pointer.press(10, 10)
    clock.now += 0.5
    pointer.press(10, 10)
    pointer.press(30, 10)
    geometry.hit = StripHit(1, 5.0, 0.2)
    pointer.press(30, 10)
    assert all(call[0] != "seek" for call in actions.calls)


def test_triple_click_does_not_seek_twice() -> None:
    clock = _Clock()
    actions = _Actions()
    pointer = TimelinePointer(
        _Geometry(StripHit(0, 5.0, 0.2)), actions, _session(), clock=clock
    )
    for _ in range(3):
        pointer.press(10, 10)
        pointer.release()
        clock.now += 0.1
    assert [call for call in actions.calls if call[0] == "seek"] == [("seek", 5.0)]


def test_ruler_press_drags_and_scrubs_once_per_tick() -> None:
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(StripHit(None, 5.0, 0.2)), actions, _session())
    pointer.press(0, 0)
    assert actions.calls == [("seek", 5.0)]
    assert pointer.scrubbing
    actions.calls.clear()
    pointer.motion(100, 0)
    pointer.motion(120, 0)
    pointer.tick()
    pointer.tick()
    assert actions.calls == [("seek", 12.0)]
    pointer.release()
    pointer.motion(200, 0)
    pointer.tick()
    assert actions.calls == [("seek", 12.0)]


def test_press_on_ruler_seeks_without_focusing_a_row() -> None:
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(StripHit(None, 3.0, 0.2)), actions, _session())
    pointer.press(0, 0)
    assert actions.calls == [("seek", 3.0)]
    assert pointer.scrubbing


def test_press_on_prefix_only_focuses_row() -> None:
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(StripHit(1, None, 0.2)), actions, _session())
    assert pointer.press(0, 0) is True
    assert actions.calls == [("focus", 1)]
    assert not pointer.scrubbing


def test_press_miss_does_nothing() -> None:
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(None), actions, _session())
    assert pointer.press(0, 0) is False
    assert actions.calls == []


def test_cancel_and_closed_strip_drop_pending_scrub() -> None:
    actions = _Actions()
    session = _session()
    pointer = TimelinePointer(_Geometry(StripHit(None, 5.0, 0.2)), actions, session)
    pointer.press(0, 0)
    pointer.motion(100, 0)
    pointer.cancel()
    pointer.tick()
    assert actions.calls[-1] == ("seek", 5.0)

    pointer.press(0, 0)
    pointer.motion(100, 0)
    session.timeline.panel_open = False
    pointer.tick()
    assert actions.calls[-1] == ("seek", 5.0)
    assert not pointer.scrubbing


def test_corner_buttons_toggle_transport_and_record() -> None:
    geometry = _Geometry(StripHit(None, None, 0.2, target="play"))
    actions = _Actions()
    pointer = TimelinePointer(geometry, actions, _session())
    assert pointer.press(0, 0) is True
    geometry.hit = StripHit(None, None, 0.2, target="record")
    assert pointer.press(0, 0) is True
    assert actions.calls == [("transport",), ("record",)]
    assert not pointer.scrubbing


def test_label_click_focuses_and_double_click_arms() -> None:
    clock = _Clock()
    actions = _Actions()
    pointer = TimelinePointer(
        _Geometry(StripHit(1, None, 0.2, target="label")), actions, _session(), clock=clock
    )
    pointer.press(10, 10)
    assert actions.calls == [("focus", 1)]
    clock.now += 0.2
    pointer.press(11, 10)
    assert actions.calls == [("focus", 1), ("arm", 1)]
    clock.now += 0.1
    pointer.press(11, 10)
    assert actions.calls[-1] == ("focus", 1)


def test_eye_click_toggles_row_visibility() -> None:
    clock = _Clock()
    actions = _Actions()
    pointer = TimelinePointer(
        _Geometry(StripHit(1, None, 0.2, target="eye")), actions, _session(), clock=clock
    )
    pointer.press(10, 10)
    clock.now += 0.1
    pointer.press(10, 10)
    assert actions.calls == [("visibility", 1), ("visibility", 1)]
    assert not pointer.scrubbing


def test_label_then_bar_press_is_not_a_double_click() -> None:
    clock = _Clock()
    geometry = _Geometry(StripHit(0, None, 0.2, target="label"))
    actions = _Actions()
    pointer = TimelinePointer(geometry, actions, _session(), clock=clock)
    pointer.press(10, 10)
    clock.now += 0.1
    geometry.hit = StripHit(0, 5.0, 0.2)
    pointer.press(12, 10)
    assert all(call[0] not in ("seek", "arm") for call in actions.calls)


def test_hover_tracks_controls_and_clears() -> None:
    geometry = _Geometry(StripHit(2, None, 0.2, target="label"))
    session = _session()
    pointer = TimelinePointer(geometry, _Actions(), session)
    pointer.motion(5, 5)
    assert session.timeline.strip_hover == ("label", 2)
    geometry.hit = StripHit(None, None, 0.2, target="record")
    pointer.motion(5, 5)
    assert session.timeline.strip_hover == ("record", None)
    geometry.hit = StripHit(0, 5.0, 0.2)
    pointer.motion(5, 5)
    assert session.timeline.strip_hover is None
    geometry.hit = StripHit(None, None, 0.2, target="play")
    pointer.motion(5, 5)
    pointer.clear_hover()
    assert session.timeline.strip_hover is None


def test_over_ruler_is_the_time_scale_clear_of_the_corner_buttons() -> None:
    geometry = _Geometry(StripHit(None, 5.0, 0.2))
    pointer = TimelinePointer(geometry, _Actions(), _session())
    assert pointer.over_ruler is False
    pointer.motion(5, 5)
    assert pointer.over_ruler is True
    geometry.hit = StripHit(None, None, 0.2, target="play")
    pointer.motion(5, 5)
    assert pointer.over_ruler is False
    geometry.hit = StripHit(0, 5.0, 0.2)
    pointer.motion(5, 5)
    assert pointer.over_ruler is False
    geometry.hit = StripHit(None, 5.0, 0.2)
    pointer.motion(5, 5)
    pointer.clear_hover()
    assert pointer.over_ruler is False


def test_hovered_eye_is_pressable_only_while_its_toggle_would_act() -> None:
    geometry = _Geometry(StripHit(1, None, 0.2, target="eye"))
    actions = _Actions()
    pointer = TimelinePointer(geometry, actions, _session())
    assert pointer.hover_pressable is False
    pointer.motion(5, 5)
    assert pointer.hover_pressable is True
    actions.eye_usable = False
    assert pointer.hover_pressable is False
    geometry.hit = StripHit(1, None, 0.2, target="label")
    pointer.motion(5, 5)
    assert pointer.hover_pressable is True


def test_row_drag_past_threshold_pans_and_does_not_scrub() -> None:
    view = _zoomed_view()
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(StripHit(0, 50.0, 0.2)), actions, _session(view=view))
    pointer.press(500, 10)
    assert not pointer.panning and not view.held
    pointer.motion(502, 10)
    assert not pointer.panning and view.start_sec == 40.0
    pointer.motion(480, 10)
    assert pointer.panning and view.held
    # Dragging left by 20px at 0.1s per pixel shows 2s later.
    assert view.start_sec == pytest.approx(42.0)
    pointer.motion(520, 10)
    assert view.start_sec == pytest.approx(38.0)
    pointer.release()
    assert not pointer.panning and not view.held
    assert not any(call[0] == "seek" for call in actions.calls)
    assert ("focus", 0) in actions.calls


def test_row_drag_does_nothing_at_full_zoom() -> None:
    view = StripView()
    pointer = TimelinePointer(_Geometry(StripHit(0, 50.0, 0.2)), _Actions(), _session(view=view))
    pointer.press(500, 10)
    pointer.motion(400, 10)
    assert not pointer.panning and not view.held
    assert view.span_sec is None


def test_a_pan_does_not_leave_a_double_click_armed() -> None:
    clock = _Clock()
    view = _zoomed_view()
    actions = _Actions()
    pointer = TimelinePointer(
        _Geometry(StripHit(0, 50.0, 0.2)), actions, _session(view=view), clock=clock
    )
    pointer.press(500, 10)
    pointer.motion(490, 10)
    pointer.motion(500, 10)
    pointer.release()
    pointer.press(500, 10)
    assert not pointer.scrubbing
    assert not any(call[0] == "seek" for call in actions.calls)


def test_middle_drag_pans_from_the_ruler_at_once() -> None:
    view = _zoomed_view()
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(StripHit(None, 50.0, 0.2)), actions, _session(view=view))
    assert pointer.press(500, 2, MIDDLE_BUTTON) is True
    assert pointer.panning and not pointer.scrubbing
    pointer.motion(510, 2)
    assert view.start_sec == pytest.approx(39.0)
    pointer.release()
    assert not view.held
    assert actions.calls == []


def test_middle_press_on_a_button_does_nothing() -> None:
    actions = _Actions()
    pointer = TimelinePointer(
        _Geometry(StripHit(None, None, 0.2, target="play")), actions, _session(view=_zoomed_view())
    )
    pointer.press(5, 5, MIDDLE_BUTTON)
    assert actions.calls == [] and not pointer.panning


def test_wheel_zooms_about_the_time_under_the_pointer() -> None:
    view = StripView()
    pointer = TimelinePointer(_Geometry(None), _Actions(), _session(view=view))
    # time_at_x(500) is 50s, the middle of the 100s song.
    pointer.wheel(500, 0.0, 1.0)
    assert view.span_sec == pytest.approx(80.0)
    assert view.start_sec == pytest.approx(10.0)
    pointer.wheel(500, 0.0, -1.0)
    assert view.span_sec is None


def test_shift_or_sideways_wheel_pans_a_tenth_of_the_window() -> None:
    view = _zoomed_view()
    pointer = TimelinePointer(_Geometry(None), _Actions(), _session(view=view))
    pointer.wheel(500, 0.0, 1.0, shift=True)
    assert view.start_sec == pytest.approx(38.0) and view.span_sec == 20.0
    pointer.wheel(500, 0.0, -1.0, shift=True)
    pointer.wheel(500, 1.0, 0.0)
    assert view.start_sec == pytest.approx(42.0) and view.span_sec == 20.0


def test_thumb_drag_moves_the_window_with_the_pointer() -> None:
    view = _zoomed_view()
    actions = _Actions()
    pointer = TimelinePointer(
        _Geometry(StripHit(None, 50.0, 0.2, target="scroll_thumb")),
        actions,
        _session(view=view),
    )
    pointer.press(500, 90)
    assert pointer.scrollbar_active and view.held and not pointer.panning
    pointer.motion(520, 90)
    assert view.start_sec == pytest.approx(50.0)
    pointer.motion(0, 90)
    assert view.start_sec == 0.0
    pointer.release()
    assert not view.held
    assert actions.calls == []


def test_track_press_centres_the_window_then_drags() -> None:
    view = _zoomed_view()
    pointer = TimelinePointer(
        _Geometry(StripHit(None, 80.0, 0.2, target="scroll_track")),
        _Actions(),
        _session(view=view),
    )
    pointer.press(800, 90)
    assert view.start_sec == pytest.approx(70.0)
    pointer.motion(810, 90)
    assert view.start_sec == pytest.approx(75.0)


def test_scrollbar_hover_is_not_a_strip_control_and_needs_zoom() -> None:
    view = StripView()
    session = _session(view=view)
    pointer = TimelinePointer(
        _Geometry(StripHit(None, 50.0, 0.2, target="scroll_thumb")), _Actions(), session
    )
    pointer.motion(5, 5)
    assert session.timeline.strip_hover is None
    assert pointer.scrollbar_active is False and pointer.over_ruler is False
    view.span_sec = 20.0
    assert pointer.scrollbar_active is True
    pointer.clear_hover()
    assert pointer.scrollbar_active is False


def test_scrub_holds_the_view_until_release_or_cancel() -> None:
    view = _zoomed_view()
    pointer = TimelinePointer(_Geometry(StripHit(None, 50.0, 0.2)), _Actions(), _session(view=view))
    pointer.press(500, 2)
    assert pointer.scrubbing and view.held
    pointer.release()
    assert not view.held
    pointer.press(500, 2)
    pointer.cancel()
    assert not view.held
