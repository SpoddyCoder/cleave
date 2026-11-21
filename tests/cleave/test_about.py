from datetime import date

from cleave.build_version import display_version
from cleave.about import about_body, about_credit


def test_about_body_lists_tagline_author_year_url_and_version() -> None:
    assert about_body(date(2031, 3, 4)).split("\n") == [
        "Stem-driven visualizer for making music videos, powered by projectM",
        "",
        "Created by P. Fernihough \u00a9 2031",
        "https://github.com/SpoddyCoder/cleave",
        "",
        display_version(),
    ]


def test_about_credit_carries_the_copyright_sign_and_year() -> None:
    assert about_credit(date(2031, 3, 4)) == "Created by P. Fernihough \u00a9 2031"
