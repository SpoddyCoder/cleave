"""User-level Cleave preferences (~/.config/cleave/config.yaml)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cleave.config import CleaveConfig, EditorConfig, dump_yaml
from cleave.config_schema import (
    DEFAULT_UI_FADE_SEC,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    UiWidthMode,
    EditorPreviewQuality,
    dump_editor_section,
    parse_editor_section,
)

USER_CONFIG_FILENAME = "config.yaml"


def user_config_path() -> Path:
    """Return the default user config file path."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return (Path(xdg_config_home) / "cleave" / USER_CONFIG_FILENAME).resolve()
    return (Path.home() / ".config" / "cleave" / USER_CONFIG_FILENAME).resolve()


USER_CONFIG_PATH = user_config_path()


@dataclass(frozen=True)
class EditorSettings:
    preview_quality: EditorPreviewQuality
    ui_width_mode: UiWidthMode
    ui_width: int
    ui_fade: float


@dataclass(frozen=True)
class UserConfig:
    editor: EditorSettings
    preset_root: Path | None
    texture_paths: tuple[Path, ...] | None
    path: Path


def default_editor_settings() -> EditorSettings:
    return EditorSettings(
        preview_quality=DEFAULT_EDITOR_PREVIEW_QUALITY,
        ui_width_mode=DEFAULT_UI_WIDTH_MODE,
        ui_width=DEFAULT_UI_WIDTH,
        ui_fade=DEFAULT_UI_FADE_SEC,
    )


def _expand_path(path: Path | str) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def _parse_paths_section(
    data: dict[str, Any],
) -> tuple[Path | None, tuple[Path, ...] | None]:
    if "paths" not in data:
        return None, None
    paths = data["paths"]
    if not isinstance(paths, dict):
        raise ValueError("paths must be a mapping")

    preset_root: Path | None = None
    if "preset_root" in paths:
        preset_root = _expand_path(paths["preset_root"])

    texture_paths: tuple[Path, ...] | None = None
    if "texture_paths" in paths:
        raw = paths["texture_paths"]
        if not isinstance(raw, list):
            raise ValueError("paths.texture_paths must be a list")
        texture_paths = tuple(_expand_path(entry) for entry in raw)

    return preset_root, texture_paths


def load_user_config(path: Path | None = None) -> UserConfig:
    resolved = (path or user_config_path()).resolve()
    if not resolved.is_file():
        return UserConfig(
            editor=default_editor_settings(),
            preset_root=None,
            texture_paths=None,
            path=resolved,
        )

    with resolved.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"user config root must be a mapping: {resolved}")

    preset_root, texture_paths = _parse_paths_section(data)
    return UserConfig(
        editor=parse_editor_section(data),
        preset_root=preset_root,
        texture_paths=texture_paths,
        path=resolved,
    )


def editor_settings_from_config(cfg: EditorConfig) -> EditorSettings:
    return EditorSettings(
        preview_quality=cfg.preview_quality,
        ui_width_mode=cfg.ui_width_mode,
        ui_width=cfg.ui_width,
        ui_fade=cfg.ui_fade,
    )


def persist_editor_settings(cfg: CleaveConfig) -> None:
    write_user_config(
        editor_settings_from_config(cfg.editor),
        cfg.user_config_path,
    )


def write_user_config(editor: EditorSettings, path: Path) -> None:
    data: dict[str, Any] = {}
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            existing = yaml.safe_load(fh)
        if isinstance(existing, dict):
            data = existing
        elif existing is not None:
            raise ValueError(f"user config root must be a mapping: {path}")

    data["editor"] = dump_editor_section(editor)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
