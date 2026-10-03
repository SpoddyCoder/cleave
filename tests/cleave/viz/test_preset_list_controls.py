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


def test_add_current_uses_playing_auto_preset_not_browse() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        root = Path(tmp) / "packs"
        browse = root / "pack" / "demo.milk"
        playing = root / "pack" / "later.milk"
        _write(browse, "milk")
        _write(playing, "milk")
        controller, session, modal = _make_controller(
            preset_root=root,
            project_dir=project,
        )
        session.layers["layer_1"].auto_preset_path = playing.resolve()
        assert controller.current_preset_path("layer_1") == playing.resolve()
        assert controller.resolve_file_path(
            "layer_1",
            RowKind.TRACK_PRESET,
            RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"),
        ) == playing.resolve()
        controller.add_current("layer_1")
        view = modal.view_state()
        assert view is not None
        assert view.message == "Add preset: later.milk?"
        modal.handle_keydown(keydown(pygame.K_RETURN))
        dest = project / "presets" / "later.milk"
        assert dest.is_file()
        assert session.layers["layer_1"].preset_list == [str(dest.resolve())]


def test_add_current_uses_projectm_playlist_position_not_stale_first() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        root = Path(tmp) / "packs"
        first = root / "pack" / "first.milk"
        later = root / "pack" / "later.milk"
        _write(first, "milk")
        _write(later, "milk")
        from unittest.mock import MagicMock

        from cleave.viz.layer import StemLayer

        stem = MagicMock(spec=StemLayer)
        stem.switching_paused = False
        stem.auto_preset_path = first.resolve()
        stem.preset_rotation = None
        playlist = MagicMock()
        playlist.get_position.return_value = 1
        playlist.item.side_effect = lambda index: (first, later)[index]
        stem.projectm_playlist = playlist
        controller, session, modal = _make_controller(
            preset_root=root,
            project_dir=project,
            preset_list=[str(first.resolve()), str(later.resolve())],
        )
        controller._layers_by_slot = {"layer_1": stem}
        session.layers["layer_1"].auto_preset_path = first.resolve()
        assert controller.current_preset_path("layer_1") == later.resolve()
        controller.add_current("layer_1")
        view = modal.view_state()
        assert view is not None
        assert view.message == "Add preset: later.milk?"


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


def test_current_preset_path_uses_browsed_preset_while_paused() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        root = Path(tmp) / "packs"
        browse = root / "pack" / "demo.milk"
        playing = root / "pack" / "later.milk"
        _write(browse, "milk")
        _write(playing, "milk")
        from unittest.mock import MagicMock

        from cleave.viz.layer import StemLayer

        controller, session, modal = _make_controller(
            preset_root=root,
            project_dir=project,
        )
        session.layers["layer_1"].auto_preset_path = playing.resolve()
        stem = MagicMock(spec=StemLayer)
        stem.switching_paused = True
        stem.playlist = session.layers["layer_1"].playlist
        stem.auto_preset_path = playing.resolve()
        stem.projectm_playlist = None
        stem.preset_rotation = None
        controller._layers_by_slot = {"layer_1": stem}
        assert controller.current_preset_path("layer_1") == browse.resolve()
        controller.add_current("layer_1")
        view = modal.view_state()
        assert view is not None
        assert view.message == "Add preset: demo.milk?"


def test_audition_pauses_switching_and_resume_clears_it() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "packs"
        current = root / "pack" / "demo.milk"
        other = root / "pack" / "other.milk"
        _write(current, "milk")
        _write(other, "milk")
        from unittest.mock import MagicMock

        from cleave.projectm import ProjectM
        from cleave.viz.layer import StemLayer
        from cleave.viz.live_layer_binding_factory import (
            LiveLayerBindingContext,
            LiveLayerBindingsFactory,
        )
        from tests.support.viz import make_test_cfg, stub_playback_state

        controller, session, _modal = _make_controller(
            preset_root=root,
            preset_list=[str(other.resolve())],
        )
        session.layers["layer_1"].preset_switching = "on"
        session.layers["layer_1"].preset_switching_trigger = "timer"
        pm = ProjectM.__new__(ProjectM)
        pm.lock_preset = MagicMock()
        pm.load_preset = MagicMock()
        pm.set_preset_start_clean = MagicMock()
        pm.set_hard_cut_enabled = MagicMock()
        stem = StemLayer(
            slot="layer_1",
            pm=pm,
            fbo=MagicMock(),
            playlist=session.layers["layer_1"].playlist,
        )
        seen: list[str] = []
        ctx = LiveLayerBindingContext(
            session=session,
            cfg=make_test_cfg(("layer_1",), preset_root=root),
            preset_root=root,
            project_dir=root.parent,
            layers_by_slot={"layer_1": stem},
            layers=[stem],
            playback=stub_playback_state(),
            duration_sec=120.0,
            signals=None,
            effect_runtime=MagicMock(),
            notification_sink=seen.append,
        )
        controller._layer_bindings = LiveLayerBindingsFactory(ctx).layer_bindings()
        controller.audition("layer_1", 5)
        controller.audition("layer_1", -1)
        assert stem.switching_paused is False
        assert seen == []
        assert session.layers["layer_1"].playlist.current is not None
        assert session.layers["layer_1"].playlist.current.resolve() == current.resolve()

        controller.audition("layer_1", 0)
        assert stem.switching_paused is True
        assert stem.playlist.current is not None
        assert stem.playlist.current.resolve() == other.resolve()
        assert session.layers["layer_1"].playlist is stem.playlist
        pm.load_preset.assert_called_with(other.resolve(), smooth=False)
        assert seen == [
            "Layer 1: Browsing presets, switching paused - "
            "use the resume button to continue."
        ]

        controller.audition("layer_1", 0)
        assert len(seen) == 1

        controller.resume("layer_1")
        assert stem.switching_paused is False
        assert len(seen) == 1
