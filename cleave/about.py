"""About Cleave text: name, tagline, author, project URL, and version."""

from __future__ import annotations

from datetime import date

from cleave import __version__

ABOUT_TITLE = "Cleave"
ABOUT_TAGLINE = "Stem separated music visualizer powered by ProjectM"
ABOUT_AUTHOR = "P. Fernihough"
ABOUT_URL = "https://github.com/SpoddyCoder/cleave"


def about_body(today: date | None = None) -> str:
    """Lines under the About title. The year is the current year."""
    year = (today or date.today()).year
    return "\n".join(
        (
            ABOUT_TAGLINE,
            f"Written by {ABOUT_AUTHOR}, {year}",
            ABOUT_URL,
            f"v{__version__}",
        )
    )
