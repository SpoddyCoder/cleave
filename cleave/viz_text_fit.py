"""Text fitting helpers for overlay labels."""

from __future__ import annotations

import re

import pygame

_COUNTER_SUFFIX = re.compile(r" \((\d+)/(\d+)\)$")


def _text_width(font: pygame.font.Font, text: str) -> int:
    return font.size(text)[0]


def fit_text_to_width(font: pygame.font.Font, text: str, max_px: int) -> str:
    """Shorten text with a trailing ellipsis until it fits max_px."""
    if not text or max_px <= 0:
        return ""
    if _text_width(font, text) <= max_px:
        return text
    ellipsis = "…"
    if _text_width(font, ellipsis) > max_px:
        return ""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_width(font, text[:mid] + ellipsis) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ellipsis if lo < len(text) else text


def fit_path_label_to_width(font: pygame.font.Font, label: str, max_px: int) -> str:
    """Shorten a path for overlay width; keep the tail (subdir + filename)."""
    if not label or max_px <= 0:
        return ""
    if _text_width(font, label) <= max_px:
        return label
    prefix = "…"
    prefix_w = _text_width(font, prefix)
    if prefix_w > max_px:
        return fit_text_to_width(font, label, max_px)

    lo, hi = 0, len(label)
    best = prefix
    while lo <= hi:
        mid = (lo + hi) // 2
        start = max(0, len(label) - mid)
        slash_pos = label.find("/", start)
        if slash_pos != -1:
            start = slash_pos + 1
        candidate = prefix + label[start:]
        if _text_width(font, candidate) <= max_px:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def fit_counter_label_to_width(font: pygame.font.Font, label: str, max_px: int) -> str:
    """Shorten a path or filename to max_px; preserve a trailing ``(N/TOTAL)`` counter."""
    match = _COUNTER_SUFFIX.search(label)
    if match is None:
        return fit_path_label_to_width(font, label, max_px)
    head = label[: match.start()]
    suffix = match.group(0)
    suffix_w = _text_width(font, suffix)
    if suffix_w >= max_px:
        return fit_text_to_width(font, label, max_px)
    return fit_path_label_to_width(font, head, max_px - suffix_w) + suffix
