"""Help panel section data and dispatch for the Cleave editor."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.row_hotkeys import node_header_descriptor
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import row_spec
from cleave.viz.shell_focus import ShellFocusState, ShellRegion

HelpEntry = tuple[str, str]


@dataclass(frozen=True)
class HelpSection:
    title: str
    entries: tuple[HelpEntry, ...]


@dataclass(frozen=True)
class DescriptionSection:
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

KEYBOARD_CONTROLS_SECTION_TITLE = "Keyboard Controls"

_REGION_MOVE_ENTRY = (
    "Up/Down",
    "in the active region: navigator nodes, inspector fields and group headers, or timeline lanes",
)
_NAVIGATOR_EXPAND_ENTRY = (
    "Left/Right",
    "expand/collapse navigator, or step an inspector value",
)
_REGION_CYCLE_ENTRY = (
    "Tab / Shift+Tab",
    "cycle Menu, Navigator, Inspector, and Timeline; skip Timeline when the strip is closed",
)
_TOP_LEVEL_NAV_ENTRY = (
    "Ctrl + Up/Down",
    "previous / next top-level navigator node",
)
_SEEK_AND_QUIT_ENTRIES: tuple[HelpEntry, ...] = (
    ("Shift + Left/Right", "skip 2s"),
    ("Ctrl + Left/Right", "skip 30s"),
    ("ESC", "hide UI"),
    ("Ctrl + Q", "quit"),
)

NAVIGATION_SECTION = HelpSection(
    "Navigation / Global",
    (
        _REGION_MOVE_ENTRY,
        _NAVIGATOR_EXPAND_ENTRY,
        _REGION_CYCLE_ENTRY,
        _TOP_LEVEL_NAV_ENTRY,
        *_SEEK_AND_QUIT_ENTRIES,
        ("Ctrl + S", "save"),
        ("Ctrl + Enter", "place song marker"),
        ("F10 / Alt", "focus menu bar"),
        ("Ctrl + R", "render"),
    ),
)

_CURATION_NAVIGATION_SECTION = HelpSection(
    "Navigation / Global",
    (
        _REGION_MOVE_ENTRY,
        _NAVIGATOR_EXPAND_ENTRY,
        _REGION_CYCLE_ENTRY,
        _TOP_LEVEL_NAV_ENTRY,
        *_SEEK_AND_QUIT_ENTRIES,
        ("F10 / Alt", "focus menu bar"),
    ),
)


def navigation_section(*, preset_curation: bool = False) -> HelpSection:
    if preset_curation:
        return _CURATION_NAVIGATION_SECTION
    return NAVIGATION_SECTION


_LAYER_SECTION_BASE: tuple[tuple[str, str], ...] = (
    ("M", "move z-order"),
    ("L", "lock/unlock layer"),
    ("S", "solo layer"),
    ("Delete", "delete layer"),
)

_LAYER_VISIBILITY_ENTRY = ("E", "enable/disable layer")
_LAYER_ADD_ENTRY = ("Ctrl + L", "add layer")
_LAYER_JUMP_ACTION = "jump to layer"

_CURATION_LAYER_SECTION = HelpSection("Layer", ())

_INSPECTOR_COMMAND_KINDS = {
    "layers.add": RowKind.LAYER_MANAGEMENT_ADD,
    "layers.delete": RowKind.LAYER_MANAGEMENT_DELETE,
    "timeline.apply_preset": RowKind.TIMELINE_PRESETS,
    "timeline.reset": RowKind.TIMELINE_RESET,
    "timeline.snap_cues": RowKind.TIMELINE_SNAP_CUES,
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
    entries = list(_LAYER_SECTION_BASE)
    if not timeline_enabled:
        entries.append(_LAYER_VISIBILITY_ENTRY)
    if layer_jumps:
        entries.append((_layer_key_range_label(layer_count), _LAYER_JUMP_ACTION))
    entries.append(_LAYER_ADD_ENTRY)
    return HelpSection("Layer", tuple(entries))


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
        ("Left/Right", "next/previous"),
        ("Enter", "open folder"),
        ("Backspace", "parent"),
    ),
)

_PRESET_CURATION_SHORTCUTS = (
    ("F", "favourite preset"),
    ("B", "blacklist preset"),
    ("C", "cast preset (bed/pulse/lead/accent)"),
    ("R", "remove favourite / restore blacklist / remove cast"),
)

_PRESET_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous preset"),
        ("PgUp/PgDn", "next/previous large step"),
        *_PRESET_CURATION_SHORTCUTS,
    ),
)

_USER_PRESET_ADD_SHORTCUT = ("P", "add current preset to switching list")

_PRESET_LIST_ITEM_SECTION = HelpSection(
    "Edit",
    (
        ("Enter", "audition preset and pause switching"),
        ("M", "reorder in list"),
        ("Delete", "remove preset"),
        *_PRESET_CURATION_SHORTCUTS,
    ),
)

_PRESET_LIST_ADD_SECTION = HelpSection(
    "Add Current Preset",
    (("Enter", "add current preset"),),
)

_PRESET_SWITCHING_RESUME_SECTION = HelpSection(
    "Switching Paused - Enter To Resume",
    (("Enter", "resume switching"),),
)


def _preset_dir_section(*, switching_on: bool = False) -> HelpSection:
    entries = list(_PRESET_DIR_SECTION.entries)
    if switching_on:
        entries.append(_USER_PRESET_ADD_SHORTCUT)
    return HelpSection(_PRESET_DIR_SECTION.title, tuple(entries))


def _preset_section(*, switching_on: bool = False) -> HelpSection:
    entries = list(_PRESET_SECTION.entries)
    if switching_on:
        entries.append(_USER_PRESET_ADD_SHORTCUT)
    return HelpSection(_PRESET_SECTION.title, tuple(entries))

_RENDER_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("E", "enable/disable"),
        ("S", "always on"),
    ),
)

_RENDER_TIMELINE_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("E", "enable/disable"),
    ),
)


def help_focus_descriptor(
    focus: RowDescriptor,
    shell_focus: ShellFocusState | None,
    *,
    timeline_focused: bool = False,
) -> RowDescriptor | None:
    """Row help should follow, or None when only the navigation section applies."""
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


def help_shell_row(
    shell_focus: ShellFocusState | None,
    *,
    timeline_focused: bool,
) -> tuple[str | int | RowKind | None, ...] | None:
    """Shell row identity for the help cache. None when help follows *focus*."""
    if shell_focus is None or timeline_focused:
        return None
    if shell_focus.region is ShellRegion.NAVIGATOR:
        return ("navigator", shell_focus.selected_id)
    command_id = shell_focus.inspector_command_id
    if command_id is not None:
        return ("inspector", "command", command_id)
    cursor = shell_focus.inspector_cursor
    if cursor is None:
        return ("inspector", "empty")
    return (
        "inspector",
        "cursor",
        cursor.kind,
        cursor.slot,
        cursor.card,
        cursor.effect_id,
        cursor.driver_slug,
        cursor.preset_index,
        cursor.marker_index,
    )


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
    entries: list[tuple[str, str]] = [("A", "toggle arm track")]

    if not recording:
        entries.append(("Shift + Enter", "toggle override"))
        if paused or override_active:
            entries.append((layer_keys, "toggle layer visibility"))

    if recording:
        entries.append((layer_keys, "toggle layer visibility"))
        entries.append((f"Ctrl + {layer_keys}", "drop cue (keep level)"))

    if recording:
        entries.append(("R", "stop record"))
        entries.append(("Ctrl + Space / Space", "stop record and pause"))
    else:
        entries.append(("Ctrl + Space / R", "start record"))
        if paused:
            entries.append(("Space", "play"))
        else:
            entries.append(("Space", "pause"))

    if recording:
        entries.append(("Left/Right", "skip 10s, fills range"))
    else:
        entries.extend(
            (
                ("Left/Right", "previous / next cue"),
                ("Enter", "seek to cue"),
            )
        )

    if not recording:
        entries.extend(
            (
                (", / .", "nudge cue opacity -/+ 1%"),
                ("Ctrl + , / .", "nudge cue opacity -/+ 10%"),
                ("B", "cycle cue blend"),
                ("C", "cycle cue cut type"),
                ("O", "cycle cue role"),
            )
        )

    entries.append(("Esc", "close timeline"))
    return HelpSection("Timeline", tuple(entries))


def _value_step_section(row_kind: RowKind) -> HelpSection:
    behavior = row_spec(row_kind)
    if behavior.help_entries is not None:
        return HelpSection(behavior.help_title or "Edit", behavior.help_entries)
    if row_kind == RowKind.TRACK_EFFECT:
        entries = (
            ("Left/Right", "adjust depth"),
            ("PgUp/PgDn", "large step"),
        )
    else:
        entries = _EDIT_SECTION.entries
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


def _keyboard_section(primary: HelpSection) -> HelpSection:
    return HelpSection(KEYBOARD_CONTROLS_SECTION_TITLE, primary.entries)


def sections_for(
    row_kind: RowKind,
    *,
    effect_id: str | None = None,
    timeline_enabled: bool = False,
    timeline_submenu_focused: bool = False,
    paused: bool = False,
    timeline_recording: bool = False,
    timeline_override_active: bool = False,
    preset_switching: str | None = None,
    preset_curation: bool = False,
    layer_count: int = 4,
) -> tuple[HelpContent, ...]:
    nav = navigation_section(preset_curation=preset_curation)
    if timeline_submenu_focused:
        strip = timeline_strip_section(
            paused=paused,
            recording=timeline_recording,
            override_active=timeline_override_active,
            layer_count=layer_count,
        )
        description = _description_section(RowKind.RENDER_TIMELINE_HEADER)
        if description is not None:
            return (description, _keyboard_section(strip), nav)
        return (strip, nav)

    behavior = row_spec(row_kind)

    if not behavior.navigable:
        return (nav,)
    if (
        behavior.affordance == RowAffordance.DISPLAY
        and behavior.help_description is None
    ):
        return (nav,)

    primary: HelpSection | None = None

    if behavior.affordance == RowAffordance.EXPAND:
        if behavior.is_sub_header:
            entries = behavior.help_entries
            primary = HelpSection(
                behavior.help_title or "Edit",
                entries if entries is not None else (("Left/Right", "expand/collapse"),),
            )
        elif behavior.can_enter_move_mode:
            section = layer_section(
                timeline_enabled=timeline_enabled,
                preset_curation=preset_curation,
                layer_count=layer_count,
                layer_jumps=not timeline_recording,
            )
            if not section.entries:
                description = _description_section(row_kind, effect_id=effect_id)
                if description is not None:
                    return (description, nav)
                return (nav,)
            primary = section
        elif (
            behavior.toggle_enabled is not None and behavior.toggle_solo is not None
        ):
            primary = _RENDER_SECTION
        elif behavior.toggle_enabled is not None:
            primary = _RENDER_TIMELINE_SECTION
        elif behavior.is_header:
            primary = HelpSection(
                behavior.help_title or "Settings",
                (("Left/Right", "expand/collapse"),),
            )
    elif behavior.affordance == RowAffordance.VALUE_STEP:
        primary = _value_step_section(row_kind)
    elif row_kind == RowKind.TRACK_PRESET_LIST_ITEM:
        primary = _PRESET_LIST_ITEM_SECTION
    elif row_kind == RowKind.TRACK_PRESET_LIST_ADD:
        primary = _PRESET_LIST_ADD_SECTION
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
            (("Enter", "confirm add"),),
        )
    elif row_kind == RowKind.LAYER_MANAGEMENT_DELETE:
        primary = HelpSection(
            behavior.help_title or "Delete layer",
            (("Enter/Delete", "confirm delete"),),
        )
    elif behavior.affordance == RowAffordance.ACTION:
        primary = HelpSection(
            behavior.help_title or "Edit",
            behavior.help_entries or (),
        )
    elif behavior.affordance == RowAffordance.DISPLAY:
        entries = behavior.help_entries
        if entries is None:
            description = _description_section(row_kind, effect_id=effect_id)
            if description is not None:
                return (description, nav)
            return (nav,)
        primary = HelpSection(
            behavior.help_title or "Edit",
            entries,
        )

    if primary is None:
        return (nav,)

    description = _description_section(row_kind, effect_id=effect_id)
    if description is not None:
        return (description, _keyboard_section(primary), nav)
    return (primary, nav)


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
    """Sections for the shell row, or for *focus* when the panel or timeline has scope."""
    described = help_focus_descriptor(
        focus,
        shell_focus,
        timeline_focused=timeline_submenu_focused,
    )
    if described is None:
        return (navigation_section(preset_curation=preset_curation),)
    return sections_for(
        described.kind,
        effect_id=described.effect_id,
        timeline_enabled=timeline_enabled,
        timeline_submenu_focused=timeline_submenu_focused,
        paused=paused,
        timeline_recording=timeline_recording,
        timeline_override_active=timeline_override_active,
        preset_switching=preset_switching,
        preset_curation=preset_curation,
        layer_count=layer_count,
    )
