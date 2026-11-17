"""Blink timing for the timeline strip: REC, playhead, arm and selection flashes."""

from __future__ import annotations

import pygame

from cleave.viz.theme import palette

REC_FLASH_MS: int = 500
PLAYHEAD_FLASH_MS: int = 400
ARM_FLASH_HALF_MS: int = 150
ARM_FLASH_DURATION_MS: int = ARM_FLASH_HALF_MS * 4
# Selected-clip flash: same blink cadence as arm flash, two flashes.
SELECTED_CLIP_FLASH_HALF_MS: int = ARM_FLASH_HALF_MS
SELECTED_CLIP_FLASH_DURATION_MS: int = SELECTED_CLIP_FLASH_HALF_MS * 4


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
        return palette().playhead_flash
    return palette().playhead


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
    """True on the yellow (highlight) half of the selected-cue blink cycle."""
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
    """Selected clip outline: the highlight once settled; the flash pulses it
    with the armed red."""
    if selected_clip_flash_bright(flash_start_ms, ticks_ms=ticks_ms):
        return palette().highlight
    if selected_clip_flash_active(flash_start_ms, ticks_ms=ticks_ms):
        return palette().armed_bg
    return palette().highlight


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
