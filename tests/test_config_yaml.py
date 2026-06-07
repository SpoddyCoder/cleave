"""Tests for Cleave YAML serialization."""

from __future__ import annotations

import io

import yaml

from cleave.config import dump_yaml

_LONG_PRESET = (
    "presets-cream-of-the-crop/Drawing/Dunes/"
    "LuxXx - Melt down the Engine inz+.milk"
)


def _preset_lines(dumped: str) -> list[str]:
    lines: list[str] = []
    collecting = False
    for line in dumped.splitlines():
        if line.strip().startswith("preset:"):
            collecting = True
            lines.append(line)
        elif collecting and line.startswith("      "):
            lines.append(line)
        elif collecting:
            break
    return lines


def test_dump_yaml_keeps_long_preset_on_one_line() -> None:
    data = {"layers": {"drums": {"preset": _LONG_PRESET}}}
    buf = io.StringIO()
    dump_yaml(data, buf)
    dumped = buf.getvalue()

    assert len(_preset_lines(dumped)) == 1
    loaded = yaml.safe_load(dumped)["layers"]["drums"]["preset"]
    assert loaded == _LONG_PRESET
