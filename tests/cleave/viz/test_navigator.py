"""Navigator model: top-level ids, badges, and preset-curation visibility."""

from __future__ import annotations

from cleave.viz.navigator import TOP_LEVEL_IDS, build_navigator, visible_top_level_ids
from cleave.viz.session import TuningSession


def _session() -> TuningSession:
    return TuningSession(layer_z_order=[])


def test_top_level_ids_in_order() -> None:
    session = _session()
    nodes = build_navigator(session)

    assert TOP_LEVEL_IDS == (
        "settings",
        "project",
        "render",
        "layers",
        "song_markers",
    )
    assert visible_top_level_ids(session) == TOP_LEVEL_IDS
    assert tuple(node.id for node in nodes) == TOP_LEVEL_IDS
    assert tuple(node.label for node in nodes) == (
        "Settings",
        "Project",
        "Render",
        "Layers",
        "Song markers",
    )
    assert all(node.depth == 0 for node in nodes)
    assert tuple(node.has_inspector for node in nodes) == (
        True,
        True,
        False,
        False,
        False,
    )
    assert nodes[0].badge is None
    assert nodes[1].badge is None
    assert nodes[2].badge is None
    assert nodes[3].badge is None


def test_song_markers_badge_is_marker_count() -> None:
    empty = _session()
    assert build_navigator(empty)[-1].badge == "0"

    session = _session()
    session.song_markers.times = [1.0, 4.5, 9.0]
    nodes = build_navigator(session)
    assert nodes[-1].id == "song_markers"
    assert nodes[-1].badge == "3"


def test_preset_curation_omits_project_render_and_song_markers() -> None:
    session = _session()
    session.settings.editor_mode = "preset_curation"
    nodes = build_navigator(session)

    assert visible_top_level_ids(session) == ("settings", "layers")
    assert tuple(node.id for node in nodes) == ("settings", "layers")
    assert tuple(node.label for node in nodes) == ("Settings", "Layers")
    assert nodes[0].has_inspector is True
    assert nodes[1].has_inspector is False
    assert all(node.badge is None for node in nodes)
    assert all(node.depth == 0 for node in nodes)
