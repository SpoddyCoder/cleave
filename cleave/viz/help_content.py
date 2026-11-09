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
    from cleave.viz.tuning_view_state import TuningViewState

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
    "cycle Menu, Navigator, Inspector, and Timeline; "
    "Timeline only while the strip is open",
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
        ("Ctrl + N", "new project"),
        ("Ctrl + O", "open project"),
        ("Ctrl + S", "save"),
        ("Ctrl + Enter", "place song marker"),
        ("F10 / Alt", "focus menu bar"),
        ("Alt + underlined letter", "open that menu (F, P, L, R, T, S, H)"),
        ("Ctrl + R", "render"),
        ("Ctrl + ,", "open Settings > Preview"),
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
        ("Alt + underlined letter", "open that menu (F, P, L, R, T, S, H)"),
    ),
)


def navigation_section(*, preset_curation: bool = False) -> HelpSection:
    if preset_curation:
        return _CURATION_NAVIGATION_SECTION
    return NAVIGATION_SECTION


_NAVIGATOR_SECTION = HelpSection(
    "Navigator",
    (
        ("Up/Down", "move across nodes"),
        ("Left/Right", "expand/collapse"),
        ("Ctrl + Up/Down", "previous / next top-level navigator node"),
    ),
)


_LAYER_SECTION_BASE: tuple[tuple[str, str], ...] = (
    ("M", "move z-order"),
    ("Drag handle", "move z-order with the mouse"),
    ("L", "lock/unlock layer"),
    ("S", "solo layer"),
    ("Delete", "delete layer"),
)

_LAYER_VISIBILITY_ENTRY = ("E", "enable/disable layer")
_LAYER_ADD_ENTRY = ("Ctrl + L", "add layer")
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
    "layers.add_current_preset": RowKind.TRACK_PRESET_LIST_ADD,
    "layers.populate_presets": RowKind.TRACK_PRESET_LIST_POPULATE,
    "layers.resume_switching": RowKind.TRACK_PRESET_SWITCHING_RESUME,
    "timeline.generate": RowKind.TIMELINE_GENERATE,
    "timeline.reset": RowKind.TIMELINE_RESET,
    "timeline.snap_cues": RowKind.TIMELINE_SNAP_CUES,
    "timeline.snap_to_markers": RowKind.TIMELINE_SNAP_CUES,
    "timeline.set_cut_type": RowKind.TIMELINE_SET_CUT_TYPE,
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
        ("Drag handle", "reorder with the mouse"),
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

def _heading_section(behavior: RowSpec) -> HelpSection | None:
    """Keys for a navigator page, or None when it has only a description."""
    entries: list[tuple[str, str]] = []
    if behavior.toggle_enabled is not None:
        entries.append(("E", "enable/disable"))
    if behavior.toggle_solo is not None:
        entries.append(("S", "always on"))
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
        entries.append(("Click/Drag ruler", "seek / scrub, fills range"))
        entries.append(("Dbl-click row", "seek, fills range"))
    else:
        entries.extend(
            (
                ("Left/Right", "previous / next cue"),
                ("Enter", "seek to cue"),
                ("Click row", "select row / cue"),
                ("Dbl-click row", "seek, hold to scrub"),
                ("Click/Drag ruler", "seek / scrub"),
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
        entries = behavior.help_entries
        if row_choice_kind(row_kind) is ChoiceKind.COMBO:
            entries = (*entries, ("Enter", "open the list"))
        return HelpSection(behavior.help_title or "Edit", entries)
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
    timeline_recording: bool = False,
    preset_switching: str | None = None,
    preset_curation: bool = False,
    layer_count: int = 4,
) -> tuple[HelpContent, ...]:
    """Description and keyboard sections for one row. No global navigation."""
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
            (("Enter", "add layer"),),
        )
    elif row_kind == RowKind.LAYER_MANAGEMENT_DELETE:
        primary = HelpSection(
            behavior.help_title or "Delete layer",
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
        return (description, _keyboard_section(primary))
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
        return (_NAVIGATOR_SECTION, *row_sections)
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
