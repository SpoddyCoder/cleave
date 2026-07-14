"""Help panel section data and dispatch for the Cleave editor."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.row_semantics import RowAffordance, RowKind, row_behavior

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

NAVIGATION_SECTION = HelpSection(
    "Navigation / Global",
    (
        ("Up/Down", "move row"),
        ("Ctrl + Up/Down", "jump section"),
        ("ESC", "hide UI"),
        ("Ctrl + Q", "quit"),
        ("Ctrl + S", "save config"),
        ("Ctrl + Enter", "place song marker"),
    ),
)

_CURATION_NAVIGATION_SECTION = HelpSection(
    "Navigation / Global",
    (
        ("Up/Down", "move row"),
        ("Ctrl + Up/Down", "jump section"),
        ("ESC", "hide UI"),
        ("Ctrl + Q", "quit"),
    ),
)


def navigation_section(*, preset_curation: bool = False) -> HelpSection:
    if preset_curation:
        return _CURATION_NAVIGATION_SECTION
    return NAVIGATION_SECTION

_TRANSPORT_SECTION = HelpSection(
    "Transport Controls",
    (
        ("Enter", "play/pause"),
        ("Left/Right", "skip 10s"),
        ("Shift + Left/Right", "skip 2s"),
        ("Ctrl + Left/Right", "skip 30s"),
    ),
)

_LAYER_SECTION_BASE: tuple[tuple[str, str], ...] = (
    ("m", "move z-order"),
    ("l", "lock/unlock layer"),
    ("Shift + Left/Right", "solo layer"),
    ("Left/Right", "expand/collapse"),
    ("Delete", "delete layer"),
)

_LAYER_VISIBILITY_ENTRY = ("Ctrl + Left/Right", "enable/disable layer")

_CURATION_LAYER_SECTION = HelpSection(
    "Layer",
    (("Left/Right", "expand/collapse"),),
)


def layer_section(
    *, timeline_enabled: bool, preset_curation: bool = False
) -> HelpSection:
    if preset_curation:
        return _CURATION_LAYER_SECTION
    entries = list(_LAYER_SECTION_BASE)
    if not timeline_enabled:
        entries.append(_LAYER_VISIBILITY_ENTRY)
    return HelpSection("Layer", tuple(entries))


_EDIT_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "adjust value"),
        ("Ctrl + Left/Right", "large step"),
    ),
)

_PRESET_DIR_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous directory"),
        ("Ctrl + Left/Right", "up/down directory tree"),
    ),
)

_PRESET_CURATION_SHORTCUTS = (
    ("f", "favourite preset"),
    ("b", "blacklist preset"),
)

_PRESET_SECTION = HelpSection(
    "Edit",
    (
        ("Left/Right", "next/previous preset"),
        ("Ctrl + Left/Right", "next/previous large step"),
        *_PRESET_CURATION_SHORTCUTS,
    ),
)

_USER_PRESET_ADD_SHORTCUT = ("+", "add current preset to rotation set")

_USER_PRESET_ITEM_SECTION = HelpSection(
    "Edit",
    (
        ("Delete", "remove preset"),
        *_PRESET_CURATION_SHORTCUTS,
    ),
)

_USER_PRESET_ADD_SECTION = HelpSection(
    "Add Current Preset",
    (("Enter", "add current preset"),),
)


def _preset_dir_section(*, user_defined: bool = False) -> HelpSection:
    entries = list(_PRESET_DIR_SECTION.entries)
    if user_defined:
        entries.append(_USER_PRESET_ADD_SHORTCUT)
    return HelpSection(_PRESET_DIR_SECTION.title, tuple(entries))


def _preset_section(*, user_defined: bool = False) -> HelpSection:
    entries = list(_PRESET_SECTION.entries)
    if user_defined:
        entries.append(_USER_PRESET_ADD_SHORTCUT)
    return HelpSection(_PRESET_SECTION.title, tuple(entries))

_RENDER_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("Ctrl + Left/Right", "enable/disable"),
        ("Shift + Left/Right", "always on"),
    ),
)

_RENDER_TIMELINE_SECTION = HelpSection(
    "Render",
    (
        ("Left/Right", "expand/collapse"),
        ("Ctrl + Left/Right", "enable/disable"),
    ),
)


def timeline_strip_section(
    *,
    paused: bool,
    recording: bool,
    override_active: bool,
) -> HelpSection:
    entries: list[tuple[str, str]] = [("a", "toggle arm track")]

    if not recording:
        entries.append(("Shift + Enter", "toggle override"))
        if paused or override_active:
            entries.append(("1-4", "toggle layer visibility"))

    if recording:
        entries.append(("1-4", "toggle layer visibility"))

    if recording:
        entries.append(("r", "stop record"))
        entries.append(("Ctrl + Space / Space", "stop record and pause"))
    else:
        entries.append(("Ctrl + Space / r", "start record"))
        if paused:
            entries.append(("Space", "play"))
        else:
            entries.append(("Space", "pause"))

    if recording:
        entries.extend(
            (
                ("Left/Right", "skip 10s, fills range"),
                ("Shift + Left/Right", "skip 2s, fills range"),
                ("Ctrl + Left/Right", "skip 30s, fills range"),
            )
        )
    else:
        entries.extend(
            (
                ("Left/Right", "skip 10s"),
                ("Shift + Left/Right", "skip 2s"),
                ("Ctrl + Left/Right", "skip 30s"),
            )
        )

    entries.append(("Esc", "close timeline"))
    return HelpSection("Timeline", tuple(entries))


_SAVE_SECTION = HelpSection(
    "Save",
    (
        ("Enter", "save config"),
        ("Ctrl + S", "save config"),
    ),
)


def _value_step_section(row_kind: RowKind) -> HelpSection:
    behavior = row_behavior(row_kind)
    if behavior.help_entries is not None:
        return HelpSection(behavior.help_title or "Edit", behavior.help_entries)
    if row_kind == RowKind.TRACK_EFFECT:
        entries = (
            ("Left/Right", "adjust depth"),
            ("Ctrl + Left/Right", "large step"),
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

    behavior = row_behavior(row_kind)
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
) -> tuple[HelpContent, ...]:
    nav = navigation_section(preset_curation=preset_curation)
    if timeline_submenu_focused:
        strip = timeline_strip_section(
            paused=paused,
            recording=timeline_recording,
            override_active=timeline_override_active,
        )
        description = _description_section(RowKind.RENDER_TIMELINE_HEADER)
        if description is not None:
            return (description, _keyboard_section(strip), nav)
        return (strip, nav)

    behavior = row_behavior(row_kind)

    if not behavior.navigable or behavior.affordance == RowAffordance.DISPLAY:
        return (nav,)

    primary: HelpSection | None = None

    if behavior.affordance == RowAffordance.EXPAND:
        if behavior.is_sub_header:
            primary = HelpSection(
                behavior.help_title or "Edit",
                (("Left/Right", "expand/collapse"),),
            )
        elif behavior.can_enter_move_mode:
            primary = layer_section(
                timeline_enabled=timeline_enabled,
                preset_curation=preset_curation,
            )
        elif behavior.can_enable_disable and behavior.can_solo:
            primary = _RENDER_SECTION
        elif behavior.can_enable_disable:
            primary = _RENDER_TIMELINE_SECTION
        elif behavior.is_header:
            primary = HelpSection(
                behavior.help_title or "Editor Settings",
                (("Left/Right", "expand/collapse"),),
            )
    elif behavior.affordance == RowAffordance.VALUE_STEP:
        primary = _value_step_section(row_kind)
    elif behavior.affordance == RowAffordance.ACTION_PARAMETER:
        primary = _value_step_section(row_kind)
    elif row_kind == RowKind.TRACK_USER_PRESET_ITEM:
        primary = _USER_PRESET_ITEM_SECTION
    elif row_kind == RowKind.TRACK_USER_PRESET_ADD:
        primary = _USER_PRESET_ADD_SECTION
    elif behavior.affordance == RowAffordance.PATH_DIR:
        primary = _preset_dir_section(
            user_defined=preset_switching == "user_defined"
        )
    elif behavior.affordance == RowAffordance.PATH_PRESET:
        primary = _preset_section(
            user_defined=preset_switching == "user_defined"
        )
    elif behavior.affordance == RowAffordance.SEEK:
        primary = _TRANSPORT_SECTION
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
        if behavior.help_entries is not None:
            primary = HelpSection(
                behavior.help_title or "Edit",
                behavior.help_entries,
            )
        else:
            primary = _SAVE_SECTION

    if primary is None:
        return (nav,)

    description = _description_section(row_kind, effect_id=effect_id)
    if description is not None:
        return (description, _keyboard_section(primary), nav)
    return (primary, nav)
