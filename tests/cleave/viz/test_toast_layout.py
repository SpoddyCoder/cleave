"""Pure toast geometry, measured without pygame."""

from __future__ import annotations

import pytest

from cleave.viz.shell_layout import ShellLayout
from cleave.viz.theme import tuning_ui_metrics
from cleave.viz.toast_layout import ToastGeometry, toast_geometry

Rect = tuple[int, int, int, int]


class _FixedMeasure:
    def __init__(self, char_w: int = 10, line_h: int = 16) -> None:
        self._char_w = char_w
        self._line_h = line_h

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * self._char_w, self._line_h)

    def get_linesize(self) -> int:
        return self._line_h


def _inside(inner: Rect, outer: Rect) -> bool:
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return (
        iw >= 0
        and ih >= 0
        and ix >= ox
        and iy >= oy
        and ix + iw <= ox + ow
        and iy + ih <= oy + oh
    )


def _overlaps(a: Rect, b: Rect) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def _assert_in_visualiser(layout: ShellLayout, geometry: ToastGeometry) -> None:
    assert _inside(geometry.rect, layout.visualiser)
    assert not _overlaps(geometry.rect, layout.navigator)
    assert not _overlaps(geometry.rect, layout.inspector)
    for line in (geometry.persistent_line, geometry.timed_line):
        if line is None:
            continue
        assert _inside(line, geometry.rect)
        assert _inside(line, layout.visualiser)
        assert not _overlaps(line, layout.navigator)
        assert not _overlaps(line, layout.inspector)


@pytest.mark.parametrize("docked", (False, True))
@pytest.mark.parametrize("persistent", (None, "Stem file missing"))
def test_toast_geometry_anchors_in_the_visualiser(
    docked: bool, persistent: str | None
) -> None:
    layout = ShellLayout.compute(1600, 900, 32, 36, 120, docked=docked)
    measure = _FixedMeasure()
    timed = "Saved"
    geometry = toast_geometry(
        layout, measure, persistent=persistent, timed=timed
    )
    metrics = tuning_ui_metrics()
    vx, vy, _vw, _vh = layout.visualiser
    texts = [timed] if persistent is None else [persistent, timed]
    text_w = max(measure.size(text)[0] for text in texts)
    line_h = measure.get_linesize()
    count = len(texts)
    content_h = (
        count * line_h
        + max(0, count - 1) * metrics.line_gap
        + metrics.padding * 2
    )
    assert geometry.rect[0] == vx + metrics.margin
    assert geometry.rect[1] == vy + metrics.margin
    assert geometry.rect[2] == text_w + metrics.padding * 2
    assert geometry.rect[3] == content_h
    assert geometry.timed_line is not None
    if persistent is None:
        assert geometry.persistent_line is None
    else:
        assert geometry.persistent_line is not None
        assert geometry.persistent_line[1] < geometry.timed_line[1]
    _assert_in_visualiser(layout, geometry)


@pytest.mark.parametrize("docked", (False, True))
def test_toast_geometry_clamps_inside_a_narrow_visualiser(docked: bool) -> None:
    layout = ShellLayout.compute(
        320,
        70,
        18,
        18,
        0,
        insp_width=200,
        docked=docked,
    )
    measure = _FixedMeasure()
    text = "M" * 80
    geometry = toast_geometry(
        layout, measure, persistent=text, timed="Saved"
    )
    metrics = tuning_ui_metrics()
    _vx, _vy, vw, vh = layout.visualiser
    max_w = vw - 2 * metrics.margin
    max_h = vh - 2 * metrics.margin
    assert max_w < measure.size(text)[0] + metrics.padding * 2
    line_h = measure.get_linesize()
    content_h = line_h * 2 + metrics.line_gap + metrics.padding * 2
    assert content_h > max_h
    assert geometry.rect[2] == max_w
    assert geometry.rect[3] == max_h
    assert geometry.rect[0] == layout.visualiser[0] + metrics.margin
    assert geometry.rect[1] == layout.visualiser[1] + metrics.margin
    _assert_in_visualiser(layout, geometry)
