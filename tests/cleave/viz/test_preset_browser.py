"""Preset browser state: listing, filtering, and navigation."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleave.preset_library import UNFILTERED_CATALOG, PresetLibrary
from cleave.viz import preset_browser
from cleave.viz.preset_browser import (
    BrowserAction,
    BrowserOutcome,
    BrowserRowKind,
    PresetBrowser,
)


def _milk(path: Path, content: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content is not None else path.as_posix(), encoding="utf-8")
    return path.resolve()


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "presets"
    _milk(root / "Pack A" / "Geiss" / "geiss - swirl.milk")
    _milk(root / "Pack A" / "Geiss" / "geiss - tunnel.milk")
    _milk(root / "Pack A" / "Other" / "flexi - swirl.milk")
    _milk(root / "Pack A" / "loose.milk")
    _milk(root / "Pack B" / "beta.milk")
    (root / "Empty").mkdir()
    return root.resolve()


def _indexed(root: Path) -> PresetLibrary:
    library = PresetLibrary.in_memory()
    library.index(root)
    return library


def _kinds(browser: PresetBrowser) -> list[tuple[BrowserRowKind, str, str]]:
    return [(row.kind, row.label, row.detail) for row in browser.rows]


@pytest.mark.parametrize("indexed", [True, False])
def test_top_level_lists_collections_then_folders_with_counts(
    tree: Path, indexed: bool
) -> None:
    catalog = _indexed(tree) if indexed else UNFILTERED_CATALOG
    browser = PresetBrowser(preset_root=tree, catalog=catalog)

    folders = [row for row in browser.rows if row.kind is BrowserRowKind.FOLDER]
    assert [(row.label, row.detail) for row in folders] == [
        ("Pack A", "4 presets"),
        ("Pack B", "1 preset"),
    ]
    assert browser.rows[0].kind is not BrowserRowKind.PARENT
    collections = [row for row in browser.rows if row.kind is BrowserRowKind.COLLECTION]
    assert len(collections) == (6 if indexed else 0)
    assert browser.crumbs()[0].label == "presets"


def test_folder_lists_parent_subfolders_then_presets(tree: Path) -> None:
    browser = PresetBrowser(
        preset_root=tree, catalog=_indexed(tree), folder=tree / "Pack A"
    )
    assert _kinds(browser) == [
        (BrowserRowKind.PARENT, "..", ""),
        (BrowserRowKind.FOLDER, "Geiss", "2 presets"),
        (BrowserRowKind.FOLDER, "Other", "1 preset"),
        (BrowserRowKind.PRESET, "loose.milk", ""),
    ]
    assert browser.selected_index == 1
    assert [crumb.label for crumb in browser.crumbs()] == ["presets", "Pack A"]


def test_starts_on_the_selected_preset(tree: Path) -> None:
    tunnel = tree / "Pack A" / "Geiss" / "geiss - tunnel.milk"
    browser = PresetBrowser(
        preset_root=tree,
        catalog=_indexed(tree),
        folder=tunnel.parent,
        select=tunnel,
    )
    assert browser.selected_preset() == tunnel


def test_open_folder_parent_and_crumbs(tree: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree), folder=tree / "Pack A")
    assert browser.handle(BrowserAction.OPEN) is BrowserOutcome.NONE
    assert browser.folder == tree / "Pack A" / "Geiss"
    assert browser.selected_preset() == tree / "Pack A" / "Geiss" / "geiss - swirl.milk"

    browser.handle(BrowserAction.PARENT)
    assert browser.folder == tree / "Pack A"
    assert browser.selected_row.path == tree / "Pack A" / "Geiss"

    browser.handle(BrowserAction.ENTER_FOLDER)
    browser.goto_crumb(0)
    assert browser.at_top
    assert browser.selected_row.path == tree / "Pack A"
    browser.handle(BrowserAction.PARENT)
    assert browser.at_top


def test_open_on_a_preset_commits(tree: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree), folder=tree / "Pack B")
    assert browser.selected_preset() == tree / "Pack B" / "beta.milk"
    assert browser.handle(BrowserAction.ENTER_FOLDER) is BrowserOutcome.NONE
    assert browser.handle(BrowserAction.OPEN) is BrowserOutcome.COMMIT


def test_filter_matches_every_term_below_the_folder(tree: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree))
    browser.type_text("SWIRL")
    assert [row.label for row in browser.rows] == [
        "Pack A/Geiss/geiss - swirl.milk",
        "Pack A/Other/flexi - swirl.milk",
    ]
    browser.type_text(" geiss")
    assert [row.label for row in browser.rows] == ["Pack A/Geiss/geiss - swirl.milk"]

    browser = PresetBrowser(
        preset_root=tree, catalog=_indexed(tree), folder=tree / "Pack A" / "Other"
    )
    browser.type_text("swirl")
    assert [row.label for row in browser.rows] == ["flexi - swirl.milk"]


def test_filter_without_matches_shows_a_note(tree: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree))
    browser.type_text("nothing like this")
    assert _kinds(browser) == [(BrowserRowKind.NOTE, "No presets match", "")]
    assert browser.selected_preset() is None
    assert browser.handle(BrowserAction.OPEN) is BrowserOutcome.NONE


def test_filter_hides_blacklisted(tree: Path) -> None:
    library = _indexed(tree)
    library.set_blacklisted(tree / "Pack A" / "Geiss" / "geiss - swirl.milk", True)
    browser = PresetBrowser(preset_root=tree, catalog=library)
    browser.type_text("swirl")
    assert [row.label for row in browser.rows] == ["Pack A/Other/flexi - swirl.milk"]
    browser.set_filter("")
    folders = {row.label: row.detail for row in browser.rows if row.kind is BrowserRowKind.FOLDER}
    assert folders["Pack A"] == "3 presets"


def test_filter_caps_rows(tree: Path, monkeypatch) -> None:
    monkeypatch.setattr(preset_browser, "MAX_ROWS", 2)
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree))
    browser.type_text(".milk")
    assert [row.kind for row in browser.rows] == [
        BrowserRowKind.PRESET,
        BrowserRowKind.PRESET,
        BrowserRowKind.NOTE,
    ]
    assert browser.rows[-1].label == "Showing the first 2 of 5 matches"


def test_backspace_and_escape_clear_the_filter_first(tree: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree), folder=tree / "Pack A")
    browser.type_text("ge")
    assert browser.handle(BrowserAction.BACKSPACE) is BrowserOutcome.NONE
    assert browser.filter_text == "g"
    assert browser.folder == tree / "Pack A"
    assert browser.handle(BrowserAction.CANCEL) is BrowserOutcome.NONE
    assert browser.filter_text == ""
    browser.handle(BrowserAction.BACKSPACE)
    assert browser.at_top
    assert browser.handle(BrowserAction.CANCEL) is BrowserOutcome.CANCEL


def test_leading_space_is_not_a_filter(tree: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree))
    browser.type_text(" ")
    assert browser.filter_text == ""


def test_collection_lists_members_and_parent_returns_to_top(tree: Path) -> None:
    library = _indexed(tree)
    beta = tree / "Pack B" / "beta.milk"
    library.set_favourite(beta, True)
    browser = PresetBrowser(preset_root=tree, catalog=library)
    favourites = next(
        index for index, row in enumerate(browser.rows) if row.collection == "favourites"
    )
    browser.select_row(favourites)
    browser.open_selected()
    assert browser.collection == "favourites"
    assert [row.label for row in browser.rows] == ["..", "Pack B/beta.milk"]
    assert [crumb.label for crumb in browser.crumbs()] == ["presets", "Favourites"]

    browser.go_parent()
    assert browser.at_top
    assert browser.selected_row.collection == "favourites"


def test_empty_folder_shows_a_note(tree: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree), folder=tree / "Empty")
    assert _kinds(browser) == [
        (BrowserRowKind.PARENT, "..", ""),
        (BrowserRowKind.NOTE, "No presets here", ""),
    ]


def test_start_outside_the_root_falls_back_to_the_top(tree: Path, tmp_path: Path) -> None:
    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree), folder=tmp_path)
    assert browser.at_top


def test_markers_show_as_detail(tree: Path) -> None:
    browser = PresetBrowser(
        preset_root=tree,
        catalog=_indexed(tree),
        folder=tree / "Pack B",
        marker=lambda path: "[F]",
    )
    assert browser.selected_row.detail == "[F]"


def test_shell_draws_the_open_browser_over_the_column(tree: Path) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from tests.support.shell import draw_shell, headless_shell_host

    browser = PresetBrowser(preset_root=tree, catalog=_indexed(tree), folder=tree / "Pack A")
    with headless_shell_host() as host:
        apply_pointer = MagicMock()
        host.context.controls.preset_browser = SimpleNamespace(
            active=True,
            view_state=browser.view_state,
            apply_pointer=apply_pointer,
            browser=browser,
            slot="layer_1",
        )
        draw_shell(host)
        draw_shell(host)
        surface = host._browser_surface
        assert surface is not None
        assert len(surface.row_rects) == len(browser.rows)
        layout = host.layout
        x = surface.row_rects[0][0]
        assert layout.navigator[0] <= x < layout.navigator[0] + layout.navigator[2]
        assert apply_pointer.called
        host.context.controls.preset_browser = SimpleNamespace(
            active=False, view_state=lambda: None
        )
