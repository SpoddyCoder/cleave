"""Aspect-fit math shared by presentation and live preview sizing."""

from __future__ import annotations


def aspect_fit_size(
    content_wh: tuple[float, float],
    rect_wh: tuple[float, float],
) -> tuple[float, float] | None:
    """Largest size with the aspect of *content_wh* that fits inside *rect_wh*.

    None when either size is empty.
    """
    content_w, content_h = content_wh
    rect_w, rect_h = rect_wh
    if rect_w <= 0 or rect_h <= 0 or content_w <= 0 or content_h <= 0:
        return None
    content_aspect = content_w / content_h
    if content_aspect >= rect_w / rect_h:
        fit_w = float(rect_w)
        return fit_w, fit_w / content_aspect
    fit_h = float(rect_h)
    return fit_h * content_aspect, fit_h
