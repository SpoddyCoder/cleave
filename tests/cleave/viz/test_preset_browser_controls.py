"""Preset browser controller: preview debounce, keep, revert, and key routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pygame
import pytest

from cleave.preset_library import PresetLibrary
from cleave.preset_playlist import preset_browse_floor, scan_preset_playlist
from cleave.preset_list_entry import PresetListEntry
from cleave.viz.edit_history import EditHistory
from cleave.viz.layer_mutations import LayerMutations
from cleave.viz.modal import ModalHost
from cleave.viz.preset_list_controls import PresetListController
from cleave.viz.preset_browser_controls import PREVIEW_DELAY_SEC, PresetBrowserControls
from cleave.viz.preset_browser_surface import BrowserPointerIntent, BrowserPointerKind
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import apply_field_action, apply_field_double_click, row_spec
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.viz import keydown, make_controls


def _milk(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(path.as_posix(), encoding="utf-8")
    return path.resolve()


class _Rig:
    def __init__(self, root: Path, *, synchronous: bool = True) -> None:
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
            synchronous=synchronous,
        )

    def loaded(self) -> list[Path | None]:
        return list(self._loaded)

    def key(self, key: int, *, mod: int = 0) -> bool:
        return self.controls.handle_keydown(keydown(key, mod=mod))

    def search(self, text: str) -> None:
        """Up to the filter, Enter, type, Enter."""
        browser = self.controls.browser
        assert browser is not None
        browser.focus_filter()
        self.key(pygame.K_RETURN)
        self.controls.handle_text_input(text)
        self.key(pygame.K_RETURN)


@pytest.fixture
def rig(tmp_path: Path) -> _Rig:
    return _Rig(tmp_path / "presets")


def test_open_starts_on_the_playing_preset(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    assert rig.controls.active
    browser = rig.controls.browser
    assert browser is not None
    assert browser.selected_preset() == rig.a1
    assert browser.title == "Browse presets: Layer 1"
    rig.text_input.start.assert_not_called()


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
    rig.search("b1")
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
    rig.search("a2")
    assert rig.controls.browser.filter_text == "a2"
    rig.key(pygame.K_ESCAPE)
    assert rig.controls.active
    assert rig.controls.browser.filter_text == ""


def test_letters_are_swallowed_and_shortcuts_pass_through(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    assert rig.key(pygame.K_l)
    assert not rig.key(pygame.K_h)
    assert not rig.key(pygame.K_s, mod=pygame.KMOD_LCTRL)
    assert not rig.key(pygame.K_F11)
    assert not rig.key(pygame.K_SPACE)
    assert not rig.controls.handle_text_input("a")


def test_editing_the_filter_takes_space_and_h_and_text_input(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.key(pygame.K_HOME)
    rig.key(pygame.K_UP)
    rig.key(pygame.K_RETURN)
    browser = rig.controls.browser
    assert browser.editing
    rig.text_input.start.assert_called_once()
    assert rig.key(pygame.K_SPACE)
    assert rig.key(pygame.K_h)
    assert not rig.key(pygame.K_s, mod=pygame.KMOD_LCTRL)
    assert rig.controls.handle_text_input("a")
    rig.key(pygame.K_BACKSPACE)
    assert browser.draft == ""
    rig.key(pygame.K_ESCAPE)
    assert not browser.editing
    assert rig.controls.active
    rig.text_input.stop.assert_called_once()


def test_click_on_the_filter_edits_and_a_click_away_searches(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.EDIT_FILTER))
    browser = rig.controls.browser
    assert browser.editing
    rig.controls.handle_text_input("a2")
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.SELECT_ROW, 0))
    assert not browser.editing
    assert browser.filter_text == "a2"
    assert browser.selected_preset() == rig.a2


def test_closed_browser_takes_no_keys(rig: _Rig) -> None:
    assert not rig.key(pygame.K_DOWN)
    assert not rig.controls.handle_text_input("x")


def test_text_input_stays_on_when_a_dialog_owns_it(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.EDIT_FILTER))
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


def test_listings_build_on_a_worker_and_preview_once_shown(tmp_path: Path) -> None:
    rig = _Rig(tmp_path / "presets", synchronous=False)
    rig.controls.open("layer_1")
    browser = rig.controls.browser
    rig.controls.wait_for_listing()
    assert not browser.loading
    assert browser.selected_preset() == rig.a1

    rig.key(pygame.K_LEFT)
    rig.controls.wait_for_listing()
    assert browser.selected_row.path == rig.a1.parent
    rig.key(pygame.K_RIGHT)
    rig.controls.wait_for_listing()
    rig.controls.tick(PREVIEW_DELAY_SEC)
    assert rig.loaded() == []
    rig.key(pygame.K_DOWN)
    rig.controls.tick(PREVIEW_DELAY_SEC)
    assert rig.loaded() == [rig.a2]


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


def _controls_with_list_entry(tmp_path: Path):
    preset = _milk(tmp_path / "Pack" / "a.milk")
    controls = make_controls(("layer_1",), project_dir=tmp_path / "project")
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_list = [PresetListEntry(str(preset))]
    return controls, RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=0
    )


def test_double_click_on_a_list_entry_opens_the_browser_to_replace_it(
    tmp_path: Path,
) -> None:
    controls, entry = _controls_with_list_entry(tmp_path)
    spec = row_spec(RowKind.TRACK_PRESET_LIST_ITEM)
    assert spec.double_click_action is not None
    assert spec.activate_on_double_click is False
    assert apply_field_double_click(controls, entry) is True
    assert controls.preset_browser.active
    assert controls.preset_browser.slot == "layer_1"
    assert controls.preset_browser.replace_index == 0


def test_double_click_on_a_locked_list_entry_does_nothing(tmp_path: Path) -> None:
    controls, entry = _controls_with_list_entry(tmp_path)
    controls.session.layers["layer_1"].locked = True
    assert apply_field_double_click(controls, entry) is True
    assert not controls.preset_browser.active


def test_enter_on_a_list_entry_still_auditions(tmp_path: Path) -> None:
    controls, entry = _controls_with_list_entry(tmp_path)
    controls.preset_list.audition = MagicMock()
    apply_field_action(controls, entry)
    controls.preset_list.audition.assert_called_once_with("layer_1", 0)
    assert not controls.preset_browser.active


def test_project_picker_closes_the_browser() -> None:
    controls = make_controls(("layer_1",))
    controls.preset_browser.open("layer_1")
    controls.project_switch.prompt_open()
    controls.tick(0.0)
    assert not controls.preset_browser.active


def test_fast_typing_runs_one_listing_at_a_time_and_ends_on_the_last(tmp_path: Path) -> None:
    rig = _Rig(tmp_path / "presets", synchronous=False)
    rig.controls.open("layer_1")
    rig.controls.wait_for_listing()
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.GOTO_CRUMB, 0))
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.EDIT_FILTER))
    for letter in "b1":
        rig.controls.handle_text_input(letter)
        assert len(rig.controls._jobs) <= 1
    rig.controls.wait_for_listing()
    browser = rig.controls.browser
    assert browser.filter_text == "b1"
    assert [row.path for row in browser.rows] == [rig.b1]
    assert browser.editing


def test_directory_row_opens_the_browser_when_there_are_no_subfolders() -> None:
    controls = make_controls(("layer_1",))
    assert not controls.layer_mutations.can_enter_directory("layer_1")
    apply_field_action(controls, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"))
    assert controls.preset_browser.active


def test_can_enter_directory_and_browse_directory(rig: _Rig) -> None:
    pack = rig.root / "Pack"
    rig.mutations.browse_directory("layer_1", pack)
    assert rig.layer.playlist.current_dir == pack
    assert rig.mutations.can_enter_directory("layer_1")
    assert rig.loaded() == [None]

    rig.mutations.browse_directory("layer_1", rig.b1.parent)
    assert rig.layer.playlist.current == rig.b1
    assert rig.layer.browse_floor == pack
    assert not rig.mutations.can_enter_directory("layer_1")
    rig.mutations.browse_directory("layer_1", rig.b1.parent)
    assert rig.loaded() == [None, rig.b1]


def test_directory_crumbs_run_from_the_pack_down(rig: _Rig) -> None:
    from cleave.viz.tuning_view_state import directory_crumbs

    crumbs = directory_crumbs(rig.layer.playlist, rig.root, "Pack/A/")
    assert [(crumb.label, crumb.path) for crumb in crumbs] == [
        ("Pack", rig.root / "Pack"),
        ("A", rig.root / "Pack" / "A"),
    ]
    rig.layer.playlist.enter_collection("favourites")
    assert [(c.label, c.path) for c in directory_crumbs(rig.layer.playlist, rig.root, "Favourites")] == [
        ("Favourites", None)
    ]


def test_preset_and_directory_rows_explain_their_gestures() -> None:
    from cleave.viz.row_spec import row_spec

    controls = make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    directory = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    assert "preset browser" in row_spec(RowKind.TRACK_PRESET).tooltip(view, preset)
    assert "preset browser" in row_spec(RowKind.TRACK_PRESET_DIR).tooltip(view, directory)
    up, down = row_spec(RowKind.TRACK_PRESET_DIR).nav_buttons
    assert down.tooltip(view, directory) == "No subfolders here"
    assert up.tooltip is not None and up.tooltip(view, directory)


def test_milkdrop_preset_page_draws_the_directory_path_as_crumbs(tmp_path: Path) -> None:
    from cleave.viz.navigator import LAYER_PAGE_MILKDROP_PRESET, layer_page_node_id
    from cleave.viz.shell_inspector import InspectorPanel
    from tests.support.shell import draw_shell, headless_shell_host

    root = (tmp_path / "presets").resolve()
    deep = _milk(root / "Pack" / "A" / "a1.milk")
    controls = make_controls(("layer_1",), preset_root=root)
    layer = controls.session.layers["layer_1"]
    layer.playlist = scan_preset_playlist(deep)
    layer.browse_floor = preset_browse_floor(deep, root)
    controls.navigator.select(layer_page_node_id("layer_1", LAYER_PAGE_MILKDROP_PRESET))
    with headless_shell_host() as host:
        host.context.controls = controls
        host.inspector.draw = lambda state: InspectorPanel.draw(host.inspector, state)
        draw_shell(host)
        draw_shell(host)
        view = controls.build_view_state(paused=False)
        assert [crumb.label for crumb in view.tracks["layer_1"].preset_dir_crumbs] == [
            "Pack",
            "A",
        ]
        assert RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1") in host.inspector.row_rects


def test_back_button_closes_and_keeps_the_previewed_preset(rig: _Rig) -> None:
    rig.controls.open("layer_1")
    rig.key(pygame.K_DOWN)
    rig.controls.tick(PREVIEW_DELAY_SEC)
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.CLOSE))
    assert not rig.controls.active
    assert rig.layer.playlist.current == rig.a2
    assert rig.loaded() == [rig.a2]


def _replace_rig(tmp_path: Path) -> tuple[_Rig, EditHistory]:
    """A rig whose browser can replace entries of a two-preset list."""
    rig = _Rig(tmp_path / "presets")
    rig.layer.preset_list = [
        PresetListEntry(str(rig.a1)),
        PresetListEntry(str(rig.b1)),
    ]
    history = EditHistory(rig.session)
    preset_list = PresetListController(
        rig.session,
        rig.root,
        tmp_path / "project",
        60.0,
        ModalHost(),
        rig.bindings,
        history=history,
    )
    rig.controls = PresetBrowserControls(
        rig.session,
        rig.root,
        rig.library,
        rig.mutations,
        preset_list=preset_list,
        start_text_input=rig.text_input.start,
        stop_text_input=rig.text_input.stop,
        text_input_shared=lambda: rig.shared,
        synchronous=True,
    )
    return rig, history


def test_replace_mode_starts_on_the_entry_and_enter_replaces_it(tmp_path: Path) -> None:
    rig, history = _replace_rig(tmp_path)
    rig.controls.open("layer_1", replace_index=1)
    browser = rig.controls.browser
    assert browser is not None
    assert browser.title == "Replace preset 2: Layer 1"
    assert browser.selected_preset() == rig.b1
    rig.controls.apply_pointer(BrowserPointerIntent(BrowserPointerKind.GOTO_CRUMB, 0))
    rig.search("a2")
    rig.key(pygame.K_RETURN)
    assert not rig.controls.active
    assert [entry.display_name for entry in rig.layer.preset_list] == [
        "a1.milk",
        "a2.milk",
    ]
    assert rig.layer.preset_list[1].file.parent == (tmp_path / "project" / "presets").resolve()
    # The replacement keeps playing as a preview.
    assert rig.layer.playlist.current == rig.a2
    assert history.undo() == "Replace preset"
    assert rig.layer.preset_list[1] == PresetListEntry(str(rig.b1))


def test_replace_mode_escape_leaves_the_list_alone(tmp_path: Path) -> None:
    rig, history = _replace_rig(tmp_path)
    rig.controls.open("layer_1", replace_index=0)
    rig.key(pygame.K_DOWN)
    rig.controls.tick(PREVIEW_DELAY_SEC)
    rig.key(pygame.K_ESCAPE)
    assert not rig.controls.active
    assert rig.layer.preset_list[0] == PresetListEntry(str(rig.a1))
    assert rig.layer.playlist.current == rig.a1
    assert not history.can_undo
