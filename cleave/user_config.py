"""User-level Cleave preferences (~/.config/cleave/config.yaml)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cleave.config import CleaveConfig, EditorConfig, dump_yaml
from cleave.paths import WINDOWS_APP_FOLDER, XDG_APP_FOLDER
from cleave.config_schema.editor import (
    DEFAULT_HELP_WIDTH,
    DEFAULT_NAVIGATOR_HEIGHT,
    DEFAULT_UI_SCALE,
    DEFAULT_INSPECTOR_WIDTH,
    DEFAULT_HELP_SIDE,
    DEFAULT_HIGHLIGHT_NEW_PAGE,
    DEFAULT_NAVIGATOR_SIDE,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_NOTIFICATION_DISPLAY_SEC,
    DEFAULT_RESIDUAL_LATENCY_MS,
    ColumnSide,
    EditorPreviewQuality,
    dump_editor_section,
    parse_editor_section,
)
from cleave.config_schema.window import (
    WINDOW_SECTION_KEY,
    WindowGeometry,
    dump_window_section,
    parse_window_section,
)

USER_CONFIG_FILENAME = "config.yaml"


def user_config_path() -> Path:
    """Return the default user config file path.

    Windows: ``%APPDATA%\\Cleave\\config.yaml``. Linux: XDG
    (``XDG_CONFIG_HOME/cleave`` or ``~/.config/cleave``).
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return (Path(appdata) / WINDOWS_APP_FOLDER / USER_CONFIG_FILENAME).resolve()
        return (
            Path.home() / "AppData" / "Roaming" / WINDOWS_APP_FOLDER / USER_CONFIG_FILENAME
        ).resolve()
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return (Path(xdg_config_home) / XDG_APP_FOLDER / USER_CONFIG_FILENAME).resolve()
    return (Path.home() / ".config" / XDG_APP_FOLDER / USER_CONFIG_FILENAME).resolve()


@dataclass(frozen=True)
class EditorSettings:
    preview_quality: EditorPreviewQuality
    notification_display_sec: int
    residual_latency_ms: int
    inspector_width: int = DEFAULT_INSPECTOR_WIDTH
    help_width: int = DEFAULT_HELP_WIDTH
    navigator_height: int = DEFAULT_NAVIGATOR_HEIGHT
    ui_scale: int = DEFAULT_UI_SCALE
    navigator_side: ColumnSide = DEFAULT_NAVIGATOR_SIDE
    help_side: ColumnSide = DEFAULT_HELP_SIDE
    highlight_new_page: bool = DEFAULT_HIGHLIGHT_NEW_PAGE


@dataclass(frozen=True)
class UserConfig:
    editor: EditorSettings
    preset_root: Path | None
    texture_paths: tuple[Path, ...] | None
    path: Path


def default_editor_settings() -> EditorSettings:
    return EditorSettings(
        preview_quality=DEFAULT_EDITOR_PREVIEW_QUALITY,
        notification_display_sec=DEFAULT_NOTIFICATION_DISPLAY_SEC,
        residual_latency_ms=DEFAULT_RESIDUAL_LATENCY_MS,
        inspector_width=DEFAULT_INSPECTOR_WIDTH,
        help_width=DEFAULT_HELP_WIDTH,
        navigator_height=DEFAULT_NAVIGATOR_HEIGHT,
        ui_scale=DEFAULT_UI_SCALE,
        navigator_side=DEFAULT_NAVIGATOR_SIDE,
        help_side=DEFAULT_HELP_SIDE,
        highlight_new_page=DEFAULT_HIGHLIGHT_NEW_PAGE,
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


def saved_ui_scale(path: Path | None = None) -> int:
    """The saved editor UI scale, for the window before the project config loads.

    An unreadable user config falls back to the default; the full config load
    reports that error in the window.
    """
    try:
        return load_user_config(path).editor.ui_scale
    except (OSError, ValueError, yaml.YAMLError):
        return DEFAULT_UI_SCALE


def editor_settings_from_config(cfg: EditorConfig) -> EditorSettings:
    return EditorSettings(
        preview_quality=cfg.preview_quality,
        notification_display_sec=cfg.notification_display_sec,
        residual_latency_ms=cfg.residual_latency_ms,
        inspector_width=cfg.inspector_width,
        help_width=cfg.help_width,
        navigator_height=cfg.navigator_height,
        ui_scale=cfg.ui_scale,
        navigator_side=cfg.navigator_side,
        help_side=cfg.help_side,
        highlight_new_page=cfg.highlight_new_page,
    )


def persist_editor_settings(cfg: CleaveConfig) -> None:
    write_user_config(
        editor_settings_from_config(cfg.editor),
        cfg.user_config_path,
    )


def _write_user_config_section(path: Path, key: str, section: dict[str, Any]) -> None:
    """Replace one top-level section and keep the rest of the file."""
    data: dict[str, Any] = {}
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            existing = yaml.safe_load(fh)
        if isinstance(existing, dict):
            data = existing
        elif existing is not None:
            raise ValueError(f"user config root must be a mapping: {path}")

    data[key] = section
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)


def write_user_config(editor: EditorSettings, path: Path) -> None:
    _write_user_config_section(path, "editor", dump_editor_section(editor))


def saved_window_geometry(path: Path | None = None) -> WindowGeometry:
    """The saved window size and maximised state, before any project loads.

    A missing or unreadable user config gives the default geometry.
    """
    resolved = (path or user_config_path()).resolve()
    try:
        if not resolved.is_file():
            return WindowGeometry()
        with resolved.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            return WindowGeometry()
        return parse_window_section(data)
    except (OSError, ValueError, yaml.YAMLError):
        return WindowGeometry()


def persist_window_geometry(
    geometry: WindowGeometry, path: Path | None = None
) -> None:
    """Write only the ``window:`` section of the user config."""
    resolved = (path or user_config_path()).resolve()
    _write_user_config_section(
        resolved, WINDOW_SECTION_KEY, dump_window_section(geometry)
    )
