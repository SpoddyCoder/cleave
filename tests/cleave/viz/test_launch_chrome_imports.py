"""Launch chrome is ImGui. Pygame overlay modules and draw helpers are gone."""

from __future__ import annotations

import ast
from pathlib import Path

_VIZ = Path(__file__).resolve().parents[3] / "cleave" / "viz"
_GONE_MODULES = ("file_picker_overlay", "modal_overlay")
_GONE_FUNCTIONS = ("compose_loading_surface", "draw_loading_screen")
_FORBIDDEN = _GONE_MODULES + _GONE_FUNCTIONS


def _imported_names(source: str) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
            names.extend(alias.name for alias in node.names)
    return names


def _defined_names(source: str) -> set[str]:
    return {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def test_viz_does_not_import_file_picker_overlay_or_modal_overlay() -> None:
    for name in _GONE_MODULES:
        assert not (_VIZ / f"{name}.py").exists()
        assert not (_VIZ / name).exists()

    offenders: list[str] = []
    for path in sorted(_VIZ.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        defined = _defined_names(source) & set(_GONE_FUNCTIONS)
        if defined:
            offenders.append(f"{path.name} defines {sorted(defined)}")
        for module in _imported_names(source):
            parts = module.split(".")
            if any(name in parts for name in _FORBIDDEN):
                offenders.append(f"{path.name}: {module}")
    assert offenders == []
