"""Tests for cleave.viz.preset_switching runtime helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.viz.layer import StemLayer
from cleave.viz.preset_switching import (
    EMPTY_ROTATION_NOTIFICATION,
    apply_preset_switching,
    reapply_projectm_preset_switching,
)
from cleave.viz.session import LayerRuntime, TuningSession

_MILK = (Path("/tmp/presets/drums/a.milk"),)


def _stem_layer(*, paths: tuple[Path, ...]) -> StemLayer:
    current_dir = Path("/tmp/presets/drums")
    playlist = PresetPlaylist(current_dir=current_dir, paths=paths, index=0)
    pm = ProjectM.__new__(ProjectM)
    pm.lock_preset = MagicMock()
    pm.set_hard_cut_enabled = MagicMock()
    pm.set_soft_cut_duration = MagicMock()
    return StemLayer(slot="layer_1", pm=pm, fbo=MagicMock(), playlist=playlist)


def test_apply_none_locks_and_disables_hard_cuts() -> None:
    layer = _stem_layer(paths=_MILK)
    mock_pl = MagicMock()
    layer.projectm_playlist = mock_pl

    apply_preset_switching(layer, mode="none", scope="directory")

    mock_pl.destroy.assert_called_once()
    assert layer.projectm_playlist is None
    layer.pm.lock_preset.assert_called_with(True)
    layer.pm.set_hard_cut_enabled.assert_called_with(False)


@patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK)
@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_connects_playlist(
    mock_playlist_cls: MagicMock,
    _mock_milk: MagicMock,
) -> None:
    layer = _stem_layer(paths=_MILK)
    playlist = MagicMock()
    mock_playlist_cls.create.return_value = playlist
    on_empty = MagicMock()

    apply_preset_switching(
        layer, mode="projectm", scope="directory", on_empty=on_empty
    )

    layer.pm.lock_preset.assert_called_with(False)
    layer.pm.set_hard_cut_enabled.assert_called_with(True)
    layer.pm.set_soft_cut_duration.assert_called_once_with(0.0)
    playlist.connect.assert_called_once_with(layer.pm)
    playlist.add_path.assert_called_once_with(
        layer.playlist.current_dir, recurse=False, allow_duplicates=False
    )
    playlist.set_shuffle.assert_called_once_with(False)
    assert layer.projectm_playlist is playlist
    on_empty.assert_not_called()


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_empty_dir_falls_back(mock_playlist_cls: MagicMock) -> None:
    layer = _stem_layer(paths=())
    on_empty = MagicMock()

    apply_preset_switching(
        layer, mode="projectm", scope="directory", on_empty=on_empty
    )

    mock_playlist_cls.create.assert_not_called()
    layer.pm.lock_preset.assert_called_with(True)
    on_empty.assert_called_once()


def test_empty_rotation_notification_text() -> None:
    assert "No presets" in EMPTY_ROTATION_NOTIFICATION


def test_reapply_projectm_preset_switching_only_projectm_layers() -> None:
    layer_projectm = _stem_layer(paths=_MILK)
    layer_none = _stem_layer(paths=_MILK)
    session = TuningSession(
        layer_z_order=["layer_1", "layer_2"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer_projectm.playlist,
                browse_floor=layer_projectm.playlist.current_dir,
                stem="drums",
                preset_switching="projectm",
            ),
            "layer_2": LayerRuntime(
                playlist=layer_none.playlist,
                browse_floor=layer_none.playlist.current_dir,
                stem="bass",
                preset_switching="none",
            ),
        },
    )

    with (
        patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK),
        patch("cleave.viz.preset_switching.apply_preset_switching") as mock_apply,
    ):
        reapply_projectm_preset_switching(
            session,
            {"layer_1": layer_projectm, "layer_2": layer_none},
        )

    mock_apply.assert_called_once()
    assert mock_apply.call_args.args[0] is layer_projectm
