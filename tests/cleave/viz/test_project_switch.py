"""In-session project switch: picker accept, unsaved prompt, and key routing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from cleave.open_target import OpenTargetKind
from cleave.paths import projects_dir
from cleave.project import PROJECT_FILENAME
from cleave.viz.file_picker import PICKER_MODE_SPECS, PickerMode
from cleave.viz.file_picker_surface import (
    FilePickerSurface,
    PickerPointerIntent,
    PickerPointerKind,
)
from cleave.viz.input_dispatch import dispatch_keydown, dispatch_keyup
from cleave.viz.menu_bar import MenuBarState
from tests.support.viz import keydown, make_controls


def _keydown_mod(key: int, mod: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def _keyup(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYUP, key=key)


def _use_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path / "data"))


def _project(parent: Path, name: str) -> Path:
    path = parent / name
    path.mkdir(parents=True)
    (path / PROJECT_FILENAME).write_text("slug: x\n")
    return path


def _wav(parent: Path, name: str) -> Path:
    path = parent / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF")
    return path


def _dirty(controls, opacity: int = 60) -> None:
    controls.session.layers["layer_1"].opacity_pct = opacity


def _select(switch, label: str) -> None:
    view = switch.view_state()
    assert view is not None
    index = next(i for i, row in enumerate(view.rows) if row.label == label)
    for _ in range(index - view.selected_index):
        switch.handle_keydown(keydown(pygame.K_DOWN))
    switch.handle_keyup(_keyup(pygame.K_DOWN))


def _accept_label(switch, label: str) -> None:
    _select(switch, label)
    switch.handle_keydown(keydown(pygame.K_RETURN))


def _choose_modal(controls, rights: int) -> None:
    for _ in range(rights):
        controls.handle_modal_keydown(keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(keydown(pygame.K_RETURN))


def test_file_picker_surface_is_modal() -> None:
    assert FilePickerSurface.modal is True


def test_accept_open_project_stores_target_without_teardown(tmp_path: Path, monkeypatch) -> None:
    _use_data(monkeypatch, tmp_path)
    project = _project(projects_dir(), "album")
    controls = make_controls()
    session = controls.session
    switch = controls.project_switch
    with (
        patch("pygame.quit") as quit_pygame,
        patch("cleave.gl_compositor.GlCompositor.destroy") as destroy_compositor,
        patch("cleave.viz.layer_pipeline.LayerFramePipeline.destroy") as destroy_layers,
    ):
        switch.prompt_open()
        assert switch.active
        _accept_label(switch, "album")
        assert not switch.active
        assert controls.session is session
        assert controls.consume_pending_switch() is True
        assert controls.consume_pending_switch() is False
        assert controls.consume_pending_exit() is False
        target = switch.take_accepted()
        assert target is not None
        assert target.path == project
        assert target.kind is OpenTargetKind.PROJECT
        assert switch.take_accepted() is None
        quit_pygame.assert_not_called()
        destroy_compositor.assert_not_called()
        destroy_layers.assert_not_called()


def test_pointer_accept_stores_the_same_target(tmp_path: Path, monkeypatch) -> None:
    _use_data(monkeypatch, tmp_path)
    project = _project(projects_dir(), "album")
    controls = make_controls()
    switch = controls.project_switch
    switch.prompt_open()
    view = switch.view_state()
    assert view is not None
    index = next(i for i, row in enumerate(view.rows) if row.label == "album")
    switch.apply_pointer(
        PickerPointerIntent(PickerPointerKind.OPEN_ROW, index=index)
    )
    assert not switch.active
    assert controls.consume_pending_switch() is True
    target = switch.take_accepted()
    assert target is not None
    assert target.path == project
    assert target.kind is OpenTargetKind.PROJECT


def test_esc_and_cancel_keep_the_session(tmp_path: Path, monkeypatch) -> None:
    _use_data(monkeypatch, tmp_path)
    controls = make_controls()
    session = controls.session
    switch = controls.project_switch
    switch.prompt_open()
    assert switch.handle_keydown(keydown(pygame.K_ESCAPE)) is True
    assert not switch.active
    assert switch.take_accepted() is None
    assert controls.consume_pending_switch() is False
    assert controls.consume_pending_exit() is False
    assert controls.session is session

    switch.prompt_open()
    assert (
        switch.handle_keydown(_keydown_mod(pygame.K_q, pygame.KMOD_CTRL)) is True
    )
    assert not switch.active
    assert switch.take_accepted() is None
    assert controls.consume_pending_switch() is False
    assert controls.pending_exit is False


def test_arrow_repeat_does_not_accept(tmp_path: Path, monkeypatch) -> None:
    _use_data(monkeypatch, tmp_path)
    _project(projects_dir(), "album")
    controls = make_controls()
    switch = controls.project_switch
    switch.prompt_open()
    switch.handle_keydown(keydown(pygame.K_RETURN))
    assert switch.active
    assert not switch.key_repeat_armed
    switch.handle_keydown(keydown(pygame.K_DOWN))
    assert switch.key_repeat_armed
    switch.tick(1.0)
    assert switch.active
    assert controls.consume_pending_switch() is False
    assert switch.take_accepted() is None
    switch.handle_keyup(_keyup(pygame.K_DOWN))
    assert not switch.key_repeat_armed


def test_dirty_accept_waits_for_save_or_discard(tmp_path: Path, monkeypatch) -> None:
    _use_data(monkeypatch, tmp_path)
    project = _project(projects_dir(), "album")
    controls = make_controls()
    switch = controls.project_switch
    _dirty(controls)
    switch.prompt_open()
    _accept_label(switch, "album")
    assert not switch.active
    assert controls.modal_host.active
    assert controls.consume_pending_switch() is False
    assert controls.consume_pending_exit() is False

    switch.prompt_new()
    assert not switch.active
    assert controls.modal_host.active

    _choose_modal(controls, 0)
    assert not controls.modal_host.active
    assert not controls.config_dirty
    assert controls.consume_pending_exit() is False
    assert controls.consume_pending_switch() is True
    target = switch.take_accepted()
    assert target is not None
    assert target.path == project

    _dirty(controls, 70)
    switch.prompt_open()
    _accept_label(switch, "album")
    _choose_modal(controls, 1)
    assert controls.consume_pending_exit() is False
    assert controls.consume_pending_switch() is True
    assert controls.config_dirty
    target = switch.take_accepted()
    assert target is not None
    assert target.path == project


def test_dirty_modal_cancel_drops_the_target(tmp_path: Path, monkeypatch) -> None:
    _use_data(monkeypatch, tmp_path)
    _project(projects_dir(), "album")
    controls = make_controls()
    switch = controls.project_switch
    _dirty(controls)
    switch.prompt_open()
    _accept_label(switch, "album")
    _choose_modal(controls, 2)
    assert not controls.modal_host.active
    assert switch.take_accepted() is None
    assert controls.consume_pending_switch() is False
    assert controls.consume_pending_exit() is False
    assert controls.config_dirty

    switch.prompt_open()
    _accept_label(switch, "album")
    controls.handle_modal_keydown(keydown(pygame.K_ESCAPE))
    assert not controls.modal_host.active
    assert switch.take_accepted() is None
    assert controls.consume_pending_switch() is False
    assert controls.pending_exit is False


def test_prompt_modes_and_new_project_accepts_audio_only(
    tmp_path: Path, monkeypatch
) -> None:
    _use_data(monkeypatch, tmp_path)
    controls = make_controls()
    switch = controls.project_switch
    switch.prompt_open()
    opened = switch.view_state()
    assert opened is not None
    assert opened.title == PICKER_MODE_SPECS[PickerMode.OPEN_PROJECT].title
    assert opened.location == str(projects_dir())
    assert switch.active

    home = tmp_path / "home"
    home.mkdir()
    song = _wav(home, "song.wav")
    _project(home, "album")
    monkeypatch.setattr(Path, "home", lambda: home)
    switch.prompt_new()
    created = switch.view_state()
    assert created is not None
    assert created.title == PICKER_MODE_SPECS[PickerMode.NEW_PROJECT].title
    assert created.location == str(home)
    assert switch.take_accepted() is None
    assert controls.consume_pending_switch() is False

    _accept_label(switch, "album")
    assert switch.active
    assert switch.take_accepted() is None
    assert controls.consume_pending_switch() is False
    inside = switch.view_state()
    assert inside is not None
    assert inside.location == str(home / "album")

    switch.handle_keydown(keydown(pygame.K_BACKSPACE))
    _accept_label(switch, "song.wav")
    assert not switch.active
    assert controls.consume_pending_switch() is True
    target = switch.take_accepted()
    assert target is not None
    assert target.path == song
    assert target.kind is OpenTargetKind.AUDIO


def test_quit_prompt_is_not_replaced_by_open(tmp_path: Path, monkeypatch) -> None:
    _use_data(monkeypatch, tmp_path)
    controls = make_controls()
    _dirty(controls)
    controls.try_quit()
    assert controls.modal_host.active
    controls.project_switch.prompt_open()
    assert not controls.project_switch.active
    _choose_modal(controls, 1)
    assert controls.consume_pending_exit() is True
    assert controls.consume_pending_switch() is False
    assert controls.project_switch.take_accepted() is None


def test_dispatch_sends_picker_keys_and_lets_the_modal_win(
    tmp_path: Path, monkeypatch
) -> None:
    _use_data(monkeypatch, tmp_path)
    controls = make_controls()
    switch = controls.project_switch
    runtime = SimpleNamespace(
        modal_host=controls.modal_host,
        controls=controls,
        menu_bar=MenuBarState(),
    )
    switch.prompt_open()
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert controls.session.help_visible is False
    switch.handle_keydown(keydown(pygame.K_DOWN))
    dispatch_keyup(_keyup(pygame.K_DOWN), runtime)
    assert not switch.key_repeat_armed

    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert not switch.active
    assert controls.consume_pending_switch() is False

    _project(projects_dir(), "album")
    _dirty(controls)
    switch.prompt_open()
    controls.try_quit()
    assert controls.modal_host.active and switch.active
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert not controls.modal_host.active
    assert switch.active
    assert controls.consume_pending_exit() is False
    assert controls.consume_pending_switch() is False
