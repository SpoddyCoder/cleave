"""Tests for Cleave config snapshot writing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
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
    EditorConfig,
    _parse_layers,
    load_config,
)
from cleave.config_schema import (
    DEFAULT_LAYER_SLOTS,
    DEFAULT_RENDER_HEIGHT,
    DEFAULT_RENDER_WIDTH,
    ParseCtx,
    parse_render_section,
    parse_timeline_section,
    template_layer_entry,
)
from tests.support.config import (
    TEST_LAYER_STEMS,
    default_render_post_fx_config,
    default_render_post_fx_runtime,
    layer_configs,
    layer_runtimes,
    make_preset_dirs,
    slot_for_stem,
)
from cleave.config_snapshot import (
    next_unnamed_path,
    persisted_session_payload,
    persisted_session_signature,
    write_session_snapshot,
)
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import playlist_at_dir
from cleave.timeline import TimelineCue
from cleave.viz.session import (
    LayerRuntime,
    RenderOverlayRuntime,
    TuningSession,
    session_from_cfg,
)


def test_next_unnamed_path_empty_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    assert next_unnamed_path(project_dir) == project_dir / "unnamed-1.yaml"


def test_next_unnamed_path_fills_gaps(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "unnamed-1.yaml").write_text("a\n", encoding="utf-8")
    (project_dir / "unnamed-3.yaml").write_text("b\n", encoding="utf-8")
    assert next_unnamed_path(project_dir) == project_dir / "unnamed-4.yaml"


def _minimal_snapshot_session(
    root: Path, config_path: Path
) -> tuple[CleaveConfig, TuningSession]:
    preset_root = root / "presets"
    make_preset_dirs(preset_root)
    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
        layers={
            slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
        editor=EditorConfig(),
        config_path=config_path,
        user_config_path=root / "user-config.yaml",
    )
    session = TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        layers={
            slot: LayerRuntime(
                stem=TEST_LAYER_STEMS[slot],
                playlist=playlist_at_dir(
                    preset_root / TEST_LAYER_STEMS[slot], index=0
                ),
                browse_floor=preset_root / TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
    )
    return cfg, session


def test_write_session_snapshot_omits_paths_when_source_has_none(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "cleave.config.yaml"
    config_path.write_text("layers: {}\n", encoding="utf-8")
    cfg, session = _minimal_snapshot_session(tmp_path, config_path)

    out_path = tmp_path / "snapshot.yaml"
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert "paths" not in data


def test_write_session_snapshot_includes_paths_when_source_has_paths(
    tmp_path: Path,
) -> None:
    preset_root = tmp_path / "presets"
    texture_path = tmp_path / "textures"
    texture_path.mkdir()
    make_preset_dirs(preset_root)

    source_paths = {
        "preset_root": str(preset_root),
        "texture_paths": [str(texture_path)],
    }
    config_path = tmp_path / "cleave.config.yaml"
    config_path.write_text(
        yaml.safe_dump({"layers": {}, "paths": source_paths}),
        encoding="utf-8",
    )
    cfg, session = _minimal_snapshot_session(tmp_path, config_path)

    out_path = tmp_path / "snapshot.yaml"
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["paths"] == source_paths


_EDITOR_USER_CONFIG_KEYS = (
    "preview_quality",
    "ui_width_mode",
    "ui_width",
    "ui_fade",
)


def test_write_session_snapshot_editor_omits_editor_fields(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "cleave.config.yaml"
    config_path.write_text("layers: {}\n", encoding="utf-8")
    cfg, session = _minimal_snapshot_session(tmp_path, config_path)
    cfg = CleaveConfig(
        paths=cfg.paths,
        layers=cfg.layers,
        editor=EditorConfig(
            preview_quality="performance",
            ui_width_mode="fixed",
            ui_width=80,
            ui_fade=5.0,
        ),
        config_path=cfg.config_path,
        user_config_path=cfg.user_config_path,
    )

    out_path = tmp_path / "snapshot.yaml"
    write_session_snapshot(out_path, cfg=cfg, session=session)

    visualizer = yaml.safe_load(out_path.read_text(encoding="utf-8"))["editor"]
    for key in _EDITOR_USER_CONFIG_KEYS:
        assert key not in visualizer


def test_write_session_snapshot_includes_locked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
        )

        session = TuningSession(
            layer_z_order=list(DEFAULT_LAYER_SLOTS),
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                    locked=(slot == "layer_2"),
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["layer_2"]["locked"] is True
        for slot in DEFAULT_LAYER_SLOTS:
            if slot != "layer_2":
                assert data["layers"][slot]["locked"] is False


def test_write_session_snapshot_sparse_effects() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
        )

        session = TuningSession(
            layer_z_order=list(DEFAULT_LAYER_SLOTS),
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                    effects={"pulse": {"onset": 60}} if slot == "layer_1" else {},
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["layer_1"]["effects"] == {"pulse": {"onset": 60}}
        assert "effects" not in data["layers"]["layer_2"]


def test_write_session_snapshot_sparse_all_effect_types() -> None:
    """Non-zero effect keys persist; zero drivers and empty effect groups are omitted."""
    session_effects: dict[str, dict[str, dict[str, int]]] = {
        "layer_1": {
            "pulse": {"onset": 35},
            "flash": {"onset": 15},
            "grit": {"onset": 10},
        },
        "layer_2": {
            "pulse": {"sub_bass": 40, "mid_bass": 0},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        },
        "layer_3": {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
            "grit": {"rms": 0},
        },
        "layer_4": {
            "pulse": {"centroid": 30},
            "flash": {"centroid": 0},
            "grit": {"centroid": 5},
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
        )

        session = TuningSession(
            layer_z_order=list(DEFAULT_LAYER_SLOTS),
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                    effects=session_effects[slot],
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["layer_1"]["effects"] == session_effects["layer_1"]
        assert data["layers"]["layer_2"]["effects"] == {
            "pulse": {"sub_bass": 40},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        }
        assert data["layers"]["layer_3"]["effects"] == {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
        }
        assert data["layers"]["layer_4"]["effects"] == {
            "pulse": {"centroid": 30},
            "grit": {"centroid": 5},
        }

        round_trip, _ = _parse_layers({"layers": data["layers"]}, preset_root)
        assert round_trip["layer_1"].effects == session_effects["layer_1"]
        assert round_trip["layer_2"].effects["pulse"] == {"sub_bass": 40}
        assert round_trip["layer_3"].effects["hue"] == {"pitch": 25}


def _stem_for_snapshot_slot(slot: str) -> str:
    return TEST_LAYER_STEMS.get(slot, "full_mix")


def _snapshot_round_trip_layer_count(layer_count: int) -> None:
    slots = [f"layer_{i}" for i in range(1, layer_count + 1)]
    session_order = list(reversed(slots))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                    preset=preset_root
                    / _stem_for_snapshot_slot(slot)
                    / "anchor.milk",
                    stem=_stem_for_snapshot_slot(slot),
                )
                for slot in slots
            },
            editor=EditorConfig(),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
            layer_z_order=list(slots),
        )

        session = TuningSession(
            layer_z_order=session_order,
            layers={
                slot: LayerRuntime(
                    stem=_stem_for_snapshot_slot(slot),
                    playlist=playlist_at_dir(
                        preset_root / _stem_for_snapshot_slot(slot), index=0
                    ),
                    browse_floor=preset_root / _stem_for_snapshot_slot(slot),
                )
                for slot in slots
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert set(data["layers"]) == set(slots)
        assert data["layer_z_order"] == session_order

        round_trip, ctx = _parse_layers({"layers": data["layers"]}, preset_root)
        assert set(round_trip) == set(slots)
        assert ctx.layer_slots == tuple(sorted(slots, key=lambda s: int(s.split("_")[1])))


@pytest.mark.parametrize("layer_count", [3, 6])
def test_write_session_snapshot_persist_layers_round_trip(layer_count: int) -> None:
    _snapshot_round_trip_layer_count(layer_count)


def test_write_session_snapshot_uses_session_z_order_when_valid() -> None:
    session_order = ["layer_4", "layer_1", "layer_2", "layer_3"]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
            layer_z_order=list(DEFAULT_LAYER_SLOTS),
        )

        session = TuningSession(
            layer_z_order=session_order,
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layer_z_order"] == session_order


def test_write_session_snapshot_falls_back_to_cfg_z_order_when_invalid() -> None:
    cfg_order = ["layer_1", "layer_3", "layer_2", "layer_4"]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
            layer_z_order=cfg_order,
        )

        session = TuningSession(
            layer_z_order=["layer_1", "layer_2"],
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layer_z_order"] == list(cfg_order)


def test_write_session_snapshot_includes_upscale() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(width=1280, height=720, upscale=2.0),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
        )

        session = TuningSession(
            layer_z_order=list(DEFAULT_LAYER_SLOTS),
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["editor"]["upscale"] == 2.0


def test_write_session_snapshot_sparse_beat_sensitivity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(beat_sensitivity=2.0),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
        )

        session = TuningSession(
            layer_z_order=list(DEFAULT_LAYER_SLOTS),
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                    beat_sensitivity=1.5 if slot == "layer_2" else 2.0,
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["editor"]["beat_sensitivity"] == 2.0
        assert "beat_sensitivity" not in data["layers"]["layer_1"]
        assert data["layers"]["layer_2"]["beat_sensitivity"] == 1.5


def test_write_session_snapshot_omits_all_zero_effects() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        make_preset_dirs(preset_root)

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
            },
            editor=EditorConfig(),
            config_path=config_path,
            user_config_path=root / "user-config.yaml",
        )

        session = TuningSession(
            layer_z_order=list(DEFAULT_LAYER_SLOTS),
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                    effects=(
                        {"pulse": {"onset": 0}}
                        if slot == "layer_3"
                        else {}
                    ),
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert "effects" not in data["layers"]["layer_3"]


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
    make_preset_dirs(preset_root)

    config_path = root / "cleave.config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "layers": {slot: {**template_layer_entry(slot), "preset": f"presets/{TEST_LAYER_STEMS[slot]}/anchor.milk"} for slot in DEFAULT_LAYER_SLOTS},
                "render": {
                    "fps": 30,
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
            slot: LayerConfig(
                preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
        editor=EditorConfig(),
        config_path=config_path,
        user_config_path=root / "user-config.yaml",
        render=RenderConfig(
            overlay=_render_overlay_cfg(),
            post_fx=default_render_post_fx_config(enabled=True, fade_in=30.0, fade_out=4.0),
        ),
    )
    session = TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        render_post_fx=default_render_post_fx_runtime(
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
            slot: LayerRuntime(
                playlist=playlist_at_dir(preset_root / slot, index=0),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
    )
    return cfg, session, root / "snapshot.yaml"


def test_write_session_snapshot_persists_render_overlay(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["render"]["width"] == DEFAULT_RENDER_WIDTH
    assert data["render"]["height"] == DEFAULT_RENDER_HEIGHT
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

    round_trip = parse_render_section(data)
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

    round_trip = parse_render_section(data)
    assert round_trip is not None
    assert round_trip.post_fx is not None
    assert round_trip.post_fx.enabled is True
    assert round_trip.post_fx.fade_in == 12.0
    assert round_trip.post_fx.fade_out == 3.0
    hr = post_fx["highlight_rolloff"]
    assert hr["mode"] == "composite"
    assert hr["curve"] == "rolloff"
    assert hr["threshold_pct"] == 78
    assert round_trip.post_fx.highlight_rolloff.threshold_pct == 78
    assert round_trip.post_fx.highlight_rolloff.mode == "composite"
    assert round_trip.post_fx.highlight_rolloff.curve == "rolloff"


def test_write_session_snapshot_persists_highlight_rolloff_curve(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.render_post_fx.highlight_rolloff.curve = "aces_fit"
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    hr = data["render"]["post_fx"]["highlight_rolloff"]
    assert hr["curve"] == "aces_fit"

    round_trip = parse_render_section(data)
    assert round_trip is not None
    assert round_trip.post_fx is not None
    assert round_trip.post_fx.highlight_rolloff.curve == "aces_fit"


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
        editor=cfg.editor,
        config_path=cfg.config_path,
        user_config_path=cfg.user_config_path,
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
        TimelineCue(t=2.5, layers={"layer_1": False, "layer_2": True}),
        TimelineCue(t=10.0, layers={"layer_3": False}),
    ]
    write_session_snapshot(out_path, cfg=cfg, session=session)

    raw = out_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    assert list(data.keys())[-1] == "timeline"
    assert data["timeline"]["enabled"] is True
    assert data["timeline"]["cues"] == [
        {"t": 2.5, "layers": {"layer_1": False, "layer_2": True}},
        {"t": 10.0, "layers": {"layer_3": False}},
    ]

    timeline = parse_timeline_section(
        data,
        ParseCtx(layer_slots=tuple(cfg.layer_z_order)),
    )
    assert timeline is not None
    playlists = _round_trip_playlists(cfg.paths.preset_root)
    cfg_with_timeline = CleaveConfig(
        paths=cfg.paths,
        layers=cfg.layers,
        editor=cfg.editor,
        config_path=out_path,
        user_config_path=cfg.user_config_path,
        render=cfg.render,
        timeline=timeline,
    )
    session2 = session_from_cfg(cfg_with_timeline, playlists)
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


def _round_trip_preset_dirs(root: Path) -> Path:
    preset_root = root / "presets"
    make_preset_dirs(preset_root)
    return preset_root


def _round_trip_playlists(preset_root: Path) -> dict[str, object]:
    return {
        slot: playlist_at_dir(preset_root / TEST_LAYER_STEMS[slot], index=0)
        for slot in DEFAULT_LAYER_SLOTS
    }


def test_session_snapshot_full_round_trip(tmp_path: Path) -> None:
    root = tmp_path
    preset_root = _round_trip_preset_dirs(root)
    texture_path = root / "textures"
    texture_path.mkdir()

    config_path = root / "cleave-viz.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "editor": {
                    "name": "round-trip-test",
                    "width": 1280,
                    "height": 720,
                    "upscale": 1.5,
                    "beat_sensitivity": 2.2,
                },
                "paths": {
                    "preset_root": str(preset_root),
                    "texture_paths": [str(texture_path)],
                },
                "layer_z_order": ["layer_3", "layer_1", "layer_4", "layer_2"],
                "layers": {
                    "layer_1": {
                        "stem": "drums",
                        "preset": "drums/anchor.milk",
                        "enabled": True,
                        "opacity": 0.9,
                        "blend_mode": "add",
                        "locked": True,
                        "effects": {"pulse": {"onset": 40}},
                    },
                    "layer_2": {
                        "stem": "bass",
                        "preset": "bass/anchor.milk",
                        "enabled": True,
                        "opacity": 1.0,
                        "blend_mode": "black-key",
                        "beat_sensitivity": 1.8,
                    },
                    "layer_3": {
                        "stem": "vocals",
                        "preset": "vocals/anchor.milk",
                        "enabled": False,
                        "opacity": 0.5,
                        "blend_mode": "black-key",
                        "effects": {"hue": {"pitch": 25}},
                    },
                    "layer_4": {
                        "stem": "other",
                        "preset": "other/anchor.milk",
                        "enabled": True,
                        "opacity": 1.0,
                        "blend_mode": "black-key",
                    },
                },
                "render": {
                    "fps": 30,
                    "post_fx": {
                        "enabled": True,
                        "fade_in": 30,
                        "fade_out": 4,
                    },
                    "overlay": {
                        "enabled": True,
                        "start_delay": 10,
                        "display_time": 30,
                        "position": "bottom-left",
                        "title": {
                            "content": "Round Trip Title",
                            "font-size": 24,
                            "font-colour": "#ffffff",
                            "margin-bottom": 10,
                        },
                        "body": {
                            "content": "Round trip body",
                            "font-size": 18,
                            "colour": "#ffffff",
                        },
                        "background": {
                            "margin": 40,
                            "padding": 20,
                            "colour": "#000000",
                            "opacity": 0.7,
                            "border": {"colour": "#ffffff", "width": 4},
                        },
                    },
                },
                "timeline": {
                    "enabled": True,
                    "cues": [
                        {"t": 1.0, "layers": {"layer_1": False, "layer_2": True}},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(config_path=config_path)
    playlists = _round_trip_playlists(preset_root)
    session = session_from_cfg(cfg, playlists)

    session.layer_z_order = ["layer_4", "layer_1", "layer_2", "layer_3"]
    session.layers["layer_1"].opacity_pct = 65
    session.layers["layer_1"].blend_mode = "black-key"
    session.layers["layer_1"].locked = False
    session.layers["layer_2"].beat_sensitivity = 2.5
    session.layers["layer_3"].enabled = True
    session.layers["layer_3"].effects = {"flash": {"rms": 15}}
    session.render_overlay.display_time = 55.0
    session.render_overlay.start_delay = 8.0
    session.render_overlay.position = "top-right"
    session.render_overlay.opacity_pct = 80
    session.render_post_fx.fade_in = 18.0
    session.render_post_fx.fade_out = 2.0
    session.timeline.cues = [
        TimelineCue(t=1.0, layers={"layer_1": False, "layer_2": True}),
        TimelineCue(t=12.5, layers={"layer_3": False, "layer_4": True}),
    ]

    expected = persisted_session_payload(cfg, session)
    assert expected["editor"]["upscale"] == 1.5

    sig_before = persisted_session_signature(cfg, session)
    cfg_upscale_changed = CleaveConfig(
        paths=cfg.paths,
        layers=cfg.layers,
        editor=EditorConfig(
            width=cfg.editor.width,
            height=cfg.editor.height,
            upscale=2.0,
            beat_sensitivity=cfg.editor.beat_sensitivity,
        ),
        config_path=cfg.config_path,
        user_config_path=cfg.user_config_path,
        layer_z_order=cfg.layer_z_order,
        render=cfg.render,
        timeline=cfg.timeline,
    )
    assert persisted_session_signature(cfg_upscale_changed, session) != sig_before

    snapshot_path = root / "snapshot.yaml"
    write_session_snapshot(snapshot_path, cfg=cfg, session=session)

    snapshot_data = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot_data["editor"]["upscale"] == 1.5
    assert snapshot_data["editor"]["beat_sensitivity"] == 2.2

    cfg2 = load_config(config_path=snapshot_path)
    session2 = session_from_cfg(cfg2, _round_trip_playlists(preset_root))
    actual = persisted_session_payload(cfg2, session2)

    assert actual == expected
