"""Tests for live layer binding factory and notification sink."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.layer import StemLayer
from cleave.viz.preset_switching import (
    advance_preset_switching,
    apply_preset_switching,
)
from cleave.viz.live_layer_binding_factory import (
    LiveLayerBindingContext,
    LiveLayerBindingsFactory,
    solo_audio_source,
    sync_mix_player_solo,
)
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.render_post_fx_bindings import RenderPostFxBindings
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.viz import make_test_cfg, stub_playback_state

_FACTORY = "cleave.viz.live_layer_binding_factory"
_MILK = (
    Path("/tmp/presets/layer_1/a.milk"),
    Path("/tmp/presets/layer_1/b.milk"),
)


def _session(*, preset_list: list[str] | None = None) -> TuningSession:
    playlist = PresetPlaylist(
        current_dir=Path("/tmp/presets/layer_1"),
        paths=_MILK,
        index=0,
    )
    return TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist,
                browse_floor=Path("/tmp/presets/layer_1"),
                stem="drums",
                preset_switching="on",
                preset_switching_trigger="projectm",
                preset_list=list(
                    preset_list
                    if preset_list is not None
                    else [str(p) for p in _MILK]
                ),
            )
        },
    )


def _layer(session: TuningSession) -> StemLayer:
    pm = ProjectM.__new__(ProjectM)
    pm.lock_preset = MagicMock()
    pm.load_preset = MagicMock()
    pm.set_preset_start_clean = MagicMock()
    pm.set_hard_cut_enabled = MagicMock()
    pm.flush_pcm = MagicMock()
    pm.set_beat_sensitivity = MagicMock()
    pm._pcm_channels = 2
    return StemLayer(
        slot="layer_1",
        pm=pm,
        fbo=MagicMock(),
        playlist=session.layers["layer_1"].playlist,
    )


def _make_factory(
    *, preset_list: list[str] | None = None
) -> tuple[LiveLayerBindingContext, LiveLayerBindingsFactory, StemLayer]:
    session = _session(preset_list=preset_list)
    layer = _layer(session)
    cfg = make_test_cfg(("layer_1",))
    ctx = LiveLayerBindingContext(
        session=session,
        cfg=cfg,
        preset_root=cfg.paths.preset_root,
        project_dir=Path("/tmp/project"),
        layers_by_slot={"layer_1": layer},
        layers=[layer],
        playback=stub_playback_state(),
        duration_sec=120.0,
        signals=None,
        effect_runtime=MagicMock(),
    )
    return ctx, LiveLayerBindingsFactory(ctx), layer


def _invoke_on_empty(*_args, on_empty=None, **_kwargs) -> None:
    if on_empty is not None:
        on_empty()


def test_layer_bindings_and_post_fx_shapes() -> None:
    _ctx, factory, _layer = _make_factory()
    layer_bindings = factory.layer_bindings()
    post_fx = factory.render_post_fx_bindings()
    assert isinstance(layer_bindings, LiveLayerBindings)
    assert isinstance(post_fx, RenderPostFxBindings)
    assert layer_bindings.on_preset_change == factory.on_preset_change
    assert layer_bindings.on_switching_resume == factory.on_switching_resume
    assert layer_bindings.on_seek == factory.on_seek
    assert post_fx.on_highlight_rolloff_apply_mode_change == (
        factory.on_highlight_rolloff_apply_mode_change
    )
    assert post_fx.is_paused == factory.is_paused


def test_notification_sink_is_settable_and_read_at_call_time() -> None:
    ctx, factory, _layer = _make_factory()
    seen: list[str] = []
    bindings = factory.layer_bindings()
    with patch(f"{_FACTORY}.apply_preset_switching", side_effect=_invoke_on_empty):
        bindings.on_preset_switching_change("layer_1")
        assert seen == []
        ctx.notification_sink = seen.append
        bindings.on_preset_switching_change("layer_1")
    assert seen == ["Layer 1: No presets in switching list"]


def test_empty_list_notify_skips_in_curation_mode() -> None:
    ctx, factory, _layer = _make_factory()
    ctx.session.settings.editor_mode = "preset_curation"
    seen: list[str] = []
    ctx.notification_sink = seen.append
    with patch(f"{_FACTORY}.apply_preset_switching", side_effect=_invoke_on_empty):
        factory.layer_bindings().on_preset_switching_change("layer_1")
    assert seen == []


def test_is_paused_reads_playback() -> None:
    ctx, factory, _layer = _make_factory()
    is_paused = factory.render_post_fx_bindings().is_paused
    assert is_paused is not None
    assert is_paused() is False
    ctx.playback.paused = True
    assert is_paused() is True


def test_on_save_config_writes_snapshot_and_returns_name() -> None:
    _ctx, factory, _layer = _make_factory()
    path = Path("/tmp/project/active.yaml")
    with patch(f"{_FACTORY}.write_session_snapshot") as mock_write:
        with patch(f"{_FACTORY}.sync_project_textures") as mock_sync:
            result = factory.on_save_config(path)
    assert result == "active.yaml"
    mock_write.assert_called_once()
    mock_sync.assert_called_once()


def test_browse_while_switching_on_pauses_and_toasts_once() -> None:
    ctx, factory, layer = _make_factory()
    seen: list[str] = []
    ctx.notification_sink = seen.append
    playlist = layer.playlist
    with patch(f"{_FACTORY}.apply_preset_switching") as mock_apply:
        factory.on_preset_change("layer_1", playlist)
        assert layer.switching_paused is True
        layer.pm.lock_preset.assert_called_with(True)
        layer.pm.set_hard_cut_enabled.assert_called_with(False)
        mock_apply.assert_not_called()
        assert seen == [
            "Browsing presets, switching paused - "
            "use the resume button to continue."
        ]
        playlist.next()
        factory.on_preset_change("layer_1", playlist)
    assert layer.switching_paused is True
    assert seen == [
        "Browsing presets, switching paused - "
        "use the resume button to continue."
    ]


def test_browse_while_timer_on_blocks_later_advance_load() -> None:
    ctx, factory, layer = _make_factory()
    runtime = ctx.session.layers["layer_1"]
    runtime.preset_switching_trigger = "timer"
    runtime.preset_duration = 10.0
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timer",
        preset_list=runtime.preset_list,
        preset_duration=10.0,
        session=ctx.session,
    )
    factory.on_preset_change("layer_1", layer.playlist)
    assert layer.switching_paused is True
    assert layer.auto_preset_path == _MILK[0].resolve()
    layer.pm.load_preset.reset_mock()
    advance_preset_switching(ctx.session, {"layer_1": layer}, 10.0)
    assert layer.list_switch_index == 1
    layer.pm.load_preset.assert_not_called()
    assert layer.auto_preset_path == _MILK[0].resolve()


def test_browse_while_timeline_on_blocks_later_advance_load() -> None:
    ctx, factory, layer = _make_factory()
    runtime = ctx.session.layers["layer_1"]
    runtime.preset_switching_trigger = "timeline"
    ctx.session.timeline.enabled = True
    ctx.session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0,
        cues=(
            SlotCue(t=1.0, level=1.0),
            SlotCue(t=2.0, level=0.0),
            SlotCue(t=3.0, level=1.0),
        ),
    )
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timeline",
        preset_list=runtime.preset_list,
        session=ctx.session,
    )
    factory.on_preset_change("layer_1", layer.playlist)
    assert layer.switching_paused is True
    layer.pm.load_preset.reset_mock()
    advance_preset_switching(ctx.session, {"layer_1": layer}, 3.5)
    assert layer.list_switch_index == 1
    layer.pm.load_preset.assert_not_called()


def test_on_switching_resume_clears_pause_and_reapplies() -> None:
    ctx, factory, layer = _make_factory()
    layer.switching_paused = True
    seen: list[str] = []
    ctx.notification_sink = seen.append
    with patch(f"{_FACTORY}.apply_preset_switching") as mock_apply:
        factory.on_switching_resume("layer_1")
    assert layer.switching_paused is False
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["mode"] == "on"
    assert mock_apply.call_args.kwargs["trigger"] == "projectm"
    assert seen == []


def test_on_preset_change_mode_off_clears_pause() -> None:
    ctx, factory, layer = _make_factory()
    ctx.session.layers["layer_1"].preset_switching = "off"
    layer.switching_paused = True
    factory.on_preset_change("layer_1", layer.playlist)
    assert layer.switching_paused is False
    layer.pm.lock_preset.assert_called_with(True)


def test_unlock_preset_after_modal_stays_locked_while_paused() -> None:
    _ctx, factory, layer = _make_factory()
    layer.switching_paused = True
    layer.pm.lock_preset.reset_mock()
    factory.unlock_preset_after_modal("layer_1")
    layer.pm.lock_preset.assert_called_once_with(True)


def test_solo_audio_source_and_mix_player_sync() -> None:
    session = _session()
    mix = MagicMock()
    assert solo_audio_source(session) is None
    sync_mix_player_solo(session, mix)
    mix.set_solo_source.assert_called_once_with(None)
    session.solo_slot = "layer_1"
    assert solo_audio_source(session) == "drums"
    sync_mix_player_solo(session, mix)
    mix.set_solo_source.assert_called_with("drums")
