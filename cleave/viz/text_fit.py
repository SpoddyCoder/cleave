"""Text fitting helpers for overlay labels."""

from __future__ import annotations

import re

import pygame

# Playlist counter and/or curation markers after a filename or path.
# Counter: " (N/TOTAL)". Markers: " [F]", " [B]", or " [F][B]".
_META_SUFFIX = re.compile(
    r"(?: \((\d+)/(\d+)\))(?: \[F\](?:\[B\])?| \[B\])?$"
    r"|"
    r"(?: \[F\](?:\[B\])?| \[B\])$"
)


_SENTENCE_END = frozenset(".?!")


def _text_width(font: pygame.font.Font, text: str) -> int:
    return font.size(text)[0]


def _max_prefix_len(font: pygame.font.Font, text: str, max_px: int) -> int:
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_width(font, text[:mid]) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _preferred_wrap_break(chunk: str) -> int:
    """Index to end the line; prefer sentence endings, then spaces."""
    for i in range(len(chunk) - 1, 0, -1):
        if chunk[i - 1] in _SENTENCE_END and chunk[i].isspace():
            return i
    if chunk[-1] in _SENTENCE_END:
        return len(chunk)
    space = chunk.rfind(" ")
    if space > 0:
        return space
    return len(chunk)


def wrap_text_to_width(
    font: pygame.font.Font, text: str, max_px: int
) -> list[str]:
    """Wrap text to max_px; prefer breaks after sentence endings, then spaces."""
    if not text:
        return []
    if max_px <= 0 or _text_width(font, text) <= max_px:
        return [text]

    lines: list[str] = []
    remaining = text
    while remaining:
        if _text_width(font, remaining) <= max_px:
            lines.append(remaining)
            break
        fit_len = _max_prefix_len(font, remaining, max_px)
        if fit_len <= 0:
            lines.append(remaining[0])
            remaining = remaining[1:]
            continue
        break_at = _preferred_wrap_break(remaining[:fit_len])
        if break_at <= 0:
            break_at = fit_len
        line = remaining[:break_at].rstrip()
        remaining = remaining[break_at:].lstrip()
        if line:
            lines.append(line)
        elif remaining:
            lines.append(remaining[0])
            remaining = remaining[1:]
    return lines


def _split_meta_suffix(label: str) -> tuple[str, str]:
    """Split ``head`` from trailing `` (N/TOTAL)`` and/or `` [F]``/`` [B]``."""
    match = _META_SUFFIX.search(label)
    if match is None:
        return label, ""
    return label[: match.start()], match.group(0)


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


def _fit_label_head(font: pygame.font.Font, head: str, max_px: int) -> str:
    """Fit the non-meta head: path-style when it contains ``/``, else keep the start."""
    if "/" in head:
        return fit_path_label_to_width(font, head, max_px)
    return fit_text_to_width(font, head, max_px)


def fit_counter_label_to_width(font: pygame.font.Font, label: str, max_px: int) -> str:
    """Shorten a path or filename to max_px; preserve counter and curation markers."""
    head, suffix = _split_meta_suffix(label)
    if not suffix:
        return _fit_label_head(font, label, max_px)
    suffix_w = _text_width(font, suffix)
    head_budget = max_px - suffix_w
    if head_budget <= 0:
        return suffix
    return _fit_label_head(font, head, head_budget) + suffix
