"""About Cleave text: name, tagline, author, project URL, and version (release tag or dev build)."""

from __future__ import annotations

from datetime import date

from cleave.build_version import display_version

ABOUT_TITLE = "About Cleave"
ABOUT_SUMMARY = "Stem-driven visualizer for making music videos"
"""What Cleave is, in a few words. The splash shows it under the logo."""
ABOUT_TAGLINE = f"{ABOUT_SUMMARY}, powered by projectM"
ABOUT_AUTHOR = "P. Fernihough"
ABOUT_URL = "https://github.com/SpoddyCoder/cleave"


def about_credit(today: date | None = None) -> str:
    """The author and copyright line. The year is the current year."""
    year = (today or date.today()).year
    return f"Created by {ABOUT_AUTHOR} \u00a9 {year}"


def about_body(today: date | None = None) -> str:
    """Lines under the About title."""
    return "\n".join(
        (
            ABOUT_TAGLINE,
            "",
            about_credit(today),
            ABOUT_URL,
            "",
            display_version(),
        )
    )
