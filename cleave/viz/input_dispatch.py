"""Layered keyboard dispatch for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.controls import TuningControls
from cleave.viz.key_repeat import mod_ctrl
from cleave.viz.timeline_controls import TimelineControls

if TYPE_CHECKING:
    from cleave.viz.app import VisualizerRuntime


def timeline_submenu_routes_to_timeline(
    tl,
    *,
    timeline_controls: TimelineControls | None,
    key: int,
) -> bool:
    """True when the key should route to timeline controls (submenu focused)."""
    return (
        tl.panel_open
        and tl.enabled
        and tl.submenu_focused
        and timeline_controls is not None
        and key not in (pygame.K_UP, pygame.K_DOWN)
    )


def key_handler_for_runtime(
    runtime: VisualizerRuntime, key: int
) -> TuningControls | TimelineControls:
    """Pick the context handler for a key (tests and dispatch)."""
    tl = runtime.session.timeline
    if timeline_submenu_routes_to_timeline(
        tl,
        timeline_controls=runtime.timeline_controls,
        key=key,
    ):
        assert runtime.timeline_controls is not None
        return runtime.timeline_controls
    assert runtime.controls is not None
    return runtime.controls


def _handle_global_keydown(
    event: pygame.event.Event, runtime: VisualizerRuntime
) -> bool | None:
    """Global shortcuts. True = handled, False = quit, None = pass through."""
    if event.key == pygame.K_q and mod_ctrl(event.mod):
        return False

    if event.key == pygame.K_h:
        runtime.session.help_visible = not runtime.session.help_visible
        return True

    tl = runtime.session.timeline
    if tl.recording:
        if event.key == pygame.K_ESCAPE:
            assert runtime.timeline_controls is not None
            runtime.timeline_controls.stop_recording()
            return True
        if event.key == pygame.K_t:
            return True

    return None


def dispatch_keydown(event: pygame.event.Event, runtime: VisualizerRuntime) -> bool:
    """Handle a key-down event. Return False when the app should quit."""
    if event.type != pygame.KEYDOWN:
        return True

    global_result = _handle_global_keydown(event, runtime)
    if global_result is not None:
        return global_result

    assert runtime.controls is not None
    if runtime.controls.handle_modal_keydown(event):
        return True

    key_handler = key_handler_for_runtime(runtime, event.key)
    return key_handler.handle_keydown(event)


def dispatch_keyup(event: pygame.event.Event, runtime: VisualizerRuntime) -> None:
    if event.type != pygame.KEYUP:
        return
    key_handler = key_handler_for_runtime(runtime, event.key)
    key_handler.handle_keyup(event)


def dispatch_should_notify_overlay(
    event: pygame.event.Event, runtime: VisualizerRuntime
) -> bool:
    """Mirror VisualizerApp.run overlay fade-in on input."""
    if event.type != pygame.KEYDOWN:
        return False
    tl = runtime.session.timeline
    key_handler = key_handler_for_runtime(runtime, event.key)
    if key_handler is not runtime.controls:
        return False
    return event.key != pygame.K_t and not tl.submenu_focused
