"""Tests for hex colour text-modal validation helpers."""

from __future__ import annotations

import pytest

from cleave.viz.colour_parse import (
    parse_hex_colour_or_none,
    validate_hex_colour,
    validate_optional_hex_colour,
)

_INVALID = "invalid hex colour (use #rgb or #rrggbb)"


def test_validate_hex_colour_short_ok() -> None:
    assert validate_hex_colour("#fff") is None
    assert validate_optional_hex_colour("#fff") is None
    assert parse_hex_colour_or_none("#fff") == (255, 255, 255)


def test_validate_hex_colour_long_ok() -> None:
    assert validate_hex_colour("#aabbcc") is None
    assert validate_optional_hex_colour("#aabbcc") is None
    assert parse_hex_colour_or_none("#aabbcc") == (170, 187, 204)


def test_validate_hex_colour_bad_digits() -> None:
    assert validate_hex_colour("#gg0000") == _INVALID
    assert validate_optional_hex_colour("#gg0000") == _INVALID
    with pytest.raises(ValueError):
        parse_hex_colour_or_none("#gg0000")


def test_validate_hex_colour_missing_hash() -> None:
    assert validate_hex_colour("fff") == _INVALID
    assert validate_hex_colour("aabbcc") == _INVALID
    with pytest.raises(ValueError):
        parse_hex_colour_or_none("fff")


def test_empty_string_required_vs_optional() -> None:
    assert validate_hex_colour("") == _INVALID
    assert validate_optional_hex_colour("") is None
    assert parse_hex_colour_or_none("") is None
