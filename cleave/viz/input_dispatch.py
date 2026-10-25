"""Layered keyboard dispatch for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.commands import command_context, command_for_shortcut
from cleave.viz.controls import SEEK_LONG, SEEK_TINY, TuningControls
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.focus_nav import FocusCursor, TimelineFocus
from cleave.viz.key_repeat import delete_key_pressed, mod_alt, mod_ctrl, mod_shift
from cleave.viz.menu_bar import menu_index_for_mnemonic, menus_for_session
from cleave.viz.shell_focus import CycleStop, ShellRegion, next_region
from cleave.viz.timeline_controls import TimelineControls

if TYPE_CHECKING:
    from cleave.viz.app import LiveVisualizerRuntime


def timeline_submenu_routes_to_timeline(
    tl,
    *,
    timeline_controls: TimelineControls | None,
    focus_cursor: FocusCursor,
) -> bool:
    """True when keys should route to timeline controls (strip has scope)."""
    return (
        tl.panel_open
        and isinstance(focus_cursor, TimelineFocus)
        and timeline_controls is not None
    )


def key_handler_for_runtime(
    runtime: LiveVisualizerRuntime, key: int
) -> TuningControls | TimelineControls:
    """Pick the context handler for a key (tests and dispatch)."""
    tl = runtime.seed.session.timeline
    if timeline_submenu_routes_to_timeline(
        tl,
        timeline_controls=runtime.timeline_controls,
        focus_cursor=runtime.controls.focus_cursor,
    ):
        return runtime.timeline_controls
    return runtime.controls


def _global_seek(
    runtime: LiveVisualizerRuntime, forward: bool, *, long: bool, tiny: bool
) -> None:
    timeline_controls = runtime.timeline_controls
    if timeline_controls is not None:
        timeline_controls.seek_step(forward, long=long, tiny=tiny)
        return
    delta_sec = SEEK_LONG if long else SEEK_TINY
    if not forward:
        delta_sec = -delta_sec
    runtime.controls.do_seek(delta_sec)


def _try_handle_global_seek(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool:
    if event.key not in (pygame.K_LEFT, pygame.K_RIGHT):
        return False
    long = mod_ctrl(event.mod)
    tiny = mod_shift(event.mod)
    if not long and not tiny:
        return False
    forward = event.key == pygame.K_RIGHT
    _global_seek(runtime, forward, long=long, tiny=tiny)
    key_handler = key_handler_for_runtime(runtime, event.key)
    key_handler.arm_key_repeat(
        event.key,
        event.mod,
        on_repeat=lambda key, mod: _global_seek(
            runtime,
            key == pygame.K_RIGHT,
            long=mod_ctrl(mod),
            tiny=mod_shift(mod),
        ),
    )
    return True


def _is_alt_key(key: int) -> bool:
    return key in (pygame.K_LALT, pygame.K_RALT)


def _run_command_shortcut(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool | None:
    """Resolved menu shortcuts. None when the key is not one of those.

    Quit returns False only when ``request_quit`` says leave now. The loop
    also reads ``consume_pending_exit`` for the menu Enter path. Digit jumps
    stay unresolved while the timeline strip has scope.
    """
    ctx = command_context(runtime.controls)
    command = command_for_shortcut(
        event.key,
        event.mod,
        menus_for_session(runtime.seed.session),
        timeline_scope=ctx.timeline_scope,
    )
    if command is None:
        return None
    command.run(runtime.controls)
    if runtime.controls.pending_exit:
        return False
    return True


def _handle_menu_bar_keydown(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool | None:
    """F10, Alt, Alt+letter mnemonics, and keys while the bar is focused.

    True = consumed, False = quit now, None = pass through.
    """
    menu = runtime.menu_bar
    if _is_alt_key(event.key):
        menu.note_alt_keydown()
        return True
    menu.cancel_alt_tap()
    if mod_alt(event.mod) and pygame.K_a <= event.key <= pygame.K_z:
        menus = menus_for_session(runtime.seed.session)
        letter = chr(ord("a") + (event.key - pygame.K_a))
        index = menu_index_for_mnemonic(menus, letter)
        if index is not None:
            menu.open_menu(index, menus)
            runtime.overlay.notify_input()
            return True
    if (
        menu.focused
        and event.key in (pygame.K_UP, pygame.K_DOWN)
        and mod_ctrl(event.mod)
    ):
        return True
    if event.key == pygame.K_F10:
        if menu.toggle_focus():
            runtime.overlay.notify_input()
        return True
    if not menu.focused:
        return None
    consumed = menu.handle_keydown(
        event.key,
        menus_for_session(runtime.seed.session),
        command_context(runtime.controls),
        runtime.controls,
    )
    if runtime.controls.pending_exit:
        return False
    if consumed:
        return True
    return None


def _handle_global_keydown(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool | None:
    """Global shortcuts. True = handled, False = quit, None = pass through."""
    if is_preset_curation_mode(runtime.seed.session.settings.editor_mode):
        if _try_handle_global_seek(event, runtime):
            return True
        # Skip other globals (F3, ...); pass through to curation allowlist.
        return None

    if event.key == pygame.K_RETURN and mod_ctrl(event.mod):
        if runtime.seed.session.timeline.recording:
            return True
        runtime.controls.song_markers.drop()
        return True

    if event.key == pygame.K_F3:
        runtime.overlay_profiler.toggle()
        state = "on" if runtime.overlay_profiler.enabled else "off"
        runtime.controls.show_notification(
            f"Overlay profiler {state} (see terminal; stats on panel when open)"
        )
        return True

    tl = runtime.seed.session.timeline
    if runtime.controls.tap_sync.active:
        if runtime.controls.tap_sync.handle_keydown(event):
            return True

    if _try_handle_global_seek(event, runtime):
        return True

    if tl.recording and event.key == pygame.K_ESCAPE:
        runtime.timeline_controls.stop_recording()
        return True

    return None


_CURATION_SHELL_SUPPRESSED = frozenset(
    {
        pygame.K_l,
        pygame.K_m,
        pygame.K_s,
        pygame.K_e,
        pygame.K_p,
        pygame.K_DELETE,
    }
)


_REGION_KEYS = frozenset(
    {
        pygame.K_UP,
        pygame.K_DOWN,
        pygame.K_LEFT,
        pygame.K_RIGHT,
        pygame.K_RETURN,
        pygame.K_KP_ENTER,
        pygame.K_ESCAPE,
        pygame.K_PAGEUP,
        pygame.K_PAGEDOWN,
    }
)


def _strip_open(runtime: LiveVisualizerRuntime) -> bool:
    return bool(runtime.seed.session.timeline.panel_open)


def _current_stop(runtime: LiveVisualizerRuntime) -> CycleStop:
    if runtime.menu_bar.focused:
        return CycleStop.MENU
    if _strip_has_scope(runtime):
        return CycleStop.TIMELINE
    if runtime.controls.shell_focus.region is ShellRegion.INSPECTOR:
        return CycleStop.INSPECTOR
    return CycleStop.NAVIGATOR


def _strip_has_scope(runtime: LiveVisualizerRuntime) -> bool:
    return _strip_open(runtime) and isinstance(
        runtime.controls.focus_cursor, TimelineFocus
    )


def _commit_cycle_stop(runtime: LiveVisualizerRuntime, stop: CycleStop) -> None:
    menu = runtime.menu_bar
    controls = runtime.controls
    if stop is CycleStop.MENU:
        menu.focus()
        return
    menu.blur()
    if stop is CycleStop.TIMELINE:
        if not isinstance(controls.focus_cursor, TimelineFocus):
            controls.open_timeline_panel(enter_submenu=True)
        return
    if isinstance(controls.focus_cursor, TimelineFocus):
        controls.exit_timeline_submenu()
    controls.shell_focus.region = (
        ShellRegion.INSPECTOR
        if stop is CycleStop.INSPECTOR
        else ShellRegion.NAVIGATOR
    )


def _handle_region_cycle(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool:
    """Tab / Shift+Tab. Runs before the menu bar so Tab blurs it."""
    if event.key != pygame.K_TAB:
        return False
    delta = -1 if mod_shift(event.mod) else 1
    stop = next_region(
        _current_stop(runtime),
        strip_open=_strip_open(runtime),
        delta=delta,
    )
    _commit_cycle_stop(runtime, stop)
    return True


def _handle_ctrl_section_nav(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool:
    """Ctrl+Up/Down across visible top-level navigator ids."""
    if event.key not in (pygame.K_UP, pygame.K_DOWN) or not mod_ctrl(event.mod):
        return False
    if runtime.menu_bar.focused:
        return False
    controls = runtime.controls
    if isinstance(controls.focus_cursor, TimelineFocus):
        controls.exit_timeline_submenu()
    delta = -1 if event.key == pygame.K_UP else 1
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    controls.navigator.quick_step(delta)
    return True


def _region_keydown(event: pygame.event.Event, runtime: LiveVisualizerRuntime) -> bool | None:
    """Navigator and inspector own arrows, Enter, Esc, and PageUp/PageDown.

    None means the key is unowned and should fall through. Timeline scope
    stays on ``key_handler_for_runtime``.
    """
    if event.key not in _REGION_KEYS:
        return None
    if runtime.menu_bar.focused:
        return None
    if _strip_has_scope(runtime):
        return None
    region = runtime.controls.shell_focus.region
    if region is ShellRegion.NAVIGATOR:
        if runtime.controls.navigator.handle_keydown(event):
            return True
        return None
    if region is ShellRegion.INSPECTOR:
        if runtime.controls.inspector.handle_keydown(event):
            return True
        return None
    return None


def _handle_shell_hotkey(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool:
    """Letter, Delete, and Backspace for the navigator or inspector."""
    if not _shell_columns_focused(runtime):
        return False
    if _curation_shell(runtime) and (
        event.key in _CURATION_SHELL_SUPPRESSED or delete_key_pressed(event)
    ):
        return True
    controls = runtime.controls
    region = controls.shell_focus.region
    if region is ShellRegion.INSPECTOR:
        return controls.inspector.handle_hotkey(event)
    if region is ShellRegion.NAVIGATOR:
        return controls.navigator.handle_hotkey(event)
    return False


def _shell_columns_focused(runtime: LiveVisualizerRuntime) -> bool:
    """Navigator or inspector has the shell, not the menu or the timeline strip."""
    if runtime.menu_bar.focused:
        return False
    if _strip_has_scope(runtime):
        return False
    return runtime.controls.shell_focus.region in (
        ShellRegion.NAVIGATOR,
        ShellRegion.INSPECTOR,
    )


def _curation_shell(runtime: LiveVisualizerRuntime) -> bool:
    return is_preset_curation_mode(
        runtime.seed.session.settings.editor_mode
    ) and _shell_columns_focused(runtime)


def dispatch_keydown(event: pygame.event.Event, runtime: LiveVisualizerRuntime) -> bool:
    """Handle a key-down event. Return False when the app should quit."""
    if event.type != pygame.KEYDOWN:
        return True

    if runtime.modal_host.active:
        runtime.menu_bar.cancel_alt_tap()
        return runtime.controls.handle_modal_keydown(event)

    if (
        not _curation_shell(runtime)
        and runtime.controls.handle_move_mode_keydown(event)
    ):
        return True

    if _handle_region_cycle(event, runtime):
        return True

    menu_result = _handle_menu_bar_keydown(event, runtime)
    if menu_result is not None:
        return menu_result

    shortcut_result = _run_command_shortcut(event, runtime)
    if shortcut_result is not None:
        return shortcut_result

    if _handle_ctrl_section_nav(event, runtime):
        return True

    global_result = _handle_global_keydown(event, runtime)
    if global_result is not None:
        return global_result

    region_result = _region_keydown(event, runtime)
    if region_result is not None:
        return region_result

    if _handle_shell_hotkey(event, runtime):
        return True

    key_handler = key_handler_for_runtime(runtime, event.key)
    return key_handler.handle_keydown(event)


def dispatch_keyup(event: pygame.event.Event, runtime: LiveVisualizerRuntime) -> None:
    if event.type != pygame.KEYUP:
        return
    if runtime.modal_host.active:
        runtime.menu_bar.cancel_alt_tap()
    elif _is_alt_key(event.key):
        if runtime.menu_bar.complete_alt_tap():
            runtime.overlay.notify_input()
        return
    if runtime.modal_host.handle_keyup(event):
        return
    key_handler = key_handler_for_runtime(runtime, event.key)
    key_handler.handle_keyup(event)


def dispatch_window_event(event: pygame.event.Event, runtime: LiveVisualizerRuntime) -> None:
    """Clear a pending Alt tap when the window loses focus."""
    if event.type == pygame.WINDOWFOCUSLOST:
        runtime.menu_bar.cancel_alt_tap()
        return
    if event.type == pygame.ACTIVEEVENT and not getattr(event, "gain", True):
        runtime.menu_bar.cancel_alt_tap()


def dispatch_should_notify_overlay(
    event: pygame.event.Event, runtime: LiveVisualizerRuntime
) -> bool:
    """Mirror VisualizerApp.run overlay fade-in on input."""
    if event.type != pygame.KEYDOWN:
        return False
    tl = runtime.seed.session.timeline
    key_handler = key_handler_for_runtime(runtime, event.key)
    if key_handler is not runtime.controls:
        return False
    return event.key != pygame.K_t and not isinstance(
        runtime.controls.focus_cursor, TimelineFocus
    )
