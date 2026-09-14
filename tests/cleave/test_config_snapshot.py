"""Tests for Cleave config snapshot writing."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from cleave.config import (
    CleaveConfig,
    LayerConfig,
    PathsConfig,
    RenderOverlayAnimationConfig,
    RenderOverlayBackgroundConfig,
    RenderOverlayBorderConfig,
    RenderConfig,
    RenderOverlayCardConfig,
    RenderOverlayClosingAnimationConfig,
    RenderOverlaysConfig,
    RenderOverlayTextBlockConfig,
    RenderPostFxConfig,
    EditorConfig,
    _parse_layers,
    load_config,
)
from cleave.config_schema.compositor import DEFAULT_COMPOSITOR_HDR
from cleave.config_schema.descriptors import (
    ParseCtx,
)
from cleave.config_schema.editor import DEFAULT_BEAT_SENSITIVITY
from cleave.config_schema.layers import (
    DEFAULT_LAYER_SLOTS,
    template_layer_entry,
)
from cleave.config_schema.render import parse_render_section
from cleave.config_schema.timeline import parse_timeline_section
from cleave.paths import resource_dir
from cleave.project import CompositorSettings, MilkdropSettings, write_manifest
from tests.support.config import (
    TEST_LAYER_STEMS,
    default_render_post_fx_config,
    default_render_post_fx_runtime,
    layer_configs,
    layer_runtimes,
    make_preset_dirs,
    slot_for_stem,
    write_minimal_config,
)
from cleave.config_snapshot import (
    persisted_session_payload,
    persisted_session_signature,
    write_session_snapshot,
)
from cleave.stems import STEM_NAMES
from cleave.preset_playlist import playlist_at_dir
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.session import (
    LayerRuntime,
    RenderOverlayAnimationRuntime,
    RenderOverlayCardRuntime,
    RenderOverlayClosingAnimationRuntime,
    RenderOverlaysRuntime,
    TuningSession,
    default_render_overlay_card_runtime,
    session_from_cfg,
)


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


def test_write_session_snapshot_omits_editor_section(
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

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert "editor" not in data


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


def test_write_session_snapshot_uses_session_z_order_when_membership_diverges() -> None:
    cfg_order = ["layer_1", "layer_3", "layer_2", "layer_4"]
    session_order = ["layer_1", "layer_2"]
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
            layer_z_order=session_order,
            layers={
                slot: LayerRuntime(
                    stem=TEST_LAYER_STEMS[slot],
                    playlist=playlist_at_dir(
                        preset_root / TEST_LAYER_STEMS[slot], index=0
                    ),
                    browse_floor=preset_root / TEST_LAYER_STEMS[slot],
                )
                for slot in session_order
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layer_z_order"] == session_order


def test_write_session_snapshot_omits_window_size() -> None:
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
        assert "editor" not in data


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
                    beat_sensitivity=(
                        1.5 if slot == "layer_2" else DEFAULT_BEAT_SENSITIVITY
                    ),
                )
                for slot in DEFAULT_LAYER_SLOTS
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert "editor" not in data
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


def _render_overlay_card_cfg(
    *,
    closing: bool = False,
    content_title: str = "My Title",
    content_body: str = "Line one\nLine two",
) -> RenderOverlayCardConfig:
    if closing:
        animation: (
            RenderOverlayAnimationConfig | RenderOverlayClosingAnimationConfig
        ) = RenderOverlayClosingAnimationConfig(
            type="fade",
            slide_direction="left",
            disappear_at=0.0,
            display_time=30.0,
        )
    else:
        animation = RenderOverlayAnimationConfig(
            type="fade",
            slide_direction="left",
            appear_at=10.0,
            display_time=30.0,
        )
    return RenderOverlayCardConfig(
        enabled=True,
        title=RenderOverlayTextBlockConfig(
            content=content_title,
            font="monospace",
            font_size=24,
            colour=(255, 255, 255),
            background_colour=(51, 51, 255),
            margin_bottom=10,
        ),
        body=RenderOverlayTextBlockConfig(
            content=content_body,
            font="monospace",
            font_size=18,
            colour=(255, 255, 255),
            background_colour=(51, 51, 255),
        ),
        animation=animation,
        position="bottom-left",
        background=RenderOverlayBackgroundConfig(
            margin=10,
            padding=10,
            colour=(34, 51, 68),
            opacity=1.0,
            border=RenderOverlayBorderConfig(colour=(34, 51, 68), width=2),
        ),
    )


def _render_overlays_cfg() -> RenderOverlaysConfig:
    return RenderOverlaysConfig(
        opening_card=_render_overlay_card_cfg(),
        closing_card=_render_overlay_card_cfg(
            closing=True, content_title="Closing", content_body="End"
        ),
    )


def _opening_card_yaml() -> dict:
    return {
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
        "animation": {
            "type": "fade",
            "slide-direction": "left",
            "appear-at": 10,
            "display-time": 30,
        },
        "position": "bottom-left",
        "background": {
            "margin": 10,
            "padding": 10,
            "colour": "#223344",
            "opacity": 1.0,
            "border": {"colour": "#223344", "width": 2},
        },
    }


def _snapshot_fixture(tmp_path: Path) -> tuple[CleaveConfig, TuningSession, Path]:
    root = tmp_path
    preset_root = root / "presets"
    make_preset_dirs(preset_root)

    config_path = root / "cleave.config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "layers": {
                    slot: {
                        **template_layer_entry(slot),
                        "preset": f"presets/{TEST_LAYER_STEMS[slot]}/anchor.milk",
                    }
                    for slot in DEFAULT_LAYER_SLOTS
                },
                "render": {
                    "fps": 30,
                    "post_fx": {
                        "enabled": True,
                        "fade_in": 30,
                        "fade_out": 4,
                    },
                    "overlays": {
                        "opening-card": _opening_card_yaml(),
                        "closing-card": {
                            "enabled": True,
                            "title": {
                                "content": "Closing",
                                "font-size": 24,
                                "font-colour": "#ffffff",
                            },
                            "body": {
                                "content": "End\n",
                                "font-size": 18,
                                "colour": "#ffffff",
                            },
                            "animation": {
                                "type": "fade",
                                "slide-direction": "left",
                                "disappear-at": 0,
                                "display-time": 30,
                            },
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
            overlays=_render_overlays_cfg(),
            post_fx=default_render_post_fx_config(enabled=True, fade_in=30.0, fade_out=4.0),
        ),
    )
    opening = RenderOverlayCardRuntime(
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
        animation=RenderOverlayAnimationRuntime(
            type="fade",
            slide_direction="left",
            appear_at=20.0,
            display_time=40.0,
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
        render_overlays=RenderOverlaysRuntime(
            expanded=False,
            opening_card=opening,
            closing_card=default_render_overlay_card_runtime(closing=True),
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
    overlays = data["render"]["overlays"]
    opening = overlays["opening-card"]
    assert "overlay" not in data["render"]
    assert "width" not in data["render"]
    assert "height" not in data["render"]
    assert "fps" not in data["render"]
    assert opening["enabled"] is True
    assert opening["title"]["content"] == "My Title"
    assert opening["body"]["content"] == "Line one\nLine two\n"
    assert opening["animation"]["appear-at"] == 20.0
    assert opening["animation"]["display-time"] == 40.0
    assert opening["position"] == "top-right"
    assert opening["title"]["font-size"] == 14
    assert opening["title"]["font"] == "dejavusans"
    assert opening["title"]["margin-bottom"] == 6
    assert opening["body"]["font-size"] == 18
    assert opening["body"]["font"] == "ubuntumono"
    assert opening["title"]["font-colour"] == "#ffffff"
    assert opening["body"]["colour"] == "#ffffff"
    assert opening["background"]["margin"] == 10
    assert opening["background"]["padding"] == 10
    assert opening["background"]["colour"] == "#223344"
    assert opening["background"]["opacity"] == 0.75
    assert opening["background"]["border"]["colour"] == "#223344"
    assert opening["background"]["border"]["width"] == 4
    assert "closing-card" in overlays

    round_trip = parse_render_section(data)
    assert round_trip is not None
    assert round_trip.overlays is not None
    assert round_trip.overlays.opening_card.enabled is True
    assert round_trip.overlays.opening_card.animation.appear_at == 20.0
    assert round_trip.overlays.opening_card.title.font_size == 14
    assert round_trip.overlays.opening_card.title.font == "dejavusans"
    assert round_trip.overlays.opening_card.title.margin_bottom == 6
    assert round_trip.overlays.opening_card.body.font_size == 18
    assert round_trip.overlays.opening_card.body.font == "ubuntumono"
    assert round_trip.overlays.opening_card.background.opacity == 0.75
    assert round_trip.overlays.opening_card.background.border.width == 4


def test_write_session_snapshot_strips_legacy_overlay_font(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    config_path = tmp_path / "cleave.config.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["render"]["overlays"]["opening-card"]["font"] = {
        "size": 10,
        "colour": "#ffaa00",
    }
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    write_session_snapshot(out_path, cfg=cfg, session=session)

    snapshot = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert "font" not in snapshot["render"]["overlays"]["opening-card"]
    assert "overlay" not in snapshot["render"]


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


def test_write_session_snapshot_persists_render_pattern_mask(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    pm = session.render_pattern_mask
    pm.enabled = True
    pm.locked = True
    pm.type = "plasma"
    pm.density = 3.5
    pm.feather_pct = 100
    pm.invert = True
    pm.transition = 1.2
    pm.seed = 77
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    pattern_mask = data["render"]["pattern_mask"]
    assert pattern_mask == {
        "enabled": True,
        "locked": True,
        "type": "plasma",
        "density": 3.5,
        "feather_pct": 100,
        "invert": True,
        "transition": 1.2,
        "seed": 77,
    }

    round_trip = parse_render_section(data)
    assert round_trip is not None
    assert round_trip.pattern_mask is not None
    assert round_trip.pattern_mask.enabled is True
    assert round_trip.pattern_mask.locked is True
    assert round_trip.pattern_mask.type == "plasma"
    assert round_trip.pattern_mask.density == 3.5
    assert round_trip.pattern_mask.feather_pct == 100
    assert round_trip.pattern_mask.invert is True
    assert round_trip.pattern_mask.transition == 1.2
    assert round_trip.pattern_mask.seed == 77


def test_write_session_snapshot_persists_pattern_mask_disabled(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.render_pattern_mask.enabled = False
    session.render_pattern_mask.density = 4.0
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    pattern_mask = data["render"]["pattern_mask"]
    assert pattern_mask["enabled"] is False
    assert pattern_mask["density"] == 4.0


def test_write_session_snapshot_overwrites_stale_pattern_mask(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    config_path = tmp_path / "cleave.config.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["render"]["pattern_mask"] = {
        "enabled": True,
        "type": "radial",
        "density": 8.0,
        "feather_pct": 100,
        "invert": True,
        "transition": 2.0,
        "seed": 1,
        "locked": True,
    }
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    session.render_pattern_mask.enabled = False
    session.render_pattern_mask.type = "strips"
    session.render_pattern_mask.density = 1.5
    session.render_pattern_mask.feather_pct = 0
    session.render_pattern_mask.invert = False
    session.render_pattern_mask.transition = 0.0
    session.render_pattern_mask.seed = 0
    session.render_pattern_mask.locked = False
    write_session_snapshot(out_path, cfg=cfg, session=session)

    snapshot = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert snapshot["render"]["pattern_mask"] == {
        "enabled": False,
        "locked": False,
        "type": "strips",
        "density": 1.5,
        "feather_pct": 0,
        "invert": False,
        "transition": 0.0,
        "seed": 0,
    }


def test_write_session_snapshot_persists_full_render_payload(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.render_overlays.locked = True
    session.render_post_fx.locked = True
    session.render_post_fx.highlight_rolloff.ceiling_pct = 40
    session.render_post_fx.highlight_rolloff.desaturation_pct = 55
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["render"]["overlays"]["locked"] is True
    assert data["render"]["post_fx"]["locked"] is True
    hr = data["render"]["post_fx"]["highlight_rolloff"]
    assert hr["ceiling_pct"] == 40
    assert hr["desaturation_pct"] == 55

    round_trip = parse_render_section(data)
    assert round_trip is not None
    assert round_trip.overlays is not None
    assert round_trip.overlays.locked is True
    assert round_trip.post_fx is not None
    assert round_trip.post_fx.locked is True
    assert round_trip.post_fx.highlight_rolloff.ceiling_pct == 40
    assert round_trip.post_fx.highlight_rolloff.desaturation_pct == 55


def test_write_session_snapshot_preserves_unknown_render_keys(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    config_path = tmp_path / "cleave.config.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["render"]["experimental_flag"] = True
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    write_session_snapshot(out_path, cfg=cfg, session=session)

    snapshot = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert snapshot["render"]["experimental_flag"] is True


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
    session.render_overlays.opening_card.enabled = False
    session.render_overlay_solo = True
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["render"]["overlays"]["opening-card"]["enabled"] is False
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
    opening = data["render"]["overlays"]["opening-card"]
    assert opening["title"]["content"] == "Cleave Final Render"
    assert opening["position"] == "top-right"
    assert opening["title"]["font-size"] == 14


def test_write_session_snapshot_persists_timeline_at_bottom(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = True
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=2.5, level=1.0)],
        ),
        "layer_2": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=2.5, level=1.0)],
        ),
        "layer_3": TimelineLane(
            baseline=1.0,
            cues=[SlotCue(t=10.0, level=0.0)],
        ),
    }
    write_session_snapshot(out_path, cfg=cfg, session=session)

    raw = out_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    assert list(data.keys())[-1] == "timeline"
    assert data["timeline"]["enabled"] is True
    assert data["timeline"]["lanes"] == {
        "layer_1": {"baseline": 0.0, "cues": [{"t": 2.5, "level": 1.0}]},
        "layer_2": {"baseline": 0.0, "cues": [{"t": 2.5, "level": 1.0}]},
        "layer_3": {"baseline": 1.0, "cues": [{"t": 10.0, "level": 0.0}]},
    }

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
    assert session2.timeline.lanes["layer_1"] == session.timeline.lanes["layer_1"]
    assert session2.timeline.lanes["layer_2"] == session.timeline.lanes["layer_2"]
    assert session2.timeline.lanes["layer_3"] == session.timeline.lanes["layer_3"]


def test_write_session_snapshot_round_trips_lane_baseline_and_cues(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = True
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=1.0,
            cues=[SlotCue(t=12.0, level=0.0)],
        ),
    }
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["timeline"]["lanes"] == {
        "layer_1": {
            "baseline": 1.0,
            "cues": [{"t": 12.0, "level": 0.0}],
        },
    }

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
    assert session2.timeline.lanes["layer_1"] == session.timeline.lanes["layer_1"]


def test_write_session_snapshot_round_trips_cue_blend_and_role(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = True
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[
                SlotCue(t=2.5, level=1.0, blend="add", role="pulse"),
                SlotCue(t=5.0, level=0.0),
            ],
        ),
    }
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["timeline"]["lanes"]["layer_1"]["cues"] == [
        {"t": 2.5, "level": 1.0, "blend": "add", "role": "pulse"},
        {"t": 5.0, "level": 0.0},
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
    assert session2.timeline.lanes["layer_1"] == session.timeline.lanes["layer_1"]


def test_persisted_session_signature_moves_when_cue_blend_changes(
    tmp_path: Path,
) -> None:
    cfg, session, _out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = True
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=1.0, level=1.0)],
        ),
    }
    before = persisted_session_signature(cfg, session)
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=1.0, level=1.0, blend="add")],
        ),
    }
    assert persisted_session_signature(cfg, session) != before


def test_write_session_snapshot_level_only_cues_omit_blend_role_keys(
    tmp_path: Path,
) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = True
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=2.5, level=1.0)],
        ),
    }
    write_session_snapshot(out_path, cfg=cfg, session=session)
    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    cues = data["timeline"]["lanes"]["layer_1"]["cues"]
    assert cues == [{"t": 2.5, "level": 1.0}]
    assert "blend" not in cues[0]
    assert "role" not in cues[0]


def test_write_session_snapshot_persists_timeline_disabled_without_cues(
    tmp_path: Path,
) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.enabled = False
    session.timeline.lanes = {}
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["timeline"] == {
        "enabled": False,
        "locked": False,
        "placement_snap": "beat",
            "cuts": {
                "hard": {
                    "enabled": False,
                    "fade_in": 2.0,
                    "fade_out": 2.0,
                    "crossfade": False,
                },
                "soft": {
                    "enabled": False,
                    "fade_in": 2.0,
                    "fade_out": 2.0,
                    "crossfade": False,
                },
            },
        "preset": {
            "character": "breathing",
            "density": "normal",
            "cue_snap": "none",
            "song_marker_snap": None,
            "timeline_cuts": "by marker",
            "repopulate": "no",
            "conductor": False,
            "mode": "layers",
        },
        "limiter": {
            "enabled": True,
            "threshold": 0.65,
            "ratio": 3.0,
            "release": 0.45,
        },
    }


def test_write_session_snapshot_round_trips_timeline_preset(tmp_path: Path) -> None:
    cfg, session, out_path = _snapshot_fixture(tmp_path)
    session.timeline.timeline_preset_kind = "arc"
    session.timeline.timeline_preset_density = "dense"
    session.timeline.timeline_preset_cue_snap = "beats"
    session.timeline.timeline_preset_song_marker_snap = 5.0
    session.timeline.timeline_preset_timeline_cuts = "all soft"
    session.timeline.timeline_preset_repopulate = "directory random"
    session.timeline.timeline_preset_conductor = True
    session.timeline.timeline_preset_mode = "pattern_mask"
    write_session_snapshot(out_path, cfg=cfg, session=session)

    data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert data["timeline"]["preset"] == {
        "character": "arc",
        "density": "dense",
        "cue_snap": "beats",
        "song_marker_snap": 5.0,
        "timeline_cuts": "all soft",
        "repopulate": "directory random",
        "conductor": True,
        "mode": "pattern_mask",
    }

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
    assert session2.timeline.timeline_preset_kind == "arc"
    assert session2.timeline.timeline_preset_density == "dense"
    assert session2.timeline.timeline_preset_cue_snap == "beats"
    assert session2.timeline.timeline_preset_song_marker_snap == 5.0
    assert session2.timeline.timeline_preset_timeline_cuts == "all soft"
    assert session2.timeline.timeline_preset_repopulate == "directory random"
    assert session2.timeline.timeline_preset_conductor is True
    assert session2.timeline.timeline_preset_mode == "pattern_mask"


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
                    "overlays": {
                        "opening-card": {
                            "enabled": True,
                            "animation": {
                                "type": "fade",
                                "slide-direction": "left",
                                "appear-at": 10,
                                "display-time": 30,
                            },
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
                        "closing-card": {
                            "enabled": True,
                            "animation": {
                                "type": "fade",
                                "slide-direction": "left",
                                "disappear-at": 0,
                                "display-time": 30,
                            },
                            "position": "bottom-left",
                            "title": {
                                "content": "Closing",
                                "font-size": 24,
                                "font-colour": "#ffffff",
                            },
                            "body": {
                                "content": "End",
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
                },
                "timeline": {
                    "enabled": True,
                    "lanes": {
                        "layer_1": {
                            "baseline": 0.0,
                            "cues": [{"t": 1.0, "level": 0.0}],
                        },
                        "layer_2": {
                            "baseline": 0.0,
                            "cues": [{"t": 1.0, "level": 1.0}],
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "slug": "round-trip-test",
                "mix": {"filename": "mix.wav"},
                "ingest": {
                    "original_path": "/tmp/source.wav",
                    "separated_at": "2026-01-01T00:00:00+00:00",
                    "demucs_model": "htdemucs",
                },
                "milkdrop": {"beat_sensitivity": 2.2},
            },
            sort_keys=False,
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
    session.render_overlays.opening_card.animation.display_time = 55.0
    session.render_overlays.opening_card.animation.appear_at = 8.0
    session.render_overlays.opening_card.position = "top-right"
    session.render_overlays.opening_card.opacity_pct = 80
    session.render_post_fx.fade_in = 18.0
    session.render_post_fx.fade_out = 2.0
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=1.0, level=1.0)],
        ),
        "layer_2": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=1.0, level=1.0)],
        ),
        "layer_3": TimelineLane(
            baseline=1.0,
            cues=[SlotCue(t=12.5, level=0.0)],
        ),
        "layer_4": TimelineLane(
            baseline=1.0,
            cues=[SlotCue(t=12.5, level=0.0)],
        ),
    }

    expected = persisted_session_payload(cfg, session)
    assert "editor" not in expected
    assert cfg.milkdrop_beat_sensitivity == 2.2

    sig_before = persisted_session_signature(cfg, session)
    cfg_upscale_changed = CleaveConfig(
        paths=cfg.paths,
        layers=cfg.layers,
        editor=EditorConfig(
            width=cfg.editor.width,
            height=cfg.editor.height,
            upscale=2.0,
        ),
        config_path=cfg.config_path,
        user_config_path=cfg.user_config_path,
        layer_z_order=cfg.layer_z_order,
        render=cfg.render,
        timeline=cfg.timeline,
        milkdrop_beat_sensitivity=cfg.milkdrop_beat_sensitivity,
        project_slug=cfg.project_slug,
    )
    assert persisted_session_signature(cfg_upscale_changed, session) == sig_before

    snapshot_path = root / "snapshot.yaml"
    write_session_snapshot(snapshot_path, cfg=cfg, session=session)

    snapshot_data = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
    assert "editor" not in snapshot_data

    cfg2 = load_config(config_path=snapshot_path)
    session2 = session_from_cfg(cfg2, _round_trip_playlists(preset_root))
    actual = persisted_session_payload(cfg2, session2)

    assert actual == expected


def test_load_config_snapshot_resolves_switching_list_and_manifest_from_project(
    tmp_path: Path,
) -> None:
    """Child-process parse: snapshot must live in the project, loaded with project_root."""
    manifest_beat = 3.5
    manifest_hdr = False
    assert manifest_beat != DEFAULT_BEAT_SENSITIVITY
    assert manifest_hdr is not DEFAULT_COMPOSITOR_HDR
    project_dir = tmp_path / "song"
    pack_root = tmp_path / "pack-presets"
    config_path = write_minimal_config(project_dir, pack_root)
    foo = project_dir / "presets" / "foo.milk"
    foo.parent.mkdir(parents=True)
    foo.write_text("MILK\n", encoding="utf-8")
    write_manifest(
        project_dir,
        slug="song",
        mix_filename="song.wav",
        original_path=tmp_path / "source.wav",
        demucs_model="htdemucs",
        separated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        milkdrop=MilkdropSettings(beat_sensitivity=manifest_beat),
        compositor=CompositorSettings(hdr=manifest_hdr),
    )

    cfg = load_config(config_path, project_dir)
    session = session_from_cfg(cfg, _round_trip_playlists(pack_root))
    session.layers["layer_1"].preset_switching = "on"
    session.layers["layer_1"].preset_list = [str(foo.resolve())]

    snapshot_path = project_dir / "cleave-render-snapshot.yaml"
    write_session_snapshot(snapshot_path, cfg=cfg, session=session)

    loaded = load_config(snapshot_path, project_dir)
    assert loaded.layers["layer_1"].preset_switching_list == [foo.resolve()]
    assert loaded.milkdrop_beat_sensitivity == manifest_beat
    assert loaded.compositor_hdr is manifest_hdr

    tmp_copy = tmp_path / "outside" / "cleave-render-snapshot.yaml"
    tmp_copy.parent.mkdir()
    tmp_copy.write_text(snapshot_path.read_text(encoding="utf-8"), encoding="utf-8")
    loaded_tmp = load_config(tmp_copy, resource_dir())
    assert foo.resolve() not in loaded_tmp.layers["layer_1"].preset_switching_list
    assert loaded_tmp.layers["layer_1"].preset_switching_list == [
        (tmp_copy.parent / "presets" / "foo.milk").resolve()
    ]
    assert loaded_tmp.milkdrop_beat_sensitivity == DEFAULT_BEAT_SENSITIVITY
    assert loaded_tmp.compositor_hdr is DEFAULT_COMPOSITOR_HDR
