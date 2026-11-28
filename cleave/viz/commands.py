"""Menu command registry for the live editor.

Static rows match the menu taxonomy. Settings and Project menus open their
pages in the inspector. Layer-focus commands are shortcut-only: they are
not menu rows. Layer focus is built from a z-order of ``(slot, stem_label)``
pairs so stem names stay with the project.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pygame

from cleave.config_schema.layers import MAX_LAYER_COUNT
from cleave.viz.config_pages import CONFIG_PAGES, ConfigPage
from cleave.viz.context_menu import ContextMenuItem
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.key_repeat import mod_alt, mod_ctrl, mod_shift
from cleave.viz.navigator import (
    LAYER_PAGE_PRESET_LIST,
    layer_node_id,
    layer_page_node_id,
    layer_slot_of,
)
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.theme import palette

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.preset_clipboard import PresetEditTarget

CommandKind = Literal["command", "jump", "check"]
LabelRole = tuple[int, int, int]

HELP_OVERLAY_ID = "help.overlay"

_RESOLVED_SHORTCUT_IDS = frozenset(
    {
        "file.new",
        "file.open",
        "file.save",
        "file.quit",
        "project.render",
        HELP_OVERLAY_ID,
        "view.fullscreen_editor",
        "view.play_fullscreen",
        "page.settings.preview",
        "layers.add",
        "edit.undo",
        "edit.redo",
        "view.page_back",
        "view.page_forward",
    }
)


# Clipboard shortcuts act on the inspector, so the strip keeps its own keys.
_CLIPBOARD_IDS = frozenset(
    {"edit.cut", "edit.copy", "edit.paste", "edit.paste_after", "edit.duplicate"}
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
    can_undo: bool = False
    can_redo: bool = False
    # The section the top Undo / Redo entry edits is locked.
    undo_locked: bool = False
    redo_locked: bool = False
    # The focused preset list entry or Milkdrop Preset row, for the clipboard.
    preset_target: PresetEditTarget | None = None
    # Why Paste cannot run, or None when the clipboard holds a preset.
    preset_paste_hint: str | None = "Nothing copied"
    # The preset browser is open on a preset.
    browser_preset_selected: bool = False
    help_visible: bool = False
    fullscreen: bool = False
    # Pages the history's Back and Forward would show, None where there is none.
    page_back_id: str | None = None
    page_forward_id: str | None = None
    # An open project and stem split (PyTorch, Demucs) installed.
    can_reseparate: bool = False


def _disabled(_ctx: CommandContext) -> bool:
    return False


def _enabled(_ctx: CommandContext) -> bool:
    return True


def _noop(_controls: TuningControls) -> None:
    return None


@dataclass(frozen=True)
class Command:
    id: str
    label: str
    kind: CommandKind
    shortcut: str | None = None
    enabled: Callable[[CommandContext], bool] = _enabled
    run: Callable[[TuningControls], None] = _noop
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


def command_context(controls: TuningControls) -> CommandContext:
    """Read the fields menu predicates need from tuning controls."""
    session = controls.session
    selected_slot = layer_slot_of(controls.shell_focus.selected_id)
    lifecycle = controls.layer_lifecycle
    timeline = session.timeline
    timeline_scope = (
        controls.shell_focus.region is ShellRegion.TIMELINE
        or bool(timeline.recording)
    )
    page_back_id, page_forward_id = controls.navigator.history_targets()
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
        can_undo=controls.edit_history.can_undo,
        can_redo=controls.edit_history.can_redo,
        undo_locked=controls.edit_history.undo_locked,
        redo_locked=controls.edit_history.redo_locked,
        preset_target=controls.preset_edit_target(),
        preset_paste_hint=controls.preset_clipboard.paste_hint(),
        browser_preset_selected=_browser_preset(controls) is not None,
        help_visible=bool(session.help_visible),
        # Command fakes without window controls read as windowed.
        fullscreen=bool(getattr(getattr(controls, "window", None), "fullscreen", False)),
        page_back_id=page_back_id,
        page_forward_id=page_forward_id,
        can_reseparate=(
            getattr(controls, "project_dir", None) is not None
            and stem_split_installed()
        ),
    )


@cache
def stem_split_installed() -> bool:
    """True when PyTorch is importable. Checks without importing it."""
    from importlib.util import find_spec

    return find_spec("torch") is not None


def command_menu_item(
    command: Command,
    controls: TuningControls,
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
    action: Callable[[TuningControls], None],
) -> Callable[[TuningControls], None]:
    def run(controls: TuningControls) -> None:
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


def _run_new(controls: TuningControls) -> None:
    controls.project_switch.prompt_new()


def _run_open(controls: TuningControls) -> None:
    controls.project_switch.prompt_open()


def _reseparate_enabled(ctx: CommandContext) -> bool:
    return ctx.can_reseparate and _project_switch_enabled(ctx)


def _run_reseparate(controls: TuningControls) -> None:
    from cleave.viz.stem_count_prompt import (
        RESEPARATE_BODY,
        RESEPARATE_TITLE,
        project_split,
        prompt_split,
    )

    project_dir = controls.project_dir
    if project_dir is None or controls.modal_host.active:
        return
    prompt_split(
        controls.modal_host,
        RESEPARATE_TITLE,
        lambda choice: controls.project_switch.request_reseparate(project_dir, choice),
        current=project_split(project_dir),
        body=RESEPARATE_BODY,
    )


def _save_enabled(ctx: CommandContext) -> bool:
    return not is_preset_curation_mode(ctx.editor_mode) and ctx.solo_slot is None


def _save_label_role(ctx: CommandContext) -> LabelRole:
    if ctx.config_dirty:
        return palette().config_dirty
    return palette().value


def _render_enabled(ctx: CommandContext) -> bool:
    return not is_preset_curation_mode(ctx.editor_mode) and not ctx.render_busy


def _run_save(controls: TuningControls) -> None:
    controls.prompt_save_config()


def _run_quit(controls: TuningControls) -> None:
    controls.request_quit()


def _run_render(controls: TuningControls) -> None:
    controls.project_render.prompt()


def _curation_checked(ctx: CommandContext) -> bool:
    return is_preset_curation_mode(ctx.editor_mode)


def _run_curation(controls: TuningControls) -> None:
    controls.editor_mode.prompt_change_editor_mode()


def _run_measure_latency(controls: TuningControls) -> None:
    controls.av_sync.prompt_start()


def _run_calibrate_tap_timing(controls: TuningControls) -> None:
    controls.tap_sync.prompt_start()


def _run_rescan_presets(controls: TuningControls) -> None:
    controls.preset_rescan.start()


def _run_manage_tags(controls: TuningControls) -> None:
    controls.tag_manager.prompt()


def _run_back_up_curation(controls: TuningControls) -> None:
    controls.curation_backup.prompt_back_up()


def _run_restore_curation(controls: TuningControls) -> None:
    controls.curation_backup.prompt_restore()


def _run_download_packages(controls: TuningControls) -> None:
    controls.prompt_welcome()


def _run_open_crash_log_folder(controls: TuningControls) -> None:
    from cleave.crash_log import open_crash_log_folder

    try:
        open_crash_log_folder(controls.cfg.user_config_path)
    except OSError as exc:
        controls.show_notification(f"Could not open the crash log folder: {exc}")


def _run_open_themes_folder(controls: TuningControls) -> None:
    controls.theme_files.open_folder()


def _run_reload_themes(controls: TuningControls) -> None:
    controls.theme_files.reload()


def _run_about(controls: TuningControls) -> None:
    controls.prompt_about()


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


def _selected_slot(controls: TuningControls) -> str:
    return command_context(controls).selected_slot


def _go_to_preset_list_enabled(ctx: CommandContext) -> bool:
    return ctx.selected_slot is not None


def _run_go_to_preset_list(controls: TuningControls) -> None:
    page_id = layer_page_node_id(_selected_slot(controls), LAYER_PAGE_PRESET_LIST)
    controls.navigator.select(page_id)
    controls.navigator.activate()


def _run_populate_presets(controls: TuningControls) -> None:
    controls.preset_list.prompt_populate(_selected_slot(controls))


def _run_resume_switching(controls: TuningControls) -> None:
    controls.preset_list.resume(_selected_slot(controls))


def _run_add(controls: TuningControls) -> None:
    controls.layer_lifecycle.add()


def _run_delete(controls: TuningControls) -> None:
    slot = command_context(controls).selected_slot
    if slot is None:
        return
    controls.layer_lifecycle.prompt_delete(slot)


def _timeline_actions_enabled(ctx: CommandContext) -> bool:
    return (
        not is_preset_curation_mode(ctx.editor_mode) and not ctx.timeline_locked
    )


def _run_generate(controls: TuningControls) -> None:
    controls.prompt_generate_timeline()


def _run_reset_timeline(controls: TuningControls) -> None:
    controls.prompt_reset_timeline()


def _run_snap_cues(controls: TuningControls) -> None:
    controls.prompt_snap_cues()


def _run_snap_to_markers(controls: TuningControls) -> None:
    controls.prompt_snap_cues_to_song_markers()


def _run_snap_song_markers(controls: TuningControls) -> None:
    controls.prompt_snap_song_markers()


def _run_set_cut_type(controls: TuningControls) -> None:
    controls.prompt_set_cut_type()


def _undo_runs(ctx: CommandContext) -> bool:
    """A locked step runs too: it names the lock instead of undoing."""
    return (
        ctx.can_undo
        and not is_preset_curation_mode(ctx.editor_mode)
        and not ctx.timeline_recording
    )


def _undo_enabled(ctx: CommandContext) -> bool:
    return _undo_runs(ctx) and not ctx.undo_locked


def _redo_runs(ctx: CommandContext) -> bool:
    """As ``_undo_runs``, for Redo."""
    return (
        ctx.can_redo
        and not is_preset_curation_mode(ctx.editor_mode)
        and not ctx.timeline_recording
    )


def _redo_enabled(ctx: CommandContext) -> bool:
    return _redo_runs(ctx) and not ctx.redo_locked


def _browser_preset(controls: TuningControls) -> Path | None:
    browser = controls.preset_browser.browser
    return browser.selected_preset() if browser is not None else None


def _list_target(ctx: CommandContext) -> PresetEditTarget | None:
    """The focused preset list entry when it can be edited."""
    target = ctx.preset_target
    if target is None or target.index is None or target.locked:
        return None
    if is_preset_curation_mode(ctx.editor_mode):
        return None
    return target


def _cut_enabled(ctx: CommandContext) -> bool:
    return _list_target(ctx) is not None


def _copy_enabled(ctx: CommandContext) -> bool:
    return ctx.browser_preset_selected or ctx.preset_target is not None


def _paste_enabled(ctx: CommandContext) -> bool:
    if ctx.preset_paste_hint is not None:
        return False
    target = ctx.preset_target
    if target is not None and target.index is None:
        return not target.locked
    return _list_target(ctx) is not None


def _paste_after_enabled(ctx: CommandContext) -> bool:
    return ctx.preset_paste_hint is None and _list_target(ctx) is not None


def _run_cut(controls: TuningControls) -> None:
    target = controls.preset_edit_target()
    if target is not None and target.index is not None:
        controls.preset_clipboard.cut_entry(target.slot, target.index)


def _run_copy(controls: TuningControls) -> None:
    path = _browser_preset(controls)
    if path is not None:
        controls.preset_clipboard.copy_path(path)
        return
    target = controls.preset_edit_target()
    if target is None:
        return
    if target.index is None:
        controls.preset_clipboard.copy_current(target.slot)
    else:
        controls.preset_clipboard.copy_entry(target.slot, target.index)


def _run_paste(controls: TuningControls) -> None:
    target = controls.preset_edit_target()
    if target is None:
        return
    if target.index is None:
        controls.preset_clipboard.paste_preview(target.slot)
    else:
        controls.preset_clipboard.paste_over(target.slot, target.index)


def _run_paste_after(controls: TuningControls) -> None:
    target = controls.preset_edit_target()
    if target is not None and target.index is not None:
        controls.preset_clipboard.paste_after(target.slot, target.index)


def _run_duplicate(controls: TuningControls) -> None:
    target = controls.preset_edit_target()
    if target is not None and target.index is not None:
        controls.preset_list.duplicate(target.slot, target.index)


def _run_undo(controls: TuningControls) -> None:
    controls.undo()


def _run_redo(controls: TuningControls) -> None:
    controls.redo()


def _run_open_page(page_id: str) -> Callable[[TuningControls], None]:
    """Show a Settings or Project page in the inspector."""

    def run(controls: TuningControls) -> None:
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


def _run_focus_node(node_id: str) -> Callable[[TuningControls], None]:
    """Select a navigator node and focus its inspector."""

    def run(controls: TuningControls) -> None:
        controls.navigator.select(node_id)
        controls.navigator.activate()

    return run


def _toggle_help(controls: TuningControls) -> None:
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
    label="New project…",
    kind="command",
    shortcut="Ctrl+N",
    enabled=_project_switch_enabled,
    run=_when_enabled(_project_switch_enabled, _run_new),
)
_OPEN = Command(
    id="file.open",
    label="Open project…",
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
_ABOUT = Command(
    id="help.about",
    label="About Cleave",
    kind="command",
    enabled=_enabled,
    run=_run_about,
)

_SEPARATE = Command(
    id="project.separate",
    label="Re-separate stems…",
    kind="command",
    enabled=_reseparate_enabled,
    run=_when_enabled(_reseparate_enabled, _run_reseparate),
)
_RENDER = Command(
    id="project.render",
    label="Render…",
    kind="command",
    shortcut="Ctrl+R",
    enabled=_render_enabled,
    run=_when_enabled(_render_enabled, _run_render),
)
_BACKUP = _later("project.backup", "Backup…", "command")
_RESTORE = _later("project.restore", "Restore…", "command")

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
    label="Delete layer…",
    kind="command",
    enabled=_delete_enabled,
    run=_when_enabled(_delete_enabled, _run_delete),
)
_GO_TO_PRESET_LIST = Command(
    id="layers.go_to_preset_list",
    label="Go to preset list",
    kind="command",
    enabled=_go_to_preset_list_enabled,
    run=_when_enabled(_go_to_preset_list_enabled, _run_go_to_preset_list),
)
_POPULATE_PRESETS = Command(
    id="layers.populate_presets",
    label="Populate list…",
    kind="command",
    enabled=_preset_list_enabled,
    run=_when_enabled(_preset_list_enabled, _run_populate_presets),
    locked=_layer_locked,
)
_RESUME_SWITCHING = Command(
    id="layers.resume_switching",
    label="Resume switching",
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
    label="Generate timeline…",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_generate),
    locked=_timeline_locked,
)
_RESET = Command(
    id="timeline.reset",
    label="Reset timeline…",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_reset_timeline),
    locked=_timeline_locked,
)
_SNAP = Command(
    id="timeline.snap_cues",
    label="Snap clips…",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_snap_cues),
    locked=_timeline_locked,
)
_SNAP_TO_MARKERS = Command(
    id="timeline.snap_to_markers",
    label="Snap clips to markers…",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_snap_to_markers),
    locked=_timeline_locked,
)
_SNAP_SONG_MARKERS = Command(
    id="timeline.snap_song_markers",
    label="Snap song markers…",
    kind="command",
    enabled=_timeline_actions_enabled,
    run=_when_enabled(_timeline_actions_enabled, _run_snap_song_markers),
    locked=_timeline_locked,
)
_SET_CUT_TYPE = Command(
    id="timeline.set_cut_type",
    label="Set cut type on clips…",
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
    run=_when_enabled(_undo_runs, _run_undo),
)
_REDO = Command(
    id="edit.redo",
    label="Redo",
    kind="command",
    shortcut="Ctrl+Y",
    enabled=_redo_enabled,
    run=_when_enabled(_redo_runs, _run_redo),
)

CUT = Command(
    id="edit.cut",
    label="Cut",
    kind="command",
    shortcut="Ctrl+X",
    enabled=_cut_enabled,
    run=_when_enabled(_cut_enabled, _run_cut),
)
COPY = Command(
    id="edit.copy",
    label="Copy",
    kind="command",
    shortcut="Ctrl+C",
    enabled=_copy_enabled,
    run=_when_enabled(_copy_enabled, _run_copy),
)
PASTE = Command(
    id="edit.paste",
    label="Paste",
    kind="command",
    shortcut="Ctrl+V",
    enabled=_paste_enabled,
    run=_when_enabled(_paste_enabled, _run_paste),
)
PASTE_AFTER = Command(
    id="edit.paste_after",
    label="Paste after",
    kind="command",
    shortcut="Ctrl+Shift+V",
    enabled=_paste_after_enabled,
    run=_when_enabled(_paste_after_enabled, _run_paste_after),
)
DUPLICATE = Command(
    id="edit.duplicate",
    label="Duplicate",
    kind="command",
    shortcut="Ctrl+D",
    enabled=_cut_enabled,
    run=_when_enabled(_cut_enabled, _run_duplicate),
)

_MEASURE_LATENCY = Command(
    id="settings.measure_latency",
    label="Measure audio latency…",
    kind="command",
    enabled=_enabled,
    run=_run_measure_latency,
)

_CALIBRATE_TAP_TIMING = Command(
    id="settings.calibrate_tap_timing",
    label="Calibrate tap timing…",
    kind="command",
    enabled=_enabled,
    run=_run_calibrate_tap_timing,
)

_RESCAN_PRESETS = Command(
    id="settings.rescan_presets",
    label="Rescan presets",
    kind="command",
    enabled=_enabled,
    run=_run_rescan_presets,
)

_MANAGE_TAGS = Command(
    id="settings.manage_tags",
    label="Manage tags…",
    kind="command",
    enabled=_enabled,
    run=_run_manage_tags,
)

_BACK_UP_CURATION = Command(
    id="settings.back_up_curation",
    label="Back up preset curation…",
    kind="command",
    enabled=_enabled,
    run=_run_back_up_curation,
)

_RESTORE_CURATION = Command(
    id="settings.restore_curation",
    label="Restore preset curation…",
    kind="command",
    enabled=_enabled,
    run=_run_restore_curation,
)

_DOWNLOAD_PACKAGES = Command(
    id="settings.download_packages",
    label="Download packages…",
    kind="command",
    enabled=_enabled,
    run=_run_download_packages,
)

_OPEN_CRASH_LOG_FOLDER = Command(
    id="settings.open_crash_log_folder",
    label="Open crash log folder",
    kind="command",
    enabled=_enabled,
    run=_run_open_crash_log_folder,
)

_OPEN_THEMES_FOLDER = Command(
    id="settings.open_themes_folder",
    label="Open themes folder",
    kind="command",
    enabled=_enabled,
    run=_run_open_themes_folder,
)

_RELOAD_THEMES = Command(
    id="settings.reload_themes",
    label="Reload themes",
    kind="command",
    enabled=_enabled,
    run=_run_reload_themes,
)

_HELP_OVERLAY = Command(
    id=HELP_OVERLAY_ID,
    label="Help",
    kind="check",
    shortcut="H",
    enabled=_enabled,
    run=_toggle_help,
    checked=_help_checked,
)

def _toggle_fullscreen_editor(controls: TuningControls) -> None:
    controls.window.request_fullscreen_toggle()


def _play_fullscreen(controls: TuningControls) -> None:
    controls.context_menu.close()
    controls.window.request_play_fullscreen(True)


_FULLSCREEN_EDITOR = Command(
    id="view.fullscreen_editor",
    label="Full screen editor",
    kind="check",
    shortcut="F11",
    enabled=_enabled,
    run=_toggle_fullscreen_editor,
    checked=_fullscreen_checked,
)

_PLAY_FULLSCREEN = Command(
    id="view.play_fullscreen",
    label="Play full screen",
    kind="command",
    shortcut="Ctrl+F",
    enabled=_enabled,
    run=_play_fullscreen,
)

def _reset_panel_layout(controls: TuningControls) -> None:
    controls.settings.reset_panel_layout()


_RESET_PANEL_LAYOUT = Command(
    id="view.reset_panel_layout",
    label="Reset panel layout",
    kind="command",
    enabled=_enabled,
    run=_reset_panel_layout,
)

def _can_page_back(ctx: CommandContext) -> bool:
    return ctx.page_back_id is not None


def _can_page_forward(ctx: CommandContext) -> bool:
    return ctx.page_forward_id is not None


def _page_back(controls: TuningControls) -> None:
    controls.navigator.go_back()


def _page_forward(controls: TuningControls) -> None:
    controls.navigator.go_forward()


_PAGE_BACK = Command(
    id="view.page_back",
    label="Back",
    kind="command",
    shortcut="Alt+Left",
    enabled=_can_page_back,
    run=_page_back,
)

_PAGE_FORWARD = Command(
    id="view.page_forward",
    label="Forward",
    kind="command",
    shortcut="Alt+Right",
    enabled=_can_page_forward,
    run=_page_forward,
)

# Shortcut text to ``(key, ctrl, alt)``.
# Key, Ctrl, Alt, and Shift (None: either).
_SHORTCUT_KEYS: dict[str, tuple[int, bool, bool, bool | None]] = {
    "Ctrl+N": (pygame.K_n, True, False, None),
    "Ctrl+O": (pygame.K_o, True, False, None),
    "Ctrl+S": (pygame.K_s, True, False, None),
    "Ctrl+Q": (pygame.K_q, True, False, None),
    "Ctrl+L": (pygame.K_l, True, False, None),
    "Ctrl+R": (pygame.K_r, True, False, None),
    "Ctrl+Y": (pygame.K_y, True, False, None),
    "Ctrl+Z": (pygame.K_z, True, False, None),
    "Ctrl+,": (pygame.K_COMMA, True, False, None),
    "Ctrl+F": (pygame.K_f, True, False, None),
    "Ctrl+X": (pygame.K_x, True, False, None),
    "Ctrl+C": (pygame.K_c, True, False, None),
    "Ctrl+V": (pygame.K_v, True, False, False),
    "Ctrl+Shift+V": (pygame.K_v, True, False, True),
    "Ctrl+D": (pygame.K_d, True, False, None),
    "H": (pygame.K_h, False, False, None),
    "F11": (pygame.K_F11, False, False, None),
    "1": (pygame.K_1, False, False, None),
    "2": (pygame.K_2, False, False, None),
    "3": (pygame.K_3, False, False, None),
    "4": (pygame.K_4, False, False, None),
    "5": (pygame.K_5, False, False, None),
    "6": (pygame.K_6, False, False, None),
    "7": (pygame.K_7, False, False, None),
    "8": (pygame.K_8, False, False, None),
    "Alt+Left": (pygame.K_LEFT, False, True, None),
    "Alt+Right": (pygame.K_RIGHT, False, True, None),
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
# Dev Tools sits at the foot of the Settings menu, after the commands.
_DEV_TOOLS_PAGE_ID = "settings.dev_tools"
_SETTINGS_PAGES = tuple(
    command
    for command in _page_commands("Settings")
    if command.id != page_command_id(_DEV_TOOLS_PAGE_ID)
)
_DEV_TOOLS_PAGE = next(
    command
    for command in _page_commands("Settings")
    if command.id == page_command_id(_DEV_TOOLS_PAGE_ID)
)


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
            Menu(
                "Edit",
                (
                    _UNDO,
                    _REDO,
                    SEPARATOR,
                    CUT,
                    COPY,
                    PASTE,
                    PASTE_AFTER,
                    DUPLICATE,
                ),
            ),
            Menu(
                "View",
                (
                    _PAGE_BACK,
                    _PAGE_FORWARD,
                    SEPARATOR,
                    _PLAY_FULLSCREEN,
                    _FULLSCREEN_EDITOR,
                    SEPARATOR,
                    _RESET_PANEL_LAYOUT,
                    SEPARATOR,
                    _CURATION,
                ),
            ),
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
            Menu(
                "Settings",
                (
                    *_SETTINGS_PAGES,
                    SEPARATOR,
                    _MEASURE_LATENCY,
                    _CALIBRATE_TAP_TIMING,
                    SEPARATOR,
                    _RESCAN_PRESETS,
                    _MANAGE_TAGS,
                    _BACK_UP_CURATION,
                    _RESTORE_CURATION,
                    _DOWNLOAD_PACKAGES,
                    SEPARATOR,
                    _DEV_TOOLS_PAGE,
                ),
            ),
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
    _SNAP_SONG_MARKERS,
    _SET_CUT_TYPE,
    _SNAP_TO_MARKERS,
    _GO_TO_PRESET_LIST,
    _POPULATE_PRESETS,
    _RESUME_SWITCHING,
    _OPEN_CRASH_LOG_FOLDER,
    _OPEN_THEMES_FOLDER,
    _RELOAD_THEMES,
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
    if command.id.startswith("layers.focus.") or command.id in _CLIPBOARD_IDS:
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

    New, open, save, quit, render, the help overlay, Back, Forward, Play full
    screen, Full screen editor,
    undo, redo, and the preset clipboard (cut, copy, paste, paste after,
    duplicate; not while *timeline_scope* is set),
    show-timeline-strip, and Settings > Preview (Ctrl+,) resolve from menu
    rows. Add-layer resolves from its inspector button. Layer jumps
    (``1``–``8``) resolve from commands that are not menu rows, and stay
    unresolved while *timeline_scope* is set. Other shortcut text stays
    on its row. Bare R does not resolve.
    """
    source = MENUS if menus is None else menus
    ctrl = mod_ctrl(mod)
    alt = mod_alt(mod)
    shift = mod_shift(mod)
    for command in _shortcut_commands(source):
        if not _shortcut_resolves(command, timeline_scope=timeline_scope):
            continue
        if command.shortcut is None:
            continue
        mapped = _SHORTCUT_KEYS.get(command.shortcut)
        if mapped is None:
            continue
        want_key, want_ctrl, want_alt, want_shift = mapped
        if key == want_key and ctrl == want_ctrl and alt == want_alt and (
            want_shift is None or shift == want_shift
        ):
            return command
    return None
