"""Deleted panel modules must not be imported from the live viz package."""

from __future__ import annotations

import ast
from pathlib import Path

_VIZ = Path(__file__).resolve().parents[3] / "cleave" / "viz"
_FORBIDDEN = ("tuning_panel_draw", "tuning_panel_cache", "row_layout")


def _imported_modules(source: str) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_viz_sources_do_not_import_deleted_panel_modules() -> None:
    offenders: list[str] = []
    for path in sorted(_VIZ.rglob("*.py")):
        for module in _imported_modules(path.read_text(encoding="utf-8")):
            parts = module.split(".")
            if any(name in parts for name in _FORBIDDEN):
                offenders.append(f"{path.name}: {module}")
    assert offenders == []
