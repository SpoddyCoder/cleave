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


def test_press_on_bar_seeks_and_scrubs_once_per_tick() -> None:
    actions = _Actions()
    pointer = TimelinePointer(_Geometry(StripHit(0, 5.0, 0.2)), actions, _session())
    pointer.press(0, 0)
    assert actions.calls[-1] == ("seek", 5.0)
    assert pointer.scrubbing
    actions.calls.clear()
    pointer.motion(100)
    pointer.motion(120)
    pointer.tick()
    pointer.tick()
    assert actions.calls == [("seek", 12.0)]
    pointer.motion(150)
    pointer.release()
    assert actions.calls[-1] == ("seek", 15.0)
    assert not pointer.scrubbing
    pointer.motion(200)
    pointer.tick()
    assert actions.calls[-1] == ("seek", 15.0)


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
    pointer = TimelinePointer(_Geometry(StripHit(0, 5.0, 0.2)), actions, session)
    pointer.press(0, 0)
    pointer.motion(100)
    pointer.cancel()
    pointer.tick()
    assert actions.calls[-1] == ("seek", 5.0)

    pointer.press(0, 0)
    pointer.motion(100)
    session.timeline.panel_open = False
    pointer.tick()
    assert actions.calls[-1] == ("seek", 5.0)
    assert not pointer.scrubbing
