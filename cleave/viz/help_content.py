"""Help panel section data and dispatch for the Cleave editor."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from cleave.viz.row_hotkeys import node_header_descriptor
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.choice import ChoiceKind
from cleave.viz.row_spec import RowSpec, row_choice_kind, row_spec
from cleave.viz.shell_focus import CycleStop, ShellFocusState, ShellRegion

if TYPE_CHECKING:
    from cleave.viz.modal import ModalHelpSection
    from cleave.viz.tuning_view_state import TuningViewState

HelpEntry = tuple[str, str]


@dataclass(frozen=True)
class HelpSection:
    """Controls: ``entries`` are keys, ``mouse_entries`` are mouse actions."""

    title: str
    entries: tuple[HelpEntry, ...]
    mouse_entries: tuple[HelpEntry, ...] = ()


@dataclass(frozen=True)
class DescriptionSection:
    """Prose, then the options it describes. Never holds controls."""

    title: str
    lines: tuple[str, ...] = ()
    entries: tuple[HelpEntry, ...] = ()


def description_section(
    title: str,
    *,
    lines: tuple[str, ...] = (),
    mode_entries: tuple[HelpEntry, ...] = (),
) -> DescriptionSection:
    return DescriptionSection(title, lines=lines, entries=mode_entries)


HelpContent = HelpSection | DescriptionSection


def modal_help_content(
    sections: tuple[ModalHelpSection, ...],
) -> tuple[HelpContent, ...]:
    """Help column sections for an open form's ``ModalHost.help_sections``."""
    content: list[HelpContent] = []
    for section in sections:
        described = bool(section.lines or section.entries)
        if described:
            content.append(
                description_section(
                    section.title, lines=section.lines, mode_entries=section.entries
                )
            )
        if section.keys:
            title = CONTROLS_SECTION_TITLE if described else section.title
            content.append(HelpSection(title, section.keys))
    return tuple(content)


CONTROLS_SECTION_TITLE = "Controls"
MOUSE_SUBHEADING = "Mouse"
KEYBOARD_SUBHEADING = "Keyboard"


def control_groups(
    section: HelpSection,
) -> tuple[tuple[str, tuple[HelpEntry, ...]], ...]:
    """The section's sub-headings with their entries, leaving out empty ones."""
    groups = (
        (MOUSE_SUBHEADING, section.mouse_entries),
        (KEYBOARD_SUBHEADING, section.entries),
    )
    return tuple((heading, entries) for heading, entries in groups if entries)


# Entries run from moving, through acting on the item and editing it, to
# leaving. Related entries sit together, and Delete and Esc come last in
# their group.
_MOVE_ENTRIES: tuple[HelpEntry, ...] = (
    ("Up/Down", "move in the active region"),
    ("Left/Right", "open/close a navigator node, or change an inspector value"),
    ("Ctrl + Up/Down", "previous / next top-level node"),
    (
        "Tab / Shift+Tab",
        "move between Menu, Navigator, Inspector, Preview, and Timeline (when the strip is open)",
    ),
    ("Alt + Left/Right", "back / forward through pages"),
    ("F10 / Alt", "focus menu bar"),
    ("Alt + underlined letter", "open that menu (F, E, V, P, S, H)"),
    ("Shift + F10 / Menu", "options for the highlighted item"),
)
_PLAYBACK_ENTRIES: tuple[HelpEntry, ...] = (
    ("Space", "play / pause"),
    ("Shift + Left/Right", "skip 2s"),
    ("Ctrl + Left/Right", "skip 30s"),
)
_VIEW_ENTRIES: tuple[HelpEntry, ...] = (
    ("H", "show / hide help"),
    ("Ctrl + F", "play full screen (Esc returns)"),
    ("F11", "full screen editor"),
)
_QUIT_ENTRY: HelpEntry = ("Ctrl + Q", "quit")

NAVIGATION_SECTION = HelpSection(
    "Navigation / Global",
    (
        *_MOVE_ENTRIES,
        *_PLAYBACK_ENTRIES,
        ("Ctrl + Enter", "add song marker"),
        ("Ctrl + Z / Ctrl + Y", "undo / redo"),
        ("Ctrl + N", "new project"),
        ("Ctrl + O", "open project"),
        ("Ctrl + S", "save"),
        ("Ctrl + R", "render"),
        ("Ctrl + ,", "open Settings > Preview"),
        *_VIEW_ENTRIES,
        ("F3", "show / hide the frame timer"),
        _QUIT_ENTRY,
    ),
    (("Right-click preview", "play, solo, on/off, quality, grab still"),),
)

_CURATION_NAVIGATION_SECTION = HelpSection(
    "Navigation / Global",
    (*_MOVE_ENTRIES, *_PLAYBACK_ENTRIES, *_VIEW_ENTRIES, _QUIT_ENTRY),
    (("Right-click preview", "play, quality, grab still"),),
)


def navigation_section(*, preset_curation: bool = False) -> HelpSection:
    if preset_curation:
        return _CURATION_NAVIGATION_SECTION
    return NAVIGATION_SECTION


PREVIEW_SECTION = HelpSection(
    "Preview",
    (
        ("Space", "play / pause"),
        ("Shift + F10 / Menu", "preview options"),
        ("Esc", "back to the navigator"),
    ),
    (("Right-click", "preview options"),),
)


PRESET_BROWSER_SECTIONS: tuple[HelpContent, ...] = (
    description_section(
        "Browse Presets",
        lines=(
            "Folders, then presets, for this layer. The layer plays the preset you move to; Enter keeps it and Esc goes back to the one you started with.",
            "The filter searches every preset in this folder and the folders under it. Highlight it and press Enter, or click it, and the list follows as you type; Enter keeps the results and Esc puts back the filter you had.",
        ),
    ),
    HelpSection(
        CONTROLS_SECTION_TITLE,
        (
            ("Up/Down", "move; Up from the top row reaches the filter"),
            ("PgUp/PgDn, Home/End", "move further"),
            ("Right", "open folder"),
            ("Left/Backspace", "parent folder"),
            ("Enter", "open folder / keep preset / edit the filter"),
            ("Esc", "clear the filter, or go back and close"),
        ),
        (
            ("Click the filter", "edit it; Enter keeps the results, Esc cancels"),
            ("Double-click", "open folder / keep preset"),
            ("Right-click preset", "favourite, blacklist, role"),
            ("Back arrow", "close, keeping the preset that is playing"),
        ),
    ),
)


_NAVIGATOR_SECTION = HelpSection(
    "Navigator",
    (
        ("Up/Down", "move across nodes"),
        ("Ctrl + Up/Down", "previous / next top-level node"),
        ("Left/Right", "open/close"),
        ("Shift + F10 / Menu", "options for the selected row"),
    ),
    (("Right-click row", "row options"),),
)


_LAYER_SWITCH_ENTRIES: tuple[HelpEntry, ...] = (
    ("S", "solo layer"),
    ("L", "lock/unlock layer"),
)
_LAYER_ARRANGE_ENTRIES: tuple[HelpEntry, ...] = (
    ("M", "change layer order"),
    ("Ctrl + L", "add layer"),
    ("Delete", "delete layer"),
)
_LAYER_MOUSE_ENTRIES: tuple[HelpEntry, ...] = (("Drag handle", "change layer order"),)
_LAYER_VISIBILITY_ENTRY = ("E", "enable/disable layer")
_LAYER_JUMP_ACTION = "jump to layer"

_CURATION_LAYER_SECTION = HelpSection("Layer", ())

_ENTER_AFFORDANCES = frozenset(
    {
        RowAffordance.COMMAND,
        RowAffordance.VALUE_TEXT,
        RowAffordance.VALUE_COLOUR,
    }
)

_INSPECTOR_COMMAND_KINDS = {
    "layers.add": RowKind.LAYER_MANAGEMENT_ADD,
    "layers.delete": RowKind.LAYER_MANAGEMENT_DELETE,
    "layers.resume_switching": RowKind.TRACK_PRESET_SWITCHING_RESUME,
    "timeline.generate": RowKind.TIMELINE_GENERATE,
    "timeline.reset": RowKind.TIMELINE_RESET,
    "timeline.snap_cues": RowKind.TIMELINE_SNAP_CUES,
    "timeline.snap_to_markers": RowKind.TIMELINE_SNAP_CUES,
    "timeline.set_cut_type": RowKind.TIMELINE_SET_CUT_TYPE,
    "settings.open_crash_log_folder": RowKind.SETTINGS_DEV_TOOLS_OPEN_CRASH_LOG_FOLDER,
    "settings.open_themes_folder": RowKind.SETTINGS_UI_OPEN_THEMES_FOLDER,
    "settings.reload_themes": RowKind.SETTINGS_UI_RELOAD_THEMES,
    "settings.measure_latency": RowKind.SETTINGS_MEASURE_AUDIO_LATENCY,
    "settings.calibrate_tap_timing": RowKind.SETTINGS_CALIBRATE_TAP_TIMING,
}


def layer_section(
    *,
    timeline_enabled: bool,
    preset_curation: bool = False,
    layer_count: int = 4,
    layer_jumps: bool = True,
) -> HelpSection:
    if preset_curation:
        return _CURATION_LAYER_SECTION
    entries: list[HelpEntry] = []
    if layer_jumps:
        entries.append((_layer_key_range_label(layer_count), _LAYER_JUMP_ACTION))
    if not timeline_enabled:
        entries.append(_LAYER_VISIBILITY_ENTRY)
    entries.extend(_LAYER_SWITCH_ENTRIES)
    entries.extend(_LAYER_ARRANGE_ENTRIES)
    return HelpSection("Layer", tuple(entries), _LAYER_MOUSE_ENTRIES)


_EDIT_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "adjust value"),
        ("PgUp/PgDn", "large step"),
    ),
)

_PRESET_DIR_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous directory"),
        ("Enter", "open directory"),
        ("Backspace", "parent directory"),
    ),
)

_PRESET_CURATION_SHORTCUTS = (
    ("F", "favourite / unfavourite preset"),
    ("B", "blacklist / unblacklist preset"),
    ("C", "set preset role (bed/pulse/lead/accent/none)"),
)

_PRESET_BROWSE_ENTRIES: tuple[HelpEntry, ...] = (
    ("Left/Right", "next/previous preset"),
    ("PgUp/PgDn", "next/previous, large step"),
)

_PRESET_CLIPBOARD_ENTRIES: tuple[HelpEntry, ...] = (
    ("Ctrl + C", "copy this preset"),
    ("Ctrl + V", "play the copied preset (preview)"),
)

_USER_PRESET_ADD_SHORTCUT = ("P", "add current preset to switching list")

_PRESET_LIST_ITEM_SECTION = HelpSection(
    "Edit",
    (
        ("Enter", "play this preset and pause switching"),
        *_PRESET_CURATION_SHORTCUTS,
        ("M", "reorder in list"),
        ("Ctrl + X / Ctrl + C", "cut / copy preset"),
        ("Ctrl + V", "paste over this entry"),
        ("Ctrl + Shift + V", "paste after this entry"),
        ("Ctrl + D", "duplicate entry"),
        ("Delete", "remove preset"),
        ("Ctrl + Z", "undo a list edit"),
    ),
    (
        ("Double-click", "replace from the preset browser"),
        ("Drag handle", "reorder in list"),
    ),
)

_PRESET_SWITCHING_RESUME_SECTION = HelpSection(
    "Previewing - Enter To Resume Switching",
    (("Enter", "resume switching"),),
)


def _preset_dir_section(*, switching_on: bool = False) -> HelpSection:
    entries = list(_PRESET_DIR_SECTION.entries)
    if switching_on:
        entries.append(_USER_PRESET_ADD_SHORTCUT)
    return HelpSection(_PRESET_DIR_SECTION.title, tuple(entries))


def _preset_section(*, switching_on: bool = False) -> HelpSection:
    entries = [*_PRESET_BROWSE_ENTRIES, *_PRESET_CURATION_SHORTCUTS]
    if switching_on:
        entries.append(_USER_PRESET_ADD_SHORTCUT)
    entries.extend(_PRESET_CLIPBOARD_ENTRIES)
    return HelpSection("Edit", tuple(entries))


def _heading_section(behavior: RowSpec) -> HelpSection | None:
    """Keys for a navigator page, or None when it has only a description."""
    entries: list[tuple[str, str]] = []
    if behavior.toggle_enabled is not None:
        entries.append(("E", "enable/disable"))
    if behavior.toggle_solo is not None:
        entries.append(("S", "solo"))
    if behavior.toggle_preview is not None:
        entries.append(("V", "preview cards"))
    if not entries:
        return None
    return HelpSection(behavior.help_title, tuple(entries))


def help_focus_descriptor(
    focus: RowDescriptor,
    shell_focus: ShellFocusState | None,
    *,
    timeline_focused: bool = False,
) -> RowDescriptor | None:
    """Navigator or inspector row help should follow, or None when that stop has no row."""
    if shell_focus is None or timeline_focused:
        return focus
    if shell_focus.region is ShellRegion.INSPECTOR:
        command_id = shell_focus.inspector_command_id
        if command_id is not None:
            kind = _INSPECTOR_COMMAND_KINDS.get(command_id)
            if kind is None:
                return None
            return RowDescriptor(kind)
        return shell_focus.inspector_cursor
    if shell_focus.region is ShellRegion.NAVIGATOR:
        return node_header_descriptor(shell_focus.selected_id)
    return None


def _layer_key_range_label(layer_count: int) -> str:
    if layer_count <= 1:
        return "1"
    return f"1-{layer_count}"


def timeline_strip_section(
    *,
    paused: bool,
    recording: bool,
    override_active: bool,
    layer_count: int = 4,
) -> HelpSection:
    layer_keys = _layer_key_range_label(layer_count)
    arm = ("A", "arm / disarm row for recording")
    row_menu = ("Right-click row", "row options; on a clip, clip options too")
    entries: list[HelpEntry] = []
    mouse: list[HelpEntry] = []

    if recording:
        entries.extend(
            (
                ("Left/Right", "skip 10s, fills range"),
                (layer_keys, "show / hide an armed layer"),
                (f"Ctrl + {layer_keys}", "drop a clip edge (keep level)"),
                arm,
                ("R / Esc", "stop record"),
                ("Ctrl + Space / Space", "stop record and pause"),
            )
        )
        mouse.extend(
            (
                ("Click eye", "show / hide an armed layer"),
                ("Dbl-click row", "seek, fills range"),
                row_menu,
                ("Click/Drag ruler", "seek / scrub, fills range"),
            )
        )
    else:
        entries.extend(
            (
                ("Left/Right", "previous / next clip"),
                ("Enter", "seek to clip start"),
                ("Space", "play" if paused else "pause"),
                (", / .", "nudge clip opacity -/+ 1%"),
                ("Ctrl + , / .", "nudge clip opacity -/+ 10%"),
                ("B", "cycle clip blend"),
                ("O", "cycle clip role"),
                ("C / Shift + C", "cycle clip cut in / cut out"),
                ("Ctrl + K", "split clip at playhead"),
                ("Delete", "delete clip"),
                arm,
                ("Ctrl + Space / R", "start record"),
                ("Shift + Enter", "override row visibility on / off"),
            )
        )
        mouse.extend(
            (
                ("Click row", "select row / clip"),
                ("Dbl-click row", "add clip; on a clip, seek"),
                row_menu,
                ("Click/Drag ruler", "seek / scrub"),
            )
        )
        if override_active:
            entries.append((layer_keys, "show / hide an overridden layer"))
            mouse.insert(0, ("Click eye", "show / hide an overridden layer"))

    entries.append(("Shift + F10 / Menu", "row options for the focused row"))
    if not recording:
        entries.append(("Esc", "close timeline"))
    mouse.extend(
        (
            ("Drag row / scrollbar", "scroll when zoomed"),
            ("Wheel", "zoom in / out"),
            ("Shift + Wheel", "scroll left / right"),
        )
    )
    return HelpSection("Timeline", tuple(entries), tuple(mouse))


def _value_step_section(row_kind: RowKind) -> HelpSection:
    behavior = row_spec(row_kind)
    if behavior.help_entries is not None:
        entries = behavior.help_entries
    elif row_kind == RowKind.TRACK_EFFECT:
        entries = (
            ("Left/Right", "adjust depth"),
            ("PgUp/PgDn", "large step"),
        )
    else:
        entries = _EDIT_SECTION.entries
    # A row whose Enter does something else has no key for its list.
    if (
        behavior.apply_action is None
        and row_choice_kind(row_kind) is ChoiceKind.COMBO
    ):
        entries = (*entries, ("Enter", "open the list"))
    return HelpSection(behavior.help_title or "Edit", entries)


def _description_section(
    row_kind: RowKind,
    *,
    effect_id: str | None = None,
) -> DescriptionSection | None:
    if row_kind == RowKind.TRACK_EFFECT and effect_id is not None:
        from cleave.effects.registry import effect_help_description, effect_help_title

        lines = effect_help_description(effect_id)
        if lines is not None:
            return DescriptionSection(effect_help_title(effect_id), lines)

    behavior = row_spec(row_kind)
    if behavior.help_description is None and behavior.help_mode_entries is None:
        return None
    return description_section(
        behavior.help_title or "About",
        lines=behavior.help_description or (),
        mode_entries=behavior.help_mode_entries or (),
    )


def _controls_section(primary: HelpSection) -> HelpSection:
    return replace(primary, title=CONTROLS_SECTION_TITLE)


def sections_for(
    row_kind: RowKind,
    *,
    effect_id: str | None = None,
    timeline_enabled: bool = False,
    timeline_recording: bool = False,
    preset_switching: str | None = None,
    preset_curation: bool = False,
    layer_count: int = 4,
) -> tuple[HelpContent, ...]:
    """Description and controls sections for one row. No global navigation."""
    behavior = row_spec(row_kind)

    if not behavior.navigable:
        return ()
    if (
        behavior.affordance == RowAffordance.DISPLAY
        and behavior.help_description is None
    ):
        return ()

    primary: HelpSection | None = None

    if behavior.affordance == RowAffordance.HEADING:
        if behavior.can_enter_move_mode:
            section = layer_section(
                timeline_enabled=timeline_enabled,
                preset_curation=preset_curation,
                layer_count=layer_count,
                layer_jumps=not timeline_recording,
            )
            if not section.entries:
                description = _description_section(row_kind, effect_id=effect_id)
                if description is not None:
                    return (description,)
                return ()
            primary = section
        else:
            primary = _heading_section(behavior)
    elif behavior.affordance == RowAffordance.VALUE_STEP:
        primary = _value_step_section(row_kind)
    elif row_kind == RowKind.TRACK_PRESET_LIST_ITEM:
        primary = _PRESET_LIST_ITEM_SECTION
    elif row_kind == RowKind.TRACK_PRESET_SWITCHING_RESUME:
        primary = _PRESET_SWITCHING_RESUME_SECTION
    elif behavior.affordance == RowAffordance.PATH_DIR:
        primary = _preset_dir_section(
            switching_on=preset_switching == "on"
        )
    elif behavior.affordance == RowAffordance.PATH_PRESET:
        primary = _preset_section(
            switching_on=preset_switching == "on"
        )
    elif row_kind == RowKind.LAYER_MANAGEMENT_ADD:
        primary = HelpSection(
            behavior.help_title or "Add Layer",
            (("Enter", "add layer"),),
        )
    elif row_kind == RowKind.LAYER_MANAGEMENT_DELETE:
        primary = HelpSection(
            behavior.help_title or "Delete Layer",
            (("Enter/Delete", "delete layer"),),
        )
    elif behavior.affordance in _ENTER_AFFORDANCES:
        primary = HelpSection(
            behavior.help_title or "Edit",
            behavior.help_entries or (),
        )
    elif behavior.affordance == RowAffordance.DISPLAY:
        entries = behavior.help_entries
        if entries is None:
            description = _description_section(row_kind, effect_id=effect_id)
            if description is not None:
                return (description,)
            return ()
        primary = HelpSection(
            behavior.help_title or "Edit",
            entries,
        )

    description = _description_section(row_kind, effect_id=effect_id)
    if primary is None:
        return () if description is None else (description,)

    if description is not None:
        return (description, _controls_section(primary))
    return (primary,)


def help_stop_for_shell(
    shell_focus: ShellFocusState | None,
    *,
    timeline_focused: bool,
) -> CycleStop:
    """Content stop from the shell region. Menu focus is not a region."""
    if timeline_focused or (
        shell_focus is not None and shell_focus.region is ShellRegion.TIMELINE
    ):
        return CycleStop.TIMELINE
    if shell_focus is None:
        return CycleStop.INSPECTOR
    if shell_focus.region is ShellRegion.INSPECTOR:
        return CycleStop.INSPECTOR
    if shell_focus.region is ShellRegion.PREVIEW:
        return CycleStop.PREVIEW
    return CycleStop.NAVIGATOR


def _described_row(
    stop: CycleStop,
    focus: RowDescriptor,
    shell_focus: ShellFocusState | None,
) -> RowDescriptor | None:
    if stop is CycleStop.NAVIGATOR:
        if shell_focus is None:
            return None
        return help_focus_descriptor(
            focus,
            replace(shell_focus, region=ShellRegion.NAVIGATOR),
            timeline_focused=False,
        )
    if stop is CycleStop.INSPECTOR:
        if shell_focus is None:
            return focus
        return help_focus_descriptor(
            focus,
            replace(shell_focus, region=ShellRegion.INSPECTOR),
            timeline_focused=False,
        )
    return None


def _sections_for_row(
    described: RowDescriptor | None,
    *,
    timeline_enabled: bool,
    timeline_recording: bool,
    preset_switching: str | None,
    preset_curation: bool,
    layer_count: int,
) -> tuple[HelpContent, ...]:
    if described is None:
        return ()
    return sections_for(
        described.kind,
        effect_id=described.effect_id,
        timeline_enabled=timeline_enabled,
        timeline_recording=timeline_recording,
        preset_switching=preset_switching,
        preset_curation=preset_curation,
        layer_count=layer_count,
    )


def help_sections_for_stop(
    stop: CycleStop,
    focus: RowDescriptor,
    *,
    shell_focus: ShellFocusState | None = None,
    timeline_enabled: bool = False,
    paused: bool = False,
    timeline_recording: bool = False,
    timeline_override_active: bool = False,
    preset_switching: str | None = None,
    preset_curation: bool = False,
    layer_count: int = 4,
) -> tuple[HelpContent, ...]:
    """Help for one Tab stop."""
    if stop is CycleStop.MENU:
        return (navigation_section(preset_curation=preset_curation),)
    if stop is CycleStop.PREVIEW:
        return (PREVIEW_SECTION,)
    if stop is CycleStop.TIMELINE:
        return (
            timeline_strip_section(
                paused=paused,
                recording=timeline_recording,
                override_active=timeline_override_active,
                layer_count=layer_count,
            ),
        )
    row_sections = _sections_for_row(
        _described_row(stop, focus, shell_focus),
        timeline_enabled=timeline_enabled,
        timeline_recording=timeline_recording,
        preset_switching=preset_switching,
        preset_curation=preset_curation,
        layer_count=layer_count,
    )
    if stop is CycleStop.NAVIGATOR:
        return (*row_sections, _NAVIGATOR_SECTION)
    return row_sections


def help_section_kwargs(
    view_state: TuningViewState,
    shell_focus: ShellFocusState | None,
    *,
    stop: CycleStop,
) -> dict[str, Any]:
    """Facts the help column passes into section dispatch."""
    focus = view_state.focus_descriptor
    described = _described_row(stop, focus, shell_focus)
    preset_switching = None
    if described is not None and described.slot is not None:
        track = view_state.tracks.get(described.slot)
        if track is not None:
            preset_switching = track.runtime.preset_switching
    return {
        "focus": focus,
        "shell_focus": shell_focus,
        "timeline_enabled": view_state.timeline.enabled,
        "paused": view_state.paused,
        "timeline_recording": view_state.timeline_recording,
        "timeline_override_active": view_state.timeline_override_active,
        "preset_switching": preset_switching,
        "preset_curation": view_state.settings.editor_mode == "preset_curation",
        "layer_count": len(view_state.layer_z_order),
    }


def help_sections(
    focus: RowDescriptor,
    *,
    shell_focus: ShellFocusState | None = None,
    timeline_enabled: bool = False,
    timeline_submenu_focused: bool = False,
    paused: bool = False,
    timeline_recording: bool = False,
    timeline_override_active: bool = False,
    preset_switching: str | None = None,
    preset_curation: bool = False,
    layer_count: int = 4,
) -> tuple[HelpContent, ...]:
    """Sections for the shell row's stop. The column passes Menu itself."""
    stop = help_stop_for_shell(
        shell_focus, timeline_focused=timeline_submenu_focused
    )
    return help_sections_for_stop(
        stop,
        focus,
        shell_focus=shell_focus,
        timeline_enabled=timeline_enabled,
        paused=paused,
        timeline_recording=timeline_recording,
        timeline_override_active=timeline_override_active,
        preset_switching=preset_switching,
        preset_curation=preset_curation,
        layer_count=layer_count,
    )
