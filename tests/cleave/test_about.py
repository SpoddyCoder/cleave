from datetime import date

from cleave.build_version import display_version
from cleave.about import about_body


def test_about_body_lists_tagline_author_year_url_and_version() -> None:
    assert about_body(date(2031, 3, 4)).split("\n") == [
        "Stem separated music visualizer powered by ProjectM",
        "",
        "Created by P. Fernihough, 2031",
        "https://github.com/SpoddyCoder/cleave",
        "",
        display_version(),
    ]
