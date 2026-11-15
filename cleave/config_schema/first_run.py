"""First-run state in the user config: whether the welcome step was completed.

The welcome step owns this section. Missing presets bring the step back on
every launch; missing model weights bring it back only until it is completed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cleave.config_schema.descriptors import (
    FieldDescriptor,
    ParseCtx,
    PersistCtx,
    as_mapping,
    dump_fields,
    dump_scalar,
    parse_field,
)

FIRST_RUN_SECTION_KEY = "first_run"

DEFAULT_WELCOME_DONE = False


@dataclass(frozen=True)
class FirstRunState:
    """``welcome_done`` is True once the user downloaded or skipped in the step."""

    welcome_done: bool = DEFAULT_WELCOME_DONE


def _parse_bool(raw: Any, _ctx: ParseCtx, label: str) -> bool:
    if not isinstance(raw, bool):
        raise ValueError(f"{label} must be true or false")
    return raw


FIRST_RUN_FIELDS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor(
        "welcome_done",
        DEFAULT_WELCOME_DONE,
        _parse_bool,
        dump_scalar,
    ),
)


def parse_first_run_section(data: dict[str, Any]) -> FirstRunState:
    section = as_mapping(data.get(FIRST_RUN_SECTION_KEY), FIRST_RUN_SECTION_KEY)
    ctx = ParseCtx()
    parsed = {
        field.yaml_key: parse_field(section, field, ctx, FIRST_RUN_SECTION_KEY)
        for field in FIRST_RUN_FIELDS
    }
    return FirstRunState(welcome_done=parsed["welcome_done"])


def dump_first_run_section(state: FirstRunState) -> dict[str, Any]:
    values = {"welcome_done": state.welcome_done}
    return dump_fields(FIRST_RUN_FIELDS, values, PersistCtx(cfg=None, session=None))
