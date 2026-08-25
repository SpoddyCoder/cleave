"""Descriptor-driven YAML parse and dump engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

@dataclass(frozen=True)
class FieldDescriptor:
    """Leaf field: YAML key, default, parse, and dump."""

    yaml_key: str
    default: Any
    parse: Callable[[Any, "ParseCtx", str], Any]
    dump: Callable[[Any, "PersistCtx"], Any]
    yaml_alt_keys: tuple[str, ...] = ()
    attr_key: str | None = None
    omit_when: Callable[[Any], bool] | None = None

    @property
    def key(self) -> str:
        if self.attr_key is not None:
            return self.attr_key
        return self.yaml_key.replace("-", "_")


@dataclass(frozen=True)
class SectionDescriptor:
    """Nested YAML section built from child field and section descriptors."""

    yaml_key: str
    fields: tuple["SchemaField", ...]
    build: Callable[[dict[str, Any]], Any]
    optional: bool = False
    default_factory: Callable[[], Any] | None = None
    attr_key: str | None = None

    @property
    def key(self) -> str:
        if self.attr_key is not None:
            return self.attr_key
        return self.yaml_key.replace("-", "_")


SchemaField = FieldDescriptor | SectionDescriptor


@dataclass
class ParseCtx:
    preset_root: Path | None = None
    layer_slots: tuple[str, ...] | None = None
    cfg_dir: Path | None = None


@dataclass
class PersistCtx:
    cfg: Any
    session: Any
    cfg_dir: Path | None = None


def as_mapping(data: Any, label: str) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a mapping")
    return data


def parse_hex_colour(value: Any, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    raw = value.strip()
    if not raw.startswith("#"):
        raise ValueError(f"{label} must be a hex colour starting with #")
    digits = raw[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    elif len(digits) != 6:
        raise ValueError(f"{label} must be #rgb or #rrggbb")
    try:
        return (
            int(digits[0:2], 16),
            int(digits[2:4], 16),
            int(digits[4:6], 16),
        )
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid hex colour") from exc


def require_non_negative_number(
    value: Any, label: str, *, as_int: bool = False
) -> float | int:
    try:
        number = int(value) if as_int else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if number < 0:
        raise ValueError(f"{label} must be non-negative")
    return number


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def parse_scalar(raw: Any, ctx: ParseCtx, label: str) -> Any:
    return raw


def dump_scalar(value: Any, ctx: PersistCtx) -> Any:
    return value


def dump_hex_colour(value: tuple[int, int, int], ctx: PersistCtx) -> str:
    return rgb_to_hex(value)


def parse_non_negative_int(raw: Any, ctx: ParseCtx, label: str) -> int:
    return int(require_non_negative_number(raw, label, as_int=True))


def parse_non_negative_float(raw: Any, ctx: ParseCtx, label: str) -> float:
    return float(require_non_negative_number(raw, label))


def parse_field(
    parent: dict[str, Any],
    field: FieldDescriptor,
    ctx: ParseCtx,
    label: str,
) -> Any:
    raw = parent.get(field.yaml_key)
    if raw is None:
        for alt in field.yaml_alt_keys:
            raw = parent.get(alt)
            if raw is not None:
                break
    if raw is None:
        return field.default
    return field.parse(raw, ctx, f"{label}.{field.yaml_key}")


def dump_field(
    field: FieldDescriptor,
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    value = values[field.key]
    if field.omit_when is not None and field.omit_when(value):
        return {}
    return {field.yaml_key: field.dump(value, ctx)}


def dump_fields(
    fields: tuple[FieldDescriptor, ...],
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        out.update(dump_field(field, values, ctx))
    return out


def parse_section(
    parent: dict[str, Any],
    section: SectionDescriptor,
    ctx: ParseCtx,
    label: str,
) -> Any:
    if section.optional and parent.get(section.yaml_key) is None:
        if section.default_factory is None:
            raise ValueError(f"{label}.{section.yaml_key} missing default_factory")
        return section.default_factory()
    section_map = as_mapping(
        parent.get(section.yaml_key),
        f"{label}.{section.yaml_key}",
    )
    parsed: dict[str, Any] = {}
    for field in section.fields:
        if isinstance(field, SectionDescriptor):
            parsed[field.key] = parse_section(
                section_map, field, ctx, f"{label}.{section.yaml_key}"
            )
        else:
            parsed[field.key] = parse_field(
                section_map, field, ctx, f"{label}.{section.yaml_key}"
            )
    return section.build(parsed)


def dump_section(
    section: SectionDescriptor,
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    section_values = values[section.key]
    out: dict[str, Any] = {}
    for field in section.fields:
        if isinstance(field, SectionDescriptor):
            out[field.yaml_key] = dump_section(field, section_values, ctx)
        else:
            out.update(dump_field(field, section_values, ctx))
    return out


def section_field_defaults(section: SectionDescriptor) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in section.fields:
        if isinstance(field, SectionDescriptor):
            out[field.key] = section_field_defaults(field)
        else:
            out[field.key] = field.default
    return out


def parse_section_fields(
    parent: dict[str, Any],
    fields: tuple[SchemaField, ...],
    ctx: ParseCtx,
    label: str,
) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for field in fields:
        if isinstance(field, SectionDescriptor):
            parsed[field.key] = parse_section(parent, field, ctx, label)
        else:
            parsed[field.key] = parse_field(parent, field, ctx, label)
    return parsed


def dump_section_fields(
    fields: tuple[SchemaField, ...],
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        if isinstance(field, SectionDescriptor):
            out[field.yaml_key] = dump_section(field, values, ctx)
        else:
            out.update(dump_field(field, values, ctx))
    return out
