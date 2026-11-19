"""About Cleave text: name, tagline, author, project URL, and version (release tag or dev build)."""

from __future__ import annotations

from datetime import date

from cleave.build_version import display_version

ABOUT_TITLE = "About Cleave"
ABOUT_TAGLINE = "Stem separated music visualizer powered by ProjectM"
ABOUT_AUTHOR = "P. Fernihough"
ABOUT_URL = "https://github.com/SpoddyCoder/cleave"


def about_body(today: date | None = None) -> str:
    """Lines under the About title. The year is the current year."""
    year = (today or date.today()).year
    return "\n".join(
        (
            ABOUT_TAGLINE,
            "",
            f"Created by {ABOUT_AUTHOR}, {year}",
            ABOUT_URL,
            "",
            display_version(),
        )
    )
