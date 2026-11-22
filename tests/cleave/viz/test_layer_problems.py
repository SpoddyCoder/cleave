"""Layer problems and notices: the navigator warning icon and bad preset file marks."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM, preset_failure_key
from cleave.stem_pcm import StemPcmBank
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz import row_hotkeys
from cleave.viz.context_menu import ContextSubmenu, MenuIcon
from cleave.viz.layer_problems import (
    PRESET_DIR_MISSING,
    PRESET_FILE_MISSING,
    ProblemPage,
    layer_issues,
    layer_issues_tooltip,
    layer_notices,
    layer_problems,
)
from cleave.viz.menu_rows import context_menu_row_views
from cleave.viz.navigator_context_menu import navigator_node_menu_entries
from cleave.viz.navigator import (
    TOGGLE_ENABLED,
    TOGGLE_NOTICE,
    TOGGLE_WARN,
    build_navigator,
    ProblemTarget,
    issue_target,
    layer_node_id,
    layer_page_node_id,
    page_toggles,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_specs.track import preset_row_problem
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.shell_focus import ShellRegion
from tests.support.viz import make_controls
from tests.support.preset_list import entries

GOOD = Path(__file__)
MISSING = GOOD.parent / "no-such-preset.milk"
GONE_DIR = GOOD.parent / "no-such-folder"


def first_problem_target(session: TuningSession, slot: str) -> ProblemTarget | None:
    items = layer_issues(session, slot).items()
    return issue_target(session, slot, items[0]) if items else None


def _layer(current: Path | None = GOOD) -> LayerRuntime:
    paths = (current,) if current is not None else ()
    return LayerRuntime(
        playlist=PresetPlaylist(current_dir=GOOD.parent, paths=paths, index=0),
        browse_floor=GOOD.parent,
        stem="drums",
    )


def _session(layer: LayerRuntime) -> TuningSession:
    """A session whose presets were checked on disk, as at project load."""
    session = TuningSession(layer_z_order=["layer_1"], layers={"layer_1": layer})
    session.preset_health.check_on_disk(session)
    return session


def _messages(session: TuningSession) -> list[str]:
    return [problem.message for problem in layer_problems(session, "layer_1")]


def test_a_layer_with_a_preset_that_exists_has_no_problem() -> None:
    assert layer_problems(_session(_layer()), "layer_1") == ()


def test_switching_on_with_an_empty_list_is_a_problem() -> None:
    layer = _layer()
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    (problem,) = layer_problems(_session(layer), "layer_1")
    assert problem.page is ProblemPage.PRESET_LIST
    assert "preset list is empty" in problem.message


def test_a_bad_list_entry_marks_the_entry_and_the_layer() -> None:
    layer = _layer()
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = entries(str(GOOD), str(MISSING))
    session = _session(layer)
    (problem,) = layer_problems(session, "layer_1")
    assert problem.page is ProblemPage.PRESET_LIST
    assert problem.message == "1 preset in the preset list can't load"
    assert session.preset_health.list_problems("layer_1", layer) == (
        None,
        PRESET_FILE_MISSING,
    )


def test_a_list_where_nothing_can_load_is_a_layer_problem() -> None:
    layer = _layer()
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = entries(str(MISSING), str(GOOD))
    session = _session(layer)
    assert _messages(session) == ["1 preset in the preset list can't load"]
    # A failure arriving later is picked up through the revision, not the disk.
    layer.failed_presets = {preset_failure_key(GOOD): "parse error"}
    layer.failed_presets_revision = 1
    (problem,) = layer_problems(session, "layer_1")
    assert problem.page is ProblemPage.PRESET_LIST
    assert problem.message == "None of the presets in the preset list can load"
    assert session.preset_health.file_problem(layer, GOOD) == (
        "Failed to load: parse error"
    )


def test_a_missing_or_failed_preset_is_a_problem_only_while_switching_is_off() -> None:
    layer = _layer(MISSING)
    session = _session(layer)
    (problem,) = layer_problems(session, "layer_1")
    assert problem.page is ProblemPage.MILKDROP_PRESET
    assert problem.message == f"Milkdrop preset not found: {MISSING.name}"
    assert problem.row is RowKind.TRACK_PRESET

    no_preset = _session(_layer(None))
    assert _messages(no_preset) == ["Milkdrop preset not found"]

    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = entries(str(GOOD))
    assert layer_problems(session, "layer_1") == ()


def test_timeline_trigger_needs_the_timeline_on_and_clips_on_the_layer() -> None:
    layer = _layer()
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timeline"
    layer.preset_list = entries(str(GOOD))
    session = _session(layer)
    session.timeline.enabled = False
    assert _messages(session) == [
        "Switching follows the timeline, but the timeline is off"
    ]
    session.timeline.enabled = True
    assert _messages(session) == [
        "Switching follows the timeline, but this layer has no clips on it"
    ]
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0, cues=[SlotCue(t=1.0, level=1.0)]
    )
    assert layer_problems(session, "layer_1") == ()
    # A layer that is on from the start is one clip for the whole song.
    session.timeline.lanes["layer_1"] = TimelineLane(baseline=1.0, cues=[])
    assert layer_problems(session, "layer_1") == ()


def _timeline_layer(clip_starts: tuple[float, ...], presets: int) -> TuningSession:
    layer = _layer()
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timeline"
    layer.preset_list = entries(GOOD) * presets
    session = _session(layer)
    session.timeline.enabled = True
    cues = []
    for start in clip_starts:
        cues += [SlotCue(t=start, level=1.0), SlotCue(t=start + 1.0, level=0.0)]
    session.timeline.lanes["layer_1"] = TimelineLane(baseline=0.0, cues=cues)
    return session


def test_more_presets_than_timeline_clips_is_a_notice_not_a_problem() -> None:
    session = _timeline_layer((1.0,), presets=3)
    assert layer_problems(session, "layer_1") == ()
    (notice,) = layer_notices(session, "layer_1")
    assert notice.page is ProblemPage.PRESET_LIST
    assert notice.message == (
        "Preset switching is on, following the timeline\n"
        "3 presets in the list but only 1 clip on the timeline: the last 2 never play"
    )
    assert notice.preset_index == 1
    two = _timeline_layer((1.0, 4.0), presets=3)
    (notice,) = layer_notices(two, "layer_1")
    assert notice.message.endswith("3 presets in the list but only 2 clips on the timeline: the last one never plays")


def test_a_whole_song_clip_with_a_long_list_is_a_notice() -> None:
    session = _timeline_layer((), presets=14)
    session.timeline.lanes["layer_1"] = TimelineLane(baseline=1.0, cues=[])
    assert layer_problems(session, "layer_1") == ()
    (notice,) = layer_notices(session, "layer_1")
    assert notice.message.endswith("14 presets in the list but only 1 clip on the timeline: the last 13 never play")


def test_no_notice_when_every_preset_gets_a_clip_or_switching_is_not_timeline() -> None:
    assert layer_notices(_timeline_layer((1.0, 4.0), presets=2), "layer_1") == ()
    assert layer_notices(_timeline_layer((1.0,), presets=1), "layer_1") == ()
    session = _timeline_layer((1.0,), presets=3)
    session.layers["layer_1"].preset_switching_trigger = "timer"
    assert layer_notices(session, "layer_1") == ()
    session.layers["layer_1"].preset_switching_trigger = "timeline"
    session.timeline.enabled = False
    assert layer_notices(session, "layer_1") == ()


def test_a_notice_lights_an_amber_icon_that_a_problem_replaces() -> None:
    session = _timeline_layer((1.0,), presets=3)
    toggles = {
        node.id: node for node in build_navigator(session, {"layers"})
    }[layer_node_id("layer_1")].toggles
    assert toggles[0].id == TOGGLE_NOTICE
    assert toggles[0].detail.split("\n")[-1] == "Click to go to the first notice"
    page = layer_page_node_id("layer_1", "preset_list")
    assert page_toggles(session, page)[0].toggle.id == TOGGLE_NOTICE
    assert first_problem_target(session, "layer_1") == ProblemTarget(
        page,
        RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=1),
    )
    session.silent_stems = frozenset({"drums"})
    toggles = {
        node.id: node for node in build_navigator(session, {"layers"})
    }[layer_node_id("layer_1")].toggles
    assert toggles[0].id == TOGGLE_WARN
    assert toggles[0].detail.split("\n") == [
        "Multiple problems",
        "Click to go to the first problem",
        "Right-click to view all",
    ]


def test_a_silent_driving_stem_is_a_problem() -> None:
    session = _session(_layer())
    session.silent_stems = frozenset({"drums"})
    (problem,) = layer_problems(session, "layer_1")
    assert problem.page is ProblemPage.COMPOSITING
    assert "drums stem is silent" in problem.message


def test_the_disk_is_read_only_when_a_project_loads() -> None:
    layer = _layer()
    layer.preset_list = entries(str(GOOD), str(MISSING))
    session = TuningSession(layer_z_order=["layer_1"], layers={"layer_1": layer})
    with patch(
        "cleave.viz.layer_problems.os.path.isfile", side_effect=os.path.isfile
    ) as isfile:
        session.preset_health.check_on_disk(session)
        assert isfile.call_count == 2
        for _ in range(3):
            layer_problems(session, "layer_1")
            session.preset_health.list_problems("layer_1", layer)
        # A preset added while editing was picked from disk: never stat'd.
        layer.preset_list.extend(entries(GOOD.parent / "added-later.milk"))
        assert session.preset_health.list_problems("layer_1", layer)[2] is None
        assert isfile.call_count == 2


def test_list_problems_are_kept_until_the_list_or_failures_change() -> None:
    layer = _layer()
    layer.preset_list = entries(str(MISSING))
    health = _session(layer).preset_health
    first = health.list_problems("layer_1", layer)
    assert health.list_problems("layer_1", layer) is first
    layer.preset_list = entries(str(GOOD))
    assert health.list_problems("layer_1", layer) == (None,)


def test_tooltip_names_one_issue_or_says_there_are_several() -> None:
    layer = _layer(MISSING)
    session = _session(layer)
    assert layer_issues_tooltip(layer_issues(session, "layer_1")).split("\n") == [
        f"Milkdrop preset not found: {MISSING.name}",
        "Click to go to the first problem",
    ]
    session.silent_stems = frozenset({"drums"})
    assert layer_issues_tooltip(layer_issues(session, "layer_1")).split("\n") == [
        "Multiple problems",
        "Click to go to the first problem",
        "Right-click to view all",
    ]


def test_several_notices_and_no_problem_say_multiple_notices() -> None:
    session = _timeline_layer((1.0,), presets=3)
    one = layer_issues(session, "layer_1")
    issues = type(one)(notices=one.notices * 2)
    assert layer_issues_tooltip(issues).split("\n")[0] == "Multiple notices"
    assert layer_issues_tooltip(issues).split("\n")[1] == (
        "Click to go to the first notice"
    )


def test_a_missing_preset_folder_is_the_one_problem_and_marks_the_directory_row() -> None:
    layer = LayerRuntime(
        playlist=PresetPlaylist(
            current_dir=GONE_DIR, paths=(GONE_DIR / "a.milk",), index=0
        ),
        browse_floor=GOOD.parent,
        stem="drums",
    )
    session = _session(layer)
    (problem,) = layer_problems(session, "layer_1")
    assert problem.message == "Preset directory not found: no-such-folder"
    assert problem.page is ProblemPage.MILKDROP_PRESET
    assert problem.row is RowKind.TRACK_PRESET_DIR
    assert first_problem_target(session, "layer_1") == ProblemTarget(
        layer_page_node_id("layer_1", "milkdrop_preset"),
        RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1"),
    )
    # An empty playlist in a missing folder is the folder problem too.
    layer.playlist = PresetPlaylist(current_dir=GONE_DIR, paths=(), index=0)
    assert _messages(session) == ["Preset directory not found: no-such-folder"]


def test_a_missing_folder_is_a_problem_with_switching_on_too() -> None:
    layer = LayerRuntime(
        playlist=PresetPlaylist(current_dir=GONE_DIR, paths=(), index=0),
        browse_floor=GOOD.parent,
        stem="drums",
    )
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "projectm"
    session = _session(layer)
    assert _messages(session) == [
        "Preset directory not found: no-such-folder",
        "Preset switching is on, but the preset list is empty",
    ]
    assert layer_issues_tooltip(layer_issues(session, "layer_1")).startswith(
        "Multiple problems"
    )


def test_view_state_marks_a_missing_folder_on_the_directory_row_only() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.playlist = PresetPlaylist(
        current_dir=GONE_DIR, paths=(GONE_DIR / "a.milk",), index=0
    )
    controls.session.preset_health.check_on_disk(controls.session)
    view = controls.build_view_state(paused=False)
    assert preset_row_problem(
        view, RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    ) == PRESET_DIR_MISSING
    assert preset_row_problem(
        view, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    ) is None


def test_issue_target_reaches_any_issue_not_only_the_first() -> None:
    session = _timeline_layer((1.0,), presets=3)
    session.silent_stems = frozenset({"drums"})
    problem, notice = layer_issues(session, "layer_1").items()
    assert issue_target(session, "layer_1", problem) == ProblemTarget(
        layer_page_node_id("layer_1", "compositing"),
        RowDescriptor(RowKind.TRACK_STEM, slot="layer_1"),
    )
    assert issue_target(session, "layer_1", notice) == ProblemTarget(
        layer_page_node_id("layer_1", "preset_list"),
        RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=1),
    )


def _menu(controls):
    return navigator_node_menu_entries(
        controls, layer_node_id("layer_1"), lambda _node: None
    )


def test_view_all_problems_leads_the_layer_menu_only_with_several_issues() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.playlist = PresetPlaylist(current_dir=GOOD.parent, paths=(MISSING,), index=0)
    controls.session.preset_health.check_on_disk(controls.session)
    assert not any(
        isinstance(entry, ContextSubmenu) and entry.id == "navigator.issues"
        for entry in _menu(controls)
    )
    controls.session.silent_stems = frozenset({"drums"})
    first = _menu(controls)[0]
    assert isinstance(first, ContextSubmenu)
    assert first.id == "navigator.issues"
    assert first.label == "View all problems"
    assert [item.label for item in first.items] == [
        f"Milkdrop preset not found: {MISSING.name}",
        "The drums stem is silent, so this layer has no audio to react to",
    ]
    assert {item.icon for item in first.items} == {MenuIcon.PROBLEM}
    assert [view.icon for view in context_menu_row_views(first.items)] == [
        MenuIcon.PROBLEM,
        MenuIcon.PROBLEM,
    ]
    first.items[1].run()
    focus = controls.shell_focus
    assert focus.selected_id == layer_page_node_id("layer_1", "compositing")
    assert focus.inspector_cursor == RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")


def test_notices_list_after_problems_with_an_amber_sign_on_one_line() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timeline"
    layer.preset_list = entries(GOOD) * 3
    controls.session.preset_health.check_on_disk(controls.session)
    controls.session.timeline.enabled = True
    controls.session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0, cues=[SlotCue(t=1.0, level=1.0), SlotCue(t=2.0, level=0.0)]
    )
    controls.session.silent_stems = frozenset({"drums"})
    submenu = _menu(controls)[0]
    assert isinstance(submenu, ContextSubmenu)
    assert [item.icon for item in submenu.items] == [MenuIcon.PROBLEM, MenuIcon.NOTICE]
    assert submenu.items[1].label == (
        "Preset switching is on, following the timeline: "
        "3 presets in the list but only 1 clip on the timeline: the last 2 never play"
    )


def test_a_problem_puts_a_warning_icon_first_on_the_layer_and_its_pages() -> None:
    layer = _layer(MISSING)
    session = _session(layer)
    nodes = {node.id: node for node in build_navigator(session, {"layers"})}
    toggles = nodes[layer_node_id("layer_1")].toggles
    assert toggles[0].id == TOGGLE_WARN
    assert toggles[0].active is True
    assert MISSING.name in toggles[0].detail
    assert toggles[1].id == TOGGLE_ENABLED
    page = layer_page_node_id("layer_1", "compositing")
    assert page_toggles(session, page)[0].toggle.id == TOGGLE_WARN

    layer.playlist = PresetPlaylist(current_dir=GOOD.parent, paths=(GOOD,), index=0)
    nodes = {node.id: node for node in build_navigator(session, {"layers"})}
    assert TOGGLE_WARN not in {t.id for t in nodes[layer_node_id("layer_1")].toggles}


def test_first_problem_page_falls_back_when_the_list_page_is_hidden() -> None:
    layer = _layer()
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    session = _session(layer)
    assert first_problem_target(session, "layer_1") == ProblemTarget(
        layer_page_node_id("layer_1", "preset_list")
    )
    layer.preset_switching_trigger = "off"
    assert first_problem_target(session, "layer_1") == ProblemTarget(
        layer_page_node_id("layer_1", "preset_switching")
    )
    layer.preset_switching = "off"
    assert first_problem_target(session, "layer_1") is None


def test_first_problem_target_is_the_first_bad_list_entry() -> None:
    layer = _layer()
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = entries(str(GOOD), str(MISSING), str(MISSING))
    session = _session(layer)
    assert first_problem_target(session, "layer_1") == ProblemTarget(
        layer_page_node_id("layer_1", "preset_list"),
        RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=1),
    )


def test_warning_toggle_focuses_the_row_of_the_first_problem() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = entries(str(GOOD), str(MISSING))
    controls.session.preset_health.check_on_disk(controls.session)
    row_hotkeys.activate_header_toggle(
        controls, TOGGLE_WARN, RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    )
    focus = controls.shell_focus
    assert focus.selected_id == layer_page_node_id("layer_1", "preset_list")
    assert focus.region is ShellRegion.INSPECTOR
    assert focus.inspector_cursor == RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=1
    )


def test_view_state_marks_bad_preset_rows() -> None:
    controls = make_controls(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_list = entries(str(GOOD), str(MISSING))
    layer.playlist = PresetPlaylist(current_dir=GOOD.parent, paths=(MISSING,), index=0)
    controls.session.preset_health.check_on_disk(controls.session)
    view = controls.build_view_state(paused=False)
    assert preset_row_problem(
        view, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    ) == PRESET_FILE_MISSING
    item = RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=0)
    assert preset_row_problem(view, item) is None
    bad = RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=1)
    assert preset_row_problem(view, bad) == PRESET_FILE_MISSING


def test_projectm_records_a_failure_until_the_preset_loads_again() -> None:
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._failure_queue = __import__("collections").deque()
    pm._failed_presets = {}
    pm._failure_revision = 0
    pm._log_queue = __import__("collections").deque()
    pm._enqueue_preset_failure("/p/bad.milk", "parse error")
    pm._enqueue_preset_failure("", "all failed", exhausted=True)
    assert pm.failed_presets == {preset_failure_key("/p/bad.milk"): "parse error"}
    assert pm.failure_revision == 1
    with patch("cleave.projectm._get_lib", return_value=MagicMock()):
        pm.load_preset("/p/bad.milk")
        pm.load_preset("/p/bad.milk")
    assert pm.failed_presets == {}
    assert pm.failure_revision == 2


def test_silent_stems_are_the_ones_with_no_sound() -> None:
    bank = StemPcmBank(
        project_dir=Path("/p"),
        duration_sec=1.0,
        _pcm={
            "drums": np.full(4, 0.5, dtype=np.float32),
            "vocals": np.zeros(4, dtype=np.float32),
            "bass": np.full(4, -0.5, dtype=np.float32),
        },
        _channels={"drums": 1, "vocals": 1, "bass": 1},
    )
    assert bank.silent_stems() == frozenset({"vocals"})
