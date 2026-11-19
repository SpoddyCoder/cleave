"""Preset browser controller: preview debounce, keep, revert, and key routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pygame
import pytest

from cleave.preset_library import PresetLibrary
from cleave.preset_playlist import preset_browse_floor, scan_preset_playlist
from cleave.viz.layer_mutations import LayerMutations
from cleave.viz.preset_browser_controls import PREVIEW_DELAY_SEC, PresetBrowserControls
from cleave.viz.preset_browser_surface import BrowserPointerIntent, BrowserPointerKind
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import apply_field_action
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.viz import keydown, make_controls


def _milk(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(path.as_posix(), encoding="utf-8")
    return path.resolve()


class _Rig:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.a1 = _milk(root / "Pack" / "A" / "a1.milk")
        self.a2 = _milk(root / "Pack" / "A" / "a2.milk")
        self.b1 = _milk(root / "Pack" / "B" / "b1.milk")
        self.library = PresetLibrary.in_memory()
        self.library.index(self.root)
        playlist = scan_preset_playlist(self.a1, catalog=self.library)
        self.layer = LayerRuntime(
            playlist=playlist,
            browse_floor=preset_browse_floor(self.a1, self.root),
            stem="drums",
            opacity_pct=50,
        )
        self.session = TuningSession(layer_z_order=["layer_1"], layers={"layer_1": self.layer})
        self.bindings = MagicMock()
        self._loaded: list[Path | None] = []
        self.bindings.on_preset_change.side_effect = (
            lambda _slot, playlist: self._loaded.append(playlist.current)
        )
        self.mutations = LayerMutations(
            self.session,
            preset_root=self.root,
            duration_sec=60.0,
            get_layer_bindings=lambda: self.bindings,
            on_notification=lambda _message: None,
        )
        self.text_input = MagicMock()
        self.shared = False
        self.controls = PresetBrowserControls(
            self.session,
            self.root,
            self.library,
            self.mutations,
            start_text_input=self.text_input.start,
            stop_text_input=self.text_input.stop,
            text_input_shared=lambda: self.shared,
        )

    def loaded(self) -> list[Path | None]:
        return list(self._loaded)

    def key(self, key: int, *, mod: int = 0) -> bool:
        return self.controls.handle_keydown(keydown(key, mod=mod))


@pytest.fixture
def rig(tmp_path: Path) -> _Rig:
    return _Rig(tmp_path / "presets")


def test_open_starts_on_the_playing_preset_and_text_input(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    assert rig.controls.active
    browser = rig.controls.browser
    assert browser is not None
    assert browser.selected_preset() == rig.a1
    assert browser.title == "Browse presets: Layer 1"
    rig.text_input.start.assert_called_once()


def test_preview_waits_for_the_delay(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.key(pygame.K_DOWN)
    rig.controls.tick(PREVIEW_DELAY_SEC / 2)
    assert rig.loaded() == []
    rig.controls.tick(PREVIEW_DELAY_SEC)
    assert rig.loaded() == [rig.a2]
    assert rig.layer.playlist.current == rig.a2
    assert rig.layer.auto_preset_path == rig.a2


def test_fast_moves_preview_only_where_the_selection_rests(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.key(pygame.K_DOWN)
    rig.controls.tick(0.05)
    rig.key(pygame.K_UP)
    rig.controls.tick(0.05)
    rig.key(pygame.K_DOWN)
    rig.controls.tick(PREVIEW_DELAY_SEC)
    assert rig.loaded() == [rig.a2]


def test_enter_keeps_the_preset_in_its_own_folder(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.GOTO_CRUMB, 0))
    rig.controls.handle_text_input("b1")
    rig.key(pygame.K_RETURN)
    assert not rig.controls.active
    assert rig.loaded() == [rig.b1]
    assert rig.layer.playlist.current_dir == rig.b1.parent
    assert rig.layer.playlist.current == rig.b1
    assert rig.layer.browse_floor == rig.root / "Pack"
    rig.text_input.stop.assert_called_once()


def test_escape_restores_the_starting_folder_and_preset(rig: _Rig) -> None:
    before = rig.layer.playlist
    rig.controls.open("layer_1")
    rig.key(pygame.K_DOWN)
    rig.controls.tick(PREVIEW_DELAY_SEC)
    assert rig.layer.playlist.current == rig.a2

    rig.key(pygame.K_ESCAPE)
    assert not rig.controls.active
    assert rig.layer.playlist is before
    assert rig.layer.playlist.current == rig.a1
    assert rig.layer.playlist.current_dir == rig.a1.parent
    assert rig.loaded() == [rig.a2, rig.a1]


def test_escape_without_a_preview_leaves_the_layer_alone(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.key(pygame.K_DOWN)
    rig.key(pygame.K_ESCAPE)
    assert not rig.controls.active
    assert rig.loaded() == []


def test_escape_clears_a_filter_before_closing(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.controls.handle_text_input("a2")
    rig.key(pygame.K_ESCAPE)
    assert rig.controls.active
    assert rig.controls.browser.filter_text == ""


def test_letters_are_swallowed_and_shortcuts_pass_through(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    assert rig.key(pygame.K_h)
    assert not rig.key(pygame.K_s, mod=pygame.KMOD_LCTRL)
    assert not rig.key(pygame.K_F11)
    assert not rig.key(pygame.K_SPACE)
    rig.controls.handle_text_input("a")
    assert rig.key(pygame.K_SPACE)


def test_closed_browser_takes_no_keys(rig: _Rig) -> None:
    assert not rig.key(pygame.K_DOWN)
    assert not rig.controls.handle_text_input("x")


def test_text_input_stays_on_when_a_dialog_owns_it(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.shared = True
    rig.controls.cancel()
    rig.text_input.stop.assert_not_called()


def test_double_click_on_a_preset_keeps_it(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    browser = rig.controls.browser
    index = next(i for i, row in enumerate(browser.rows) if row.path == rig.a2)
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.OPEN_ROW, index))
    assert not rig.controls.active
    assert rig.layer.playlist.current == rig.a2


def test_crumb_click_goes_up(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.GOTO_CRUMB, 0))
    assert rig.controls.browser.at_top


def test_curation_change_refreshes_the_list(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.library.set_blacklisted(rig.a2, True)
    rig.controls.tick(0.0)
    paths = [row.path for row in rig.controls.browser.rows]
    assert rig.a2 not in paths


def test_removed_layer_closes_the_browser(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    del rig.session.layers["layer_1"]
    rig.controls.tick(0.0)
    assert not rig.controls.active


def test_enter_on_the_preset_row_opens_the_browser() -> None:
    controls = make_controls(("layer_1",))
    apply_field_action(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"))
    assert controls.preset_browser.active
    assert controls.preset_browser.slot == "layer_1"


def test_locked_layer_does_not_open_the_browser() -> None:
    controls = make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    apply_field_action(controls, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"))
    assert not controls.preset_browser.active


def test_project_picker_closes_the_browser() -> None:
    controls = make_controls(("layer_1",))
    controls.preset_browser.open("layer_1")
    controls.project_switch.prompt_open()
    controls.tick(0.0)
    assert not controls.preset_browser.active
