"""Cleave logo artwork: the files, a theme-matched ink, GL textures, and drawing.

Two logos ship in ``assets/``: the full wordmark (``Logo.FULL``) and the C mark
(``Logo.MARK``). Each draws at exactly the pixel size asked for: the artwork is
resampled once per size and kept as a texture, so the GPU never has to shrink
a 1500 px image and edges stay crisp. On a backdrop where the brand navy would
be hard to read (every dark theme), the navy lettering draws white and the
navy spectrum bars a brighter indigo instead.

Textures need a live GL context. :class:`ImGuiHost` turns uploads on for its
real renderer only (:func:`enable_logo_textures`), so a headless host draws
nothing and still lays out the same space.
"""

from __future__ import annotations

import functools
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from cleave.paths import resource_dir

if TYPE_CHECKING:
    import pygame
    from imgui_bundle import imgui
    from PIL import Image

RGB = tuple[int, int, int]


class Logo(Enum):
    """A logo file in ``assets/``."""

    FULL = "cleave-logo-full.png"
    MARK = "cleave-logo-square.png"


BRAND_INK: RGB = (46, 49, 146)
"""The navy of the lettering and the mark's C."""

REVERSED_INK: RGB = (255, 255, 255)
"""What the navy lettering draws as on a backdrop it cannot be read on."""

REVERSED_BAR_INK: RGB = (125, 120, 240)
"""What the navy spectrum bars draw as there, so the rainbow still ends in blue."""

# Rows of each logo that hold the lettering, as fractions of its height.
# Navy outside them is a spectrum bar.
_LETTER_ROWS: dict[str, tuple[float, float]] = {
    "FULL": (0.355, 0.64),
    "MARK": (0.0, 1.0),
}

# Below this contrast ratio against the backdrop the navy turns white.
_MIN_INK_CONTRAST = 3.0
# Sized textures kept at once (splash, About, welcome, menu bar, and a resize).
_TEXTURE_LIMIT = 8
# Window icon edge in pixels. SDL scales it for the title bar and taskbar.
_WINDOW_ICON_PX = 256


def logo_path(logo: Logo) -> Path:
    return resource_dir() / "assets" / logo.value


@functools.cache
def _source(logo: Logo) -> Image.Image:
    from PIL import Image

    with Image.open(logo_path(logo)) as image:
        return image.convert("RGBA")


def logo_aspect(logo: Logo) -> float:
    """Width over height of the artwork."""
    width, height = _source(logo).size
    return width / height


def logo_size(logo: Logo, height: float, max_width: float | None = None) -> tuple[int, int]:
    """Whole-pixel size at *height*, shrunk to fit *max_width* when given."""
    aspect = logo_aspect(logo)
    h = max(1.0, float(height))
    if max_width is not None and h * aspect > max_width:
        h = max(1.0, float(max_width) / aspect)
    return max(1, round(h * aspect)), max(1, round(h))


def _luminance(rgb: RGB) -> float:
    def channel(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: RGB, b: RGB) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def ink_reversed(backdrop: RGB) -> bool:
    """True when the navy is too dark to read on *backdrop* and draws white."""
    return _contrast(BRAND_INK, backdrop) < _MIN_INK_CONTRAST


def logo_image(logo: Logo, size: tuple[int, int], *, reversed_ink: bool) -> Image.Image:
    """The artwork resampled to *size*, with the navy white when *reversed_ink*.

    Resamples with premultiplied alpha, so the transparent border cannot bleed
    a white fringe into the edges.
    """
    from PIL import Image

    image = _source(logo)
    if reversed_ink:
        pixels = np.array(image)
        navy = np.all(pixels[..., :3] == BRAND_INK, axis=-1)
        top, bottom = _LETTER_ROWS[logo.name]
        rows = np.arange(pixels.shape[0])[:, None] / pixels.shape[0]
        letters = navy & (rows >= top) & (rows < bottom)
        pixels[navy, :3] = REVERSED_BAR_INK
        pixels[letters, :3] = REVERSED_INK
        image = Image.fromarray(pixels, "RGBA")
    return image.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")


_TextureKey = tuple[Logo, int, int, bool]
_textures: OrderedDict[_TextureKey, int] = OrderedDict()
_uploads_enabled = False


def enable_logo_textures(enabled: bool) -> None:
    """Allow GL uploads (a real renderer) or not (headless). Off releases them."""
    global _uploads_enabled
    if not enabled:
        release_logo_textures()
    _uploads_enabled = enabled


def release_logo_textures() -> None:
    """Delete every logo texture. Call while the GL context is still current."""
    if not _textures:
        return
    names = list(_textures.values())
    _textures.clear()
    if not _uploads_enabled:
        return
    from OpenGL.GL import glDeleteTextures

    glDeleteTextures(names)


def _upload(image: Image.Image) -> int:
    from OpenGL.GL import (
        GL_CLAMP_TO_EDGE,
        GL_LINEAR,
        GL_RGBA,
        GL_RGBA8,
        GL_TEXTURE_2D,
        GL_TEXTURE_BINDING_2D,
        GL_TEXTURE_MAG_FILTER,
        GL_TEXTURE_MIN_FILTER,
        GL_TEXTURE_WRAP_S,
        GL_TEXTURE_WRAP_T,
        GL_UNSIGNED_BYTE,
        glBindTexture,
        glGenTextures,
        glGetIntegerv,
        glTexImage2D,
        glTexParameteri,
    )

    previous = int(glGetIntegerv(GL_TEXTURE_BINDING_2D))
    name = int(glGenTextures(1))
    glBindTexture(GL_TEXTURE_2D, name)
    try:
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        width, height = image.size
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA8,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            image.tobytes(),
        )
    finally:
        glBindTexture(GL_TEXTURE_2D, previous)
    return name


def _texture(logo: Logo, size: tuple[int, int], reversed_ink: bool) -> int | None:
    if not _uploads_enabled:
        return None
    key = (logo, size[0], size[1], reversed_ink)
    name = _textures.get(key)
    if name is not None:
        _textures.move_to_end(key)
        return name
    name = _upload(logo_image(logo, size, reversed_ink=reversed_ink))
    _textures[key] = name
    while len(_textures) > _TEXTURE_LIMIT:
        _key, evicted = _textures.popitem(last=False)
        from OpenGL.GL import glDeleteTextures

        glDeleteTextures([evicted])
    return name


def draw_logo(
    draw: imgui.ImDrawList,
    logo: Logo,
    rect: tuple[int, int, int, int],
    *,
    backdrop: RGB,
    alpha: float = 1.0,
) -> None:
    """Draw *logo* filling *rect* (x, y, w, h, whole pixels) over *backdrop*.

    Read *backdrop* from ``palette()`` at draw time so a theme change applies.
    """
    from imgui_bundle import imgui

    x, y, width, height = rect
    if width <= 0 or height <= 0 or alpha <= 0.0:
        return
    name = _texture(logo, (width, height), ink_reversed(backdrop))
    if name is None:
        return
    tint = (round(max(0.0, min(1.0, alpha)) * 255) << 24) | 0x00FFFFFF
    draw.add_image(
        imgui.ImTextureRef(name),
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        col=tint,
    )


def window_icon() -> pygame.Surface:
    """The C mark centred on a transparent square, for the window and taskbar."""
    import pygame
    from PIL import Image

    edge = _WINDOW_ICON_PX
    mark = logo_image(Logo.MARK, logo_size(Logo.MARK, edge, edge), reversed_ink=False)
    canvas = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
    canvas.paste(mark, ((edge - mark.width) // 2, (edge - mark.height) // 2))
    return pygame.image.frombytes(canvas.tobytes(), canvas.size, "RGBA")
