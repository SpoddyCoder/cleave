"""Tests for preset list populate helpers."""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import patch

from cleave.preset_library import UNFILTERED_CATALOG, PresetLibrary
from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import SlotCue, TimelineLane
from cleave.preset_list_fill import needed_preset_count
from cleave.preset_list_entry import PresetListEntry
from cleave.viz.preset_list_populate import (
    kept_list_for_clips,
    populate_from_cue_marker_roles,
    populate_from_directory,
    repopulate_preset_lists,
)
from cleave.viz.session import LayerRuntime, TuningSession


def _session(
    tmp: Path,
    *,
    timeline_enabled: bool = False,
    trigger: str = "timer",
    cues: tuple[SlotCue, ...] = (),
) -> TuningSession:
    browse = tmp / "presets" / "pack"
    browse.mkdir(parents=True)
    runtime = LayerRuntime(
        playlist=PresetPlaylist(current_dir=browse, paths=(), index=0),
        browse_floor=browse,
        stem="drums",
        preset_switching="on",
        preset_switching_trigger=trigger,  # type: ignore[arg-type]
    )
    session = TuningSession(layer_z_order=["layer_1"], layers={"layer_1": runtime})
    session.timeline.enabled = timeline_enabled
    if cues:
        session.timeline.lanes["layer_1"] = TimelineLane(baseline=0.0, cues=cues)
    return session


def test_needed_preset_count_timer_and_projectm() -> None:
    assert needed_preset_count(
        song_duration_sec=120.0, preset_duration=30.0, trigger="timer"
    ) == 4
    assert needed_preset_count(
        song_duration_sec=120.0, preset_duration=30.0, trigger="projectm"
    ) == 6
    assert needed_preset_count(
        song_duration_sec=10.0, preset_duration=30.0, trigger="timer"
    ) == 1


def test_populate_from_directory_timer_shuffles_all(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timer")
    browse = session.layers["layer_1"].playlist.current_dir
    for name in ("a.milk", "b.milk", "c.milk"):
        (browse / name).write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_directory(
            session,
            "layer_1",
            project_dir=tmp_path,
            order="random",
            rng=random.Random(0),
        )
    assert sorted(Path(path).name for path in out) == ["a.milk", "b.milk", "c.milk"]
    assert session.layers["layer_1"].preset_list == out
    # Seeded shuffle should not match sorted directory order.
    assert [Path(path).name for path in out] != ["a.milk", "b.milk", "c.milk"]


def test_populate_from_directory_sequential_keeps_sorted_order(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path, trigger="timer")
    browse = session.layers["layer_1"].playlist.current_dir
    for name in ("c.milk", "a.milk", "b.milk"):
        (browse / name).write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_directory(
            session,
            "layer_1",
            project_dir=tmp_path,
            order="sequential",
            rng=random.Random(0),
        )
    assert [Path(path).name for path in out] == ["a.milk", "b.milk", "c.milk"]


def test_populate_from_directory_sequential_respects_max_count(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path, trigger="timer")
    browse = session.layers["layer_1"].playlist.current_dir
    for name in ("a.milk", "b.milk", "c.milk", "d.milk", "e.milk"):
        (browse / name).write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_directory(
            session,
            "layer_1",
            project_dir=tmp_path,
            max_count=2,
            order="sequential",
            rng=random.Random(0),
        )
    assert [Path(path).name for path in out] == ["a.milk", "b.milk"]


def test_populate_from_directory_respects_max_count(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timer")
    browse = session.layers["layer_1"].playlist.current_dir
    for name in ("a.milk", "b.milk", "c.milk", "d.milk", "e.milk"):
        (browse / name).write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_directory(
            session,
            "layer_1",
            project_dir=tmp_path,
            max_count=2,
            order="random",
            rng=random.Random(0),
        )
    assert len(out) == 2
    assert len(set(out)) == 2


def test_populate_from_directory_timeline_trigger_one_per_segment(
    tmp_path: Path,
) -> None:
    session = _session(
        tmp_path,
        trigger="timeline",
        timeline_enabled=False,
        cues=(
            SlotCue(t=1.0, level=1.0),
            SlotCue(t=2.0, level=0.0),
            SlotCue(t=3.0, level=1.0),
        ),
    )
    browse = session.layers["layer_1"].playlist.current_dir
    (browse / "a.milk").write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_directory(
            session,
            "layer_1",
            project_dir=tmp_path,
            order="random",
            rng=random.Random(0),
        )
    assert len(out) == 2


def test_populate_from_directory_timeline_sequential_cycles_sorted(
    tmp_path: Path,
) -> None:
    session = _session(
        tmp_path,
        trigger="timeline",
        timeline_enabled=True,
        cues=(
            SlotCue(t=1.0, level=1.0),
            SlotCue(t=2.0, level=0.0),
            SlotCue(t=3.0, level=1.0),
            SlotCue(t=4.0, level=0.0),
            SlotCue(t=5.0, level=1.0),
        ),
    )
    browse = session.layers["layer_1"].playlist.current_dir
    for name in ("b.milk", "a.milk"):
        (browse / name).write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_directory(
            session,
            "layer_1",
            project_dir=tmp_path,
            order="sequential",
            rng=random.Random(0),
        )
    assert [Path(path).name for path in out] == ["a.milk", "b.milk", "a.milk"]


def test_populate_from_cue_marker_roles(tmp_path: Path) -> None:
    session = _session(
        tmp_path,
        trigger="timeline",
        timeline_enabled=True,
        cues=(
            SlotCue(t=1.0, level=1.0, role="pulse"),
            SlotCue(t=2.0, level=0.0),
            SlotCue(t=3.0, level=1.0, role="lead"),
        ),
    )
    library = PresetLibrary.in_memory()
    pack = tmp_path / "presets" / "role_pack"
    pack.mkdir(parents=True)
    for role in ("pulse", "lead"):
        (pack / f"{role}.milk").write_text(f"MILK {role}")
    library.index(tmp_path / "presets")
    for role in ("pulse", "lead"):
        library.set_role(pack / f"{role}.milk", role)
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_cue_marker_roles(
            session,
            "layer_1",
            project_dir=tmp_path,
            catalog=library,
            rng=random.Random(0),
        )
    assert [Path(path).name for path in out] == ["pulse.milk", "lead.milk"]


def test_repopulate_preset_lists_cue_roles(tmp_path: Path) -> None:
    session = _session(
        tmp_path,
        trigger="timeline",
        timeline_enabled=True,
        cues=(SlotCue(t=1.0, level=1.0, role="accent"),),
    )
    library = PresetLibrary.in_memory()
    pack = tmp_path / "presets" / "role_pack"
    pack.mkdir(parents=True)
    (pack / "accent.milk").write_text("MILK")
    library.index(tmp_path / "presets")
    library.set_role(pack / "accent.milk", "accent")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        repopulate_preset_lists(
            session,
            mode="cue roles",
            project_dir=tmp_path,
            catalog=library,
            rng=random.Random(0),
        )
    assert Path(session.layers["layer_1"].preset_list[0]).name == "accent.milk"


def test_repopulate_skips_layers_with_switching_off(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timeline", timeline_enabled=True)
    session.layers["layer_1"].preset_switching = "off"
    browse = session.layers["layer_1"].playlist.current_dir
    (browse / "a.milk").write_text("MILK")
    repopulate_preset_lists(
        session,
        mode="directory random",
        project_dir=tmp_path,
        catalog=UNFILTERED_CATALOG,
        rng=random.Random(0),
    )
    assert session.layers["layer_1"].preset_list == []


def test_repopulate_skips_non_timeline_trigger(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timer", timeline_enabled=True)
    browse = session.layers["layer_1"].playlist.current_dir
    (browse / "a.milk").write_text("MILK")
    repopulate_preset_lists(
        session,
        mode="directory random",
        project_dir=tmp_path,
        catalog=UNFILTERED_CATALOG,
        rng=random.Random(0),
    )
    assert session.layers["layer_1"].preset_list == []


def test_populate_records_where_each_copy_came_from(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timer")
    browse = session.layers["layer_1"].playlist.current_dir
    (browse / "a.milk").write_text("MILK")
    out = populate_from_directory(
        session, "layer_1", project_dir=tmp_path / "project", order="sequential"
    )
    assert [entry.source for entry in out] == [str((browse / "a.milk").resolve())]
    assert Path(out[0].path).parent == (tmp_path / "project" / "presets").resolve()


def test_kept_list_loops_its_presets_over_more_clips() -> None:
    a, b = PresetListEntry("a.milk"), PresetListEntry("b.milk")
    assert kept_list_for_clips([a, b], 5) == [a, b, a, b, a]
    # Fewer clips leave the rest as spares; repeats from a loop fold back.
    assert kept_list_for_clips([a, b, a, b, a], 1) == [a, b]
    assert kept_list_for_clips([], 3) == []


def test_repopulate_keep_loops_the_layers_own_list(tmp_path: Path) -> None:
    cues = tuple(SlotCue(t=float(t), level=1.0, cut="hard") for t in range(0, 50, 10))
    session = _session(tmp_path, trigger="timeline", timeline_enabled=True, cues=cues)
    a, b = PresetListEntry("a.milk"), PresetListEntry("b.milk")
    session.layers["layer_1"].preset_list = [a, b]
    repopulate_preset_lists(
        session,
        mode="keep",
        project_dir=tmp_path,
        catalog=UNFILTERED_CATALOG,
        rng=random.Random(0),
    )
    listed = session.layers["layer_1"].preset_list
    assert listed[:2] == [a, b]
    assert set(listed) == {a, b}
    assert len(listed) >= 2


def test_repopulate_keep_fills_an_empty_list_from_the_folder(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timeline", timeline_enabled=True)
    browse = session.layers["layer_1"].playlist.current_dir
    (browse / "a.milk").write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        repopulate_preset_lists(
            session,
            mode="keep",
            project_dir=tmp_path,
            catalog=UNFILTERED_CATALOG,
            rng=random.Random(0),
        )
    assert [Path(e).name for e in session.layers["layer_1"].preset_list] == ["a.milk"]
