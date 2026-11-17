"""Preview right-click menu items, through real ``TuningControls``."""

from __future__ import annotations

from pathlib import Path

from cleave.config_schema.editor import EDITOR_PREVIEW_QUALITIES
from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
from cleave.viz.preview_context_menu import (
    play_fullscreen_menu,
    preview_menu,
    preview_menu_entries,
)
from tests.support.viz import make_controls


class _Transport:
    def __init__(self, paused: bool = True) -> None:
        self.paused = paused
        self.toggles = 0

    def toggle_transport(self) -> None:
        self.toggles += 1
        self.paused = not self.paused


def _entries(controls, transport: _Transport | None = None):
    return {
        entry.id: entry
        for entry in preview_menu_entries(controls, transport or _Transport())
        if isinstance(entry, (ContextMenuItem, ContextSubmenu))
    }


def test_menu_lists_the_agreed_items_in_order(tmp_path: Path) -> None:
    controls = make_controls(("layer_1",), project_dir=tmp_path)
    assert list(_entries(controls)) == [
        "preview.transport",
        "preview.solo",
        "preview.enabled.pattern_mask",
        "preview.quality",
        "preview.grab_still",
        "view.play_fullscreen",
        "view.fullscreen_editor",
    ]


def test_transport_label_follows_playback_and_toggles() -> None:
    controls = make_controls(("layer_1",))
    transport = _Transport(paused=True)
    provider = preview_menu(controls, transport)
    item = next(e for e in provider() if getattr(e, "id", "") == "preview.transport")
    assert item.label == "Play"
    assert item.shortcut == "Space"
    item.run()
    assert transport.toggles == 1
    item = next(e for e in provider() if getattr(e, "id", "") == "preview.transport")
    assert item.label == "Pause"


def test_solo_submenu_checks_none_then_the_soloed_layer() -> None:
    controls = make_controls(("layer_1", "layer_2"))
    solo = _entries(controls)["preview.solo"]
    assert [item.id for item in solo.items] == [
        "preview.solo.none",
        "preview.solo.layer_1",
        "preview.solo.layer_2",
    ]
    assert solo.items[0].checked is True
    solo.items[2].run()
    assert controls.session.solo_slot == "layer_2"

    solo = _entries(controls)["preview.solo"]
    assert solo.items[0].checked is False
    assert solo.items[2].checked is True
    solo.items[0].run()
    assert controls.session.solo_slot is None


def test_block_item_toggles_enabled_and_greys_out_when_locked() -> None:
    controls = make_controls(("layer_1",))
    item = _entries(controls)["preview.enabled.pattern_mask"]
    was = controls.session.pattern_mask.enabled
    assert item.checked is was
    item.run()
    assert controls.session.pattern_mask.enabled is not was

    controls.session.pattern_mask.locked = True
    item = _entries(controls)["preview.enabled.pattern_mask"]
    assert item.enabled is False
    assert item.hint == "Locked: unlock to change"


def test_quality_submenu_checks_the_setting_and_sets_it() -> None:
    controls = make_controls(("layer_1",))
    quality = _entries(controls)["preview.quality"]
    assert [item.label for item in quality.items] == list(EDITOR_PREVIEW_QUALITIES)
    current = controls.cfg.editor.preview_quality
    assert [item.checked for item in quality.items] == [
        mode == current for mode in EDITOR_PREVIEW_QUALITIES
    ]
    quality.items[0].run()
    assert controls.cfg.editor.preview_quality == EDITOR_PREVIEW_QUALITIES[0]


def test_curation_leaves_out_solo_and_block_items(tmp_path: Path) -> None:
    controls = make_controls(("layer_1",), project_dir=tmp_path)
    controls.session.settings.editor_mode = "preset_curation"
    assert list(_entries(controls)) == [
        "preview.transport",
        "preview.quality",
        "preview.grab_still",
        "view.play_fullscreen",
        "view.fullscreen_editor",
    ]


def test_grab_still_needs_a_project_folder_and_greys_out_while_busy(
    tmp_path: Path,
) -> None:
    item = _entries(make_controls(("layer_1",)))["preview.grab_still"]
    assert item.enabled is False
    assert item.hint == "No project folder to save into"

    controls = make_controls(("layer_1",), project_dir=tmp_path)
    item = _entries(controls)["preview.grab_still"]
    assert item.enabled is True
    item.run()
    item = _entries(controls)["preview.grab_still"]
    assert item.enabled is False
    assert item.hint == "Capturing a still"


def test_play_fullscreen_menu_plays_pauses_and_exits() -> None:
    controls = make_controls(("layer_1",))
    transport = _Transport(paused=False)
    items = play_fullscreen_menu(controls, transport)()
    assert [item.id for item in items] == [
        "preview.transport",
        "play_fullscreen.exit",
    ]
    transport_item, exit_item = items
    assert transport_item.label == "Pause"
    assert exit_item.label == "Exit Full Screen"
    assert exit_item.shortcut == "Esc"

    transport_item.run()
    assert transport.paused is True
    controls.window.play_fullscreen = True
    exit_item.run()
    assert controls.window.consume_play_fullscreen() is False
