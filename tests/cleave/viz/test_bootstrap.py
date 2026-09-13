"""Unit tests for visualizer bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

from cleave.config import VIZ_CONFIG_FILENAME
from cleave.viz.bootstrap import resolve_config_path


def test_resolve_config_path_prefers_cli_override(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / VIZ_CONFIG_FILENAME).write_text("editor: {}\n", encoding="utf-8")

    override = tmp_path / "override.yaml"
    override.write_text("editor: {}\n", encoding="utf-8")

    assert resolve_config_path(override, project) == override


def test_resolve_config_path_uses_project_config(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / VIZ_CONFIG_FILENAME
    project_config.write_text("editor: {}\n", encoding="utf-8")

    assert resolve_config_path(None, project) == project_config


def test_resolve_config_path_missing_project_config_returns_none(tmp_path: Path) -> None:
    project = tmp_path / "empty-project"
    project.mkdir()

    assert resolve_config_path(None, project) is None
