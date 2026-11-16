"""Blink timing for the timeline strip: REC, playhead, arm and selection flashes."""

from __future__ import annotations

import pygame

from cleave.viz.theme import ARMED_BG, HIGHLIGHT, PLAYHEAD, PLAYHEAD_FLASH

REC_FLASH_MS: int = 500
PLAYHEAD_FLASH_MS: int = 400
ARM_FLASH_HALF_MS: int = 150
ARM_FLASH_DURATION_MS: int = ARM_FLASH_HALF_MS * 4
# Selected-clip flash: same blink cadence as arm flash, two flashes.
SELECTED_CLIP_FLASH_HALF_MS: int = ARM_FLASH_HALF_MS
SELECTED_CLIP_FLASH_DURATION_MS: int = SELECTED_CLIP_FLASH_HALF_MS * 4
# Settled selected outline (HIGHLIGHT yellow); the flash pulses yellow/red.
SELECTED_CLIP_COLOR: tuple[int, int, int] = HIGHLIGHT
SELECTED_CLIP_FLASH_YELLOW: tuple[int, int, int] = HIGHLIGHT
SELECTED_CLIP_FLASH_RED: tuple[int, int, int] = ARMED_BG


def rec_flash_visible(ticks_ms: int | None = None) -> bool:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return (ticks_ms // REC_FLASH_MS) % 2 == 0


def playhead_flash_bright(ticks_ms: int | None = None) -> bool:
    """True on the bright half of the playhead blink cycle."""
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return (ticks_ms // PLAYHEAD_FLASH_MS) % 2 == 0


def playhead_color(ticks_ms: int | None = None) -> tuple[int, int, int]:
    if playhead_flash_bright(ticks_ms):
        return PLAYHEAD_FLASH
    return PLAYHEAD


def prune_expired_arm_flashes(
    flash_starts: dict[str, int],
    ticks_ms: int | None = None,
) -> None:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    expired = [
        slot
        for slot, start_ms in flash_starts.items()
        if ticks_ms - start_ms >= ARM_FLASH_DURATION_MS
    ]
    for slot in expired:
        flash_starts.pop(slot, None)


def prune_expired_selected_clip_flash(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> int | None:
    if flash_start_ms is None:
        return None
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    if ticks_ms - flash_start_ms >= SELECTED_CLIP_FLASH_DURATION_MS:
        return None
    return flash_start_ms


def arm_flash_active(
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    start_ms = flash_starts.get(slot)
    if start_ms is None:
        return False
    return ticks_ms - start_ms < ARM_FLASH_DURATION_MS


def arm_flash_visible(
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if not arm_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    start_ms = flash_starts[slot]
    elapsed = ticks_ms - start_ms
    return (elapsed // ARM_FLASH_HALF_MS) % 2 == 0


def selected_clip_flash_active(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> bool:
    if flash_start_ms is None:
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return ticks_ms - flash_start_ms < SELECTED_CLIP_FLASH_DURATION_MS


def selected_clip_flash_bright(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> bool:
    """True on the yellow (HIGHLIGHT) half of the selected-cue blink cycle."""
    if not selected_clip_flash_active(flash_start_ms, ticks_ms=ticks_ms):
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    assert flash_start_ms is not None
    elapsed = ticks_ms - flash_start_ms
    return (elapsed // SELECTED_CLIP_FLASH_HALF_MS) % 2 == 0


def selected_clip_flash_color(
    flash_start_ms: int | None,
    ticks_ms: int | None = None,
) -> tuple[int, int, int]:
    if selected_clip_flash_bright(flash_start_ms, ticks_ms=ticks_ms):
        return SELECTED_CLIP_FLASH_YELLOW
    if selected_clip_flash_active(flash_start_ms, ticks_ms=ticks_ms):
        return SELECTED_CLIP_FLASH_RED
    return SELECTED_CLIP_COLOR


def arm_button_lit(
    *,
    armed: bool,
    recording: bool,
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if arm_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return arm_flash_visible(flash_starts, slot, ticks_ms=ticks_ms)
    return armed and (not recording or rec_flash_visible(ticks_ms))
