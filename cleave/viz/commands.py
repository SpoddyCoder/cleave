"""Menu command registry for the live editor.

Static rows match the menu taxonomy. Layer jumps are built from a z-order
of ``(slot, stem_label)`` pairs so stem names stay with the project.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import pygame

from cleave.config_schema.layers import MAX_LAYER_COUNT
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.key_repeat import mod_ctrl
from cleave.viz.theme import ACTION, CONFIG_DIRTY

CommandKind = Literal["command", "jump", "check"]
LabelRole = tuple[int, int, int]

_PHASE1_SHORTCUT_IDS = frozenset(
    {
        "file.save",
        "file.quit",
        "project.render",
        "help.overlay",
    }
)


@dataclass(frozen=True)
class CommandContext:
    """Snapshot ``enabled``, ``checked``, and ``label_role`` read."""

    editor_mode: str = "visualizer"
    solo_slot: str | None = None
    config_dirty: bool = False
    render_busy: bool = False


def _disabled(_ctx: CommandContext) -> bool:
    return False


def _enabled(_ctx: CommandContext) -> bool:
    return True


def _noop(_controls: Any) -> None:
    return None


@dataclass(frozen=True)
class Command:
    id: str
    label: str
    kind: CommandKind
    shortcut: str | None = None
    enabled: Callable[[CommandContext], bool] = _enabled
    run: Callable[[Any], None] = _noop
    checked: Callable[[CommandContext], bool] | None = None
    label_role: Callable[[CommandContext], LabelRole] | None = None


class MenuSeparator:
    """Visual break between menu items."""


SEPARATOR = MenuSeparator()
MenuItem = Command | MenuSeparator


@dataclass(frozen=True)
class Menu:
    label: str
    items: tuple[MenuItem, ...]


def command_context(controls: Any) -> CommandContext:
    """Read the fields menu predicates need from tuning controls."""
    session = controls.session
    return CommandContext(
        editor_mode=session.settings.editor_mode,
        solo_slot=session.solo_slot,
        config_dirty=bool(controls.config_dirty),
        render_busy=bool(controls.project_render.busy),
    )


def _unchecked(_ctx: CommandContext) -> bool:
    return False


def _later(
    command_id: str,
    label: str,
    kind: CommandKind,
    shortcut: str | None = None,
) -> Command:
    return Command(
        id=command_id,
        label=label,
        kind=kind,
        shortcut=shortcut,
        enabled=_disabled,
        run=_noop,
        checked=_unchecked if kind == "check" else None,
    )


def _when_enabled(
    enabled: Callable[[CommandContext], bool],
    action: Callable[[Any], None],
) -> Callable[[Any], None]:
    def run(controls: Any) -> None:
        if not enabled(command_context(controls)):
            return
        action(controls)

    return run


def _save_enabled(ctx: CommandContext) -> bool:
    return not is_preset_curation_mode(ctx.editor_mode) and ctx.solo_slot is None


def _save_label_role(ctx: CommandContext) -> LabelRole:
    if ctx.config_dirty:
        return CONFIG_DIRTY
    return ACTION


def _render_enabled(ctx: CommandContext) -> bool:
    return not is_preset_curation_mode(ctx.editor_mode) and not ctx.render_busy


def _run_save(controls: Any) -> None:
    controls.prompt_save_config()


def _run_quit(controls: Any) -> None:
    controls.request_quit()


def _run_render(controls: Any) -> None:
    controls.project_render.prompt()


def _curation_checked(ctx: CommandContext) -> bool:
    return is_preset_curation_mode(ctx.editor_mode)


def _run_curation(controls: Any) -> None:
    controls.editor_mode.prompt_change_editor_mode()


def _run_measure_latency(controls: Any) -> None:
    controls.tap_sync.prompt_start()


def _toggle_help(controls: Any) -> None:
    session = controls.session
    session.help_visible = not session.help_visible


_OPEN = _later("file.open", "Open project...", "command", "Ctrl+O")
_SAVE = Command(
    id="file.save",
    label="Save",
    kind="command",
    shortcut="Ctrl+S",
    enabled=_save_enabled,
    run=_when_enabled(_save_enabled, _run_save),
    label_role=_save_label_role,
)
_QUIT = Command(
    id="file.quit",
    label="Quit",
    kind="command",
    shortcut="Ctrl+Q",
    enabled=_enabled,
    run=_run_quit,
)

_PROJECT_SETTINGS = _later("project.settings", "Project settings", "jump")
_SEPARATE = _later("project.separate", "Separate stems...", "command")
_RENDER = Command(
    id="project.render",
    label="Render project...",
    kind="command",
    shortcut="Ctrl+R",
    enabled=_render_enabled,
    run=_when_enabled(_render_enabled, _run_render),
)
_BACKUP = _later("project.backup", "Backup...", "command")
_RESTORE = _later("project.restore", "Restore...", "command")

_ADD = _later("layers.add", "Add layer", "command", "Ctrl+L")
_DELETE = _later("layers.delete", "Delete layer", "command")
_CURATION = Command(
    id="layers.preset_curation",
    label="Preset curation mode",
    kind="check",
    enabled=_enabled,
    run=_run_curation,
    checked=_curation_checked,
)

_OVERLAYS = _later("render.overlays", "Overlays", "check")
_POST_FX = _later("render.post_fx", "Post-FX", "check")
_PATTERN_MASK = _later("render.pattern_mask", "Pattern mask", "check")
_EDIT_OVERLAYS = _later("render.edit_overlays", "Edit overlays", "jump")
_EDIT_POST_FX = _later("render.edit_post_fx", "Edit post-FX", "jump")

_SHOW_STRIP = _later("timeline.show_strip", "Show timeline strip", "check", "T")
_APPLY_PRESET = _later("timeline.apply_preset", "Apply timeline preset", "command")
_RESET = _later("timeline.reset", "Reset timeline", "command")
_SNAP = _later("timeline.snap_cues", "Snap cues", "command")
_UNDO_CUT = _later("timeline.undo_cut", "Undo last cut", "command")
_SONG_MARKERS = _later("timeline.song_markers", "Song markers", "jump")

_EDITOR = _later("settings.editor", "Editor settings", "jump", "Ctrl+,")
_MEASURE_LATENCY = Command(
    id="settings.measure_latency",
    label="Measure latency...",
    kind="command",
    enabled=_enabled,
    run=_run_measure_latency,
)

_HELP_OVERLAY = Command(
    id="help.overlay",
    label="Help overlay",
    kind="command",
    shortcut="H",
    enabled=_enabled,
    run=_toggle_help,
)
_HELP_SHORTCUTS = Command(
    id="help.shortcuts",
    label="Keyboard shortcuts",
    kind="command",
    enabled=_enabled,
    run=_toggle_help,
)
_ABOUT = _later("help.about", "About Cleave", "command")

_STATIC_COMMANDS: tuple[Command, ...] = (
    _OPEN,
    _SAVE,
    _QUIT,
    _PROJECT_SETTINGS,
    _SEPARATE,
    _RENDER,
    _BACKUP,
    _RESTORE,
    _ADD,
    _DELETE,
    _CURATION,
    _OVERLAYS,
    _POST_FX,
    _PATTERN_MASK,
    _EDIT_OVERLAYS,
    _EDIT_POST_FX,
    _SHOW_STRIP,
    _APPLY_PRESET,
    _RESET,
    _SNAP,
    _UNDO_CUT,
    _SONG_MARKERS,
    _EDITOR,
    _MEASURE_LATENCY,
    _HELP_OVERLAY,
    _HELP_SHORTCUTS,
    _ABOUT,
)

_SHORTCUT_KEYS: dict[str, tuple[int, bool]] = {
    "Ctrl+O": (pygame.K_o, True),
    "Ctrl+S": (pygame.K_s, True),
    "Ctrl+Q": (pygame.K_q, True),
    "Ctrl+L": (pygame.K_l, True),
    "Ctrl+R": (pygame.K_r, True),
    "Ctrl+,": (pygame.K_COMMA, True),
    "T": (pygame.K_t, False),
    "H": (pygame.K_h, False),
    "1": (pygame.K_1, False),
    "2": (pygame.K_2, False),
    "3": (pygame.K_3, False),
    "4": (pygame.K_4, False),
    "5": (pygame.K_5, False),
    "6": (pygame.K_6, False),
    "7": (pygame.K_7, False),
    "8": (pygame.K_8, False),
}


def layer_focus_commands(
    slots: Sequence[tuple[str, str]],
) -> tuple[Command, ...]:
    """Disabled Layers jumps in z-order.

    ``slots`` is ``(slot, stem_label)``. ``stem_label`` is shown as given.
    Shortcuts are ``1`` through ``8``; later rows keep no shortcut.
    """
    commands: list[Command] = []
    for index, (slot, stem_label) in enumerate(slots):
        number = index + 1
        shortcut = str(number) if number <= MAX_LAYER_COUNT else None
        commands.append(
            Command(
                id=f"layers.focus.{slot}",
                label=f"Layer {number}  {stem_label}",
                kind="jump",
                shortcut=shortcut,
                enabled=_disabled,
                run=_noop,
            )
        )
    return tuple(commands)


def build_menus(
    layer_slots: Sequence[tuple[str, str]] = (),
) -> tuple[Menu, ...]:
    """Full menu bar. Layer jumps occupy the slot between the two Layers separators."""
    jumps = layer_focus_commands(layer_slots)
    return (
        Menu("File", (_OPEN, _SAVE, SEPARATOR, _QUIT)),
        Menu(
            "Project",
            (
                _PROJECT_SETTINGS,
                SEPARATOR,
                _SEPARATE,
                _RENDER,
                SEPARATOR,
                _BACKUP,
                _RESTORE,
            ),
        ),
        Menu(
            "Layers",
            (_ADD, _DELETE, SEPARATOR, *jumps, SEPARATOR, _CURATION),
        ),
        Menu(
            "Render",
            (
                _OVERLAYS,
                _POST_FX,
                _PATTERN_MASK,
                SEPARATOR,
                _EDIT_OVERLAYS,
                _EDIT_POST_FX,
            ),
        ),
        Menu(
            "Timeline",
            (
                _SHOW_STRIP,
                SEPARATOR,
                _APPLY_PRESET,
                _RESET,
                _SNAP,
                _UNDO_CUT,
                SEPARATOR,
                _SONG_MARKERS,
            ),
        ),
        Menu("Settings", (_EDITOR, _MEASURE_LATENCY)),
        Menu("Help", (_HELP_OVERLAY, _HELP_SHORTCUTS, SEPARATOR, _ABOUT)),
    )


MENUS: tuple[Menu, ...] = build_menus()


def iter_commands(menus: Sequence[Menu]) -> Iterator[Command]:
    for menu in menus:
        for item in menu.items:
            if isinstance(item, Command):
                yield item


def command_by_id(
    command_id: str,
    menus: Sequence[Menu] | None = None,
) -> Command:
    source = MENUS if menus is None else menus
    for command in iter_commands(source):
        if command.id == command_id:
            return command
    raise KeyError(command_id)


def command_for_shortcut(key: int, mod: int) -> Command | None:
    """Phase-1 shortcut, or None.

    Save, quit, render, and the help overlay resolve. Other shortcut text
    stays on its row. Bare R does not resolve.
    """
    ctrl = mod_ctrl(mod)
    for command in _STATIC_COMMANDS:
        if command.id not in _PHASE1_SHORTCUT_IDS or command.shortcut is None:
            continue
        mapped = _SHORTCUT_KEYS.get(command.shortcut)
        if mapped is None:
            continue
        want_key, want_ctrl = mapped
        if key == want_key and ctrl == want_ctrl:
            return command
    return None
