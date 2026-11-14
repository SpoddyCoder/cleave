"""Hover tooltips, gated by the Settings > UI > tooltips preference.

Every editor tooltip goes through ``show_tooltip`` so the one switch hides them all.
"""

from __future__ import annotations

from cleave.config_schema.editor import DEFAULT_SHOW_TOOLTIPS

_enabled: bool = DEFAULT_SHOW_TOOLTIPS


def set_tooltips_enabled(on: bool) -> None:
    global _enabled
    _enabled = bool(on)


def tooltips_enabled() -> bool:
    return _enabled


def show_tooltip(text: str) -> None:
    """Show *text* as a tooltip for this frame, unless tooltips are off."""
    if not (_enabled and text):
        return
    # Imported here: imgui_bundle pulls in matplotlib, which the play path
    # must not load before the window opens.
    from imgui_bundle import imgui

    imgui.set_tooltip(text)
