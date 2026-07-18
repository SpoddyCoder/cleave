"""Tests for user-level Cleave config (~/.config/cleave/config.yaml)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cleave.config_schema import (
    DEFAULT_UI_FADE_SEC,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_RESIDUAL_LATENCY_MS,
)
from dataclasses import replace

from cleave.config import EditorConfig
from cleave.user_config import (
    EditorSettings,
    default_editor_settings,
    editor_settings_from_config,
    load_user_config,
    persist_editor_settings,
    user_config_path,
    write_user_config,
)
from tests.support.viz import make_test_cfg


def test_load_user_config_missing_file_returns_defaults(tmp_path: Path) -> None:
    missing = tmp_path / "config.yaml"
    cfg = load_user_config(missing)

    assert cfg.path == missing.resolve()
    assert cfg.preset_root is None
    assert cfg.texture_paths is None
    assert cfg.editor.preview_quality == DEFAULT_EDITOR_PREVIEW_QUALITY
    assert cfg.editor.ui_width_mode == DEFAULT_UI_WIDTH_MODE
    assert cfg.editor.ui_width == DEFAULT_UI_WIDTH
    assert cfg.editor.ui_fade == DEFAULT_UI_FADE_SEC
    assert cfg.editor.residual_latency_ms == DEFAULT_RESIDUAL_LATENCY_MS


def test_default_editor_settings_matches_schema_defaults() -> None:
    editor = default_editor_settings()
    assert editor.preview_quality == DEFAULT_EDITOR_PREVIEW_QUALITY
    assert editor.ui_width_mode == DEFAULT_UI_WIDTH_MODE
    assert editor.ui_width == DEFAULT_UI_WIDTH
    assert editor.ui_fade == DEFAULT_UI_FADE_SEC
    assert editor.residual_latency_ms == DEFAULT_RESIDUAL_LATENCY_MS


def test_load_user_config_empty_file_returns_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("", encoding="utf-8")

    cfg = load_user_config(config_path)

    assert cfg.path == config_path.resolve()
    assert cfg.editor == default_editor_settings()
    assert cfg.preset_root is None
    assert cfg.texture_paths is None


def test_load_user_config_rejects_non_mapping_root(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("not a mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="user config root must be a mapping"):
        load_user_config(config_path)


def test_load_user_config_parses_editor_and_paths(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    texture_a = tmp_path / "tex-a.png"
    texture_b = tmp_path / "tex-b.png"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "editor": {
                    "preview_quality": "performance",
                    "ui_width_mode": "fixed",
                    "ui_width": 80,
                    "ui_fade": 25,
                },
                "paths": {
                    "preset_root": str(preset_root),
                    "texture_paths": [str(texture_a), str(texture_b)],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    cfg = load_user_config(config_path)

    assert cfg.editor.preview_quality == "performance"
    assert cfg.editor.ui_width_mode == "fixed"
    assert cfg.editor.ui_width == 80
    assert cfg.editor.ui_fade == 25.0
    assert cfg.preset_root == preset_root.resolve()
    assert cfg.texture_paths == (texture_a.resolve(), texture_b.resolve())


def test_write_user_config_preserves_paths_and_rewrites_editor(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "editor": {
                    "preview_quality": "balanced",
                    "ui_width_mode": "flexible",
                    "ui_width": 110,
                    "ui_fade": 10,
                },
                "paths": {
                    "preset_root": str(preset_root),
                    "texture_paths": [str(tmp_path / "tex.png")],
                },
                "future_key": {"keep": True},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    new_editor = EditorSettings(
        preview_quality="ultra-performance",
        ui_width_mode="fixed",
        ui_width=90,
        ui_fade=30.0,
        residual_latency_ms=210,
    )
    write_user_config(new_editor, config_path)

    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    assert data["editor"]["preview_quality"] == "ultra-performance"
    assert data["editor"]["ui_width_mode"] == "fixed"
    assert data["editor"]["ui_width"] == 90
    assert data["editor"]["ui_fade"] == 30.0
    assert data["editor"]["residual_latency_ms"] == 210
    assert data["paths"]["preset_root"] == str(preset_root)
    assert data["paths"]["texture_paths"] == [str(tmp_path / "tex.png")]
    assert data["future_key"] == {"keep": True}


def test_editor_settings_from_config() -> None:
    vis = EditorConfig(
        preview_quality="performance",
        ui_width_mode="fixed",
        ui_width=75,
        ui_fade=22.5,
        residual_latency_ms=150,
    )
    editor = editor_settings_from_config(vis)
    assert editor == EditorSettings(
        preview_quality="performance",
        ui_width_mode="fixed",
        ui_width=75,
        ui_fade=22.5,
        residual_latency_ms=150,
    )


def test_persist_editor_settings_writes_visualizer_editor_fields(
    tmp_path: Path,
) -> None:
    user_path = tmp_path / "config.yaml"
    cfg = replace(
        make_test_cfg(("layer_1",)),
        user_config_path=user_path,
        editor=EditorConfig(
            preview_quality="ultra-performance",
            ui_width_mode="fixed",
            ui_width=88,
            ui_fade=17.5,
            residual_latency_ms=200,
        ),
    )

    persist_editor_settings(cfg)

    loaded = load_user_config(user_path)
    assert loaded.editor.preview_quality == "ultra-performance"
    assert loaded.editor.ui_width_mode == "fixed"
    assert loaded.editor.ui_width == 88
    assert loaded.editor.ui_fade == 17.5
    assert loaded.editor.residual_latency_ms == 200


def test_user_config_path_respects_xdg_config_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    expected = (tmp_path / "cleave" / "config.yaml").resolve()
    assert user_config_path() == expected
