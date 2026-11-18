"""Tests for user theme files (cleave.viz.user_themes) and their controls."""

from __future__ import annotations

from collections.abc import Iterator
import dataclasses
from pathlib import Path

import pytest

from cleave.viz.theme import (
    DAYLIGHT,
    ULTRAVIOLET,
    palette,
    palette_for_theme,
    set_palette,
    set_user_palettes,
    theme_ids,
    theme_label,
)
from cleave.viz.theme_file_controls import (
    MAX_LISTED_PROBLEMS,
    problems_body,
    reloaded_message,
)
from cleave.viz.user_themes import (
    install_user_themes,
    load_user_themes,
    parse_colour,
    theme_roles,
)


@pytest.fixture(autouse=True)
def _restore_themes() -> Iterator[None]:
    previous = palette()
    yield
    set_user_palettes(())
    set_palette(previous)


def _write(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_folder_has_no_themes(tmp_path: Path) -> None:
    loaded = load_user_themes(tmp_path / "themes")
    assert loaded.palettes == ()
    assert loaded.problems == ()


def test_theme_file_overrides_only_listed_roles(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "Midnight.yaml",
        'name: Midnight Blue\nbase: ultraviolet\nlabel: "#a0b0ff"\n'
        "hover: [1, 2, 3]\nhover_bg_alpha: 60\nbutton_sheen: 0.5\n"
        "row_selected_alpha: [0.4, 0.1]\n"
        'timeline_track_colors: ["#010203", [4, 5, 6]]\n',
    )
    loaded = load_user_themes(tmp_path)
    assert loaded.problems == ()
    (midnight,) = loaded.palettes
    assert midnight.id == "midnight"
    assert midnight.name == "Midnight Blue"
    assert midnight.label == (0xA0, 0xB0, 0xFF)
    assert midnight.hover == (1, 2, 3)
    assert midnight.hover_bg_alpha == 60
    assert midnight.button_sheen == 0.5
    assert midnight.row_selected_alpha == (0.4, 0.1)
    assert midnight.timeline_track_colors == ((1, 2, 3), (4, 5, 6))
    assert midnight.value == ULTRAVIOLET.value
    assert midnight.background == ULTRAVIOLET.background


def test_name_and_base_default_to_file_name_and_ultraviolet(tmp_path: Path) -> None:
    _write(tmp_path, "plain.yml", "")
    (plain,) = load_user_themes(tmp_path).palettes
    assert plain.id == "plain"
    assert plain.name == "plain"
    assert plain.label == ULTRAVIOLET.label


def test_bad_roles_and_values_keep_the_base_and_are_reported(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "oops.yaml",
        "lable: [1, 2, 3]\n"
        "value: #ffffff\n"
        "hover: red\n"
        "hover_bg_alpha: 300\n"
        "button_sheen: true\n"
        "id: other\n",
    )
    loaded = load_user_themes(tmp_path)
    (oops,) = loaded.palettes
    assert oops.id == "oops"
    assert oops.value == ULTRAVIOLET.value
    assert oops.hover == ULTRAVIOLET.hover
    assert oops.hover_bg_alpha == ULTRAVIOLET.hover_bg_alpha
    assert oops.button_sheen == ULTRAVIOLET.button_sheen
    problems = loaded.problems
    assert len(problems) == 6
    assert all(problem.startswith("oops.yaml: ") for problem in problems)
    assert "unknown role 'lable' (did you mean 'label'?)" in problems[0]
    assert '"#a0b0ff"' in problems[1]
    assert "unknown role 'id'" in problems[5]


def test_unreadable_files_are_skipped_and_reported(tmp_path: Path) -> None:
    _write(tmp_path, "a_broken.yaml", "label: [1, 2\n")
    _write(tmp_path, "b_list.yaml", "- label\n")
    _write(tmp_path, "c_base.yaml", "base: dusk\n")
    _write(tmp_path, "ultraviolet.yaml", "")
    _write(tmp_path, "notes.txt", "label: nope\n")
    _write(tmp_path, "good.yaml", "")
    _write(tmp_path, "GOOD.yml", "")
    loaded = load_user_themes(tmp_path)
    assert [candidate.id for candidate in loaded.palettes] == ["good"]
    problems = loaded.problems
    assert problems[0].startswith("a_broken.yaml: the file is not valid YAML")
    assert problems[1].startswith("b_list.yaml: ")
    assert "unknown base theme 'dusk'" in problems[2]
    assert "GOOD.yml" in problems[3] or "good.yaml" in problems[3]
    assert any("ultraviolet.yaml: a built-in theme" in p for p in problems)
    assert len(problems) == 5


def test_a_theme_can_start_from_daylight(tmp_path: Path) -> None:
    _write(tmp_path, "paper.yaml", 'base: daylight\nlabel: "#102030"\n')
    loaded = load_user_themes(tmp_path)
    assert loaded.problems == ()
    (paper,) = loaded.palettes
    assert paper.background == DAYLIGHT.background
    assert paper.label == (16, 32, 48)


def test_icon_lifts_may_darken_but_fractions_may_not(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "lifts.yaml",
        "icon_lit_hover_lift: -0.2\nicon_lit_hover_edge_lift: -1.5\nbutton_sheen: -0.1\n",
    )
    loaded = load_user_themes(tmp_path)
    (lifts,) = loaded.palettes
    assert lifts.icon_lit_hover_lift == -0.2
    assert lifts.icon_lit_hover_edge_lift == ULTRAVIOLET.icon_lit_hover_edge_lift
    assert lifts.button_sheen == ULTRAVIOLET.button_sheen
    assert len(loaded.problems) == 2
    assert "icon_lit_hover_edge_lift: must be a number from -1 to 1" in loaded.problems[0]
    assert "button_sheen: must be a number from 0 to 1" in loaded.problems[1]


def test_theme_roles_exclude_id_and_name() -> None:
    roles = theme_roles()
    assert "id" not in roles
    assert "name" not in roles
    assert "label" in roles
    assert "timeline_track_colors" in roles


def test_parse_colour_accepts_hex_without_hash() -> None:
    assert parse_colour("ff8000") == (255, 128, 0)
    with pytest.raises(ValueError):
        parse_colour([1, 2, 256])


def test_installed_themes_follow_the_built_ins(tmp_path: Path) -> None:
    _write(tmp_path, "zed.yaml", "name: Zed\n")
    assert install_user_themes(tmp_path) == ()
    assert theme_ids() == ("ultraviolet", "chocolate", "mint", "daylight", "zed")
    assert theme_label("zed") == "Zed"
    assert palette_for_theme("zed").id == "zed"
    set_user_palettes(())
    assert palette_for_theme("zed") is ULTRAVIOLET


def test_problems_body_caps_the_list() -> None:
    problems = [f"p{index}" for index in range(MAX_LISTED_PROBLEMS + 3)]
    lines = problems_body(problems).split("\n")
    assert len(lines) == MAX_LISTED_PROBLEMS + 1
    assert lines[-1] == "and 3 more"
    assert reloaded_message(1) == "Themes reloaded: 1 user theme found"


def test_reload_themes_applies_the_chosen_theme_and_reports(
    tmp_path: Path, monkeypatch
) -> None:
    from dataclasses import replace

    from cleave.viz import theme_file_controls
    from cleave.viz.commands import command_by_id
    from tests.support.viz import make_controls

    folder = tmp_path / "themes"
    monkeypatch.setattr(theme_file_controls, "themes_dir", lambda: folder)
    controls = make_controls()
    controls.cfg.editor = replace(controls.cfg.editor, theme="mine")
    _write(folder, "mine.yaml", 'label: "#010203"\n')
    command_by_id("settings.reload_themes").run(controls)
    assert palette().id == "mine"
    assert palette().label == (1, 2, 3)
    assert controls.notification_active().message == reloaded_message(1)
    assert not controls.modal_host.active

    _write(folder, "mine.yaml", 'label: "#040506"\nlabl: [1, 1, 1]\n')
    command_by_id("settings.reload_themes").run(controls)
    assert palette().label == (4, 5, 6)
    assert controls.modal_host.active



def test_user_guide_lists_every_theme_role() -> None:
    guide = (
        Path(__file__).resolve().parents[3] / "docs" / "user-guide" / "user-themes.md"
    ).read_text(encoding="utf-8")
    missing = [role for role in theme_roles() if f"`{role}`" not in guide]
    assert missing == []


def test_user_guide_starter_theme_matches_ultraviolet(tmp_path: Path) -> None:
    import re

    import yaml

    guide = (
        Path(__file__).resolve().parents[3] / "docs" / "user-guide" / "user-themes.md"
    ).read_text(encoding="utf-8")
    section = guide[guide.index("## Starter theme") :]
    block = re.search(r"```yaml\n(.*?)```", section, re.DOTALL)
    assert block is not None
    data = yaml.safe_load(block.group(1))
    assert set(data) - {"name", "base"} == set(theme_roles())
    _write(tmp_path, "starter.yaml", block.group(1))
    loaded = load_user_themes(tmp_path)
    assert loaded.problems == ()
    assert loaded.palettes == (
        dataclasses.replace(ULTRAVIOLET, id="starter", name=data["name"]),
    )
