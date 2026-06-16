"""Tests for context-sensitive help overlay content."""

from __future__ import annotations

from cleave.viz.help_overlay import _layer_section, _sections_for
from cleave.viz.overlay import RowKind


def test_layer_section_includes_visibility_when_timeline_disabled() -> None:
    section = _layer_section(timeline_enabled=False)
    entries = dict(section.entries)
    assert entries.get("Shift+Left/Right") == "solo"
    assert entries.get("Ctrl+Left/Right") == "enable/disable"


def test_layer_section_omits_visibility_when_timeline_enabled() -> None:
    section = _layer_section(timeline_enabled=True)
    keys = [entry[0] for entry in section.entries]
    assert "Ctrl+Left/Right" not in keys


def test_track_header_help_reflects_timeline_enabled() -> None:
    disabled = _sections_for(RowKind.TRACK_HEADER, timeline_enabled=False)
    enabled = _sections_for(RowKind.TRACK_HEADER, timeline_enabled=True)
    disabled_keys = [key for section in disabled for key, _ in section.entries]
    enabled_keys = [key for section in enabled for key, _ in section.entries]
    assert "Ctrl+Left/Right" in disabled_keys
    assert "Ctrl+Left/Right" not in enabled_keys


def test_preset_dir_help() -> None:
    section = _sections_for(RowKind.TRACK_PRESET_DIR)[0]
    entries = dict(section.entries)
    assert entries["Left/Right"] == "next/previous directory"
    assert entries["Ctrl+Left/Right"] == "up/down directory tree"


def test_preset_file_help() -> None:
    section = _sections_for(RowKind.TRACK_PRESET)[0]
    entries = dict(section.entries)
    assert entries["Left/Right"] == "next/previous preset"
    assert entries["Ctrl+Left/Right"] == "next/previous large step"


def test_cleave_effects_help() -> None:
    header = _sections_for(RowKind.TRACK_EFFECTS_HEADER)[0]
    effect = _sections_for(RowKind.TRACK_EFFECT)[0]
    assert header.title == "Cleave Effects"
    assert effect.title == "Cleave Effects"
    assert "Ctrl+Left/Right" not in [key for key, _ in header.entries]
    assert dict(effect.entries)["Ctrl+Left/Right"] == "large step"


def test_render_timeline_help_has_no_solo() -> None:
    section = _sections_for(RowKind.RENDER_TIMELINE_HEADER)[0]
    keys = [key for key, _ in section.entries]
    assert "Shift+Left/Right" not in keys
    assert dict(section.entries)["Left/Right"] == "expand/collapse"
