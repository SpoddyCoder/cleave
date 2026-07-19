"""Tests for cleave.viz.key_repeat."""

from __future__ import annotations

import pygame

from cleave.viz.key_repeat import (
    ACCEL_AFTER_SEC,
    FAST_INTERVAL_SEC,
    INITIAL_DELAY_SEC,
    SLOW_INTERVAL_SEC,
    KeyRepeatController,
    add_current_preset_key_pressed,
    delete_key_pressed,
)


def _arm(controller: KeyRepeatController, repeats: list[tuple[int, int]]) -> None:
    controller.on_keydown(
        pygame.K_RIGHT,
        0,
        on_repeat=lambda key, mod: repeats.append((key, mod)),
    )


def test_no_repeat_before_initial_delay() -> None:
    controller = KeyRepeatController()
    repeats: list[tuple[int, int]] = []
    _arm(controller, repeats)

    controller.tick(INITIAL_DELAY_SEC - 0.01)
    assert repeats == []


def test_first_repeat_at_delay_boundary() -> None:
    controller = KeyRepeatController()
    repeats: list[tuple[int, int]] = []
    _arm(controller, repeats)

    controller.tick(INITIAL_DELAY_SEC)
    assert repeats == [(pygame.K_RIGHT, 0)]


def test_slow_then_fast_interval_after_accel() -> None:
    slow_ctrl = KeyRepeatController()
    slow_repeats: list[tuple[int, int]] = []
    _arm(slow_ctrl, slow_repeats)
    slow_ctrl.tick(INITIAL_DELAY_SEC)
    slow_ctrl.tick(SLOW_INTERVAL_SEC)
    assert len(slow_repeats) == 2
    slow_ctrl.tick(SLOW_INTERVAL_SEC * 0.99)
    assert len(slow_repeats) == 2
    slow_ctrl.tick(SLOW_INTERVAL_SEC * 0.01)
    assert len(slow_repeats) == 3

    fast_ctrl = KeyRepeatController()
    fast_repeats: list[tuple[int, int]] = []
    _arm(fast_ctrl, fast_repeats)
    fast_ctrl.tick(INITIAL_DELAY_SEC)
    held = INITIAL_DELAY_SEC
    n_slow = int((ACCEL_AFTER_SEC - INITIAL_DELAY_SEC) / SLOW_INTERVAL_SEC)
    for _ in range(n_slow):
        fast_ctrl.tick(SLOW_INTERVAL_SEC)
        held += SLOW_INTERVAL_SEC
    fast_ctrl.tick(ACCEL_AFTER_SEC - held + 0.001)
    count_at_accel = len(fast_repeats)
    fast_ctrl.tick(FAST_INTERVAL_SEC * 0.5)
    assert len(fast_repeats) == count_at_accel
    fast_ctrl.tick(FAST_INTERVAL_SEC * 0.5)
    assert len(fast_repeats) > count_at_accel


def test_on_keyup_disarms() -> None:
    controller = KeyRepeatController()
    repeats: list[tuple[int, int]] = []
    _arm(controller, repeats)

    controller.on_keyup(pygame.K_RIGHT)
    controller.tick(INITIAL_DELAY_SEC + 1.0)
    assert repeats == []


def test_is_armed_while_held() -> None:
    controller = KeyRepeatController()
    assert controller.is_armed is False
    _arm(controller, [])
    assert controller.is_armed is True
    controller.on_keyup(pygame.K_RIGHT)
    assert controller.is_armed is False


def test_up_down_keys_arm_repeat() -> None:
    for key in (pygame.K_UP, pygame.K_DOWN):
        controller = KeyRepeatController()
        repeats: list[tuple[int, int]] = []
        controller.on_keydown(
            key,
            0,
            accel=False,
            on_repeat=lambda k, mod: repeats.append((k, mod)),
        )
        controller.tick(INITIAL_DELAY_SEC)
        assert repeats == [(key, 0)]


def test_navigation_repeat_stays_at_constant_interval() -> None:
    controller = KeyRepeatController()
    repeats: list[tuple[int, int]] = []
    controller.on_keydown(
        pygame.K_DOWN,
        0,
        accel=False,
        on_repeat=lambda key, mod: repeats.append((key, mod)),
    )
    controller.tick(INITIAL_DELAY_SEC)
    held = INITIAL_DELAY_SEC
    n_slow = int((ACCEL_AFTER_SEC - INITIAL_DELAY_SEC) / SLOW_INTERVAL_SEC)
    for _ in range(n_slow):
        controller.tick(SLOW_INTERVAL_SEC)
        held += SLOW_INTERVAL_SEC
    controller.tick(ACCEL_AFTER_SEC - held + 0.001)
    count_before = len(repeats)
    controller.tick(FAST_INTERVAL_SEC)
    assert len(repeats) == count_before
    controller.tick(SLOW_INTERVAL_SEC - FAST_INTERVAL_SEC)
    assert len(repeats) == count_before + 1


def test_delete_key_pressed_matches_keysym_and_scancode() -> None:
    keysym = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DELETE, scancode=0)
    assert delete_key_pressed(keysym) is True

    scancode = pygame.event.Event(
        pygame.KEYDOWN,
        key=0,
        scancode=pygame.KSCAN_DELETE,
    )
    assert delete_key_pressed(scancode) is True

    backspace = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, scancode=0)
    assert delete_key_pressed(backspace) is False


def test_add_current_preset_key_pressed() -> None:
    assert add_current_preset_key_pressed(pygame.K_u, 0)
    assert not add_current_preset_key_pressed(pygame.K_PLUS, 0)
    assert not add_current_preset_key_pressed(pygame.K_KP_PLUS, 0)
    assert not add_current_preset_key_pressed(
        pygame.K_EQUALS, pygame.KMOD_SHIFT
    )
