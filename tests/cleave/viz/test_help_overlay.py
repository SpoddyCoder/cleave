"""Tests for context-sensitive help overlay content."""

from __future__ import annotations

from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES, BLEND_MODES
from cleave.config_schema import (
    PRESET_SWITCHING_MODE_HELP_ENTRIES,
    VISUALIZER_RENDER_MODE_HELP_ENTRIES,
)
from cleave.viz.help_content import (
    DescriptionSection,
    HelpSection,
    KEYBOARD_CONTROLS_SECTION_TITLE,
    NAVIGATION_SECTION,
    layer_section,
    sections_for,
    timeline_strip_section,
)
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.theme import LABEL, VALUE
from cleave.viz.row_semantics import ROW_BEHAVIORS, RowKind


def _keyboard_section(sections: tuple[object, ...]) -> HelpSection:
    for section in sections:
        if isinstance(section, HelpSection) and section is not NAVIGATION_SECTION:
            return section
    raise AssertionError("no keyboard help section found")


def _description_section(sections: tuple[object, ...]) -> DescriptionSection | None:
    for section in sections:
        if isinstance(section, DescriptionSection):
            return section
    return None


def _timeline_keys(**kwargs: object) -> list[str]:
    section = _keyboard_section(
        sections_for(
            RowKind.RENDER_TIMELINE_HEADER,
            timeline_submenu_focused=True,
            **kwargs,
        )
    )
    return [key for key, _ in section.entries]


def test_help_entry_columns_align_to_widest_key() -> None:
    overlay = HelpOverlay()
    font = overlay._font_get()
    mode_description = DescriptionSection(
        "Blend mode",
        lines=("How this layer is composited onto the layers below it.",),
        entries=BLEND_MODE_HELP_ENTRIES,
    )
    sections = (NAVIGATION_SECTION, layer_section(timeline_enabled=False), mode_description)
    key_column_width = overlay._max_key_width(font, sections)
    entry_gap = overlay._entry_gap(font)

    all_keys = [
        key
        for section in sections
        for key, _ in (
            section.entries
            if isinstance(section, (HelpSection, DescriptionSection))
            else ()
        )
    ]
    widest_key = max(
        all_keys,
        key=lambda key: font.render(key, True, LABEL).get_width(),
    )
    assert key_column_width == font.render(widest_key, True, LABEL).get_width()

    for section in sections:
        if not isinstance(section, (HelpSection, DescriptionSection)):
            continue
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
    section = layer_section(timeline_enabled=False)
    entries = dict(section.entries)
    assert entries.get("Ctrl + Enter") == "lock/unlock layer"
    assert entries.get("Shift + Left/Right") == "solo layer"
    assert entries.get("Ctrl + Left/Right") == "enable/disable layer"
    assert entries.get("Delete") == "delete layer"


def test_layer_section_omits_visibility_when_timeline_enabled() -> None:
    section = layer_section(timeline_enabled=True)
    keys = [entry[0] for entry in section.entries]
    assert "Ctrl + Left/Right" not in keys


def test_track_header_help_includes_delete() -> None:
    section = _keyboard_section(
        sections_for(RowKind.TRACK_HEADER, timeline_enabled=False)
    )
    assert dict(section.entries)["Delete"] == "delete layer"


def test_track_header_help_reflects_timeline_enabled() -> None:
    disabled = sections_for(RowKind.TRACK_HEADER, timeline_enabled=False)
    enabled = sections_for(RowKind.TRACK_HEADER, timeline_enabled=True)
    disabled_keys = [
        key
        for section in disabled
        if isinstance(section, HelpSection)
        for key, _ in section.entries
    ]
    enabled_keys = [
        key
        for section in enabled
        if isinstance(section, HelpSection)
        for key, _ in section.entries
    ]
    assert "Ctrl + Left/Right" in disabled_keys
    assert "Ctrl + Left/Right" not in enabled_keys


def test_preset_dir_help_titles() -> None:
    sections = sections_for(RowKind.TRACK_PRESET_DIR)
    description = _description_section(sections)
    keyboard = _keyboard_section(sections)
    assert description is not None
    assert description.title == "Preset Directory"
    assert keyboard.title == KEYBOARD_CONTROLS_SECTION_TITLE
    entries = dict(keyboard.entries)
    assert entries["Left/Right"] == "next/previous directory"
    assert entries["Ctrl + Left/Right"] == "up/down directory tree"


def test_preset_file_help_titles() -> None:
    sections = sections_for(RowKind.TRACK_PRESET)
    description = _description_section(sections)
    keyboard = _keyboard_section(sections)
    assert description is not None
    assert description.title == "Milkdrop Preset File"
    entries = dict(keyboard.entries)
    assert entries["Left/Right"] == "next/previous preset"
    assert entries["Ctrl + Left/Right"] == "next/previous large step"


def test_blend_mode_help_lists_modes() -> None:
    description = _description_section(sections_for(RowKind.TRACK_BLEND))
    assert description is not None
    assert description.title == "Blend mode"
    assert description.lines == (
        "How this layer is composited onto the layers below it.",
    )
    assert description.entries == BLEND_MODE_HELP_ENTRIES
    assert [mode for mode, _ in description.entries] == list(BLEND_MODES)


def test_switching_mode_help_lists_modes() -> None:
    description = _description_section(
        sections_for(RowKind.TRACK_PRESET_SWITCHING_MODE)
    )
    assert description is not None
    assert description.title == "Switching mode"
    assert description.lines == ()
    assert description.entries == PRESET_SWITCHING_MODE_HELP_ENTRIES


def test_render_mode_help_lists_modes() -> None:
    description = _description_section(sections_for(RowKind.SETTINGS_RENDER_MODE))
    assert description is not None
    assert description.title == "Render mode"
    assert "live view only" in " ".join(description.lines)
    assert description.entries == VISUALIZER_RENDER_MODE_HELP_ENTRIES


def test_timeline_help_mentions_visibility_handoff() -> None:
    description = _description_section(sections_for(RowKind.RENDER_TIMELINE_HEADER))
    assert description is not None
    assert any("standard layer visibility is disabled" in line for line in description.lines)


def test_stem_row_help() -> None:
    sections = sections_for(RowKind.TRACK_STEM)
    description = _description_section(sections)
    section = _keyboard_section(sections)
    assert description is not None
    assert description.title == "Stem"
    assert section.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert dict(section.entries)["Left/Right"] == "cycle stem source"
    assert "Effects reset when the stem changes." in description.lines


def test_cleave_effects_help() -> None:
    header = _keyboard_section(sections_for(RowKind.TRACK_EFFECTS_HEADER))
    effect = _keyboard_section(sections_for(RowKind.TRACK_EFFECT))
    assert header.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert effect.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert "Ctrl + Left/Right" not in [key for key, _ in header.entries]
    assert dict(effect.entries)["Ctrl + Left/Right"] == "large step"


def test_effect_row_help_uses_registry_description() -> None:
    sections = sections_for(RowKind.TRACK_EFFECT, effect_id="pulse")
    description = _description_section(sections)
    assert description is not None
    assert description.title == "Pulse"
    assert "Opacity follows the audio driver signal." in description.lines


def test_render_timeline_help_has_no_solo() -> None:
    section = _keyboard_section(sections_for(RowKind.RENDER_TIMELINE_HEADER))
    keys = [key for key, _ in section.entries]
    assert "Shift + Left/Right" not in keys
    assert dict(section.entries)["Left/Right"] == "expand/collapse"


def test_render_overlay_sub_header_help_expand_collapse() -> None:
    for row_kind in (
        RowKind.RENDER_OVERLAY_TITLE_HEADER,
        RowKind.RENDER_OVERLAY_BODY_HEADER,
    ):
        section = _keyboard_section(sections_for(row_kind))
        entries = dict(section.entries)
        assert entries["Left/Right"] == "expand/collapse"
        assert "adjust value" not in entries.values()


def test_layer_management_add_help() -> None:
    section = _keyboard_section(sections_for(RowKind.LAYER_MANAGEMENT_ADD))
    assert section.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert dict(section.entries)["Enter"] == "confirm add"


def test_layer_management_delete_help() -> None:
    sections = sections_for(RowKind.LAYER_MANAGEMENT_DELETE)
    section = _keyboard_section(sections)
    description = _description_section(sections)
    assert section.title == KEYBOARD_CONTROLS_SECTION_TITLE
    entries = dict(section.entries)
    assert entries["Enter/Delete"] == "confirm delete"
    assert "" not in entries
    assert description is not None
    assert "At least one layer must remain." in description.lines


def test_navigable_row_kinds_have_help_sections() -> None:
    for row_kind, behavior in ROW_BEHAVIORS.items():
        if not behavior.navigable:
            continue
        sections = sections_for(row_kind)
        assert sections, f"{row_kind} returned no help sections"
        assert any(
            (
                isinstance(section, DescriptionSection)
                and (section.lines or section.entries)
            )
            or (
                isinstance(section, HelpSection) and section.entries
            )
            for section in sections
        ), f"{row_kind} returned only empty sections"


def test_navigable_row_kinds_with_description_use_keyboard_controls_title() -> None:
    for row_kind, behavior in ROW_BEHAVIORS.items():
        if not behavior.navigable:
            continue
        if behavior.help_description is None and behavior.help_mode_entries is None:
            continue
        if row_kind == RowKind.TRACK_EFFECT:
            continue
        keyboard = _keyboard_section(sections_for(row_kind))
        assert keyboard.title == KEYBOARD_CONTROLS_SECTION_TITLE, row_kind


def test_navigable_row_kinds_with_description_have_three_sections() -> None:
    for row_kind, behavior in ROW_BEHAVIORS.items():
        if not behavior.navigable:
            continue
        if behavior.help_description is None and behavior.help_mode_entries is None:
            continue
        sections = sections_for(row_kind)
        assert len(sections) == 3, f"{row_kind} expected 3 sections, got {len(sections)}"
        assert isinstance(sections[0], DescriptionSection)
        assert isinstance(sections[1], HelpSection)
        assert sections[2] is NAVIGATION_SECTION


def test_description_sections_use_control_name_not_about() -> None:
    for row_kind, behavior in ROW_BEHAVIORS.items():
        if not behavior.navigable:
            continue
        if behavior.help_description is None and behavior.help_mode_entries is None:
            continue
        if row_kind == RowKind.TRACK_EFFECT:
            continue
        description = _description_section(sections_for(row_kind))
        assert description is not None, row_kind
        assert description.title != "About", row_kind
        assert description.title == behavior.help_title, row_kind


def test_settings_render_mode_description_separated_from_keyboard() -> None:
    sections = sections_for(RowKind.SETTINGS_RENDER_MODE)
    keyboard = _keyboard_section(sections)
    description = _description_section(sections)
    assert dict(keyboard.entries) == {"Left/Right": "cycle mode"}
    assert description is not None
    assert "live view only" in " ".join(description.lines)


def test_timeline_submenu_help_has_three_sections() -> None:
    sections = sections_for(
        RowKind.RENDER_TIMELINE_HEADER,
        timeline_submenu_focused=True,
        paused=True,
    )
    assert len(sections) == 3
    assert isinstance(sections[0], DescriptionSection)
    assert sections[0].title == "Timeline"
    assert isinstance(sections[1], HelpSection)
    assert sections[1].title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert sections[2] is NAVIGATION_SECTION


def test_timeline_strip_help_paused() -> None:
    section = timeline_strip_section(paused=True, recording=False, override_active=False)
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
        timeline_strip_section(
            paused=False, recording=False, override_active=False
        ).entries
    )["Space"] == "pause"


def test_timeline_strip_help_playing_with_override() -> None:
    entries = dict(
        timeline_strip_section(
            paused=False, recording=False, override_active=True
        ).entries
    )
    assert entries["1-4"] == "toggle layer visibility"


def test_timeline_strip_help_recording_while_playing() -> None:
    entries = dict(
        timeline_strip_section(paused=False, recording=True, override_active=False).entries
    )
    assert "Ctrl + Enter" not in entries
    assert entries["1-4"] == "toggle layer visibility"
    assert "Shift + Enter" not in entries
    assert entries["Left/Right"] == "skip 10s, fills range"
    assert entries["Ctrl + Left/Right"] == "skip 30s, fills range"
    assert entries["r"] == "stop record"
    assert entries["Ctrl + Space / Space"] == "stop record and pause"
    assert "Space" not in entries
