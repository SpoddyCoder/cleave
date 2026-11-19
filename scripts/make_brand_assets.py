"""Write the logo files built from the artwork in ``assets/``.

- ``packaging/windows/cleave.ico``: the C mark (``assets/cleave-logo-square.png``),
  which is taller than it is wide, centred on a transparent square at each icon
  size. The freeze and the installer read it.
- ``assets/cleave-logo-full-dark.png``: the full logo with the navy lettering
  white and the navy bars indigo, the same colours the editor draws on a dark
  theme. The README shows it to readers in GitHub's dark mode.

Run after the artwork changes and commit the results.

    python scripts/make_brand_assets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
MARK = REPO / "assets" / "cleave-logo-square.png"
ICON = REPO / "packaging" / "windows" / "cleave.ico"
DARK_LOGO = REPO / "assets" / "cleave-logo-full-dark.png"
# Every size Explorer, the taskbar, and Start pick from.
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def icon_frame(mark: Image.Image, edge: int) -> Image.Image:
    """*mark* scaled to fit an *edge* square and centred on transparency."""
    scale = edge / max(mark.size)
    size = (max(1, round(mark.width * scale)), max(1, round(mark.height * scale)))
    scaled = mark.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    frame = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
    frame.paste(scaled, ((edge - size[0]) // 2, (edge - size[1]) // 2))
    return frame


def write_icon(mark_path: Path = MARK, icon_path: Path = ICON) -> None:
    with Image.open(mark_path) as source:
        mark = source.convert("RGBA")
    frames = [icon_frame(mark, edge) for edge in SIZES]
    largest = frames[-1]
    largest.save(
        icon_path,
        format="ICO",
        sizes=[frame.size for frame in frames],
        append_images=frames[:-1],
    )


def write_dark_logo(path: Path = DARK_LOGO) -> None:
    sys.path.insert(0, str(REPO))
    from cleave.viz.brand import Logo, logo_image

    with Image.open(REPO / "assets" / Logo.FULL.value) as source:
        size = source.size
    logo_image(Logo.FULL, size, reversed_ink=True).save(path, optimize=True)


if __name__ == "__main__":
    write_icon()
    write_dark_logo()
    print(ICON.relative_to(REPO))
    print(DARK_LOGO.relative_to(REPO))
