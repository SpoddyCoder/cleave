"""Command registry: taxonomy, resolved shortcuts, and wired controllers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame

from cleave.viz.commands import (
    MENUS,
    CommandContext,
    MenuSeparator,
    build_menus,
    command_by_id,
    command_for_shortcut,
    iter_commands,
    layer_focus_commands,
)
from cleave.viz.modal import ModalKind
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.theme import ACTION, CONFIG_DIRTY
from tests.cleave.viz.test_controls import _keydown, _make_controls, _mutate_dirty

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
    "render.edit_overlays",
    "render.edit_post_fx",
    "timeline.song_markers",
    "layers.add",
    "layers.delete",
    "render.overlays",
    "render.post_fx",
    "render.pattern_mask",
    "timeline.show_strip",
    "timeline.apply_preset",
    "timeline.reset",
    "timeline.snap_cues",
)

_DISABLED_JUMP_IDS = (
    "render.edit_overlays",
    "render.edit_post_fx",
    "timeline.song_markers",
)
_ENABLED_JUMP_IDS = (
    "project.settings",
    "settings.editor",
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
):
    return SimpleNamespace(
        session=SimpleNamespace(
            settings=SimpleNamespace(editor_mode=editor_mode),
            solo_slot=solo_slot,
            help_visible=help_visible,
        ),
        config_dirty=config_dirty,
        project_render=SimpleNamespace(busy=render_busy, prompt=MagicMock()),
        prompt_save_config=MagicMock(),
        request_quit=MagicMock(),
        editor_mode=SimpleNamespace(prompt_change_editor_mode=MagicMock()),
        tap_sync=SimpleNamespace(prompt_start=MagicMock()),
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
    assert _row_ids(menus[5]) == ["settings.editor", "settings.measure_latency"]
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
    assert command_for_shortcut(pygame.K_l, pygame.KMOD_CTRL) is None
    assert command_for_shortcut(pygame.K_t, 0) is None
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
    for command_id in _DISABLED_JUMP_IDS:
        command = command_by_id(command_id, menus)
        assert command.kind == "jump"
        assert command.enabled(ctx) is False
    for command_id in _ENABLED_JUMP_IDS:
        command = command_by_id(command_id, menus)
        assert command.kind == "jump"
        assert command.enabled(ctx) is True
    for command in iter_commands(menus):
        if command.id.startswith("layers.focus."):
            assert command.enabled(ctx) is False


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


def test_disabled_run_does_not_call_a_controller() -> None:
    menus = _menus()
    controls = MagicMock()
    for command in iter_commands(menus):
        if command.enabled(CommandContext()):
            continue
        command.run(controls)
    assert controls.mock_calls == []


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
