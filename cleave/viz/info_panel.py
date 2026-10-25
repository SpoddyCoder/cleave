"""Read-only copy for a centred info panel. No pygame or ImGui."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InfoPanelViewState:
    title_lines: tuple[str, ...]
    body_lines: tuple[str, ...]
    footer_line: str | None = None
