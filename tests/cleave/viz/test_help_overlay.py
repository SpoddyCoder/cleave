"""Tests for context-sensitive help overlay content."""

from __future__ import annotations

from cleave.viz.help_overlay import (
    HelpOverlay,
    NAVIGATION_SECTION,
    _layer_section,
    _sections_for,
    _timeline_strip_section,
)
from cleave.viz.theme import LABEL, VALUE
from cleave.viz.row_semantics import ROW_BEHAVIORS, RowKind


def _timeline_keys(**kwargs: object) -> list[str]:
    section = _sections_for(
        RowKind.RENDER_TIMELINE_HEADER,
        timeline_submenu_focused=True,
        **kwargs,
    )[0]
    return [key for key, _ in section.entries]


def test_help_entry_columns_align_to_widest_key() -> None:
    overlay = HelpOverlay()
    font = overlay._font_get()
    sections = (NAVIGATION_SECTION, _layer_section(timeline_enabled=False))
    key_column_width = overlay._max_key_width(font, sections)
    entry_gap = overlay._entry_gap(font)

    widest_key = max(
        (key for section in sections for key, _ in section.entries),
        key=lambda key: font.render(key, True, LABEL).get_width(),
    )
    assert key_column_width == font.render(widest_key, True, LABEL).get_width()

    for section in sections:
        for key, description in section.entries:
            assert overlay._entry_width(
                font,
                key,
                description,
                key_column_width=key_column_width,
                entry_gap=entry_gap,
            ) == key_column_width + entry_gap + font.render(
                description, True, VALUE
            ).get_width()


def test_layer_section_includes_visibility_when_timeline_disabled() -> None:
    section = _layer_section(timeline_enabled=False)
    entries = dict(section.entries)
    assert entries.get("Ctrl + Enter") == "lock/unlock layer"
    assert entries.get("Shift + Left/Right") == "solo layer"
    assert entries.get("Ctrl + Left/Right") == "enable/disable layer"
    assert entries.get("Delete") == "delete layer"


def test_layer_section_omits_visibility_when_timeline_enabled() -> None:
    section = _layer_section(timeline_enabled=True)
    keys = [entry[0] for entry in section.entries]
    assert "Ctrl + Left/Right" not in keys


def test_track_header_help_includes_delete() -> None:
    section = _sections_for(RowKind.TRACK_HEADER, timeline_enabled=False)[0]
    assert dict(section.entries)["Delete"] == "delete layer"


def test_track_header_help_reflects_timeline_enabled() -> None:
    disabled = _sections_for(RowKind.TRACK_HEADER, timeline_enabled=False)
    enabled = _sections_for(RowKind.TRACK_HEADER, timeline_enabled=True)
    disabled_keys = [key for section in disabled for key, _ in section.entries]
    enabled_keys = [key for section in enabled for key, _ in section.entries]
    assert "Ctrl + Left/Right" in disabled_keys
    assert "Ctrl + Left/Right" not in enabled_keys


def test_preset_dir_help() -> None:
    section = _sections_for(RowKind.TRACK_PRESET_DIR)[0]
    entries = dict(section.entries)
    assert entries["Left/Right"] == "next/previous directory"
    assert entries["Ctrl + Left/Right"] == "up/down directory tree"


def test_preset_file_help() -> None:
    section = _sections_for(RowKind.TRACK_PRESET)[0]
    entries = dict(section.entries)
    assert entries["Left/Right"] == "next/previous preset"
    assert entries["Ctrl + Left/Right"] == "next/previous large step"


def test_stem_row_help() -> None:
    section = _sections_for(RowKind.TRACK_STEM)[0]
    assert section.title == "Stem"
    assert dict(section.entries)["Left/Right"] == (
        "cycle stem source; effects reset on change"
    )


def test_cleave_effects_help() -> None:
    header = _sections_for(RowKind.TRACK_EFFECTS_HEADER)[0]
    effect = _sections_for(RowKind.TRACK_EFFECT)[0]
    assert header.title == "Cleave Effects"
    assert effect.title == "Cleave Effects"
    assert "Ctrl + Left/Right" not in [key for key, _ in header.entries]
    assert dict(effect.entries)["Ctrl + Left/Right"] == "large step"


def test_render_timeline_help_has_no_solo() -> None:
    section = _sections_for(RowKind.RENDER_TIMELINE_HEADER)[0]
    keys = [key for key, _ in section.entries]
    assert "Shift + Left/Right" not in keys
    assert dict(section.entries)["Left/Right"] == "expand/collapse"


def test_render_overlay_sub_header_help_expand_collapse() -> None:
    for row_kind in (
        RowKind.RENDER_OVERLAY_TITLE_HEADER,
        RowKind.RENDER_OVERLAY_BODY_HEADER,
    ):
        section = _sections_for(row_kind)[0]
        entries = dict(section.entries)
        assert entries["Left/Right"] == "expand/collapse"
        assert "adjust value" not in entries.values()


def test_layer_management_add_help() -> None:
    section = _sections_for(RowKind.LAYER_MANAGEMENT_ADD)[0]
    assert section.title == "Add Layer"
    assert dict(section.entries)["Enter"] == "confirm add"


def test_layer_management_delete_help() -> None:
    section = _sections_for(RowKind.LAYER_MANAGEMENT_DELETE)[0]
    assert section.title == "Delete layer"
    entries = dict(section.entries)
    assert entries["Enter/Delete"] == "confirm delete"
    assert entries[""] == "at least 1 layer required"


def test_navigable_row_kinds_have_help_sections() -> None:
    for row_kind, behavior in ROW_BEHAVIORS.items():
        if not behavior.navigable:
            continue
        sections = _sections_for(row_kind)
        assert sections, f"{row_kind} returned no help sections"
        assert any(section.entries for section in sections), (
            f"{row_kind} returned only empty sections"
        )


def test_timeline_strip_help_paused() -> None:
    section = _timeline_strip_section(paused=True, recording=False, override_active=False)
    keys = [key for key, _ in section.entries]
    assert keys.index("Shift + Enter") + 1 == keys.index("1-4")
    entries = dict(section.entries)
    assert entries["1-4"] == "toggle layer visibility"
    assert entries["Shift + Enter"] == "toggle override"
    assert "Ctrl + Enter" not in entries
    assert entries["Space"] == "play"
    assert entries["Ctrl + Space / r"] == "start record"
    keys = [key for key, _ in section.entries]
    assert keys.index("Ctrl + Space / r") + 1 == keys.index("Space")
    assert "Left/Right" in entries


def test_timeline_strip_help_playing_without_override() -> None:
    keys = _timeline_keys(paused=False, timeline_recording=False, timeline_override_active=False)
    assert "1-4" not in keys
    assert "Shift + Enter" in keys
    assert dict(
        _timeline_strip_section(
            paused=False, recording=False, override_active=False
        ).entries
    )["Space"] == "pause"


def test_timeline_strip_help_playing_with_override() -> None:
    entries = dict(
        _timeline_strip_section(
            paused=False, recording=False, override_active=True
        ).entries
    )
    assert entries["1-4"] == "toggle layer visibility"


def test_timeline_strip_help_recording_while_playing() -> None:
    entries = dict(
        _timeline_strip_section(paused=False, recording=True, override_active=False).entries
    )
    assert "Ctrl + Enter" not in entries
    assert entries["1-4"] == "toggle layer visibility"
    assert "Shift + Enter" not in entries
    assert entries["Left/Right"] == "skip 10s, fills range"
    assert entries["Ctrl + Left/Right"] == "skip 30s, fills range"
    assert entries["r"] == "stop record"
    assert entries["Ctrl + Space / Space"] == "stop record and pause"
    assert "Space" not in entries
