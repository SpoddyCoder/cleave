"""Tests for Cleave config snapshot writing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from cleave.config import (
    CleaveConfig,
    LayerConfig,
    PathsConfig,
    RenderOverlayBackgroundConfig,
    RenderOverlayBorderConfig,
    RenderConfig,
    RenderOverlayConfig,
    RenderOverlayTextBlockConfig,
    RenderPostFxConfig,
    VisualizerConfig,
    _parse_layers,
    _parse_render,
    _parse_timeline,
)
from cleave.config_snapshot import next_unnamed_path, write_session_snapshot
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import playlist_at_dir
from cleave.timeline import TimelineCue
from cleave.viz.controls import (
    LayerRuntime,
    RenderOverlayRuntime,
    RenderPostFxRuntime,
    TuningSession,
)
from cleave.viz.layer import _session_from_cfg


def test_next_unnamed_path_empty_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    assert next_unnamed_path(project_dir) == project_dir / "unnamed-1.yaml"


def test_next_unnamed_path_fills_gaps(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "unnamed-1.yaml").write_text("a\n", encoding="utf-8")
    (project_dir / "unnamed-3.yaml").write_text("b\n", encoding="utf-8")
    assert next_unnamed_path(project_dir) == project_dir / "unnamed-4.yaml"


def test_write_session_snapshot_includes_locked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    locked=(name == "bass"),
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["bass"]["locked"] is True
        for name in STEM_NAMES:
            if name != "bass":
                assert data["layers"][name]["locked"] is False


def test_write_session_snapshot_sparse_effects() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    effects={"pulse": {"onset": 60}} if name == "drums" else {},
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["drums"]["effects"] == {"pulse": {"onset": 60}}
        assert "effects" not in data["layers"]["bass"]


def test_write_session_snapshot_sparse_all_effect_types() -> None:
    """Non-zero effect keys persist; zero drivers and empty effect groups are omitted."""
    session_effects: dict[str, dict[str, dict[str, int]]] = {
        "drums": {
            "pulse": {"onset": 35},
            "flare": {"onset": 20},
            "flash": {"onset": 15},
            "grit": {"onset": 10},
        },
        "bass": {
            "pulse": {"sub_bass": 40, "mid_bass": 0},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        },
        "vocals": {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
            "grit": {"rms": 0},
        },
        "other": {
            "pulse": {"centroid": 30},
            "flash": {"centroid": 0},
            "grit": {"centroid": 5},
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    effects=session_effects[name],
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["drums"]["effects"] == session_effects["drums"]
        assert data["layers"]["bass"]["effects"] == {
            "pulse": {"sub_bass": 40},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        }
        assert data["layers"]["vocals"]["effects"] == {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
        }
        assert data["layers"]["other"]["effects"] == {
            "pulse": {"centroid": 30},
            "grit": {"centroid": 5},
        }

        round_trip = _parse_layers({"layers": data["layers"]}, preset_root)
        assert round_trip["drums"].effects == session_effects["drums"]
        assert round_trip["bass"].effects["pulse"] == {"sub_bass": 40}
        assert round_trip["vocals"].effects["hue"] == {"pitch": 25}


def test_write_session_snapshot_uses_session_z_order_when_valid() -> None:
    session_order = ["other", "drums", "bass", "vocals"]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
            layer_z_order=("drums", "vocals", "bass", "other"),
        )

        session = TuningSession(
            layer_z_order=session_order,
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layer_z_order"] == session_order


def test_write_session_snapshot_falls_back_to_cfg_z_order_when_invalid() -> None:
    cfg_order = ("drums", "vocals", "bass", "other")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
            layer_z_order=cfg_order,
        )

        session = TuningSession(
            layer_z_order=["drums", "bass"],
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layer_z_order"] == list(cfg_order)


def test_write_session_snapshot_sparse_beat_sensitivity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(beat_sensitivity=1.0),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    beat_sensitivity=1.5 if name == "bass" else 1.0,
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["visualizer"]["beat_sensitivity"] == 1.0
        assert "beat_sensitivity" not in data["layers"]["drums"]
        assert data["layers"]["bass"]["beat_sensitivity"] == 1.5


def test_write_session_snapshot_omits_all_zero_effects() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    effects=(
                        {"pulse": {"onset": 0}, "flare": {"onset": 0}}
                        if name == "vocals"
                        else {}
                    ),
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert "effects" not in data["layers"]["vocals"]


def _render_overlay_cfg() -> RenderOverlayConfig:
    return RenderOverlayConfig(
        enabled=True,
        title=RenderOverlayTextBlockConfig(
            content="My Title",
            font="monospace",
            font_size=24,
            colour=(255, 255, 255),
            background_colour=(51, 51, 255),
            margin_bottom=10,
        ),
        body=RenderOverlayTextBlockConfig(
            content="Line one\nLine two",
            font="monospace",
            font_size=18,
            colour=(255, 255, 255),
            background_colour=(51, 51, 255),
        ),
        start_delay=10.0,
        display_time=30.0,
        position="bottom-left",
        background=RenderOverlayBackgroundConfig(
            margin=10,
            padding=10,
            colour=(34, 51, 68),
            opacity=1.0,
            border=RenderOverlayBorderConfig(colour=(34, 51, 68), width=2),
        ),
    )


def _snapshot_fixture(tmp_path: Path) -> tuple[CleaveConfig, TuningSession, Path]:
    root = tmp_path
    preset_root = root / "presets"
    for name in STEM_NAMES:
        stem_dir = preset_root / name
        stem_dir.mkdir(parents=True)
        (stem_dir / "anchor.milk").write_text("milk")

    config_path = root / "cleave.config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "layers": {name: {"preset": f"presets/{name}/anchor.milk"} for name in STEM_NAMES},
                "render": {
                    "post_fx": {
                        "enabled": True,
                        "fade_in": 30,
                        "fade_out": 4,
                    },
                    "overlay": {
                        "enabled": True,
                        "title": {
                            "content": "My Title",
                            "font-size": 24,
                            "font-colour": "#ffffff",
                            "background-colour": "#3333ff",
                            "margin-bottom": 10,
                        },
                        "body": {
                            "content": "Line one\nLine two\n",
                            "font-size": 18,
                            "colour": "#ffffff",
                            "background-colour": "#3333ff",
                        },
                        "start_delay": 10,
                        "display_time": 30,
                        "position": "bottom-left",
                        "background": {
                            "margin": 10,
                            "padding": 10,
                            "colour": "#223344",
                            "opacity": 1.0,
                            "border": {"colour": "#223344", "width": 2},
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
        layers={
            name: LayerConfig(preset=preset_root / name / "anchor.milk")
            for name in STEM_NAMES
        },
        visualizer=VisualizerConfig(),
        config_path=config_path,
        render=RenderConfig(
            overlay=_render_overlay_cfg(),
            post_fx=RenderPostFxConfig(
                enabled=True, fade_in=30.0, fade_out=4.0
            ),
        ),
    )
    session = TuningSession(
        layer_z_order=list(STEM_NAMES),
        render_post_fx=RenderPostFxRuntime(
            enabled=True,
            expanded=False,
            fade_in=12.0,
            fade_out=3.0,
        ),
        render_overlay=RenderOverlayRuntime(
            enabled=True,
            expanded=False,
            position="top-right",
            title_expanded=False,
            body_expanded=False,
            title_font_size=14,
            title_font="dejavusans",
            title_margin_bottom=6,
            body_font_size=18,
            body_font="ubuntumono",
            opacity_pct=75,
            border_width=4,
            start_delay=20.0,
            display_time=40.0,
        ),
        layers={
            name: LayerRuntime(
                playlist=playlist_at_dir(preset_root / name, index=0),
                browse_floor=preset_root / name,
            )
            for name in STEM_NAMES
        },
    )
    return cfg, session, root / "snapshot.yaml"


def test_write_session_snapshot_persists_render_overlay(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    overlay = data["render"]["overlay"]
    assert overlay["enabled"] is True
    assert overlay["title"]["content"] == "My Title"
    assert overlay["body"]["content"] == "Line one\nLine two\n"
    assert overlay["start_delay"] == 20.0
    assert overlay["display_time"] == 40.0
    assert overlay["position"] == "top-right"
    assert overlay["title"]["font-size"] == 14
    assert overlay["title"]["font"] == "dejavusans"
    assert overlay["title"]["margin-bottom"] == 6
    assert overlay["body"]["font-size"] == 18
    assert overlay["body"]["font"] == "ubuntumono"
    assert overlay["title"]["font-colour"] == "#ffffff"
    assert overlay["body"]["colour"] == "#ffffff"
    assert overlay["background"]["margin"] == 10
    assert overlay["background"]["padding"] == 10
    assert overlay["background"]["colour"] == "#223344"
    assert overlay["background"]["opacity"] == 0.75
    assert overlay["background"]["border"]["colour"] == "#223344"
    assert overlay["background"]["border"]["width"] == 4

    round_trip = _parse_render(data)
    assert round_trip is not None
    assert round_trip.overlay is not None
    assert round_trip.overlay.enabled is True
    assert round_trip.overlay.start_delay == 20.0
    assert round_trip.overlay.title.font_size == 14
    assert round_trip.overlay.title.font == "dejavusans"
    assert round_trip.overlay.title.margin_bottom == 6
    assert round_trip.overlay.body.font_size == 18
    assert round_trip.overlay.body.font == "ubuntumono"
    assert round_trip.overlay.background.opacity == 0.75
    assert round_trip.overlay.background.border.width == 4


def test_write_session_snapshot_strips_legacy_overlay_font(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    config_path = tmp_path / "cleave.config.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["render"]["overlay"]["font"] = {"size": 10, "colour": "#ffaa00"}
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    write_session_snapshot(out_path, cfg=cfg, session=session)

    snapshot = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert "font" not in snapshot["render"]["overlay"]


def test_write_session_snapshot_persists_render_post_fx(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    post_fx = data["render"]["post_fx"]
    assert post_fx["enabled"] is True
    assert post_fx["fade_in"] == 12.0
    assert post_fx["fade_out"] == 3.0

    round_trip = _parse_render(data)
    assert round_trip is not None
    assert round_trip.post_fx is not None
    assert round_trip.post_fx.enabled is True
    assert round_trip.post_fx.fade_in == 12.0
    assert round_trip.post_fx.fade_out == 3.0


def test_write_session_snapshot_render_post_fx_solo_does_not_affect_enabled(
    tmp_path: Path,
) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.render_post_fx.enabled = False
    session.render_post_fx_solo = True
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["render"]["post_fx"]["enabled"] is False
    assert "render_post_fx_solo" not in yaml.safe_dump(data)


def test_write_session_snapshot_render_overlay_solo_does_not_affect_enabled(
    tmp_path: Path,
) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.render_overlay.enabled = False
    session.render_overlay_solo = True
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["render"]["overlay"]["enabled"] is False
    assert "render_overlay_solo" not in yaml.safe_dump(data)


def test_write_session_snapshot_render_overlay_without_cfg_render(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    cfg = CleaveConfig(
        paths=cfg.paths,
        layers=cfg.layers,
        visualizer=cfg.visualizer,
        config_path=cfg.config_path,
        render=None,
    )
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    overlay = data["render"]["overlay"]
    assert overlay["title"]["content"] == "Cleave Final Render"
    assert overlay["position"] == "top-right"
    assert overlay["title"]["font-size"] == 14


def test_write_session_snapshot_persists_timeline_at_bottom(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = True
    session.timeline.cues = [
        TimelineCue(t=2.5, layers={"drums": False, "bass": True}),
        TimelineCue(t=10.0, layers={"vocals": False}),
    ]
    write_session_snapshot(out_path, cfg=cfg, session=session)

    raw = out_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    assert list(data.keys())[-1] == "timeline"
    assert data["timeline"]["enabled"] is True
    assert data["timeline"]["cues"] == [
        {"t": 2.5, "layers": {"drums": False, "bass": True}},
        {"t": 10.0, "layers": {"vocals": False}},
    ]

    timeline = _parse_timeline(data)
    assert timeline is not None
    playlists = {
        name: playlist_at_dir(cfg.paths.preset_root / name, index=0)
        for name in STEM_NAMES
    }
    cfg_with_timeline = CleaveConfig(
        paths=cfg.paths,
        layers=cfg.layers,
        visualizer=cfg.visualizer,
        config_path=out_path,
        render=cfg.render,
        timeline=timeline,
    )
    session2 = _session_from_cfg(cfg_with_timeline, playlists)
    assert session2.timeline.enabled is True
    assert session2.timeline.cues == list(timeline.cues)


def test_write_session_snapshot_persists_timeline_disabled_without_cues(
    tmp_path: Path,
) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = False
    session.timeline.cues = []
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["timeline"] == {"enabled": False}
