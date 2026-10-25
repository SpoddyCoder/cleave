"""Command registry: taxonomy, resolved shortcuts, and wired controllers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame

from cleave.config_schema.editor import DEFAULT_SHELL_LAYOUT_MODE
from cleave.user_config import load_user_config
from cleave.viz.commands import (
    MENUS,
    CommandContext,
    MenuSeparator,
    build_menus,
    command_by_id,
    command_context,
    command_for_shortcut,
    iter_commands,
    layer_focus_commands,
)
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.help_content import help_focus_descriptor
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.modal import ModalKind
from cleave.viz.navigator import layer_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import apply_field_action, row_spec
from cleave.viz.session import LayerRuntime
from cleave.viz.shell_focus import InspectorGroupKey, ShellRegion
from cleave.viz.theme import ACTION, CONFIG_DIRTY
from tests.cleave.viz.test_controls import (
    _keydown,
    _make_controls,
    _make_controls_with_manager,
    _make_playlist,
    _mutate_dirty,
)

_SLOTS = (("slot_a", "snare"), ("slot_b", "pad"))

_STATIC_IDS = (
    "file.open",
    "file.save",
    "file.quit",
    "project.settings",
    "project.separate",
    "project.render",
    "project.backup",
    "project.restore",
    "layers.add",
    "layers.delete",
    "layers.preset_curation",
    "render.overlays",
    "render.post_fx",
    "render.pattern_mask",
    "render.edit_overlays",
    "render.edit_post_fx",
    "timeline.show_strip",
    "timeline.apply_preset",
    "timeline.reset",
    "timeline.snap_cues",
    "timeline.undo_cut",
    "timeline.song_markers",
    "settings.editor",
    "settings.docked_layout",
    "settings.measure_latency",
    "help.overlay",
    "help.shortcuts",
    "help.about",
)

_DISABLED_IDS = (
    "file.open",
    "project.separate",
    "project.backup",
    "project.restore",
    "help.about",
    "timeline.undo_cut",
    "layers.add",
    "layers.delete",
)

_ENABLED_JUMP_IDS = (
    "project.settings",
    "settings.editor",
    "render.edit_overlays",
    "render.edit_post_fx",
    "timeline.song_markers",
)


def _menus():
    return build_menus(_SLOTS)


def _row_ids(menu) -> list[str | None]:
    return [
        None if isinstance(item, MenuSeparator) else item.id for item in menu.items
    ]


def _fake_controls(
    *,
    editor_mode: str = "visualizer",
    solo_slot: str | None = None,
    config_dirty: bool = False,
    render_busy: bool = False,
    help_visible: bool = False,
    selected_id: str = "settings",
    can_add: bool = False,
    can_remove: bool = False,
    recording: bool = False,
):
    return SimpleNamespace(
        session=SimpleNamespace(
            settings=SimpleNamespace(editor_mode=editor_mode),
            solo_slot=solo_slot,
            help_visible=help_visible,
            timeline=SimpleNamespace(
                recording=recording,
                panel_open=False,
                locked=False,
            ),
            render_overlays=SimpleNamespace(
                opening_card=SimpleNamespace(enabled=False),
                closing_card=SimpleNamespace(enabled=False),
                locked=False,
            ),
            render_post_fx=SimpleNamespace(enabled=False, locked=False),
            render_pattern_mask=SimpleNamespace(enabled=False, locked=False),
        ),
        config_dirty=config_dirty,
        project_render=SimpleNamespace(busy=render_busy, prompt=MagicMock()),
        prompt_save_config=MagicMock(),
        request_quit=MagicMock(),
        editor_mode=SimpleNamespace(prompt_change_editor_mode=MagicMock()),
        tap_sync=SimpleNamespace(prompt_start=MagicMock()),
        shell_focus=SimpleNamespace(selected_id=selected_id),
        focus_cursor=object(),
        layer_lifecycle=SimpleNamespace(
            can_add=lambda: can_add,
            can_remove=lambda: can_remove,
            prompt_add=MagicMock(),
            prompt_delete=MagicMock(),
        ),
        navigator=SimpleNamespace(select=MagicMock(), activate=MagicMock()),
        cfg=SimpleNamespace(
            editor=SimpleNamespace(shell_layout_mode=DEFAULT_SHELL_LAYOUT_MODE),
        ),
    )


def test_menus_list_taxonomy_ids_once() -> None:
    menus = _menus()
    assert [menu.label for menu in menus] == [
        "File",
        "Project",
        "Layers",
        "Render",
        "Timeline",
        "Settings",
        "Help",
    ]
    assert _row_ids(menus[0]) == ["file.open", "file.save", None, "file.quit"]
    assert _row_ids(menus[1]) == [
        "project.settings",
        None,
        "project.separate",
        "project.render",
        None,
        "project.backup",
        "project.restore",
    ]
    assert _row_ids(menus[2]) == [
        "layers.add",
        "layers.delete",
        None,
        "layers.focus.slot_a",
        "layers.focus.slot_b",
        None,
        "layers.preset_curation",
    ]
    assert _row_ids(menus[3]) == [
        "render.overlays",
        "render.post_fx",
        "render.pattern_mask",
        None,
        "render.edit_overlays",
        "render.edit_post_fx",
    ]
    assert _row_ids(menus[4]) == [
        "timeline.show_strip",
        None,
        "timeline.apply_preset",
        "timeline.reset",
        "timeline.snap_cues",
        "timeline.undo_cut",
        None,
        "timeline.song_markers",
    ]
    assert _row_ids(menus[5]) == [
        "settings.editor",
        "settings.docked_layout",
        "settings.measure_latency",
    ]
    assert _row_ids(menus[6]) == [
        "help.overlay",
        "help.shortcuts",
        None,
        "help.about",
    ]
    ids = [command.id for command in iter_commands(menus)]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(_STATIC_IDS) | {
        "layers.focus.slot_a",
        "layers.focus.slot_b",
    }
    assert "Start render..." not in [command.label for command in iter_commands(menus)]
    assert [menu.label for menu in MENUS] == [menu.label for menu in menus]
    assert not any(
        command.id.startswith("layers.focus.") for command in iter_commands(MENUS)
    )


def test_layer_jumps_use_given_labels() -> None:
    jumps = layer_focus_commands((("layer_9", "snare"), ("layer_2", "pad")))
    assert [(command.id, command.label, command.shortcut) for command in jumps] == [
        ("layers.focus.layer_9", "Layer 1  snare", "1"),
        ("layers.focus.layer_2", "Layer 2  pad", "2"),
    ]
    assert all(command.kind == "jump" for command in jumps)
    ninth = layer_focus_commands(tuple((f"s{i}", f"stem-{i}") for i in range(9)))
    assert ninth[7].shortcut == "8"
    assert ninth[8].shortcut is None


def test_only_project_render_owns_ctrl_r() -> None:
    menus = _menus()
    owners = [
        command
        for command in iter_commands(menus)
        if command.shortcut == "Ctrl+R"
    ]
    assert [command.id for command in owners] == ["project.render"]
    assert command_for_shortcut(pygame.K_r, pygame.KMOD_CTRL) is owners[0]
    assert command_for_shortcut(pygame.K_r, pygame.KMOD_LCTRL) is owners[0]
    assert command_for_shortcut(pygame.K_r, 0) is None
    assert all(command.shortcut != "R" for command in iter_commands(menus))


def test_later_shortcuts_stay_on_rows_but_do_not_resolve() -> None:
    menus = _menus()
    assert command_by_id("file.open", menus).shortcut == "Ctrl+O"
    assert command_by_id("layers.add", menus).shortcut == "Ctrl+L"
    assert command_by_id("timeline.show_strip", menus).shortcut == "T"
    assert command_by_id("settings.editor", menus).shortcut == "Ctrl+,"
    assert command_by_id("layers.focus.slot_a", menus).shortcut == "1"
    assert command_for_shortcut(pygame.K_o, pygame.KMOD_CTRL) is None
    assert command_for_shortcut(pygame.K_t, 0).id == "timeline.show_strip"
    assert (
        command_for_shortcut(pygame.K_t, 0, timeline_scope=True).id
        == "timeline.show_strip"
    )
    assert command_for_shortcut(pygame.K_COMMA, pygame.KMOD_CTRL).id == "settings.editor"
    assert command_for_shortcut(pygame.K_1, 0) is None
    assert command_for_shortcut(pygame.K_s, pygame.KMOD_CTRL).id == "file.save"
    assert command_for_shortcut(pygame.K_q, pygame.KMOD_CTRL).id == "file.quit"
    assert command_for_shortcut(pygame.K_h, 0).id == "help.overlay"
    assert command_for_shortcut(pygame.K_h, pygame.KMOD_CTRL) is None


def test_disabled_items_and_jumps_stay_disabled() -> None:
    menus = _menus()
    ctx = CommandContext()
    for command_id in _DISABLED_IDS:
        assert command_by_id(command_id, menus).enabled(ctx) is False
    for command_id in _ENABLED_JUMP_IDS:
        command = command_by_id(command_id, menus)
        assert command.kind == "jump"
        assert command.enabled(ctx) is True
    for command in iter_commands(menus):
        if command.id.startswith("layers.focus."):
            assert command.enabled(ctx) is True
            assert command.kind == "jump"


def test_project_and_editor_jumps_select_the_inspector() -> None:
    menus = _menus()
    controls = _make_controls(("layer_1",))
    project = command_by_id("project.settings", menus)
    editor = command_by_id("settings.editor", menus)
    assert project.enabled(CommandContext()) is True
    assert editor.enabled(CommandContext()) is True

    project.run(controls)
    assert controls.shell_focus.selected_id == "project"
    assert controls.shell_focus.region is ShellRegion.INSPECTOR

    editor.run(controls)
    assert controls.shell_focus.selected_id == "settings"
    assert controls.shell_focus.region is ShellRegion.INSPECTOR

    assert command_for_shortcut(pygame.K_COMMA, pygame.KMOD_CTRL) is editor
    assert command_for_shortcut(pygame.K_r, pygame.KMOD_CTRL).id == "project.render"


def test_docked_layout_check_follows_editor_setting_and_toggles(tmp_path: Path) -> None:
    menus = _menus()
    command = command_by_id("settings.docked_layout", menus)
    assert command.kind == "check"
    assert command.label == "Docked layout"
    assert command.shortcut is None
    assert command.enabled(CommandContext()) is True
    assert command.checked(CommandContext()) is False
    assert command.checked(CommandContext(shell_layout_mode="docked")) is True

    controls = _make_controls(("layer_1",))
    user_path = tmp_path / "user.yaml"
    controls.cfg.user_config_path = user_path
    selected_id = controls.shell_focus.selected_id
    inspector_cursor = controls.shell_focus.inspector_cursor
    focus_cursor = controls.focus_cursor
    assert controls.cfg.editor.shell_layout_mode == DEFAULT_SHELL_LAYOUT_MODE
    assert command.checked(command_context(controls)) is False

    command.run(controls)
    assert controls.cfg.editor.shell_layout_mode == "docked"
    assert command.checked(command_context(controls)) is True
    assert load_user_config(user_path).editor.shell_layout_mode == "docked"
    assert controls.shell_focus.selected_id == selected_id
    assert controls.shell_focus.inspector_cursor == inspector_cursor
    assert controls.focus_cursor is focus_cursor

    command.run(controls)
    assert controls.cfg.editor.shell_layout_mode == DEFAULT_SHELL_LAYOUT_MODE
    assert command.checked(command_context(controls)) is False
    assert load_user_config(user_path).editor.shell_layout_mode == (
        DEFAULT_SHELL_LAYOUT_MODE
    )
    assert controls.shell_focus.selected_id == selected_id
    assert controls.shell_focus.inspector_cursor == inspector_cursor
    assert controls.focus_cursor is focus_cursor


def test_disabled_run_does_not_call_a_controller() -> None:
    menus = _menus()
    controls = _fake_controls()
    for command in iter_commands(menus):
        if command.enabled(CommandContext()):
            continue
        command.run(controls)
    controls.prompt_save_config.assert_not_called()
    controls.request_quit.assert_not_called()
    controls.project_render.prompt.assert_not_called()
    controls.editor_mode.prompt_change_editor_mode.assert_not_called()
    controls.tap_sync.prompt_start.assert_not_called()
    controls.layer_lifecycle.prompt_add.assert_not_called()
    controls.layer_lifecycle.prompt_delete.assert_not_called()
    controls.navigator.select.assert_not_called()
    controls.navigator.activate.assert_not_called()


def test_save_and_render_honor_curation_solo_and_busy() -> None:
    menus = _menus()
    save = command_by_id("file.save", menus)
    render = command_by_id("project.render", menus)
    assert save.label_role is not None
    assert save.label_role(CommandContext()) == ACTION
    assert save.label_role(CommandContext(config_dirty=True)) == CONFIG_DIRTY
    assert save.enabled(CommandContext()) is True
    assert save.enabled(CommandContext(editor_mode="preset_curation")) is False
    assert save.enabled(CommandContext(solo_slot="slot_a")) is False
    assert render.enabled(CommandContext()) is True
    assert render.enabled(CommandContext(editor_mode="preset_curation")) is False
    assert render.enabled(CommandContext(render_busy=True)) is False

    blocked = _fake_controls(editor_mode="preset_curation")
    save.run(blocked)
    render.run(blocked)
    blocked.prompt_save_config.assert_not_called()
    blocked.project_render.prompt.assert_not_called()

    solo = _fake_controls(solo_slot="slot_a")
    save.run(solo)
    solo.prompt_save_config.assert_not_called()

    busy = _fake_controls(render_busy=True)
    render.run(busy)
    busy.project_render.prompt.assert_not_called()


def test_wired_run_calls_controllers() -> None:
    menus = _menus()
    controls = _fake_controls(help_visible=False)
    command_by_id("file.save", menus).run(controls)
    command_by_id("file.quit", menus).run(controls)
    command_by_id("project.render", menus).run(controls)
    command_by_id("layers.preset_curation", menus).run(controls)
    command_by_id("settings.measure_latency", menus).run(controls)
    controls.prompt_save_config.assert_called_once_with()
    controls.request_quit.assert_called_once_with()
    controls.project_render.prompt.assert_called_once_with()
    controls.editor_mode.prompt_change_editor_mode.assert_called_once_with()
    controls.tap_sync.prompt_start.assert_called_once_with()

    curation = command_by_id("layers.preset_curation", menus)
    assert curation.kind == "check"
    assert curation.checked is not None
    assert curation.checked(CommandContext()) is False
    assert curation.checked(CommandContext(editor_mode="preset_curation")) is True

    command_by_id("help.overlay", menus).run(controls)
    assert controls.session.help_visible is True
    command_by_id("help.shortcuts", menus).run(controls)
    assert controls.session.help_visible is False


def test_request_quit_clean_sets_pending_exit() -> None:
    controls = _make_controls(("layer_1",))
    assert controls.try_quit() is True
    assert controls.consume_pending_exit() is False

    controls.request_quit()
    assert not controls.modal_host.active
    assert controls.consume_pending_exit() is True
    assert controls.consume_pending_exit() is False


def test_request_quit_dirty_opens_unsaved_prompt_without_exiting() -> None:
    controls = _make_controls(("layer_1",))
    _mutate_dirty(controls)
    controls.request_quit()
    assert controls.pending_exit is False
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.kind == ModalKind.UNSAVED_QUIT

    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RETURN))
    assert controls.consume_pending_exit() is True


def test_layer_add_and_delete_follow_context_flags() -> None:
    add = command_by_id("layers.add")
    delete = command_by_id("layers.delete")
    assert add.enabled(CommandContext(can_add_layer=True)) is True
    assert add.enabled(CommandContext(can_add_layer=False)) is False
    assert (
        add.enabled(CommandContext(can_add_layer=True, editor_mode="preset_curation"))
        is False
    )
    assert (
        delete.enabled(CommandContext(selected_slot="layer_1", can_remove_layer=True))
        is True
    )
    assert delete.enabled(CommandContext(can_remove_layer=True)) is False
    assert (
        delete.enabled(CommandContext(selected_slot="layer_1", can_remove_layer=False))
        is False
    )
    assert (
        delete.enabled(
            CommandContext(
                selected_slot="layer_1",
                can_remove_layer=True,
                editor_mode="preset_curation",
            )
        )
        is False
    )

    curated = _fake_controls(
        can_add=True,
        can_remove=True,
        editor_mode="preset_curation",
        selected_id="layer:layer_1",
    )
    add.run(curated)
    delete.run(curated)
    curated.layer_lifecycle.prompt_add.assert_not_called()
    curated.layer_lifecycle.prompt_delete.assert_not_called()

    missing_slot = _fake_controls(can_add=True, can_remove=True, selected_id="layers")
    assert command_context(missing_slot).selected_slot is None
    delete.run(missing_slot)
    missing_slot.layer_lifecycle.prompt_delete.assert_not_called()

    ready = _fake_controls(
        can_add=True, can_remove=True, selected_id="layer:layer_1"
    )
    ctx = command_context(ready)
    assert ctx.selected_slot == "layer_1"
    assert ctx.can_add_layer is True
    assert ctx.can_remove_layer is True
    assert ctx.timeline_scope is False
    add.run(ready)
    delete.run(ready)
    ready.layer_lifecycle.prompt_add.assert_called_once_with()
    ready.layer_lifecycle.prompt_delete.assert_called_once_with("layer_1")

    recording = _fake_controls(recording=True)
    assert command_context(recording).timeline_scope is True


def test_command_context_reads_live_layer_flags() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))
    controls.shell_focus.selected_id = "project"
    ctx = command_context(controls)
    assert ctx.selected_slot is None
    assert ctx.can_add_layer is True
    assert ctx.can_remove_layer is True
    assert ctx.timeline_scope is False

    controls.shell_focus.selected_id = layer_node_id("layer_2")
    assert command_context(controls).selected_slot == "layer_2"

    controls.focus_cursor = TimelineFocus(1)
    assert command_context(controls).timeline_scope is True
    controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    )
    controls.session.timeline.recording = True
    assert command_context(controls).timeline_scope is True

    manager.can_add.return_value = False
    manager.can_remove.return_value = False
    ctx = command_context(controls)
    assert ctx.can_add_layer is False
    assert ctx.can_remove_layer is False

    plain = _make_controls(("layer_1",))
    plain.shell_focus.selected_id = layer_node_id("layer_1")
    ctx = command_context(plain)
    assert ctx.selected_slot == "layer_1"
    assert ctx.can_add_layer is False
    assert ctx.can_remove_layer is False


def test_menu_and_inspector_share_layer_add_and_delete() -> None:
    menus = _menus()
    controls, _manager = _make_controls_with_manager(("layer_1", "layer_2"))
    controls.shell_focus.selected_id = layer_node_id("layer_1")
    controls.layer_lifecycle.prompt_add = MagicMock()
    controls.layer_lifecycle.prompt_delete = MagicMock()
    add = command_by_id("layers.add", menus)
    delete = command_by_id("layers.delete", menus)
    assert add.run is command_by_id("layers.add").run
    assert delete.run is command_by_id("layers.delete").run

    add.run(controls)
    controls.layer_lifecycle.prompt_add.assert_called_once_with()
    delete.run(controls)
    controls.layer_lifecycle.prompt_delete.assert_called_once_with("layer_1")

    view = controls.build_view_state(paused=False)
    focus = controls.shell_focus
    add_row = next(
        row
        for row in build_inspector_rows(view, "layers", focus.collapsed, focus.opened)
        if row.command_id == "layers.add"
    )
    delete_row = next(
        row
        for row in build_inspector_rows(
            view, layer_node_id("layer_1"), focus.collapsed, focus.opened
        )
        if row.command_id == "layers.delete"
    )
    controls.layer_lifecycle.prompt_add.reset_mock()
    controls.layer_lifecycle.prompt_delete.reset_mock()
    controls.shell_focus.selected_id = "layers"
    controls.inspector.activate(add_row)
    controls.layer_lifecycle.prompt_add.assert_called_once_with()
    controls.layer_lifecycle.prompt_delete.assert_not_called()

    controls.layer_lifecycle.prompt_add.reset_mock()
    controls.shell_focus.selected_id = layer_node_id("layer_1")
    controls.inspector.activate(delete_row)
    controls.layer_lifecycle.prompt_delete.assert_called_once_with("layer_1")
    controls.layer_lifecycle.prompt_add.assert_not_called()


def test_render_menu_checks_mirror_flags_and_jumps_open_inspectors() -> None:
    menus = _menus()
    overlays = command_by_id("render.overlays", menus)
    post_fx = command_by_id("render.post_fx", menus)
    pattern = command_by_id("render.pattern_mask", menus)
    edit_overlays = command_by_id("render.edit_overlays", menus)
    edit_post_fx = command_by_id("render.edit_post_fx", menus)
    checks = (overlays, post_fx, pattern)
    jumps = (edit_overlays, edit_post_fx)

    assert all(command.kind == "check" and command.shortcut is None for command in checks)
    assert all(command.kind == "jump" and command.shortcut is None for command in jumps)
    assert overlays.checked(CommandContext(overlays_enabled=True)) is True
    assert overlays.checked(CommandContext()) is False
    assert post_fx.checked(CommandContext(post_fx_enabled=True)) is True
    assert post_fx.checked(CommandContext()) is False
    assert pattern.checked(CommandContext(pattern_mask_enabled=True)) is True
    assert pattern.checked(CommandContext()) is False

    visualizer = CommandContext()
    curation = CommandContext(editor_mode="preset_curation")
    for command in (*checks, *jumps):
        assert command.enabled(visualizer) is True
        assert command.enabled(curation) is False
    assert overlays.enabled(CommandContext(overlays_locked=True)) is False
    assert post_fx.enabled(CommandContext(post_fx_locked=True)) is False
    assert pattern.enabled(CommandContext(pattern_mask_locked=True)) is False
    assert edit_overlays.enabled(CommandContext(overlays_locked=True)) is True
    assert edit_post_fx.enabled(CommandContext(post_fx_locked=True)) is True

    live = _make_controls(("layer_1",))
    ctx = command_context(live)
    assert ctx.overlays_enabled is True
    assert ctx.post_fx_enabled is True
    assert ctx.pattern_mask_enabled is False
    assert ctx.overlays_locked is False
    assert ctx.post_fx_locked is False
    assert ctx.pattern_mask_locked is False
    assert overlays.checked(ctx) is True
    assert post_fx.checked(ctx) is True
    assert pattern.checked(ctx) is False
    live.session.render_overlays.opening_card.enabled = False
    assert overlays.checked(command_context(live)) is True
    live.session.render_overlays.closing_card.enabled = False
    assert overlays.checked(command_context(live)) is False
    live.session.render_post_fx.enabled = False
    live.session.render_pattern_mask.enabled = True
    assert post_fx.checked(command_context(live)) is False
    assert pattern.checked(command_context(live)) is True

    toggled = _make_controls(("layer_1",))
    overlays.run(toggled)
    assert toggled.session.render_overlays.opening_card.enabled is False
    assert toggled.session.render_overlays.closing_card.enabled is False
    post_fx.run(toggled)
    assert toggled.session.render_post_fx.enabled is False
    pattern.run(toggled)
    assert toggled.session.render_pattern_mask.enabled is True

    locked = _make_controls(("layer_1",))
    locked.session.render_overlays.locked = True
    locked.session.render_post_fx.locked = True
    locked.session.render_pattern_mask.locked = True
    locked_ctx = command_context(locked)
    assert locked_ctx.overlays_locked is True
    assert overlays.enabled(locked_ctx) is False
    assert post_fx.enabled(locked_ctx) is False
    assert pattern.enabled(locked_ctx) is False
    assert edit_overlays.enabled(locked_ctx) is True
    overlays.run(locked)
    post_fx.run(locked)
    pattern.run(locked)
    assert locked.session.render_overlays.opening_card.enabled is True
    assert locked.session.render_post_fx.enabled is True
    assert locked.session.render_pattern_mask.enabled is False

    curated = _make_controls(("layer_1",))
    curated.session.settings.editor_mode = "preset_curation"
    curated.shell_focus.selected_id = "project"
    curated.shell_focus.region = ShellRegion.NAVIGATOR
    assert command_context(curated).editor_mode == "preset_curation"
    overlays.run(curated)
    edit_overlays.run(curated)
    edit_post_fx.run(curated)
    assert curated.session.render_overlays.opening_card.enabled is True
    assert curated.shell_focus.selected_id == "project"
    assert curated.shell_focus.region is ShellRegion.NAVIGATOR

    focused = _make_controls(("layer_1",))
    edit_overlays.run(focused)
    assert focused.shell_focus.selected_id == "render.overlays"
    assert focused.shell_focus.region is ShellRegion.INSPECTOR
    edit_post_fx.run(focused)
    assert focused.shell_focus.selected_id == "render.post_fx"
    assert focused.shell_focus.region is ShellRegion.INSPECTOR


def test_layer_jumps_select_the_layer_inspector() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    jump = layer_focus_commands((("layer_2", "pad"),))[0]
    assert jump.enabled(CommandContext()) is True
    assert jump.id == "layers.focus.layer_2"
    assert jump.label == "Layer 1  pad"
    assert jump.shortcut == "1"
    jump.run(controls)
    assert controls.shell_focus.selected_id == layer_node_id("layer_2")
    assert controls.shell_focus.region is ShellRegion.INSPECTOR


def test_ctrl_l_and_layer_digits_follow_timeline_scope() -> None:
    slots = tuple((f"layer_{number}", f"stem-{number}") for number in range(1, 9))
    menus = build_menus(slots)
    assert command_for_shortcut(pygame.K_l, pygame.KMOD_CTRL, menus).id == "layers.add"
    assert (
        command_for_shortcut(
            pygame.K_l, pygame.KMOD_CTRL, menus, timeline_scope=True
        ).id
        == "layers.add"
    )
    for number in range(1, 9):
        key = getattr(pygame, f"K_{number}")
        command = command_for_shortcut(key, 0, menus)
        assert command is not None
        assert command.id == f"layers.focus.layer_{number}"
        assert command_for_shortcut(key, 0, menus, timeline_scope=True) is None
    assert command_for_shortcut(pygame.K_1, 0) is None
    assert command_for_shortcut(pygame.K_r, 0, menus) is None
    assert command_for_shortcut(pygame.K_r, pygame.KMOD_CTRL, menus).id == "project.render"
    assert [
        command.id
        for command in iter_commands(menus)
        if command.shortcut == "Ctrl+R"
    ] == ["project.render"]


def test_add_selects_new_layer_and_delete_selects_neighbour() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))
    controls.shell_focus.selected_id = "layers"
    controls.shell_focus.nav_expanded.discard("layers")

    def add_layer() -> str:
        slot = "layer_3"
        controls.session.layer_z_order.append(slot)
        controls.session.layers[slot] = LayerRuntime(
            playlist=_make_playlist(slot),
            browse_floor=Path("/tmp/presets") / slot,
            stem="bass",
            opacity_pct=50,
        )
        return slot

    manager.add_layer.side_effect = add_layer
    controls.layer_lifecycle.confirm_add()
    assert controls.shell_focus.selected_id == layer_node_id("layer_3")
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert "layers" in controls.shell_focus.nav_expanded

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    controls.shell_focus.selected_id = layer_node_id("layer_2")
    controls.layer_lifecycle.confirm_delete("layer_2")
    assert controls.shell_focus.selected_id == layer_node_id("layer_3")
    assert controls.shell_focus.region is ShellRegion.INSPECTOR

    controls.layer_lifecycle.confirm_delete("layer_3")
    assert controls.shell_focus.selected_id == layer_node_id("layer_1")

    controls.layer_lifecycle.confirm_delete("layer_1")
    assert controls.shell_focus.selected_id == "layers"
    assert controls.shell_focus.region is ShellRegion.INSPECTOR


def test_show_strip_toggles_panel_and_is_disabled_while_recording_or_curating() -> None:
    show = command_by_id("timeline.show_strip")
    assert show.kind == "check"
    assert show.label == "Show timeline strip"
    assert show.shortcut == "T"
    assert command_for_shortcut(pygame.K_t, 0) is show
    assert command_for_shortcut(pygame.K_t, 0, timeline_scope=True) is show
    assert command_for_shortcut(pygame.K_r, 0) is None
    assert command_for_shortcut(pygame.K_r, pygame.KMOD_CTRL).id == "project.render"
    assert [command.id for command in iter_commands(MENUS) if command.shortcut == "T"] == [
        "timeline.show_strip"
    ]

    assert show.checked(CommandContext(timeline_panel_open=False)) is False
    assert show.checked(CommandContext(timeline_panel_open=True)) is True
    assert show.enabled(CommandContext()) is True
    assert show.enabled(CommandContext(timeline_recording=True)) is False
    assert show.enabled(CommandContext(editor_mode="preset_curation")) is False

    closed = _make_controls(("layer_1",))
    assert command_context(closed).timeline_panel_open is False
    assert show.checked(command_context(closed)) is False
    show.run(closed)
    assert closed.session.timeline.panel_open is True
    assert isinstance(closed.focus_cursor, TimelineFocus)
    assert command_context(closed).timeline_panel_open is True
    assert show.checked(command_context(closed)) is True
    show.run(closed)
    assert closed.session.timeline.panel_open is False
    assert isinstance(closed.focus_cursor, TimelineFocus)
    assert closed.shell_focus.region is ShellRegion.NAVIGATOR

    recording = _make_controls(("layer_1",))
    recording.session.timeline.recording = True
    recording.session.timeline.panel_open = True
    assert command_context(recording).timeline_recording is True
    assert show.enabled(command_context(recording)) is False
    show.run(recording)
    assert recording.session.timeline.panel_open is True
    assert not isinstance(recording.focus_cursor, TimelineFocus)

    curated = _make_controls(("layer_1",))
    curated.session.settings.editor_mode = "preset_curation"
    show.run(curated)
    assert curated.session.timeline.panel_open is False


def test_undo_cut_stays_disabled_and_run_is_a_noop() -> None:
    undo = command_by_id("timeline.undo_cut")
    assert undo.enabled(CommandContext()) is False
    sentinel = MagicMock()
    undo.run(sentinel)
    assert sentinel.mock_calls == []


def test_timeline_actions_share_run_with_the_inspector() -> None:
    controls = _make_controls(("layer_1",))
    controls.prompt_apply_timeline_preset = MagicMock()
    controls.prompt_reset_timeline = MagicMock()
    controls.prompt_snap_cues = MagicMock()
    actions = (
        ("timeline.apply_preset", RowKind.TIMELINE_PRESETS, controls.prompt_apply_timeline_preset),
        ("timeline.reset", RowKind.TIMELINE_RESET, controls.prompt_reset_timeline),
        ("timeline.snap_cues", RowKind.TIMELINE_SNAP_CUES, controls.prompt_snap_cues),
    )
    visualizer = CommandContext()
    locked = CommandContext(timeline_locked=True)
    recording = CommandContext(timeline_recording=True)
    curated = CommandContext(editor_mode="preset_curation")
    for command_id, _kind, _prompt in actions:
        command = command_by_id(command_id)
        assert command.enabled(visualizer) is True
        assert command.enabled(recording) is True
        assert command.enabled(locked) is False
        assert command.enabled(curated) is False

    view = controls.build_view_state(paused=False)
    opened = frozenset({InspectorGroupKey(RowKind.TIMELINE_BEAT_BAR_GRID_HEADER)})
    rows = build_inspector_rows(view, "render.timeline", frozenset(), opened)
    by_id = {row.command_id: row for row in rows if row.command_id}
    assert set(by_id) == {"timeline.apply_preset", "timeline.reset", "timeline.snap_cues"}
    assert all(row.descriptor is None for row in by_id.values())
    descriptor_kinds = {
        row.descriptor.kind for row in rows if row.descriptor is not None
    }
    assert RowKind.TIMELINE_PRESETS not in descriptor_kinds
    assert RowKind.TIMELINE_RESET not in descriptor_kinds
    assert RowKind.TIMELINE_SNAP_CUES not in descriptor_kinds

    controls.shell_focus.region = ShellRegion.INSPECTOR
    controls.shell_focus.selected_id = "render.timeline"
    for command_id, kind, prompt in actions:
        prompt.reset_mock()
        command_by_id(command_id).run(controls)
        prompt.assert_called_once_with()
        prompt.reset_mock()
        controls.inspector.activate(by_id[command_id])
        prompt.assert_called_once_with()
        prompt.reset_mock()
        assert apply_field_action(controls, RowDescriptor(kind)) is True
        prompt.assert_called_once_with()
        controls.shell_focus.inspector_command_id = command_id
        followed = help_focus_descriptor(
            RowDescriptor(RowKind.RENDER_TIMELINE_HEADER),
            controls.shell_focus,
        )
        assert followed == RowDescriptor(kind)

    controls.session.timeline.locked = True
    assert command_context(controls).timeline_locked is True
    for command_id, kind, prompt in actions:
        prompt.reset_mock()
        command_by_id(command_id).run(controls)
        controls.inspector.activate(by_id[command_id])
        apply_field_action(controls, RowDescriptor(kind))
        prompt.assert_not_called()

    controls.session.timeline.locked = False
    controls.session.settings.editor_mode = "preset_curation"
    for command_id, kind, prompt in actions:
        prompt.reset_mock()
        command_by_id(command_id).run(controls)
        controls.inspector.activate(by_id[command_id])
        apply_field_action(controls, RowDescriptor(kind))
        prompt.assert_not_called()


def test_song_markers_jump_opens_the_inspector() -> None:
    jump = command_by_id("timeline.song_markers")
    assert jump.kind == "jump"
    assert jump.label == "Song markers"
    assert jump.enabled(CommandContext()) is True
    assert jump.enabled(CommandContext(timeline_locked=True)) is True
    assert jump.enabled(CommandContext(editor_mode="preset_curation")) is False

    controls = _make_controls(("layer_1",))
    jump.run(controls)
    assert controls.shell_focus.selected_id == "song_markers"
    assert controls.shell_focus.region is ShellRegion.INSPECTOR

    curated = _make_controls(("layer_1",))
    curated.session.settings.editor_mode = "preset_curation"
    before_id = curated.shell_focus.selected_id
    before_region = curated.shell_focus.region
    jump.run(curated)
    assert curated.shell_focus.selected_id == before_id
    assert curated.shell_focus.region is before_region


def test_inspector_only_timeline_actions_are_not_menu_commands() -> None:
    labels = [command.label for command in iter_commands(MENUS)]
    assert "Apply to Cues" not in labels
    assert "Remove from Cues" not in labels
    assert labels.count("Snap cues") == 1

    controls = _make_controls(("layer_1",))
    controls.session.song_markers.times = [10.0, 40.0]
    prompts = (
        (RowKind.TIMELINE_APPLY_SOFT_CUTS, "prompt_apply_soft_cuts"),
        (RowKind.TIMELINE_APPLY_HARD_CUTS, "prompt_apply_hard_cuts"),
        (RowKind.TIMELINE_REMOVE_SOFT_CUTS, "prompt_remove_timeline_cuts"),
        (RowKind.TIMELINE_REMOVE_HARD_CUTS, "prompt_remove_timeline_cuts"),
        (RowKind.TIMELINE_SNAP_TO_SONG_MARKERS, "prompt_snap_cues_to_song_markers"),
    )
    for kind, method_name in prompts:
        method = MagicMock()
        setattr(controls, method_name, method)
        desc = RowDescriptor(kind)
        row_spec(kind).apply_action(controls, desc)
        method.assert_called_once_with()
        controls.session.timeline.locked = True
        method.reset_mock()
        row_spec(kind).apply_action(controls, desc)
        method.assert_not_called()
        controls.session.timeline.locked = False

    view = controls.build_view_state(paused=False)
    marker_rows = build_inspector_rows(view, "song_markers", frozenset())
    snap = next(
        row
        for row in marker_rows
        if row.descriptor is not None
        and row.descriptor.kind is RowKind.TIMELINE_SNAP_TO_SONG_MARKERS
    )
    assert snap.command_id is None
    marker = next(
        row
        for row in marker_rows
        if row.descriptor is not None
        and row.descriptor.kind is RowKind.SONG_MARKER_ITEM
    )
    assert marker.command_id is None

    controls.seek_to = MagicMock()
    marker_desc = RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=1)
    row_spec(RowKind.SONG_MARKER_ITEM).apply_action(controls, marker_desc)
    controls.seek_to.assert_called_once_with(40.0)
    controls.session.timeline.locked = True
    controls.seek_to.reset_mock()
    row_spec(RowKind.SONG_MARKER_ITEM).apply_action(controls, marker_desc)
    controls.seek_to.assert_not_called()
    controls.session.timeline.locked = False
    controls.seek_to.reset_mock()
    row_spec(RowKind.SONG_MARKER_ITEM).apply_action(
        controls, RowDescriptor(RowKind.SONG_MARKER_ITEM)
    )
    controls.seek_to.assert_not_called()
