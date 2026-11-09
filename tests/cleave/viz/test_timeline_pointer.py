"""Mouse gestures on the timeline strip, with fake geometry and actions."""

from __future__ import annotations

from types import SimpleNamespace

from cleave.viz.timeline_overlay import StripHit
from cleave.viz.timeline_pointer import TimelinePointer


class _Geometry:
    def __init__(self, hit: StripHit | None) -> None:
        self.hit = hit

    def hit_at(self, x: float, y: float) -> StripHit | None:
        return self.hit

    def time_at_x(self, x: float) -> float | None:
        return x / 10.0


class _Actions:
    def __init__(self, *, cue_hit: bool = False) -> None:
        self.cue_hit = cue_hit
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


def _session(panel_open: bool = True):
    return SimpleNamespace(
        layer_z_order=["layer_1", "layer_2"],
        timeline=SimpleNamespace(panel_open=panel_open),
    )


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
