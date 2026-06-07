#!/usr/bin/env python3
"""Preview drawn transport icons without launching the visualizer.

Renders playing and paused transport rows at overlay line height, saves
magnified PNG previews, and prints surface dimensions and opaque pixel counts.

Usage:
    python scripts/transport_icon_probe.py
    python scripts/transport_icon_probe.py --out /tmp/transport-icons
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cleave.viz_transport_icons import render_transport_icons

_LINE_HEIGHT = 17
_COLOR = (255, 255, 255)
_MAGNIFY = 4
_BG = (40, 40, 40, 255)


def _opaque_count(surf: pygame.Surface) -> int:
    return pygame.mask.from_surface(surf).count()


def _preview_png(icon_surf: pygame.Surface, scale: int = _MAGNIFY) -> pygame.Surface:
    magnified = pygame.transform.scale(
        icon_surf,
        (icon_surf.get_width() * scale, icon_surf.get_height() * scale),
    )
    out = pygame.Surface(
        (magnified.get_width() + 20, icon_surf.get_height() + magnified.get_height() + 20),
        pygame.SRCALPHA,
    )
    out.fill(_BG)
    out.blit(icon_surf, (10, 10))
    out.blit(magnified, (10, icon_surf.get_height() + 10))
    return out


def _magnified_png(icon_surf: pygame.Surface, scale: int = _MAGNIFY) -> pygame.Surface:
    big = pygame.transform.scale(
        icon_surf,
        (icon_surf.get_width() * scale, icon_surf.get_height() * scale),
    )
    out = pygame.Surface((big.get_width() + 20, big.get_height() + 20), pygame.SRCALPHA)
    out.fill(_BG)
    out.blit(big, (10, 10))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("transport-icon-probe"),
        help="Directory for PNG previews (default: ./transport-icon-probe)",
    )
    args = parser.parse_args()
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    pygame.init()

    playing = render_transport_icons(color=_COLOR, line_height=_LINE_HEIGHT, paused=False)
    paused = render_transport_icons(color=_COLOR, line_height=_LINE_HEIGHT, paused=True)

    for label, surf in (("playing", playing), ("paused", paused)):
        w, h = surf.get_size()
        print(f"{label}: size={w}x{h} opaque={_opaque_count(surf)}")

    pygame.image.save(_preview_png(playing), out_dir / "row-playing.png")
    pygame.image.save(_preview_png(paused), out_dir / "row-paused.png")
    pygame.image.save(_magnified_png(playing), out_dir / "playing.png")
    pygame.image.save(_magnified_png(paused), out_dir / "paused.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
