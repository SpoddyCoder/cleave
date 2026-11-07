"""Caret and draft editing shared by the text modal and inline fields."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import pygame


class TextEditing(Protocol):
    """State the editing helpers read and write."""

    draft: str
    caret_index: int
    editing: bool
    error: str | None
    caret_blink_sec: float


def text_field_lines(
    draft: str,
    *,
    single_line: bool,
    wrap: Callable[[str], list[str]] | None = None,
) -> list[str]:
    """Visual lines for caret movement: wrap when provided, else ``split("\\n")``."""
    if single_line:
        return [draft]
    if wrap is not None:
        lines = wrap(draft)
        return lines if lines else [""]
    return draft.split("\n")


def caret_line_column(
    text: str, lines: list[str], caret_index: int
) -> tuple[int, int]:
    """Map caret_index in *text* to (line, column) in wrapped *lines*.

    Hard newlines sit at the end of the preceding visual line. Spaces dropped
    at wrap points sit at the end of the line before the wrap.
    """
    caret_index = max(0, min(caret_index, len(text)))
    if not lines:
        return 0, 0
    if not text:
        return 0, 0

    src = 0
    last_i = len(lines) - 1
    for line_i, line in enumerate(lines):
        if not line:
            if caret_index <= src:
                return line_i, 0
            if src < len(text) and text[src] == "\n":
                src += 1
                continue
            return line_i, 0

        while (
            src < len(text)
            and text[src].isspace()
            and text[src] != "\n"
            and not text.startswith(line, src)
        ):
            if caret_index == src:
                return line_i, 0
            src += 1

        line_start = src
        if text.startswith(line, src):
            src += len(line)
        else:
            found = text.find(line, src)
            newline = text.find("\n", src)
            if found >= 0 and (newline < 0 or found <= newline):
                line_start = found
                src = found + len(line)
            else:
                src = min(len(text), src + len(line))
        line_end = src

        if line_start <= caret_index <= line_end:
            return line_i, caret_index - line_start

        trail = src
        while (
            trail < len(text)
            and text[trail].isspace()
            and text[trail] != "\n"
        ):
            trail += 1
        if line_end < caret_index < trail:
            return line_i, len(line)

        src = trail
        if src < len(text) and text[src] == "\n":
            if caret_index == src:
                return line_i, len(line)
            src += 1

    return last_i, len(lines[last_i])


def caret_index_for_line_column(
    text: str, lines: list[str], line: int, column: int
) -> int:
    """Source index for *column* on visual *line* in wrapped *lines*."""
    if not lines:
        return 0
    line = max(0, min(line, len(lines) - 1))
    src = 0
    for line_i, line_text in enumerate(lines):
        if not line_text:
            if line_i == line:
                return src
            if src < len(text) and text[src] == "\n":
                src += 1
            continue

        while (
            src < len(text)
            and text[src].isspace()
            and text[src] != "\n"
            and not text.startswith(line_text, src)
        ):
            src += 1

        line_start = src
        if text.startswith(line_text, src):
            src += len(line_text)
        else:
            found = text.find(line_text, src)
            newline = text.find("\n", src)
            if found >= 0 and (newline < 0 or found <= newline):
                line_start = found
                src = found + len(line_text)
            else:
                src = min(len(text), src + len(line_text))
        line_end = src

        if line_i == line:
            return min(line_start + max(0, column), line_end)

        trail = src
        while (
            trail < len(text)
            and text[trail].isspace()
            and text[trail] != "\n"
        ):
            trail += 1
        src = trail
        if src < len(text) and text[src] == "\n":
            src += 1

    return len(text)


def move_caret_vertical(
    state: TextEditing,
    delta: int,
    wrap: Callable[[str], list[str]] | None,
) -> None:
    if state.single_line:
        return
    lines = text_field_lines(state.draft, single_line=False, wrap=wrap)
    line, column = caret_line_column(state.draft, lines, state.caret_index)
    target = line + delta
    if target < 0 or target >= len(lines):
        return
    dest_col = min(column, len(lines[target]))
    state.caret_index = caret_index_for_line_column(
        state.draft, lines, target, dest_col
    )


TEXT_EDIT_REPEAT_KEYS = frozenset(
    {
        pygame.K_LEFT,
        pygame.K_RIGHT,
        pygame.K_UP,
        pygame.K_DOWN,
        pygame.K_BACKSPACE,
    }
)


_CARET_BLINK_CYCLE_SEC = 1.0


_CARET_BLINK_VISIBLE_SEC = 0.5


def reset_caret_blink(state: TextEditing) -> None:
    state.caret_blink_sec = 0.0


def text_caret_visible(state: TextEditing) -> bool:
    if not state.editing:
        return False
    return (state.caret_blink_sec % _CARET_BLINK_CYCLE_SEC) < _CARET_BLINK_VISIBLE_SEC


def insert_text_at_caret(state: TextEditing, text: str) -> None:
    caret = state.caret_index
    state.draft = state.draft[:caret] + text + state.draft[caret:]
    state.caret_index = caret + len(text)
    state.error = None
    reset_caret_blink(state)


def apply_text_edit_key(
    state: TextEditing,
    key: int,
    wrap: Callable[[str], list[str]] | None = None,
) -> None:
    reset_caret_blink(state)
    if key == pygame.K_BACKSPACE:
        if state.caret_index > 0:
            caret = state.caret_index
            state.draft = state.draft[:caret - 1] + state.draft[caret:]
            state.caret_index = caret - 1
            state.error = None
        return
    if key == pygame.K_LEFT:
        state.caret_index = max(0, state.caret_index - 1)
        return
    if key == pygame.K_RIGHT:
        state.caret_index = min(len(state.draft), state.caret_index + 1)
        return
    if key == pygame.K_UP:
        move_caret_vertical(state, -1, wrap)
        return
    if key == pygame.K_DOWN:
        move_caret_vertical(state, 1, wrap)

