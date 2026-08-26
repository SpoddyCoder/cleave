"""Tests for user preset-list controller."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cleave.preset_playlist import PresetPlaylist
from cleave.viz.modal import ModalHost
from cleave.viz.preset_list_controls import PresetListController
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.viz import keydown, noop_layer_bindings

import pygame


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_controller(
    *,
    preset_root: Path,
    project_dir: Path | None = None,
    duration_sec: float = 120.0,
    modal: ModalHost | None = None,
    layer_bindings=None,
    on_notification=None,
    get_active_config_path=None,
    on_focus_preset_item=None,
    preset_list: list[str] | None = None,
) -> tuple[PresetListController, TuningSession, ModalHost]:
    modal_host = modal if modal is not None else ModalHost()
    milk = preset_root / "pack" / "demo.milk"
    playlist = PresetPlaylist(
        current_dir=preset_root / "pack",
        paths=(milk,),
        index=0,
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist,
                browse_floor=preset_root,
                stem="drums",
                opacity_pct=50,
                preset_list=list(preset_list or []),
                preset_switching="on",
            ),
        },
    )
    controller = PresetListController(
        session,
        preset_root,
        project_dir if project_dir is not None else preset_root.parent,
        duration_sec,
        modal_host,
        layer_bindings if layer_bindings is not None else noop_layer_bindings(),
        on_notification=on_notification,
        get_active_config_path=get_active_config_path,
        on_focus_preset_item=on_focus_preset_item,
    )
    return controller, session, modal_host


def test_resolve_file_path_current_and_list_item() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "presets"
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        listed = root / "pack" / "listed.milk"
        _write(listed, "milk")
        controller, _session, _modal = _make_controller(
            preset_root=root,
            preset_list=[str(listed)],
        )
        assert controller.resolve_file_path(
            "layer_1",
            RowKind.TRACK_PRESET,
            RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"),
        ) == src
        assert controller.resolve_file_path(
            "layer_1",
            RowKind.TRACK_PRESET_LIST_ITEM,
            RowDescriptor(
                RowKind.TRACK_PRESET_LIST_ITEM,
                slot="layer_1",
                preset_index=0,
            ),
        ) == listed


def test_enter_move_mode_and_swap_updates_list_and_focus() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "presets"
        _write(root / "pack" / "demo.milk", "milk")
        focused: list[tuple[str, int]] = []
        a = str(root / "a.milk")
        b = str(root / "b.milk")
        controller, session, _modal = _make_controller(
            preset_root=root,
            preset_list=[a, b],
            on_focus_preset_item=lambda slot, index: focused.append((slot, index)),
        )
        controller.enter_move_mode("layer_1", 0)
        assert controller.move_mode_preset == ("layer_1", 0)
        controller.swap_item(1)
        assert session.layers["layer_1"].preset_list == [b, a]
        assert controller.move_mode_preset == ("layer_1", 1)
        assert focused == [("layer_1", 1)]


def test_cancel_move_mode_restores_original_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "presets"
        _write(root / "pack" / "demo.milk", "milk")
        a = str(root / "a.milk")
        b = str(root / "b.milk")
        controller, session, _modal = _make_controller(
            preset_root=root,
            preset_list=[a, b],
        )
        controller.enter_move_mode("layer_1", 0)
        controller.swap_item(1)
        controller.cancel_move_mode()
        assert session.layers["layer_1"].preset_list == [a, b]
        assert controller.move_mode_preset is None


def test_confirm_move_mode_keeps_order_and_notifies_bindings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "presets"
        _write(root / "pack" / "demo.milk", "milk")
        switched: list[str] = []
        a = str(root / "a.milk")
        b = str(root / "b.milk")
        controller, session, _modal = _make_controller(
            preset_root=root,
            preset_list=[a, b],
            layer_bindings=noop_layer_bindings(
                on_preset_switching_change=switched.append,
            ),
        )
        controller.enter_move_mode("layer_1", 0)
        controller.swap_item(1)
        controller.confirm_move_mode()
        assert session.layers["layer_1"].preset_list == [b, a]
        assert controller.move_mode_preset is None
        assert switched == ["layer_1"]


def test_prompt_populate_timeline_trigger_includes_cue_roles() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "presets"
        _write(root / "pack" / "demo.milk", "milk")
        controller, session, modal = _make_controller(preset_root=root)
        session.layers["layer_1"].preset_switching_trigger = "timeline"
        session.timeline.enabled = False
        controller.prompt_populate("layer_1")
        view = modal.view_state()
        assert view is not None
        assert view.message == "Populate the preset list with 1 presets?"
        assert view.options == (
            "Using Cue Marker Roles (Random)",
            "From Current Directory (Random)",
            "From Current Directory (Sequential)",
            "Cancel",
        )


def test_prompt_populate_timer_omits_cue_roles() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "presets"
        _write(root / "pack" / "demo.milk", "milk")
        controller, session, modal = _make_controller(preset_root=root)
        session.layers["layer_1"].preset_switching_trigger = "timer"
        controller.prompt_populate("layer_1")
        view = modal.view_state()
        assert view is not None
        assert view.options == (
            "From Current Directory (Random)",
            "From Current Directory (Sequential)",
            "Cancel",
        )


def test_add_current_copies_into_user_presets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        root = Path(tmp) / "packs"
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        switched: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            project_dir=project,
            layer_bindings=noop_layer_bindings(
                on_preset_switching_change=switched.append,
            ),
        )
        controller.add_current("layer_1")
        view = modal.view_state()
        assert view is not None
        assert view.message == "Add preset: demo.milk?"
        modal.handle_keydown(keydown(pygame.K_RETURN))
        dest = project / "presets" / "demo.milk"
        assert dest.is_file()
        assert session.layers["layer_1"].preset_list == [str(dest.resolve())]
        assert switched == ["layer_1"]


def test_confirm_delete_unlinks_unreferenced_user_preset() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        root = project / "pack-root"
        _write(root / "pack" / "demo.milk", "milk")
        dest = project / "presets" / "keep.milk"
        _write(dest, "milk")
        controller, session, _modal = _make_controller(
            preset_root=root,
            project_dir=project,
            preset_list=[str(dest.resolve())],
            get_active_config_path=lambda: None,
        )
        controller.confirm_delete("layer_1", 0)
        assert session.layers["layer_1"].preset_list == []
        assert not dest.exists()
