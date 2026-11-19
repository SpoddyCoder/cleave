"""Write the Windows icon (``packaging/windows/cleave.ico``) from the C mark.

The mark (``assets/cleave-logo-square.png``) is taller than it is wide, so
each icon size centres it on a transparent square. Run after the artwork
changes and commit the result; the freeze and the installer read the file.

    python scripts/make_windows_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
MARK = REPO / "assets" / "cleave-logo-square.png"
ICON = REPO / "packaging" / "windows" / "cleave.ico"
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


if __name__ == "__main__":
    write_icon()
    print(ICON.relative_to(REPO))
