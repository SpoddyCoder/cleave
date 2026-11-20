"""Tests for context-sensitive help overlay content."""

from __future__ import annotations

import pytest

from dataclasses import replace

from cleave.viz.modal import ModalHost
from cleave.viz.context_menu import ContextMenuState
from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES, BLEND_MODES
from cleave.cue_roles import CUE_ROLE_MARKER_HELP_ENTRIES
from cleave.config_schema.editor import EDITOR_PREVIEW_QUALITY_HELP_ENTRIES
from cleave.config_schema.layers import (
    PRESET_SWITCHING_TRIGGER_HELP_ENTRIES,
)
from cleave.config_schema.render import (
    HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_APPLY_MODES,
    HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_CURVES,
)
from cleave.timeline_presets import TIMELINE_PRESET_HELP_ENTRIES
from unittest.mock import MagicMock
from cleave.viz.inline_edit import InlineEditController
from cleave.viz.help_column import help_column_text
from cleave.viz.help_content import (
    DescriptionSection,
    HelpSection,
    KEYBOARD_CONTROLS_SECTION_TITLE,
    NAVIGATION_SECTION,
    help_sections,
    help_sections_for_stop,
    layer_section,
    navigation_section,
    sections_for,
    timeline_strip_section,
)
from cleave.viz.shell_focus import CycleStop, ShellFocusState, ShellRegion
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import ROW_SPECS, RowSpec


_ROW_SECTION_SKIP_TITLES = {NAVIGATION_SECTION.title, "Navigator"}


def _is_navigation_section(section: object) -> bool:
    return isinstance(section, HelpSection) and section.title == NAVIGATION_SECTION.title


def _keyboard_section(sections: tuple[object, ...]) -> HelpSection:
    for section in sections:
        if (
            isinstance(section, HelpSection)
            and section.title not in _ROW_SECTION_SKIP_TITLES
        ):
            return section
    raise AssertionError("no keyboard help section found")


def _description_section(sections: tuple[object, ...]) -> DescriptionSection | None:
    for section in sections:
        if isinstance(section, DescriptionSection):
            return section
    return None


def _timeline_keys(**kwargs: object) -> list[str]:
    section = timeline_strip_section(
        paused=bool(kwargs.get("paused", False)),
        recording=bool(kwargs.get("timeline_recording", False)),
        override_active=bool(kwargs.get("timeline_override_active", False)),
        layer_count=int(kwargs.get("layer_count", 4)),
    )
    return [key for key, _ in section.entries]


def _assert_shell_navigation(entries: dict[str, str]) -> None:
    cycle = entries["Tab / Shift+Tab"]
    for name in ("Menu", "Navigator", "Inspector", "Timeline"):
        assert name in cycle
    assert "Help" not in cycle
    assert "(when the strip is open)" in cycle
    move = entries["Up/Down"]
    assert move == "move in the active region"
    joined = " ".join(entries.values()).lower()
    assert "move row" not in joined
    assert "one tree" not in joined
    assert "walk" not in joined
    assert "open/close a navigator node" in entries["Left/Right"]
    assert "change an inspector value" in entries["Left/Right"]
    assert entries["Ctrl + Up/Down"] == "previous / next top-level node"
    assert entries["F10 / Alt"] == "focus menu bar"
    assert (
        entries["Alt + underlined letter"]
        == "open that menu (F, E, V, P, S, H)"
    )


def _says(lines: tuple[str, ...], *phrases: str) -> bool:
    """True when the description mentions every phrase, ignoring case."""
    text = " ".join(lines).lower()
    return all(phrase in text for phrase in phrases)


def test_help_content_navigation_cycles_regions() -> None:
    normal = dict(navigation_section().entries)
    curation = dict(navigation_section(preset_curation=True).entries)
    _assert_shell_navigation(normal)
    _assert_shell_navigation(curation)
    sections = sections_for(RowKind.TRACK_HEADER)
    assert all(getattr(section, "title", "") != "Transport Controls" for section in sections)


def test_layer_section_includes_visibility_when_timeline_disabled() -> None:
    section = layer_section(timeline_enabled=False)
    entries = dict(section.entries)
    assert entries.get("L") == "lock/unlock layer"
    assert entries.get("S") == "solo layer"
    assert entries.get("E") == "enable/disable layer"
    assert entries.get("Delete") == "delete layer"


def test_layer_section_omits_visibility_when_timeline_enabled() -> None:
    section = layer_section(timeline_enabled=True)
    keys = [entry[0] for entry in section.entries]
    assert "E" not in keys


def test_curation_layer_section_omits_add_delete_and_expand() -> None:
    section = layer_section(timeline_enabled=False, preset_curation=True)
    assert section.entries == ()
    sections = sections_for(RowKind.TRACK_HEADER, preset_curation=True)
    keys = [key for section in sections for key, _ in section.entries]
    actions = [action for section in sections for _, action in section.entries]
    assert "Ctrl + L" not in keys
    assert "delete layer" not in actions
    assert "expand/collapse" not in actions
    nav = dict(navigation_section(preset_curation=True).entries)
    assert "open/close a navigator node" in nav["Left/Right"]
    assert "change an inspector value" in nav["Left/Right"]
    assert "Ctrl + L" not in nav
    preset = dict(
        _keyboard_section(
            sections_for(RowKind.TRACK_PRESET, preset_curation=True)
        ).entries
    )
    assert preset["Left/Right"] == "next/previous preset"
    assert preset["F"] == "favourite / unfavourite preset"


def _help_text(sections: tuple[object, ...]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(getattr(section, "title", ""))
        lines = getattr(section, "lines", ())
        parts.extend(lines)
        parts.extend(f"{key} {action}" for key, action in section.entries)
    return "\n".join(parts)


def test_layer_section_jump_and_add_layer() -> None:
    section = layer_section(timeline_enabled=True, layer_count=4)
    entries = dict(section.entries)
    assert entries["M"] == "change layer order"
    assert entries["L"] == "lock/unlock layer"
    assert entries["S"] == "solo layer"
    assert entries["Delete"] == "delete layer"
    assert entries["1-4"] == "jump to layer"
    assert entries["Ctrl + L"] == "add layer"
    assert "Left/Right" not in entries
    single = dict(layer_section(timeline_enabled=True, layer_count=1).entries)
    assert single["1"] == "jump to layer"
    wide = dict(layer_section(timeline_enabled=False, layer_count=8).entries)
    assert wide["1-8"] == "jump to layer"
    assert wide["E"] == "enable/disable layer"


def test_layer_section_omits_jump_while_recording() -> None:
    entries = dict(
        _keyboard_section(
            sections_for(
                RowKind.TRACK_HEADER,
                timeline_enabled=True,
                timeline_recording=True,
                layer_count=4,
            )
        ).entries
    )
    assert "1-4" not in entries
    assert "jump to layer" not in entries.values()
    assert entries["Ctrl + L"] == "add layer"
    assert entries["L"] == "lock/unlock layer"


def test_navigation_left_right_expands_navigator() -> None:
    normal = dict(navigation_section().entries)
    curation = dict(navigation_section(preset_curation=True).entries)
    assert normal["Left/Right"] == curation["Left/Right"]
    assert "open/close a navigator node" in normal["Left/Right"]
    assert "change an inspector value" in normal["Left/Right"]
    assert "Ctrl + L" not in normal
    assert "1-4" not in normal
    assert "jump to layer" not in normal.values()


def test_help_follows_inspector_row_not_leftover() -> None:
    leftover = RowDescriptor(RowKind.OVERLAYS_HEADER)
    shell = ShellFocusState(
        region=ShellRegion.INSPECTOR,
        selected_id="layer:drums",
        inspector_cursor=RowDescriptor(RowKind.TRACK_OPACITY, slot="drums"),
    )
    sections = help_sections(leftover, shell_focus=shell)
    description = _description_section(sections)
    assert description is not None
    assert description.title == "Opacity"
    keyboard = dict(_keyboard_section(sections).entries)
    assert keyboard["Left/Right"] == "adjust value"
    assert "jump to layer" not in keyboard.values()
    assert "Credits overlays" not in _help_text(sections)
    assert "Ctrl + Q" not in _help_text(sections)
    assert NAVIGATION_SECTION.title not in _help_text(sections)


def test_help_follows_navigator_layer() -> None:
    leftover = RowDescriptor(RowKind.OVERLAYS_HEADER)
    sections = help_sections(
        leftover,
        shell_focus=ShellFocusState(
            region=ShellRegion.NAVIGATOR,
            selected_id="layer:drums",
        ),
        layer_count=6,
    )
    keyboard = dict(_keyboard_section(sections).entries)
    assert keyboard["L"] == "lock/unlock layer"
    assert keyboard["1-6"] == "jump to layer"
    assert keyboard["Ctrl + L"] == "add layer"
    assert keyboard["Delete"] == "delete layer"
    assert "Left/Right" not in keyboard
    nav = dict(
        next(
            section.entries
            for section in sections
            if isinstance(section, HelpSection) and section.title == "Navigator"
        )
    )
    assert nav["Up/Down"] == "move across nodes"
    assert nav["Left/Right"] == "open/close"
    assert nav["Ctrl + Up/Down"] == "previous / next top-level node"
    assert "Ctrl + L" not in nav
    assert "Ctrl + S" not in nav
    assert "1-6" not in nav
    assert "Credits overlays" not in _help_text(sections)


def test_help_follows_navigator_render_node() -> None:
    leftover = RowDescriptor(RowKind.TRACK_OPACITY, slot="drums")
    overlays = help_sections(
        leftover,
        shell_focus=ShellFocusState(
            region=ShellRegion.NAVIGATOR,
            selected_id="overlay",
        ),
    )
    description = _description_section(overlays)
    assert description is not None
    assert description.title == "Credits Overlays"
    keyboard = dict(_keyboard_section(overlays).entries)
    assert "E" not in keyboard
    assert "S" not in keyboard
    assert keyboard["V"] == "preview cards"
    assert overlays != (navigation_section(),)

    post = help_sections(
        leftover,
        shell_focus=ShellFocusState(
            region=ShellRegion.NAVIGATOR,
            selected_id="post_fx",
        ),
    )
    post_description = _description_section(post)
    assert post_description is not None
    assert post_description.title == "Post FX"
    with pytest.raises(AssertionError, match="no keyboard help section"):
        _keyboard_section(post)
    assert "combined picture" in _help_text(post)


def test_navigator_other_nodes_keep_navigation_only() -> None:
    leftover = RowDescriptor(RowKind.OVERLAYS_HEADER)
    for selected_id in ("settings", "project", "layers"):
        sections = help_sections(
            leftover,
            shell_focus=ShellFocusState(
                region=ShellRegion.NAVIGATOR,
                selected_id=selected_id,
            ),
        )
        assert len(sections) == 1, selected_id
        assert isinstance(sections[0], HelpSection)
        assert sections[0].title == "Navigator"
        assert "Ctrl + S" not in dict(sections[0].entries)


def test_inspector_command_rows_use_layer_management_help() -> None:
    leftover = RowDescriptor(RowKind.TRACK_OPACITY, slot="drums")
    add = help_sections(
        leftover,
        shell_focus=ShellFocusState(
            region=ShellRegion.INSPECTOR,
            selected_id="layers",
            inspector_command_id="layers.add",
        ),
    )
    add_description = _description_section(add)
    assert add_description is not None
    assert add_description.title == "Add Layer"
    assert dict(_keyboard_section(add).entries)["Enter"] == "add layer"
    delete = help_sections(
        leftover,
        shell_focus=ShellFocusState(
            region=ShellRegion.INSPECTOR,
            selected_id="layer:drums",
            inspector_command_id="layers.delete",
        ),
    )
    delete_description = _description_section(delete)
    assert delete_description is not None
    assert delete_description.title == "Delete Layer"
    assert "Opacity" not in _help_text(delete)


def test_timeline_strip_help_keeps_lane_keys_when_layer_selected() -> None:
    sections = help_sections(
        RowDescriptor(RowKind.OVERLAYS_HEADER),
        shell_focus=ShellFocusState(
            region=ShellRegion.TIMELINE,
            selected_id="layer:drums",
        ),
        timeline_submenu_focused=True,
        paused=True,
        timeline_override_active=True,
        layer_count=4,
    )
    entries = dict(_keyboard_section(sections).entries)
    assert entries["1-4"] == "show / hide an overridden layer"
    assert "jump to layer" not in entries.values()
    assert "Ctrl + L" not in entries


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
    assert "E" in disabled_keys
    assert "E" not in enabled_keys


def test_preset_dir_help_titles() -> None:
    sections = sections_for(RowKind.TRACK_PRESET_DIR)
    description = _description_section(sections)
    keyboard = _keyboard_section(sections)
    assert description is not None
    assert description.title == "Preset Directory"
    assert _says(description.lines, 'parent folder', 'subfolder')
    assert keyboard.title == KEYBOARD_CONTROLS_SECTION_TITLE
    entries = dict(keyboard.entries)
    assert entries["Left/Right"] == "next/previous directory"
    assert entries["Enter"] == "open directory"
    assert entries["Backspace"] == "parent directory"
    assert "Shift + +" not in entries


def test_preset_dir_help_includes_add_shortcut_when_switching_on() -> None:
    sections = sections_for(
        RowKind.TRACK_PRESET_DIR,
        preset_switching="on",
    )
    entries = dict(_keyboard_section(sections).entries)
    assert entries["P"] == "add current preset to switching list"


def test_preset_file_help_titles() -> None:
    sections = sections_for(RowKind.TRACK_PRESET)
    description = _description_section(sections)
    keyboard = _keyboard_section(sections)
    assert description is not None
    assert description.title == "Milkdrop Preset File"
    assert _says(description.lines, 'tags after the name')
    assert dict(description.entries) == {
        "[F]": "favourite",
        "[B]": "blacklisted",
        "[L]": "in this layer's preset list (not in preset curation)",
        "[R:B]": "bed (calm, dark background)",
        "[R:P]": "pulse (reacts to the beat, middle depth)",
        "[R:L]": "lead (busy, bright main visual)",
        "[R:A]": "accent (short, bright hits)",
    }
    entries = dict(keyboard.entries)
    assert entries["Left/Right"] == "next/previous preset"
    assert entries["PgUp/PgDn"] == "next/previous, large step"
    assert entries["F"] == "favourite / unfavourite preset"
    assert entries["B"] == "blacklist / unblacklist preset"
    assert entries["C"] == "set preset role (bed/pulse/lead/accent/none)"
    assert "R" not in entries
    assert "Shift + +" not in entries


def test_preset_file_help_includes_add_shortcut_when_switching_on() -> None:
    sections = sections_for(
        RowKind.TRACK_PRESET,
        preset_switching="on",
    )
    entries = dict(_keyboard_section(sections).entries)
    assert entries["P"] == "add current preset to switching list"


def test_blend_mode_help_lists_modes() -> None:
    description = _description_section(sections_for(RowKind.TRACK_BLEND))
    assert description is not None
    assert description.title == "Blend Mode"
    assert _says(description.lines, 'pattern mask overrides')
    assert description.entries == BLEND_MODE_HELP_ENTRIES
    assert [mode for mode, _ in description.entries] == list(BLEND_MODES)


def test_switching_page_help_is_description_only() -> None:
    sections = sections_for(RowKind.TRACK_PRESET_SWITCHING)
    description = _description_section(sections)
    assert description is not None
    assert description.title == "Preset Switching"
    assert _says(description.lines, 'list of presets')
    assert not description.entries
    assert len(sections) == 1



def test_timeline_presets_help_lists_characters() -> None:
    sections = sections_for(RowKind.TIMELINE_GENERATE)
    description = _description_section(sections)
    assert description is not None
    assert description.title == "Generate Timeline"
    assert _says(description.lines, 'replacing the current clips', 'crescendo')
    assert description.entries == TIMELINE_PRESET_HELP_ENTRIES
    assert [name for name, _ in description.entries] == [
        "Breathing",
        "Dialogue",
        "Arc",
        "Pulse",
    ]
    keyboard = _keyboard_section(sections)
    assert keyboard.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert keyboard.entries == (("Enter", "open generate dialog"),)


def test_timeline_reset_help_lists_choices() -> None:
    from cleave.timeline_presets import TIMELINE_RESET_HELP_ENTRIES

    sections = sections_for(RowKind.TIMELINE_RESET)
    description = _description_section(sections)
    assert description is not None
    assert description.title == "Reset Timeline"
    assert description.entries == TIMELINE_RESET_HELP_ENTRIES
    assert [name for name, _ in description.entries] == ["Layers off", "Layers on"]
    keyboard = _keyboard_section(sections)
    assert keyboard.entries == (("Enter", "open reset dialog"),)



def test_preview_quality_help_lists_modes() -> None:
    description = _description_section(sections_for(RowKind.SETTINGS_PREVIEW_QUALITY))
    assert description is not None
    assert description.title == "Preview Quality"
    assert _says(description.lines, "renders are unaffected")
    assert description.entries == EDITOR_PREVIEW_QUALITY_HELP_ENTRIES



def test_preset_switching_trigger_help_lists_options() -> None:
    sections = sections_for(RowKind.TRACK_PRESET_SWITCHING_TRIGGER)
    description = next(s for s in sections if isinstance(s, DescriptionSection))
    assert description.entries == PRESET_SWITCHING_TRIGGER_HELP_ENTRIES


def test_preset_list_help() -> None:
    sections = sections_for(RowKind.TRACK_PRESET_LIST)
    description = _description_section(sections)
    assert description is not None
    assert description.title == "Preset List"
    assert _says(description.lines, 'presets this layer cycles through')
    assert not description.entries
    assert len(sections) == 1


def test_preset_list_entry_help() -> None:
    sections = sections_for(RowKind.TRACK_PRESET_LIST_ITEM)
    description = _description_section(sections)
    keyboard = _keyboard_section(sections)
    assert description is not None
    assert description.title == "Preset List Entry"
    assert _says(description.lines, 'switching list', 'tags after the name')
    assert description.entries == (
        ("[F]", "favourite"),
        ("[B]", "blacklisted"),
        *CUE_ROLE_MARKER_HELP_ENTRIES,
    )
    assert "Delete" not in " ".join(description.lines)
    assert keyboard.title == KEYBOARD_CONTROLS_SECTION_TITLE
    entries = dict(keyboard.entries)
    assert entries == {
        "Enter": "play this preset and pause switching",
        "M": "reorder in list",
        "Drag handle": "reorder with the mouse",
        "Delete": "remove preset",
        "F": "favourite / unfavourite preset",
        "B": "blacklist / unblacklist preset",
        "C": "set preset role (bed/pulse/lead/accent/none)",
    }


def test_resume_switching_help() -> None:
    resume_sections = sections_for(RowKind.TRACK_PRESET_SWITCHING_RESUME)
    resume_description = _description_section(resume_sections)
    resume_keyboard = _keyboard_section(resume_sections)
    assert resume_description is not None
    assert resume_description.title == "Resume Switching"
    assert _says(resume_description.lines, 'ends the preview')
    assert dict(resume_keyboard.entries) == {"Enter": "resume switching"}


def test_highlight_rolloff_mode_help_lists_modes() -> None:
    description = _description_section(
        sections_for(RowKind.POST_FX_HIGHLIGHT_ROLLOFF_MODE)
    )
    assert description is not None
    assert description.title == "Mode"
    assert _says(description.lines, "rolloff runs")
    assert description.entries == HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES
    assert [mode for mode, _ in description.entries] == list(
        HIGHLIGHT_ROLLOFF_APPLY_MODES
    )


def test_highlight_rolloff_curve_help_lists_curves() -> None:
    description = _description_section(
        sections_for(RowKind.POST_FX_HIGHLIGHT_ROLLOFF_CURVE)
    )
    assert description is not None
    assert description.title == "Curve"
    assert _says(description.lines, "above the threshold")
    assert description.entries == HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES
    assert [curve for curve, _ in description.entries] == list(HIGHLIGHT_ROLLOFF_CURVES)


def test_highlight_rolloff_header_help() -> None:
    description = _description_section(
        sections_for(RowKind.POST_FX_HIGHLIGHT_ROLLOFF_HEADER)
    )
    assert description is not None
    assert _says(description.lines, "compresses highlights", "flat white")


def test_post_fx_header_help() -> None:
    description = _description_section(sections_for(RowKind.POST_FX_HEADER))
    assert description is not None
    assert _says(description.lines, "combined picture")


def test_timeline_help_mentions_visibility_handoff() -> None:
    description = _description_section(sections_for(RowKind.TIMELINE_HEADER))
    assert description is not None
    assert _says(description.lines, "own on/off switches are ignored")


def test_stem_row_help() -> None:
    sections = sections_for(RowKind.TRACK_STEM)
    description = _description_section(sections)
    section = _keyboard_section(sections)
    assert description is not None
    assert description.title == "Stem"
    assert section.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert dict(section.entries)["Left/Right"] == "choose stem source"
    assert _says(description.lines, "resets the layer's cleave effects")


def test_compositing_header_and_opacity_help() -> None:
    header = _description_section(sections_for(RowKind.TRACK_COMPOSITING_HEADER))
    opacity = _description_section(sections_for(RowKind.TRACK_OPACITY))
    mask = _description_section(sections_for(RowKind.PATTERN_MASK_HEADER))
    assert header is not None
    assert header.title == "Compositing"
    assert _says(header.lines, 'pattern mask overrides')
    assert opacity is not None
    assert _says(opacity.lines, 'opacity', 'pattern mask overrides')
    assert mask is not None
    assert _says(mask.lines, "overrides each layer's compositing settings")


def test_cleave_effects_help() -> None:
    effect = _keyboard_section(sections_for(RowKind.TRACK_EFFECT))
    assert effect.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert dict(effect.entries)["PgUp/PgDn"] == "large step"


def test_effect_row_help_uses_registry_description() -> None:
    sections = sections_for(RowKind.TRACK_EFFECT, effect_id="pulse")
    description = _description_section(sections)
    assert description is not None
    assert description.title == "Pulse"
    assert _says(description.lines, "opacity", "audio driver")


def test_timeline_help_has_no_solo() -> None:
    section = _keyboard_section(sections_for(RowKind.TIMELINE_HEADER))
    keys = [key for key, _ in section.entries]
    assert "S" not in keys
    assert dict(section.entries)["E"] == "enable/disable"


def test_overlay_title_text_help() -> None:
    section = _keyboard_section(sections_for(RowKind.OVERLAY_CARD_TITLE_TEXT))
    assert dict(section.entries)["Enter"] == "edit title"


def test_overlay_title_colour_help() -> None:
    section = _keyboard_section(sections_for(RowKind.OVERLAY_CARD_TITLE_COLOUR))
    assert dict(section.entries)["Enter"] == "edit hex value"


def test_overlay_remaining_colour_rows_help() -> None:
    for kind in (
        RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
        RowKind.OVERLAY_CARD_BODY_COLOUR,
        RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
        RowKind.OVERLAY_CARD_BACKGROUND_COLOUR,
        RowKind.OVERLAY_CARD_BORDER_COLOUR,
    ):
        section = _keyboard_section(sections_for(kind))
        assert dict(section.entries)["Enter"] == "edit hex value"


def test_overlay_background_margin_and_padding_help() -> None:
    for kind in (
        RowKind.OVERLAY_CARD_BACKGROUND_MARGIN,
        RowKind.OVERLAY_CARD_BACKGROUND_PADDING,
    ):
        section = _keyboard_section(sections_for(kind))
        entries = dict(section.entries)
        assert entries["Left/Right"] == "adjust value"
        assert entries["PgUp/PgDn"] == "large step"


def test_overlay_body_text_help() -> None:
    section = _keyboard_section(sections_for(RowKind.OVERLAY_CARD_BODY_TEXT))
    assert dict(section.entries)["Enter"] == "edit body"


def test_layer_management_add_help() -> None:
    section = _keyboard_section(sections_for(RowKind.LAYER_MANAGEMENT_ADD))
    assert section.title == KEYBOARD_CONTROLS_SECTION_TITLE
    assert dict(section.entries)["Enter"] == "add layer"


def test_layer_management_delete_help() -> None:
    sections = sections_for(RowKind.LAYER_MANAGEMENT_DELETE)
    section = _keyboard_section(sections)
    description = _description_section(sections)
    assert section.title == KEYBOARD_CONTROLS_SECTION_TITLE
    entries = dict(section.entries)
    assert entries["Enter/Delete"] == "delete layer"
    assert "" not in entries
    assert description is not None
    assert _says(description.lines, "last one cannot be deleted")


def test_navigable_row_kinds_have_help_sections() -> None:
    for row_kind, behavior in ROW_SPECS.items():
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


def _page_without_keys(behavior: RowSpec) -> bool:
    """A navigator page with no E or S key has a description and no key list."""
    return (
        behavior.affordance == RowAffordance.HEADING
        and behavior.toggle_enabled is None
        and behavior.toggle_solo is None
        and not behavior.can_enter_move_mode
    )


def test_navigable_row_kinds_with_description_use_keyboard_controls_title() -> None:
    for row_kind, behavior in ROW_SPECS.items():
        if not behavior.navigable:
            continue
        if behavior.help_description is None and behavior.help_mode_entries is None:
            continue
        if row_kind == RowKind.TRACK_EFFECT or _page_without_keys(behavior):
            continue
        keyboard = _keyboard_section(sections_for(row_kind))
        assert keyboard.title == KEYBOARD_CONTROLS_SECTION_TITLE, row_kind


def test_navigable_row_kinds_with_description_have_three_sections() -> None:
    for row_kind, behavior in ROW_SPECS.items():
        if not behavior.navigable:
            continue
        if behavior.help_description is None and behavior.help_mode_entries is None:
            continue
        if _page_without_keys(behavior):
            continue
        sections = sections_for(row_kind)
        assert len(sections) == 2, f"{row_kind} expected 2 sections, got {len(sections)}"
        assert isinstance(sections[0], DescriptionSection)
        assert isinstance(sections[1], HelpSection)
        assert sections[1].title == KEYBOARD_CONTROLS_SECTION_TITLE


def test_description_sections_use_control_name_not_about() -> None:
    for row_kind, behavior in ROW_SPECS.items():
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


def test_settings_preview_quality_description_separated_from_keyboard() -> None:
    sections = sections_for(RowKind.SETTINGS_PREVIEW_QUALITY)
    keyboard = _keyboard_section(sections)
    description = _description_section(sections)
    assert dict(keyboard.entries) == {
        "Left/Right": "choose mode",
        "Enter": "open the list",
    }
    assert description is not None
    assert _says(description.lines, "renders are unaffected")


def test_timeline_stop_help_is_the_strip_only() -> None:
    sections = help_sections_for_stop(
        CycleStop.TIMELINE,
        RowDescriptor(RowKind.TIMELINE_HEADER),
        paused=True,
        layer_count=4,
    )
    assert sections == (
        timeline_strip_section(
            paused=True, recording=False, override_active=False, layer_count=4
        ),
    )


def test_each_stop_has_its_own_shortcut_section() -> None:
    focus = RowDescriptor(RowKind.TRACK_OPACITY, slot="drums")
    shell = ShellFocusState(
        region=ShellRegion.INSPECTOR,
        selected_id="layer:drums",
        inspector_cursor=focus,
    )
    menu = help_sections_for_stop(CycleStop.MENU, focus, shell_focus=shell)
    navigator = help_sections_for_stop(
        CycleStop.NAVIGATOR,
        focus,
        shell_focus=replace(shell, region=ShellRegion.NAVIGATOR),
        layer_count=4,
    )
    inspector = help_sections_for_stop(
        CycleStop.INSPECTOR, focus, shell_focus=shell
    )
    timeline = help_sections_for_stop(
        CycleStop.TIMELINE,
        focus,
        shell_focus=replace(shell, region=ShellRegion.TIMELINE),
        paused=True,
        layer_count=4,
    )
    assert menu[0].title == "Navigation / Global"
    assert "Ctrl + S" in dict(menu[0].entries)
    assert navigator[-1].title == "Navigator"
    assert "Ctrl + S" not in _help_text(navigator)
    assert any(
        isinstance(section, HelpSection)
        and dict(section.entries).get("L") == "lock/unlock layer"
        for section in navigator
    )
    assert _description_section(inspector) is not None
    assert _description_section(inspector).title == "Opacity"
    assert "Ctrl + Q" not in _help_text(inspector)
    assert timeline[0].title == "Timeline"
    assert "Ctrl + Q" not in _help_text(timeline)
    assert {menu[0].title, navigator[-1].title, inspector[0].title, timeline[0].title} == {
        "Navigation / Global",
        "Navigator",
        "Opacity",
        "Timeline",
    }


def test_curation_navigation_omits_disabled_global_hotkeys() -> None:
    focus = RowDescriptor(RowKind.TRACK_PRESET)
    sections = help_sections_for_stop(
        CycleStop.MENU, focus, preset_curation=True
    )
    nav = sections[0]
    assert isinstance(nav, HelpSection)
    assert nav is navigation_section(preset_curation=True)
    keys = dict(nav.entries)
    assert "Ctrl + N" not in keys
    assert "Ctrl + O" not in keys
    assert "Ctrl + S" not in keys
    assert "Ctrl + Enter" not in keys
    assert "Ctrl + R" not in keys
    assert keys["Ctrl + Q"] == "quit"
    assert "move row" not in keys["Up/Down"]
    assert "one tree" not in " ".join(keys.values()).lower()
    assert keys["Shift + Left/Right"] == "skip 2s"
    assert keys["Ctrl + Left/Right"] == "skip 30s"

    visualizer_nav = help_sections_for_stop(CycleStop.MENU, focus)[0]
    assert isinstance(visualizer_nav, HelpSection)
    vis_keys = dict(visualizer_nav.entries)
    assert vis_keys["Ctrl + N"] == "new project"
    assert vis_keys["Ctrl + O"] == "open project"
    assert "Ctrl + S" in vis_keys
    assert vis_keys["Ctrl + Enter"] == "add song marker"
    assert vis_keys["Ctrl + R"] == "render"
    assert vis_keys["Ctrl + ,"] == "open Settings > Preview"
    assert "Ctrl + ," not in keys
    assert vis_keys["Shift + Left/Right"] == "skip 2s"
    assert vis_keys["Ctrl + Left/Right"] == "skip 30s"


def test_timeline_strip_help_paused() -> None:
    section = timeline_strip_section(
        paused=True, recording=False, override_active=False, layer_count=4
    )
    entries = dict(section.entries)
    assert entries["A"] == "arm / disarm row for recording"
    assert "1-4" not in entries
    assert "Click eye" not in entries
    assert entries["Right-click row"] == "row options; on a clip, clip options too"
    assert entries["Shift + F10 / Menu"] == "row options for the focused row"
    assert entries["Shift + Enter"] == "override row visibility on / off"
    assert "Ctrl + Enter" not in entries
    assert entries["Space"] == "play"
    assert entries["Ctrl + Space / R"] == "start record"
    assert entries["B"] == "cycle clip blend"
    assert entries["C / Shift + C"] == "cycle clip cut in / cut out"
    assert entries["O"] == "cycle clip role"
    assert entries["Left/Right"] == "previous / next clip"
    assert entries["Enter"] == "seek to clip start"
    assert entries[", / ."] == "nudge clip opacity -/+ 1%"
    assert entries["Ctrl + , / ."] == "nudge clip opacity -/+ 10%"
    keys = [key for key, _ in section.entries]
    assert keys.index("Ctrl + Space / R") + 1 == keys.index("Space")


def test_timeline_strip_help_single_layer() -> None:
    entries = dict(
        timeline_strip_section(
            paused=True, recording=False, override_active=True, layer_count=1
        ).entries
    )
    assert entries["1"] == "show / hide an overridden layer"
    assert "1-4" not in entries


def test_timeline_strip_help_playing_without_override() -> None:
    keys = _timeline_keys(paused=False, timeline_recording=False, timeline_override_active=False)
    assert "1-4" not in keys
    assert "Shift + Enter" in keys
    assert dict(
        timeline_strip_section(
            paused=False, recording=False, override_active=False, layer_count=4
        ).entries
    )["Space"] == "pause"


def test_timeline_strip_help_playing_with_override() -> None:
    entries = dict(
        timeline_strip_section(
            paused=False, recording=False, override_active=True, layer_count=6
        ).entries
    )
    assert entries["1-6"] == "show / hide an overridden layer"
    assert entries["Click eye"] == "show / hide an overridden layer"


def test_timeline_strip_help_recording_while_playing() -> None:
    entries = dict(
        timeline_strip_section(
            paused=False, recording=True, override_active=False, layer_count=4
        ).entries
    )
    assert "Ctrl + Enter" not in entries
    assert entries["1-4"] == "show / hide an armed layer"
    assert entries["Click eye"] == "show / hide an armed layer"
    assert entries["Ctrl + 1-4"] == "drop a clip edge (keep level)"
    assert "Shift + Enter" not in entries
    assert entries["Left/Right"] == "skip 10s, fills range"
    assert "Shift + Left/Right" not in entries
    assert "Ctrl + Left/Right" not in entries
    assert entries["R"] == "stop record"
    assert entries["Ctrl + Space / Space"] == "stop record and pause"
    assert "Space" not in entries


def test_help_column_text_includes_the_key_label() -> None:
    sections = help_sections_for_stop(
        CycleStop.MENU, RowDescriptor(RowKind.TRACK_HEADER)
    )
    assert "Ctrl + Q" in help_column_text(sections)


def test_help_column_draws_the_subject_stop() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    from imgui_bundle import imgui

    from cleave.viz import imgui_host
    from cleave.viz.commands import CommandContext
    from cleave.viz.menu_bar import MenuBarState
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.shell_menu_bar import menu_bar_height_px
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.progress_bar import accent_at
    from cleave.viz.theme import palette

    overlay = SimpleNamespace(visibility=1.0, notify_input=lambda: None)
    menu = MenuBarState()
    menu.focused = True
    controls = SimpleNamespace(
        cfg=SimpleNamespace(project_slug="song"),
        config_dirty=False,
        session=SimpleNamespace(
            layer_z_order=(),
            help_visible=True,
            timeline=SimpleNamespace(panel_open=False),
        ),
        shell_focus=ShellFocusState(region=ShellRegion.NAVIGATOR),
        focus_cursor=None,
        build_view_state=lambda **_kwargs: SimpleNamespace(
            focus_descriptor=RowDescriptor(RowKind.TRACK_HEADER),
            timeline=SimpleNamespace(enabled=False),
            paused=False,
            timeline_recording=False,
            timeline_override_active=False,
            settings=SimpleNamespace(editor_mode="visualizer"),
            layer_z_order=("drums",),
            tracks={},
        ),
        inline_edit=InlineEditController(),
        preset_browser=SimpleNamespace(active=False, view_state=lambda: None),
        context_menu=ContextMenuState(),
        modal_host=ModalHost(),
        transport=MagicMock(),
    )
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        from cleave.viz.imgui_host import ImGuiHost
        from cleave.viz.shell_host import ShellHost

        host = ShellHost(
            ImGuiHost.create(),
            menu,
            controls,
            menu_bar_height_px(),
        )
    try:
        host.imgui.display_size = (1280, 720)
        height = menu_bar_height_px()
        host.set_layout(
            ShellLayout.compute(1280, 720, height, height, 0, help_width=320)
        )
        host.navigator.draw = lambda _frame: None
        host.navigator.visible_nodes = lambda: ()
        host.inspector.draw = lambda _state: None
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        lists = list(imgui.get_draw_data().cmd_lists)
        help_list = next(
            draw_list
            for draw_list in lists
            if str(draw_list._owner_name) == "##shell-help"
        )
        colors = {int(vtx.col) for vtx in help_list.vtx_buffer}

        def color_u32(rgb: tuple[int, int, int]) -> int:
            return int(
                imgui.get_color_u32(
                    imgui.ImVec4(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0)
                )
            )

        assert color_u32(accent_at(0.0)) in colors
        assert color_u32(accent_at(1.0)) in colors
        assert color_u32(palette().value) in colors
        assert color_u32(palette().label) in colors
        del lists, help_list, colors
    finally:
        host.imgui.destroy()


def test_help_description_lines_end_in_punctuation() -> None:
    """Each line is a paragraph the column wraps; it ends in punctuation."""
    import re

    from cleave.effects.registry import EFFECT_IDS, effect_help_description
    from cleave.viz.row_spec import ROW_SPECS

    sources = [(kind.name, spec.help_description) for kind, spec in ROW_SPECS.items()]
    sources += [(effect_id, effect_help_description(effect_id)) for effect_id in EFFECT_IDS]
    for name, lines in sources:
        for line in lines or ():
            assert re.search(r"[.!?:)]$", line), (name, line)


def test_help_titles_are_capital_case() -> None:
    import re

    from cleave.effects.registry import EFFECT_IDS, effect_help_title
    from cleave.viz.row_spec import ROW_SPECS

    titles = [spec.help_title for spec in ROW_SPECS.values() if spec.help_title]
    titles += [effect_help_title(effect_id) for effect_id in EFFECT_IDS]
    for title in titles:
        for word in re.findall(r"[A-Za-z][A-Za-z']*", title):
            # Names that set their own casing.
            if word in {"projectM"}:
                continue
            assert word[0].isupper(), title


def test_preview_stop_lists_its_menu_and_keys() -> None:
    focus = RowDescriptor(RowKind.TRACK_OPACITY, slot="drums")
    shell = ShellFocusState(region=ShellRegion.PREVIEW, selected_id="layer:drums")
    sections = help_sections(focus, shell_focus=shell)
    assert [section.title for section in sections] == ["Preview"]
    entries = dict(sections[0].entries)
    assert entries["Shift + F10 / Menu"] == "preview options"
    assert entries["Esc"] == "back to the navigator"
