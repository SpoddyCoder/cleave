"""Tests for preset list populate helpers."""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import patch

from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.preset_list_populate import (
    auto_populate_for_reshuffle,
    needed_preset_count,
    populate_from_cue_marker_roles,
    populate_from_directory,
)
from cleave.viz.session import LayerRuntime, TuningSession


def _session(
    tmp: Path,
    *,
    timeline_enabled: bool = False,
    trigger: str = "timer",
    conductor: bool = False,
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
    session.timeline.timeline_preset_conductor = conductor
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
    for role in ("pulse", "lead"):
        role_dir = tmp_path / "presets" / "roles" / role
        role_dir.mkdir(parents=True)
        (role_dir / f"{role}.milk").write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        out = populate_from_cue_marker_roles(
            session,
            "layer_1",
            project_dir=tmp_path,
            preset_root=tmp_path / "presets",
            rng=random.Random(0),
        )
    assert [Path(path).name for path in out] == ["pulse.milk", "lead.milk"]


def test_auto_populate_for_reshuffle_uses_roles_when_conductor(tmp_path: Path) -> None:
    session = _session(
        tmp_path,
        trigger="timeline",
        timeline_enabled=True,
        conductor=True,
        cues=(SlotCue(t=1.0, level=1.0, role="accent"),),
    )
    role_dir = tmp_path / "presets" / "roles" / "accent"
    role_dir.mkdir(parents=True)
    (role_dir / "accent.milk").write_text("MILK")
    with patch(
        "cleave.viz.preset_list_populate.copy_with_dedup",
        side_effect=lambda dest, src: dest / src.name,
    ):
        auto_populate_for_reshuffle(
            session,
            project_dir=tmp_path,
            preset_root=tmp_path / "presets",
            rng=random.Random(0),
        )
    assert Path(session.layers["layer_1"].preset_list[0]).name == "accent.milk"


def test_auto_populate_skips_layers_with_switching_off(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timeline", timeline_enabled=True)
    session.layers["layer_1"].preset_switching = "off"
    auto_populate_for_reshuffle(
        session,
        project_dir=tmp_path,
        preset_root=tmp_path / "presets",
        rng=random.Random(0),
    )
    assert session.layers["layer_1"].preset_list == []


def test_auto_populate_skips_non_timeline_trigger(tmp_path: Path) -> None:
    session = _session(tmp_path, trigger="timer", timeline_enabled=True)
    browse = session.layers["layer_1"].playlist.current_dir
    (browse / "a.milk").write_text("MILK")
    auto_populate_for_reshuffle(
        session,
        project_dir=tmp_path,
        preset_root=tmp_path / "presets",
        rng=random.Random(0),
    )
    assert session.layers["layer_1"].preset_list == []
