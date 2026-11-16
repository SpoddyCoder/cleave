"""PyOpenGL error checking: off in the frozen build unless asked for.

PyOpenGL calls ``glGetError`` after every GL call by default. The ImGui
renderer is PyOpenGL in Python, so it pays that per draw command. The frozen
build turns it off; ``CLEAVE_GL_ERROR_CHECKING=1`` turns it back on for a bug
report. A checkout keeps it on. The flag is read when ``OpenGL.GL`` is first
imported, so call this before anything imports it.
"""

from __future__ import annotations

import os

from cleave.paths import is_frozen

ENV_VAR = "CLEAVE_GL_ERROR_CHECKING"


def gl_error_checking_wanted() -> bool:
    if os.environ.get(ENV_VAR, "").strip() == "1":
        return True
    return not is_frozen()


def configure_gl_error_checking() -> None:
    """Set ``OpenGL.ERROR_CHECKING`` for this build, before ``OpenGL.GL`` loads."""
    if gl_error_checking_wanted():
        return
    import OpenGL

    OpenGL.ERROR_CHECKING = False
