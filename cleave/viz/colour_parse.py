"""Hex colour helpers for text-modal validation."""

from __future__ import annotations

from cleave.config_schema.descriptors import parse_hex_colour

_INVALID_HEX_COLOUR = "invalid hex colour (use #rgb or #rrggbb)"


def validate_hex_colour(draft: str) -> str | None:
    try:
        parse_hex_colour(draft, "colour")
    except ValueError:
        return _INVALID_HEX_COLOUR
    return None


def validate_optional_hex_colour(draft: str) -> str | None:
    if draft.strip() == "":
        return None
    return validate_hex_colour(draft)


def parse_hex_colour_or_none(draft: str) -> tuple[int, int, int] | None:
    if draft.strip() == "":
        return None
    return parse_hex_colour(draft, "colour")
