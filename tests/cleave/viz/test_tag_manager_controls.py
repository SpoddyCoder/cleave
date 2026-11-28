"""Tests for Settings > Manage tags."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.preset_library import FavouriteTag, PresetLibrary
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.preset_curation_controls import PresetCurationController
from cleave.viz.session import TuningSession
from cleave.viz.tag_manager_controls import TagManagerController
from tests.support.viz import keydown


def _manager(tmp_path: Path):
    preset = tmp_path / "pack" / "a.milk"
    preset.parent.mkdir(parents=True)
    preset.write_text("a", encoding="utf-8")
    library = PresetLibrary.in_memory()
    library.index(tmp_path)
    modal = ModalHost()
    curation = PresetCurationController(
        TuningSession(layer_z_order=[], layers={}), modal, None, library
    )
    shown: list[FavouriteTag] = []
    manager = TagManagerController(library, modal, curation, show_tag=shown.append)
    return manager, modal, library, preset, shown


def test_no_tags_offers_a_new_one_and_comes_back(tmp_path: Path) -> None:
    manager, modal, library, _preset, _shown = _manager(tmp_path)
    manager.prompt()
    view = modal.view_state()
    assert view is not None and view.kind == ModalKind.CONFIRM
    assert view.options[0] == "New tag"
    modal.handle_keydown(keydown(pygame.K_RETURN))
    modal.handle_text_input("dark")
    modal.handle_keydown(keydown(pygame.K_RETURN))
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert library.tags() == ("dark",)
    view = modal.view_state()
    assert view is not None and view.kind == ModalKind.FORM


def test_lists_tags_with_counts_and_shows_one(tmp_path: Path) -> None:
    manager, modal, library, preset, shown = _manager(tmp_path)
    library.add_tag("dark")
    library.add_tag("bright")
    library.set_tagged(preset, "dark", True)
    manager.prompt(select="dark")
    view = modal.view_state()
    assert view is not None and view.kind == ModalKind.FORM
    tag_row = view.form_rows[0]
    assert tag_row.options == ("bright (0 presets)", "dark (1 preset)", "New tag…")
    assert tag_row.value == 1
    manager._run(library.tags(), {"tag": 1, "action": 0})
    assert shown == [FavouriteTag("dark")]


def test_delete_from_the_manager_reopens_it(tmp_path: Path) -> None:
    manager, modal, library, _preset, _shown = _manager(tmp_path)
    library.add_tag("dark")
    library.add_tag("bright")
    manager._run(library.tags(), {"tag": 0, "action": 2})
    modal.handle_keydown(keydown(pygame.K_LEFT))
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert library.tags() == ("dark",)
    view = modal.view_state()
    assert view is not None and view.kind == ModalKind.FORM
