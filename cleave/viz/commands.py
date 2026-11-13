"""Menu command registry for the live editor.

Static rows match the menu taxonomy. Settings and Project menus open their
pages in the inspector. Layer-focus commands are shortcut-only: they are
not menu rows. Layer focus is built from a z-order of ``(slot, stem_label)``
pairs so stem names stay with the project.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import pygame

from cleave.config_schema.layers import MAX_LAYER_COUNT
from cleave.viz.config_pages import CONFIG_PAGES, ConfigPage
from cleave.viz.context_menu import ContextMenuItem
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.key_repeat import mod_ctrl
from cleave.viz.navigator import layer_node_id, layer_slot_of
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.theme import CONFIG_DIRTY, VALUE

CommandKind = Literal["command", "jump", "check"]
LabelRole = tuple[int, int, int]

_RESOLVED_SHORTCUT_IDS = frozenset(
    {
        "file.new",
        "file.open",
        "file.save",
        "file.quit",
        "project.render",
        "help.overlay",
        "view.fullscreen",
        "page.settings.preview",
        "layers.add",
        "edit.undo",
        "edit.redo",
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
    selected_layer_locked: bool = False
    timeline_scope: bool = False
    timeline_recording: bool = False
    timeline_locked: bool = False
    timeline_can_undo: bool = False
    timeline_can_redo: bool = False
    help_visible: bool = False
    fullscreen: bool = False


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
    locked: Callable[[CommandContext], bool] = _disabled


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
    selected_slot = layer_slot_of(controls.shell_focus.selected_id)
    lifecycle = controls.layer_lifecycle
    timeline = session.timeline
    timeline_scope = (
        controls.shell_focus.region is ShellRegion.TIMELINE
        or bool(timeline.recording)
    )
    return CommandContext(
        editor_mode=session.settings.editor_mode,
        solo_slot=session.solo_slot,
        config_dirty=bool(controls.config_dirty),
        render_busy=bool(controls.project_render.busy),
        selected_slot=selected_slot,
        can_add_layer=lifecycle.can_add(),
        can_remove_layer=lifecycle.can_remove(),
        selected_layer_locked=(
            selected_slot is not None
            and selected_slot in session.layers
            and bool(session.layers[selected_slot].locked)
        ),
        timeline_scope=timeline_scope,
        timeline_recording=bool(timeline.recording),
        timeline_locked=bool(timeline.locked),
        timeline_can_undo=controls.timeline_history.can_undo,
        timeline_can_redo=controls.timeline_history.can_redo,
        help_visible=bool(session.help_visible),
        # Command fakes without window controls read as windowed.
        fullscreen=bool(getattr(getattr(controls, "window", None), "fullscreen", False)),
    )


def command_menu_item(
    command: Command,
    controls: Any,
    *,
    item_id: str | None = None,
    label: str | None = None,
    enabled: bool = True,
    disabled_hint: str | None = None,
) -> ContextMenuItem:
    """Context menu row for *command*: its label, shortcut, enabled state, and check.

    *enabled* False also disables it, for a reason the command does not know.
    *disabled_hint* says why when the row is disabled.
    """
    ctx = command_context(controls)
    live = enabled and bool(command.enabled(ctx))
    return ContextMenuItem(
        id=item_id or command.id,
        label=label or command.label,
        run=lambda: command.run(controls),
        enabled=live,
        checked=None if command.checked is None else bool(command.checked(ctx)),
        shortcut=command.shortcut,
        hint=None if live else disabled_hint,
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


def _project_switch_enabled(ctx: CommandContext) -> bool:
    return (
        not is_preset_curation_mode(ctx.editor_mode)
        and not ctx.render_busy
        and not ctx.timeline_recording
    )


def _run_new(controls: Any) -> None:
    controls.project_switch.prompt_new()


def _run_open(controls: Any) -> None:
    controls.project_switch.prompt_open()


def _save_enabled(ctx: CommandContext) -> bool:
    return not is_preset_curation_mode(ctx.editor_mode) and ctx.solo_slot is None


def _save_label_role(ctx: CommandContext) -> LabelRole:
    if ctx.config_dirty:
        return CONFIG_DIRTY
    return VALUE


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


def _help_checked(ctx: CommandContext) -> bool:
    return ctx.help_visible


def _fullscreen_checked(ctx: CommandContext) -> bool:
    return ctx.fullscreen


def _add_enabled(ctx: CommandContext) -> bool:
    return ctx.can_add_layer and not is_preset_curation_mode(ctx.editor_mode)


def _delete_enabled(ctx: CommandContext) -> bool:
    return (
        ctx.selected_slot is not None
        and ctx.can_remove_layer
        and not is_preset_curation_mode(ctx.editor_mode)
    )


def _preset_list_enabled(ctx: CommandContext) -> bool:
    return ctx.selected_slot is not None and not ctx.selected_layer_locked


def _layer_locked(ctx: CommandContext) -> bool:
    return ctx.selected_layer_locked


def _timeline_locked(ctx: CommandContext) -> bool:
    return ctx.timeline_locked


def _selected_slot(controls: Any) -> str:
    return command_context(controls).selected_slot


def _run_add_current_preset(controls: Any) -> None:
    controls.preset_list.add_current(_selected_slot(controls))


def _run_populate_presets(controls: Any) -> None:
    controls.preset_list.prompt_populate(_selected_slot(controls))


def _run_resume_switching(controls: Any) -> None:
    controls.preset_list.resume(_selected_slot(controls))


def _run_add(controls: Any) -> None:
    controls.layer_lifecycle.add()


def _run_delete(controls: Any) -> None:
    slot = command_context(controls).selected_slot
    if slot is None:
        return
    controls.layer_lifecycle.prompt_delete(slot)


def _timeline_actions_enabled(ctx: CommandContext) -> bool:
    return (
        not is_preset_curation_mode(ctx.editor_mode) and not ctx.timeline_locked
    )


def _run_generate(controls: Any) -> None:
    controls.prompt_generate_timeline()


def _run_reset_timeline(controls: Any) -> None:
    controls.prompt_reset_timeline()


def _run_snap_cues(controls: Any) -> None:
    controls.prompt_snap_cues()


def _run_snap_to_markers(controls: Any) -> None:
    controls.prompt_snap_cues_to_song_markers()


def _run_set_cut_type(controls: Any) -> None:
    controls.prompt_set_cut_type()


def _undo_enabled(ctx: CommandContext) -> bool:
    return (
        ctx.timeline_can_undo
        and _timeline_actions_enabled(ctx)
        and not ctx.timeline_recording
    )


def _redo_enabled(ctx: CommandContext) -> bool:
    return (
        ctx.timeline_can_redo
        and _timeline_actions_enabled(ctx)
        and not ctx.timeline_recording
    )


def _run_undo(controls: Any) -> None:
    controls.undo_timeline()


def _run_redo(controls: Any) -> None:
    controls.redo_timeline()


def _run_open_page(page_id: str) -> Callable[[Any], None]:
    """Show a Settings or Project page in the inspector."""

    def run(controls: Any) -> None:
        controls.navigator.open_page(page_id)

    return run


def _project_page_enabled(ctx: CommandContext) -> bool:
    return not is_preset_curation_mode(ctx.editor_mode)


_PAGE_SHORTCUTS: dict[str, str] = {"settings.preview": "Ctrl+,"}


def page_command_id(page_id: str) -> str:
    """Command id for the menu row that opens *page_id*."""
    return f"page.{page_id}"


def _page_command(page: ConfigPage) -> Command:
    enabled = _project_page_enabled if page.menu == "Project" else _enabled
    return Command(
        id=page_command_id(page.id),
        label=page.label,
        kind="jump",
        shortcut=_PAGE_SHORTCUTS.get(page.id),
        enabled=enabled,
        run=_when_enabled(enabled, _run_open_page(page.id)),
    )


def _page_commands(menu: str) -> tuple[Command, ...]:
    return tuple(_page_command(page) for page in CONFIG_PAGES if page.menu == menu)


def _run_focus_node(node_id: str) -> Callable[[Any], None]:
    """Select a navigator node and focus its inspector."""

    def run(controls: Any) -> None:
        controls.navigator.select(node_id)
        controls.navigator.activate()

    return run


def _toggle_help(controls: Any) -> None:
    session = controls.session
    if not session.help_visible:
        session.help_visible = True
        return
    # TuningControls.close_help restores the subject when Help is focused.
    # Command fakes that only flip the flag have no close_help method.
    if getattr(type(controls), "close_help", None) is None:
        session.help_visible = False
        return
    controls.close_help()


_NEW = Command(
    id="file.new",
    label="New project...",
    kind="command",
    shortcut="Ctrl+N",
    enabled=_project_switch_enabled,
    run=_when_enabled(_project_switch_enabled, _run_new),
)
_OPEN = Command(
    id="file.open",
    label="Open project...",
    kind="command",
    shortcut="Ctrl+O",
    enabled=_project_switch_enabled,
    run=_when_enabled(_project_switch_enabled, _run_open),
)
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
_ABOUT = _later("help.about", "About Cleave", "command")

_SEPARATE = _later("project.separate", "Re-separate stems...", "command")
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
    label="Delete layer...",
    kind="command",
    enabled=_delete_enabled,
    run=_when_enabled(_delete_enabled, _run_delete),
)
_ADD_CURRENT_PRESET = Command(
    id="layers.add_current_preset",
    label="Add To Preset List",
    kind="command",
    enabled=_preset_list_enabled,
    run=_when_enabled(_preset_list_enabled, _run_add_current_preset),
    locked=_layer_locked,
)
_POPULATE_PRESETS = Command(
    id="layers.populate_presets",
    label="Populate...",
    kind="command",
    enabled=_preset_list_enabled,
    run=_when_enabled(_preset_list_enabled, _run_populate_presets),
    locked=_layer_locked,
)
_RESUME_SWITCHING = Command(
    id="layers.resume_switching",
    label="Resume",
    kind="command",
    enabled=_preset_list_enabled,
    run=_when_enabled(_preset_list_enabled, _run_resume_switching),
    locked=_layer_locked,
)
_CURATION = Command(
    id="view.preset_curation",
    label="Preset curation mode",
    kind="check",
    enabled=_enabled,
    run=_run_curation,
    checked=_curation_checked,
)

_GENERATE = Command(
    id="timeline.generate",
    label="Generate timeline...",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_generate),
    locked=_timeline_locked,
)
_RESET = Command(
    id="timeline.reset",
    label="Reset timeline...",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_reset_timeline),
    locked=_timeline_locked,
)
_SNAP = Command(
    id="timeline.snap_cues",
    label="Snap cues...",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_snap_cues),
    locked=_timeline_locked,
)
_SNAP_TO_MARKERS = Command(
    id="timeline.snap_to_markers",
    label="Snap cues to markers...",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_snap_to_markers),
    locked=_timeline_locked,
)
_SET_CUT_TYPE = Command(
    id="timeline.set_cut_type",
    label="Set cut type on cues...",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_set_cut_type),
    locked=_timeline_locked,
)
_UNDO = Command(
    id="edit.undo",
    label="Undo",
    kind="command",
    shortcut="Ctrl+Z",
    enabled=_undo_enabled,
    run=_when_enabled(_undo_enabled, _run_undo),
)
_REDO = Command(
    id="edit.redo",
    label="Redo",
    kind="command",
    shortcut="Ctrl+Y",
    enabled=_redo_enabled,
    run=_when_enabled(_redo_enabled, _run_redo),
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
    label="Help",
    kind="check",
    shortcut="H",
    enabled=_enabled,
    run=_toggle_help,
    checked=_help_checked,
)

def _toggle_fullscreen(controls: Any) -> None:
    controls.window.request_fullscreen_toggle()


_FULLSCREEN = Command(
    id="view.fullscreen",
    label="Fullscreen",
    kind="check",
    shortcut="F11",
    enabled=_enabled,
    run=_toggle_fullscreen,
    checked=_fullscreen_checked,
)

_SHORTCUT_KEYS: dict[str, tuple[int, bool]] = {
    "Ctrl+N": (pygame.K_n, True),
    "Ctrl+O": (pygame.K_o, True),
    "Ctrl+S": (pygame.K_s, True),
    "Ctrl+Q": (pygame.K_q, True),
    "Ctrl+L": (pygame.K_l, True),
    "Ctrl+R": (pygame.K_r, True),
    "Ctrl+Y": (pygame.K_y, True),
    "Ctrl+Z": (pygame.K_z, True),
    "Ctrl+,": (pygame.K_COMMA, True),
    "H": (pygame.K_h, False),
    "F11": (pygame.K_F11, False),
    "1": (pygame.K_1, False),
    "2": (pygame.K_2, False),
    "3": (pygame.K_3, False),
    "4": (pygame.K_4, False),
    "5": (pygame.K_5, False),
    "6": (pygame.K_6, False),
    "7": (pygame.K_7, False),
    "8": (pygame.K_8, False),
}


class MenuSet(tuple[Menu, ...]):
    """Menus plus the layer z-order used by number-key shortcuts.

    Layer-focus commands are not items of any menu.
    """

    layer_slots: tuple[tuple[str, str], ...]

    def __new__(
        cls,
        menus: tuple[Menu, ...],
        layer_slots: tuple[tuple[str, str], ...] = (),
    ) -> MenuSet:
        obj = super().__new__(cls, menus)
        obj.layer_slots = layer_slots
        return obj


def layer_focus_commands(
    slots: Sequence[tuple[str, str]],
) -> tuple[Command, ...]:
    """Layer jumps in z-order. Not inserted into a menu.

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


_PROJECT_PAGES = _page_commands("Project")
_SETTINGS_PAGES = _page_commands("Settings")


def build_menus(
    layer_slots: Sequence[tuple[str, str]] = (),
) -> MenuSet:
    """Full menu bar. Commands, checks, and Settings / Project page opens.

    Navigator rows have no menu jump. ``layer_slots`` is stored for
    number-key shortcuts and is not shown.
    """
    return MenuSet(
        (
            Menu("File", (_NEW, _OPEN, _SAVE, SEPARATOR, _QUIT)),
            Menu("Edit", (_UNDO, _REDO)),
            Menu("View", (_FULLSCREEN, SEPARATOR, _CURATION)),
            Menu(
                "Project",
                (
                    *_PROJECT_PAGES,
                    SEPARATOR,
                    _RENDER,
                    _SEPARATE,
                    SEPARATOR,
                    _BACKUP,
                    _RESTORE,
                ),
            ),
            Menu("Settings", (*_SETTINGS_PAGES, SEPARATOR, _MEASURE_LATENCY)),
            Menu("Help", (_HELP_OVERLAY, SEPARATOR, _ABOUT)),
        ),
        tuple(layer_slots),
    )


MENUS: tuple[Menu, ...] = build_menus()

# Reachable from an inspector button only.
_INSPECTOR_COMMANDS: tuple[Command, ...] = (
    _ADD,
    _DELETE,
    _GENERATE,
    _RESET,
    _SNAP,
    _SET_CUT_TYPE,
    _SNAP_TO_MARKERS,
    _ADD_CURRENT_PRESET,
    _POPULATE_PRESETS,
    _RESUME_SWITCHING,
)


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
    for command in (*iter_commands(source), *_INSPECTOR_COMMANDS):
        if command.id == command_id:
            return command
    raise KeyError(command_id)


def _shortcut_resolves(command: Command, *, timeline_scope: bool) -> bool:
    if command.id in _RESOLVED_SHORTCUT_IDS:
        return True
    if command.id.startswith("layers.focus."):
        return not timeline_scope
    return False


def _shortcut_commands(menus: Sequence[Menu]) -> Iterator[Command]:
    """Menu rows, inspector buttons, then shortcut-only layer focus."""
    yield from iter_commands(menus)
    yield from _INSPECTOR_COMMANDS
    slots = getattr(menus, "layer_slots", ())
    yield from layer_focus_commands(slots)


def command_for_shortcut(
    key: int,
    mod: int,
    menus: Sequence[Menu] | None = None,
    *,
    timeline_scope: bool = False,
) -> Command | None:
    """Resolved shortcut, or None.

    New, open, save, quit, render, the help overlay, fullscreen, undo, redo,
    show-timeline-strip, and Settings > Preview (Ctrl+,) resolve from menu
    rows. Add-layer resolves from its inspector button. Layer jumps
    (``1``–``8``) resolve from commands that are not menu rows, and stay
    unresolved while *timeline_scope* is set. Other shortcut text stays
    on its row. Bare R does not resolve.
    """
    source = MENUS if menus is None else menus
    ctrl = mod_ctrl(mod)
    for command in _shortcut_commands(source):
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
