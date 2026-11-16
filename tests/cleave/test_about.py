from datetime import date

from cleave import __version__
from cleave.about import about_body


def test_about_body_lists_tagline_author_year_url_and_version() -> None:
    assert about_body(date(2031, 3, 4)).split("\n") == [
        "Stem separated music visualizer powered by ProjectM",
        "Written by P. Fernihough, 2031",
        "https://github.com/SpoddyCoder/cleave",
        f"v{__version__}",
    ]
