"""User theme files: one YAML file per theme in the data folder's ``themes/``.

A file names a built-in theme as its ``base`` (Ultraviolet when left out), an
optional display ``name``, and then any ``Palette`` roles to override, each at
the top level::

    name: Midnight
    base: ultraviolet
    label: "#a0b0ff"
    hover: [128, 84, 255]
    hover_bg_alpha: 60

The theme's id is the file name without its extension, in lower case. A file
that cannot be read, or names an unknown base, is skipped. An unknown role or a
bad value is left at the base's value. Each of these is a problem the editor
shows in the window.
"""

from __future__ import annotations

import dataclasses
import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cleave.viz.theme import (
    BUILTIN_PALETTES,
    ULTRAVIOLET,
    Palette,
    RGB,
    set_user_palettes,
)

THEME_FILE_SUFFIXES: tuple[str, ...] = (".yaml", ".yml")
# Keys a theme file sets that are not colour roles.
_NAME_KEY = "name"
_BASE_KEY = "base"
# Palette fields a theme file cannot set: the id comes from the file name.
_FIXED_FIELDS = frozenset({"id", "name"})
_MAX_TRACK_COLOURS = 8
# Number roles that may be negative (-1 to 1): a negative amount darkens.
_SIGNED_FIELDS = frozenset({"icon_lit_hover_lift", "icon_lit_hover_edge_lift"})


@dataclass(frozen=True)
class UserThemes:
    """Palettes read from theme files, and what was wrong with them."""

    palettes: tuple[Palette, ...]
    problems: tuple[str, ...]


def theme_roles() -> tuple[str, ...]:
    """Every role a theme file may set, in ``Palette`` order."""
    return tuple(
        field.name
        for field in dataclasses.fields(Palette)
        if field.name not in _FIXED_FIELDS
    )


def load_user_themes(folder: Path) -> UserThemes:
    """Read every theme file in *folder*. A missing folder has no themes."""
    if not folder.is_dir():
        return UserThemes((), ())
    try:
        paths = sorted(
            (
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in THEME_FILE_SUFFIXES
            ),
            key=lambda path: path.name.casefold(),
        )
    except OSError as exc:
        return UserThemes((), (f"Could not read the themes folder: {exc}",))
    builtin_ids = {candidate.id for candidate in BUILTIN_PALETTES}
    palettes: list[Palette] = []
    problems: list[str] = []
    taken: dict[str, str] = {}
    for path in paths:
        theme_id = path.stem.casefold()
        if theme_id in builtin_ids:
            problems.append(
                f"{path.name}: a built-in theme already uses the name '{theme_id}'; "
                "rename the file"
            )
            continue
        if theme_id in taken:
            problems.append(
                f"{path.name}: {taken[theme_id]} already uses the name '{theme_id}'; "
                "rename one of them"
            )
            continue
        file_problems: list[str] = []
        loaded = _load_theme_file(path, theme_id, file_problems)
        problems.extend(f"{path.name}: {problem}" for problem in file_problems)
        if loaded is not None:
            taken[theme_id] = path.name
            palettes.append(loaded)
    return UserThemes(tuple(palettes), tuple(problems))


def install_user_themes(folder: Path) -> tuple[str, ...]:
    """Load *folder*'s theme files into the Theme setting; return the problems."""
    loaded = load_user_themes(folder)
    set_user_palettes(loaded.palettes)
    return loaded.problems


def _load_theme_file(
    path: Path, theme_id: str, problems: list[str]
) -> Palette | None:
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        problems.append(f"could not read the file ({exc.strerror or exc})")
        return None
    except UnicodeDecodeError:
        problems.append("the file is not UTF-8 text")
        return None
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" on line {mark.line + 1}" if mark is not None else ""
        problems.append(f"the file is not valid YAML{where}")
        return None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        problems.append("the file must list roles as 'role: value' lines")
        return None
    return _theme_from_mapping(data, theme_id, problems)


def _theme_from_mapping(
    data: dict[Any, Any], theme_id: str, problems: list[str]
) -> Palette | None:
    base_id = data.get(_BASE_KEY, ULTRAVIOLET.id)
    base = next(
        (candidate for candidate in BUILTIN_PALETTES if candidate.id == base_id),
        None,
    )
    if base is None:
        choices = ", ".join(candidate.id for candidate in BUILTIN_PALETTES)
        problems.append(f"unknown base theme '{base_id}' (choose from: {choices})")
        return None
    name = data.get(_NAME_KEY, theme_id)
    if not isinstance(name, str) or not name.strip():
        problems.append("name must be text")
        name = theme_id
    field_types = {
        field.name: str(field.type)
        for field in dataclasses.fields(Palette)
        if field.name not in _FIXED_FIELDS
    }
    overrides: dict[str, Any] = {}
    for key, raw in data.items():
        if key in (_NAME_KEY, _BASE_KEY):
            continue
        role = str(key)
        field_type = field_types.get(role)
        if field_type is None:
            problems.append(_unknown_role(role, field_types))
            continue
        try:
            overrides[role] = _parse_value(role, field_type, raw)
        except ValueError as exc:
            problems.append(f"{role}: {exc}")
    return dataclasses.replace(
        base, id=theme_id, name=name.strip(), **overrides
    )


def _unknown_role(role: str, known: dict[str, str]) -> str:
    close = difflib.get_close_matches(role, list(known), n=1)
    if close:
        return f"unknown role '{role}' (did you mean '{close[0]}'?)"
    return f"unknown role '{role}'"


def _parse_value(role: str, field_type: str, raw: Any) -> Any:
    if field_type == "RGB":
        return parse_colour(raw)
    if field_type == "int":
        return _parse_alpha(raw)
    if field_type == "float":
        return _parse_signed(raw) if role in _SIGNED_FIELDS else _parse_fraction(raw)
    if field_type == "tuple[float, float]":
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError("must be two numbers from 0 to 1, like [0.3, 0.06]")
        return (_parse_fraction(raw[0]), _parse_fraction(raw[1]))
    if field_type == "tuple[RGB, ...]":
        if not isinstance(raw, list) or not 1 <= len(raw) <= _MAX_TRACK_COLOURS:
            raise ValueError(
                f"must be a list of 1 to {_MAX_TRACK_COLOURS} colours"
            )
        return tuple(parse_colour(item) for item in raw)
    raise ValueError("cannot be set in a theme file")


def parse_colour(raw: Any) -> RGB:
    """A colour from ``"#rrggbb"`` or ``[r, g, b]`` (each 0 to 255)."""
    if isinstance(raw, str):
        text = raw.strip()
        digits = text[1:] if text.startswith("#") else text
        if len(digits) == 6:
            try:
                value = int(digits, 16)
            except ValueError:
                pass
            else:
                return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
    elif isinstance(raw, list) and len(raw) == 3:
        if all(_is_int(part) and 0 <= part <= 255 for part in raw):
            return (int(raw[0]), int(raw[1]), int(raw[2]))
    if raw is None:
        raise ValueError(
            'has no value; put a hex colour in quotes, like "#a0b0ff"'
        )
    raise ValueError(
        'must be a colour, like "#a0b0ff" in quotes or [160, 176, 255]'
    )


def _parse_alpha(raw: Any) -> int:
    if _is_int(raw) and 0 <= raw <= 255:
        return int(raw)
    raise ValueError("must be a whole number from 0 to 255")


def _parse_fraction(raw: Any) -> float:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and 0 <= raw <= 1:
        return float(raw)
    raise ValueError("must be a number from 0 to 1")


def _parse_signed(raw: Any) -> float:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and -1 <= raw <= 1:
        return float(raw)
    raise ValueError("must be a number from -1 to 1")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
