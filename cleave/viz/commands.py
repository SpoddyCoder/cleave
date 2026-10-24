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
from cleave.viz.focus_nav import TimelineFocus
from cleave.viz.key_repeat import mod_ctrl
from cleave.viz.navigator import LAYER_ID_PREFIX, layer_node_id
from cleave.viz.theme import ACTION, CONFIG_DIRTY

CommandKind = Literal["command", "jump", "check"]
LabelRole = tuple[int, int, int]

_RESOLVED_SHORTCUT_IDS = frozenset(
    {
        "file.save",
        "file.quit",
        "project.render",
        "help.overlay",
        "settings.editor",
        "layers.add",
    }
)


@dataclass(frozen=True)
class CommandContext:
    """Snapshot ``enabled``, ``checked``, and ``label_role`` read."""

    editor_mode: str = "visualizer"
    solo_slot: str | None = None
    config_dirty: bool = False
    render_busy: bool = False
    selected_slot: str | None = None
    can_add_layer: bool = False
    can_remove_layer: bool = False
    timeline_scope: bool = False
    overlays_enabled: bool = False
    post_fx_enabled: bool = False
    pattern_mask_enabled: bool = False
    overlays_locked: bool = False
    post_fx_locked: bool = False
    pattern_mask_locked: bool = False


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
    selected = controls.shell_focus.selected_id
    selected_slot = None
    if isinstance(selected, str) and selected.startswith(LAYER_ID_PREFIX):
        selected_slot = selected[len(LAYER_ID_PREFIX) :]
    lifecycle = controls.layer_lifecycle
    timeline_scope = isinstance(controls.focus_cursor, TimelineFocus) or bool(
        session.timeline.recording
    )
    overlays = session.render_overlays
    post_fx = session.render_post_fx
    pattern_mask = session.render_pattern_mask
    return CommandContext(
        editor_mode=session.settings.editor_mode,
        solo_slot=session.solo_slot,
        config_dirty=bool(controls.config_dirty),
        render_busy=bool(controls.project_render.busy),
        selected_slot=selected_slot,
        can_add_layer=lifecycle.can_add(),
        can_remove_layer=lifecycle.can_remove(),
        timeline_scope=timeline_scope,
        overlays_enabled=bool(
            overlays.opening_card.enabled or overlays.closing_card.enabled
        ),
        post_fx_enabled=bool(post_fx.enabled),
        pattern_mask_enabled=bool(pattern_mask.enabled),
        overlays_locked=bool(overlays.locked),
        post_fx_locked=bool(post_fx.locked),
        pattern_mask_locked=bool(pattern_mask.locked),
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


def _add_enabled(ctx: CommandContext) -> bool:
    return ctx.can_add_layer and not is_preset_curation_mode(ctx.editor_mode)


def _delete_enabled(ctx: CommandContext) -> bool:
    return (
        ctx.selected_slot is not None
        and ctx.can_remove_layer
        and not is_preset_curation_mode(ctx.editor_mode)
    )


def _run_add(controls: Any) -> None:
    controls.layer_lifecycle.prompt_add()


def _run_delete(controls: Any) -> None:
    slot = command_context(controls).selected_slot
    if slot is None:
        return
    controls.layer_lifecycle.prompt_delete(slot)


def _render_block_menu_enabled(locked: bool, editor_mode: str) -> bool:
    return not locked and not is_preset_curation_mode(editor_mode)


def _overlays_menu_enabled(ctx: CommandContext) -> bool:
    return _render_block_menu_enabled(ctx.overlays_locked, ctx.editor_mode)


def _post_fx_menu_enabled(ctx: CommandContext) -> bool:
    return _render_block_menu_enabled(ctx.post_fx_locked, ctx.editor_mode)


def _pattern_mask_menu_enabled(ctx: CommandContext) -> bool:
    return _render_block_menu_enabled(ctx.pattern_mask_locked, ctx.editor_mode)


def _render_jump_enabled(ctx: CommandContext) -> bool:
    return not is_preset_curation_mode(ctx.editor_mode)


def _overlays_checked(ctx: CommandContext) -> bool:
    return ctx.overlays_enabled


def _post_fx_checked(ctx: CommandContext) -> bool:
    return ctx.post_fx_enabled


def _pattern_mask_checked(ctx: CommandContext) -> bool:
    return ctx.pattern_mask_enabled


def _run_toggle_enabled(node_id: str) -> Callable[[Any], None]:
    def run(controls: Any) -> None:
        from cleave.viz.row_hotkeys import node_header_descriptor
        from cleave.viz.row_spec import apply_field_toggle_enabled

        descriptor = node_header_descriptor(node_id)
        if descriptor is None:
            return
        apply_field_toggle_enabled(controls, descriptor)

    return run


def _run_focus_node(node_id: str) -> Callable[[Any], None]:
    """Select a navigator node and focus its inspector."""

    def run(controls: Any) -> None:
        controls.navigator.select(node_id)
        controls.navigator.activate()

    return run


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

_PROJECT_SETTINGS = Command(
    id="project.settings",
    label="Project settings",
    kind="jump",
    enabled=_enabled,
    run=_run_focus_node("project"),
)
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

_ADD = Command(
    id="layers.add",
    label="Add layer",
    kind="command",
    shortcut="Ctrl+L",
    enabled=_add_enabled,
    run=_when_enabled(_add_enabled, _run_add),
)
_DELETE = Command(
    id="layers.delete",
    label="Delete layer",
    kind="command",
    enabled=_delete_enabled,
    run=_when_enabled(_delete_enabled, _run_delete),
)
_CURATION = Command(
    id="layers.preset_curation",
    label="Preset curation mode",
    kind="check",
    enabled=_enabled,
    run=_run_curation,
    checked=_curation_checked,
)

_OVERLAYS = Command(
    id="render.overlays",
    label="Overlays",
    kind="check",
    enabled=_overlays_menu_enabled,
    run=_when_enabled(_overlays_menu_enabled, _run_toggle_enabled("render.overlays")),
    checked=_overlays_checked,
)
_POST_FX = Command(
    id="render.post_fx",
    label="Post-FX",
    kind="check",
    enabled=_post_fx_menu_enabled,
    run=_when_enabled(_post_fx_menu_enabled, _run_toggle_enabled("render.post_fx")),
    checked=_post_fx_checked,
)
_PATTERN_MASK = Command(
    id="render.pattern_mask",
    label="Pattern mask",
    kind="check",
    enabled=_pattern_mask_menu_enabled,
    run=_when_enabled(
        _pattern_mask_menu_enabled, _run_toggle_enabled("render.pattern_mask")
    ),
    checked=_pattern_mask_checked,
)
_EDIT_OVERLAYS = Command(
    id="render.edit_overlays",
    label="Edit overlays",
    kind="jump",
    enabled=_render_jump_enabled,
    run=_when_enabled(_render_jump_enabled, _run_focus_node("render.overlays")),
)
_EDIT_POST_FX = Command(
    id="render.edit_post_fx",
    label="Edit post-FX",
    kind="jump",
    enabled=_render_jump_enabled,
    run=_when_enabled(_render_jump_enabled, _run_focus_node("render.post_fx")),
)

_SHOW_STRIP = _later("timeline.show_strip", "Show timeline strip", "check", "T")
_APPLY_PRESET = _later("timeline.apply_preset", "Apply timeline preset", "command")
_RESET = _later("timeline.reset", "Reset timeline", "command")
_SNAP = _later("timeline.snap_cues", "Snap cues", "command")
_UNDO_CUT = _later("timeline.undo_cut", "Undo last cut", "command")
_SONG_MARKERS = _later("timeline.song_markers", "Song markers", "jump")

_EDITOR = Command(
    id="settings.editor",
    label="Editor settings",
    kind="jump",
    shortcut="Ctrl+,",
    enabled=_enabled,
    run=_run_focus_node("settings"),
)
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
    """Layer jumps in z-order.

    ``slots`` is ``(slot, stem_label)``. ``stem_label`` is shown as given.
    Shortcuts are ``1`` through ``8``; later rows keep no shortcut.
    ``run`` selects ``layer:<slot>`` and focuses its inspector.
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
                enabled=_enabled,
                run=_run_focus_node(layer_node_id(slot)),
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


def _shortcut_resolves(command: Command, *, timeline_scope: bool) -> bool:
    if command.id in _RESOLVED_SHORTCUT_IDS:
        return True
    if command.id.startswith("layers.focus."):
        return not timeline_scope
    return False


def command_for_shortcut(
    key: int,
    mod: int,
    menus: Sequence[Menu] | None = None,
    *,
    timeline_scope: bool = False,
) -> Command | None:
    """Resolved shortcut from *menus*, or None.

    Save, quit, render, the help overlay, editor settings, and add-layer
    resolve. Layer jumps resolve unless *timeline_scope* is set. Other
    shortcut text stays on its row. Bare R does not resolve.
    """
    source = MENUS if menus is None else menus
    ctrl = mod_ctrl(mod)
    for command in iter_commands(source):
        if not _shortcut_resolves(command, timeline_scope=timeline_scope):
            continue
        if command.shortcut is None:
            continue
        mapped = _SHORTCUT_KEYS.get(command.shortcut)
        if mapped is None:
            continue
        want_key, want_ctrl = mapped
        if key == want_key and ctrl == want_ctrl:
            return command
    return None
