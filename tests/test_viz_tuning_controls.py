"""Unit-style tests for live tuning controls (no Milkdrop window)."""

from __future__ import annotations

import io
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pygame

from cleave.preset_playlist import (
    PresetPlaylist,
    directory_display,
    playlist_at_dir,
    preset_browse_floor,
    preset_filename_display,
    scan_preset_playlist,
)
from cleave.viz_playback import PlaybackState, format_mmss
from cleave.viz_tuning_controls import (
    LayerRuntime,
    SEEK_LONG,
    SEEK_SHORT,
    TOAST_DURATION_SEC,
    TuningControls,
    TuningSession,
    _REPEAT_ROW_KINDS,
    allow_overwrite_for_path,
    config_path_display,
)
from cleave.viz_theme import (
    CONFIG_HEADER_TEXT,
    HIGHLIGHT,
    LOCK_TEXT,
    MOVE_MODE,
    PANEL_CONTENT_MAX_WIDTH,
    TEXT,
    TEXT_DIM,
)
from cleave.viz_material_icons import (
    FILE_GLYPH,
    FOLDER_GLYPH,
    LOCK_GLYPH,
    VISIBILITY_GLYPH,
    VISIBILITY_OFF_GLYPH,
    render_glyph,
    render_transport_icons,
    row_icon_prefix_width,
    track_header_lock_suffix_width,
    visibility_icon_prefix_width,
)
from cleave.viz_tuning_overlay import (
    find_row,
    RowKind,
    TrackBlock,
    TuningViewState,
    TREE_INDENT,
    _row_bg_color,
    _row_indent,
    _row_text,
    _row_text_color,
    fit_row_text,
    navigable_row_indices,
    quick_nav_row_indices,
    row_count,
    row_kind,
    row_stem,
    row_visible,
    visible_row_indices,
)


def _keydown(key: int, *, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def _overlay_font() -> pygame.font.Font:
    pygame.font.init()
    return pygame.font.SysFont("monospace", 14)


def _make_playlist(name: str, count: int = 3) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{name}")
    paths = tuple(current_dir / f"preset-{i}.milk" for i in range(count))
    return PresetPlaylist(current_dir=current_dir, paths=paths, index=0)


_REPO_ROOT_EXAMPLE = Path("/tmp/cleave.config.yaml")
_DEFAULT_ACTIVE_CONFIG = Path("/tmp/saved-cleave-configs/active.yaml")


def _make_controls(
    stems: tuple[str, ...] = ("drums", "bass"),
    *,
    launch_config_path: Path | None = _DEFAULT_ACTIVE_CONFIG,
    repo_root_example: Path = _REPO_ROOT_EXAMPLE,
) -> TuningControls:
    preset_root = Path("/tmp/presets")
    session = TuningSession(
        layer_z_order=list(stems),
        layers={
            stem: LayerRuntime(
                playlist=_make_playlist(stem),
                browse_floor=preset_root / stem,
                opacity_pct=50,
            )
            for stem in stems
        },
    )
    return TuningControls(
        session,
        preset_root=preset_root,
        playback=PlaybackState(),
        duration_sec=120.0,
        launch_config_path=launch_config_path,
        repo_root_example=repo_root_example,
    )


def _row(
    view: TuningViewState,
    stem: str,
    kind: RowKind,
    *,
    effect_id: str | None = None,
    driver_slug: str | None = None,
) -> int:
    return find_row(view, stem, kind, effect_id=effect_id, driver_slug=driver_slug)


def test_allow_overwrite_for_path_hides_repo_root_template_only() -> None:
    root = Path("/repo/cleave.config.yaml")
    assert allow_overwrite_for_path(root, repo_root_example=root) is False
    assert (
        allow_overwrite_for_path(
            Path("/repo/saved-cleave-configs/foo.yaml"),
            repo_root_example=root,
        )
        is True
    )
    assert allow_overwrite_for_path(None, repo_root_example=root) is False


def test_focus_navigation_wraps() -> None:
    controls = _make_controls(("a", "b"))
    view = controls.build_view_state(paused=False)
    navigable = navigable_row_indices(view)
    assert controls.focus_index == 0

    for _ in range(len(navigable) - 1):
        assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
    assert controls.focus_index == navigable[-1]

    assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
    assert controls.focus_index == 0

    assert controls.handle_keydown(_keydown(pygame.K_UP)) is True
    assert controls.focus_index == navigable[-1]


def test_opacity_clamps() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    opacity_row = _row(view, "drums", RowKind.TRACK_OPACITY)
    controls.focus_index = opacity_row

    for _ in range(60):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].opacity_pct == 100

    for _ in range(120):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["drums"].opacity_pct == 0


def test_header_toggles_enabled() -> None:
    enabled_events: list[tuple[str, bool]] = []
    controls = _make_controls(("drums",))
    controls._on_layer_enabled_change = lambda stem, on: enabled_events.append(
        (stem, on)
    )

    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    controls.focus_index = header_row
    assert controls.session.layers["drums"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].enabled is False
    assert enabled_events == [("drums", False)]
    assert controls.session.layers["drums"].opacity_pct == 50

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].enabled is True
    assert enabled_events == [("drums", False), ("drums", True)]
    assert controls.session.layers["drums"].opacity_pct == 50


def test_navigation_skips_sub_rows_when_collapsed() -> None:
    controls = _make_controls(("drums", "bass"))
    controls.session.layers["drums"].enabled = False
    controls.session.layers["drums"].expanded = False
    view = controls.build_view_state(paused=False)

    drums_header = next(
        i
        for i in range(12)
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "drums"
    )
    bass_header = next(
        i
        for i in range(12)
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "bass"
    )
    navigable = navigable_row_indices(view)
    assert drums_header in navigable
    assert bass_header in navigable
    for i in navigable:
        stem = row_stem(view, i)
        if stem == "drums":
            assert row_kind(view, i) == RowKind.TRACK_HEADER

    controls.focus_index = drums_header
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == bass_header


def test_re_enable_allows_sub_row_focus() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].enabled = False
    controls.session.layers["drums"].expanded = False
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "drums", RowKind.TRACK_PRESET_DIR)
    transport_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.TRANSPORT
    )
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == transport_row

    controls.focus_index = header_row
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == preset_dir_row


def test_header_collapses_and_expands_sub_rows() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "drums", RowKind.TRACK_PRESET_DIR)
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["drums"].expanded is False
    assert controls.focus_index == header_row

    view = controls.build_view_state(paused=False)
    assert preset_dir_row not in navigable_row_indices(view)
    assert preset_dir_row not in visible_row_indices(view)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].expanded is True

    view = controls.build_view_state(paused=False)
    assert preset_dir_row in navigable_row_indices(view)
    assert preset_dir_row in visible_row_indices(view)


def test_disable_auto_collapses_sub_rows() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "drums", RowKind.TRACK_PRESET_DIR)
    controls.focus_index = header_row
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == preset_dir_row

    controls.focus_index = header_row
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].enabled is False
    assert controls.session.layers["drums"].expanded is False
    assert controls.focus_index == header_row

    view = controls.build_view_state(paused=False)
    assert not row_visible(view, preset_dir_row)
    assert preset_dir_row not in visible_row_indices(view)


def test_disabled_track_can_expand_sub_rows() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "drums", RowKind.TRACK_PRESET_DIR)
    controls.focus_index = header_row
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].enabled is False
    assert controls.session.layers["drums"].expanded is False

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].enabled is False
    assert controls.session.layers["drums"].expanded is True

    view = controls.build_view_state(paused=False)
    assert preset_dir_row in visible_row_indices(view)
    assert preset_dir_row in navigable_row_indices(view)

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == preset_dir_row


def test_beat_sensitivity_clamps() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    beat_row = _row(view, "drums", RowKind.TRACK_BEAT)
    controls.focus_index = beat_row

    for _ in range(300):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].beat_sensitivity == 2.0

    for _ in range(300):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["drums"].beat_sensitivity == 0.0


def test_opacity_ctrl_step_is_ten_percent() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    opacity_row = _row(view, "drums", RowKind.TRACK_OPACITY)
    controls.focus_index = opacity_row
    controls.session.layers["drums"].opacity_pct = 50

    controls.handle_keydown(
        _keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL),
    )
    assert controls.session.layers["drums"].opacity_pct == 60

    controls.handle_keydown(
        _keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL),
    )
    assert controls.session.layers["drums"].opacity_pct == 50


def test_move_mode_swaps_z_order() -> None:
    z_orders: list[list[str]] = []
    controls = _make_controls(("drums", "bass", "vocals"))
    controls._on_z_order_change = lambda order: z_orders.append(list(order))

    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(15)
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "bass"
    )
    controls.focus_index = header_row

    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    assert controls.move_mode_stem == "bass"

    assert controls.handle_keydown(_keydown(pygame.K_UP)) is True
    assert controls.session.layer_z_order == ["bass", "drums", "vocals"]

    assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
    assert controls.session.layer_z_order == ["drums", "bass", "vocals"]

    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    assert controls.move_mode_stem is None
    assert z_orders == [["drums", "bass", "vocals"]]


def test_move_mode_esc_cancels_without_applying() -> None:
    z_orders: list[list[str]] = []
    controls = _make_controls(("drums", "bass", "vocals"))
    controls._on_z_order_change = lambda order: z_orders.append(list(order))

    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(15)
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "bass"
    )
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    controls.handle_keydown(_keydown(pygame.K_UP))
    assert controls.session.layer_z_order == ["bass", "drums", "vocals"]

    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert controls.move_mode_stem is None
    assert controls.session.layer_z_order == ["drums", "bass", "vocals"]
    assert z_orders == []


def test_move_mode_backspace_cancels_without_applying() -> None:
    z_orders: list[list[str]] = []
    controls = _make_controls(("drums", "bass", "vocals"))
    controls._on_z_order_change = lambda order: z_orders.append(list(order))

    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(15)
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "bass"
    )
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.session.layer_z_order == ["drums", "vocals", "bass"]

    assert controls.handle_keydown(_keydown(pygame.K_BACKSPACE)) is True
    assert controls.move_mode_stem is None
    assert controls.session.layer_z_order == ["drums", "bass", "vocals"]
    assert z_orders == []


def test_save_as_new_triggers_toast_and_blocks_input() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    save_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.SAVE_AS_NEW_CONFIG
    )
    assert _row_text(view, save_row) == "SAVE AS NEW CONFIG"
    controls.focus_index = save_row

    stderr = io.StringIO()
    with patch.object(time, "monotonic", return_value=1000.0):
        with patch("sys.stderr", stderr):
            assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True

        assert "Config saved to unnamed-1.cleave.config.yaml" in stderr.getvalue()
        state = controls.build_view_state(paused=False)
        assert state.toast_message == "Config saved to unnamed-1.cleave.config.yaml"
        assert state.toast_remaining_sec == TOAST_DURATION_SEC

        before = controls.focus_index
        assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
        assert controls.focus_index == before


def test_config_header_shows_active_path() -> None:
    launch_path = Path("/tmp/saved-cleave-configs/my-track.yaml")
    controls = _make_controls(("drums",))
    controls._active_config_path = launch_path
    view = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.CONFIG_HEADER
    )
    assert _row_text(view, header_row) == config_path_display(launch_path)
    assert header_row not in navigable_row_indices(view)


def test_config_header_truncates_long_paths() -> None:
    long_path = Path(
        "/very/long/root/saved-cleave-configs/nested/deep/unnamed-99.cleave.config.yaml"
    )
    controls = _make_controls(("drums",))
    controls._active_config_path = long_path
    view = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.CONFIG_HEADER
    )
    font = _overlay_font()
    label = fit_row_text(font, view, header_row)
    icon_budget = row_icon_prefix_width(font.get_linesize())
    assert font.size(label)[0] + icon_budget <= PANEL_CONTENT_MAX_WIDTH
    assert label.startswith("…")
    assert "…/" not in label


def test_preset_row_truncates_long_filenames() -> None:
    long_name = (
        "Phat_Zylot_Eo.S. rainbow bubble_mid3-starpoints_spirals_VE "
        "- Bitcore Tweak.milk (1/50)"
    )
    view = TuningViewState(
        layer_z_order=("drums",),
        tracks={
            "drums": TrackBlock(
                stem="drums",
                preset_dir_label="short (1/1)",
                preset_label=long_name,
                blend_mode="alpha",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                enabled=True,
                preset_empty=False,
            )
        },
        paused=False,
        position_sec=0.0,
        focus_index=0,
        move_mode_stem=None,
        toast_message=None,
        toast_remaining_sec=0.0,
    )
    preset_row = _row(view, "drums", RowKind.TRACK_PRESET)
    font = _overlay_font()
    label = fit_row_text(font, view, preset_row)
    assert font.size(label)[0] <= PANEL_CONTENT_MAX_WIDTH - 16
    assert label.endswith("(1/50)")
    assert label.startswith("…")
    assert "…/" not in label


def test_fit_row_text_config_and_preset_share_panel_width() -> None:
    long_path = Path(
        "/very/long/root/saved-cleave-configs/nested/deep/unnamed-99.cleave.config.yaml"
    )
    long_name = (
        "Phat_Zylot_Eo.S. rainbow bubble_mid3-starpoints_spirals_VE "
        "- Bitcore Tweak.milk (1/50)"
    )
    controls = _make_controls(("drums",))
    controls._active_config_path = long_path
    view = controls.build_view_state(paused=False)
    view.tracks["drums"] = TrackBlock(
        stem="drums",
        preset_dir_label="short (1/1)",
        preset_label=long_name,
        blend_mode="alpha",
        opacity_pct=50,
        beat_sensitivity=1.0,
        effects={},
        enabled=True,
        preset_empty=False,
    )
    header_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.CONFIG_HEADER
    )
    preset_row = _row(view, "drums", RowKind.TRACK_PRESET)
    font = _overlay_font()
    config_label = fit_row_text(font, view, header_row)
    preset_label = fit_row_text(font, view, preset_row)
    icon_budget = row_icon_prefix_width(font.get_linesize())
    assert font.size(config_label)[0] + icon_budget <= PANEL_CONTENT_MAX_WIDTH
    assert font.size(preset_label)[0] + TREE_INDENT + icon_budget <= PANEL_CONTENT_MAX_WIDTH


def test_save_as_new_updates_active_config_path() -> None:
    saved_path = Path("/tmp/saved-cleave-configs/unnamed-2.cleave.config.yaml")
    controls = _make_controls(("drums",))
    controls._on_save_new_config = lambda: saved_path

    view = controls.build_view_state(paused=False)
    save_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.SAVE_AS_NEW_CONFIG
    )
    controls.focus_index = save_row
    controls.handle_keydown(_keydown(pygame.K_RETURN))

    assert controls._active_config_path == saved_path
    state = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(row_count(state)) if row_kind(state, i) == RowKind.CONFIG_HEADER
    )
    assert _row_text(state, header_row) == config_path_display(saved_path)


def test_save_as_new_enables_overwrite_from_root_template() -> None:
    saved_path = Path("/tmp/saved-cleave-configs/unnamed-2.cleave.config.yaml")
    controls = _make_controls(
        ("drums",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    assert controls.build_view_state(paused=False).allow_overwrite is False

    controls._on_save_new_config = lambda: saved_path
    view = controls.build_view_state(paused=False)
    save_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.SAVE_AS_NEW_CONFIG
    )
    controls.focus_index = save_row
    controls.handle_keydown(_keydown(pygame.K_RETURN))

    state = controls.build_view_state(paused=False)
    assert state.allow_overwrite is True
    kinds = {row_kind(state, i) for i in range(row_count(state))}
    assert RowKind.OVERWRITE_CONFIG in kinds


def test_overwrite_after_save_uses_new_active_path() -> None:
    saved_path = Path("/tmp/saved-cleave-configs/unnamed-1.cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(
        ("drums",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    controls._on_save_new_config = lambda: saved_path
    controls._on_overwrite_config = lambda path: writes.append(path) or path.name

    view = controls.build_view_state(paused=False)
    save_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.SAVE_AS_NEW_CONFIG
    )

    with patch.object(time, "monotonic", return_value=3000.0):
        controls.focus_index = save_row
        controls.handle_keydown(_keydown(pygame.K_RETURN))

    with patch.object(time, "monotonic", return_value=3000.0 + TOAST_DURATION_SEC + 1):
        state = controls.build_view_state(paused=False)
        overwrite_row = next(
            i
            for i in range(row_count(state))
            if row_kind(state, i) == RowKind.OVERWRITE_CONFIG
        )
        controls.focus_index = overwrite_row
        controls.handle_keydown(_keydown(pygame.K_RETURN))
        controls.handle_keydown(_keydown(pygame.K_RETURN))

    assert writes == [saved_path]


def test_navigable_rows_without_overwrite() -> None:
    controls = _make_controls(
        ("drums",),
        launch_config_path=_REPO_ROOT_EXAMPLE,
        repo_root_example=_REPO_ROOT_EXAMPLE,
    )
    view = controls.build_view_state(paused=False)
    assert view.allow_overwrite is False
    assert row_count(view) == 10

    kinds = {row_kind(view, i) for i in range(row_count(view))}
    assert RowKind.CONFIG_HEADER in kinds
    assert RowKind.SAVE_AS_NEW_CONFIG in kinds
    assert RowKind.OVERWRITE_CONFIG not in kinds

    navigable = navigable_row_indices(view)
    assert all(row_kind(view, i) != RowKind.CONFIG_HEADER for i in navigable)
    assert all(row_kind(view, i) != RowKind.OVERWRITE_CONFIG for i in navigable)

    transport_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.TRANSPORT
    )
    save_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.SAVE_AS_NEW_CONFIG
    )
    controls.focus_index = transport_row
    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == save_row


def test_navigable_rows_with_overwrite() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    assert view.allow_overwrite is True
    assert row_count(view) == 11

    overwrite_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
    )
    assert overwrite_row in navigable_row_indices(view)


def test_overwrite_shows_confirm_before_write() -> None:
    launch_path = Path("/tmp/custom/cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("drums",), launch_config_path=launch_path)
    controls._on_overwrite_config = lambda path: (
        writes.append(path) or path.name
    )

    view = controls.build_view_state(paused=False)
    overwrite_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
    )
    controls.focus_index = overwrite_row

    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    state = controls.build_view_state(paused=False)
    assert state.confirm_message == "Overwrite cleave.config.yaml?"
    assert writes == []

    assert controls.handle_keydown(_keydown(pygame.K_n)) is True
    state = controls.build_view_state(paused=False)
    assert state.confirm_message == "Overwrite cleave.config.yaml?"
    assert state.confirm_focus_yes is False
    assert writes == []

    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    state = controls.build_view_state(paused=False)
    assert state.confirm_message is None
    assert writes == []


def test_overwrite_confirm_yes_writes_launch_path() -> None:
    launch_path = Path("/tmp/my-launch.cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("drums",))
    controls._active_config_path = launch_path
    controls._on_overwrite_config = lambda path: (
        writes.append(path) or path.name
    )

    view = controls.build_view_state(paused=False)
    overwrite_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
    )
    controls.focus_index = overwrite_row

    stderr = io.StringIO()
    with patch.object(time, "monotonic", return_value=2000.0):
        with patch("sys.stderr", stderr):
            controls.handle_keydown(_keydown(pygame.K_RETURN))
            controls.handle_keydown(_keydown(pygame.K_RETURN))

        assert writes == [launch_path]
        state = controls.build_view_state(paused=False)
        assert state.confirm_message is None
        assert state.toast_message == "Config overwritten: my-launch.cleave.config.yaml"
        assert "Config overwritten: my-launch.cleave.config.yaml" in stderr.getvalue()


def test_overwrite_confirm_esc_dismisses() -> None:
    launch_path = Path("/tmp/custom/cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("drums",), launch_config_path=launch_path)
    controls._on_overwrite_config = lambda path: (
        writes.append(path) or path.name
    )

    view = controls.build_view_state(paused=False)
    overwrite_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
    )
    controls.focus_index = overwrite_row

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    state = controls.build_view_state(paused=False)
    assert state.confirm_message is None
    assert writes == []


def test_esc_during_confirm_does_not_quit() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    overwrite_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
    )
    controls.focus_index = overwrite_row
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True


def test_ctrl_q_requests_quit() -> None:
    controls = _make_controls()
    assert controls.handle_keydown(
        _keydown(pygame.K_q, mod=pygame.KMOD_CTRL)
    ) is False


def test_q_alone_does_not_quit() -> None:
    controls = _make_controls()
    assert controls.handle_keydown(_keydown(pygame.K_q)) is True


def test_row_icons_render() -> None:
    line_height = 17
    color = (255, 255, 255)
    for glyph in (FOLDER_GLYPH, FILE_GLYPH, VISIBILITY_GLYPH, VISIBILITY_OFF_GLYPH):
        surf = render_glyph(glyph, color=color, line_height=line_height)
        assert surf.get_width() > 0
        assert surf.get_height() == line_height
        assert pygame.mask.from_surface(surf).count() > 0


def test_track_header_icons_render() -> None:
    line_height = 17
    header_color = (170, 210, 255)
    lock_color = (235, 90, 90)
    for glyph in (VISIBILITY_GLYPH, VISIBILITY_OFF_GLYPH):
        surf = render_glyph(glyph, color=header_color, line_height=line_height)
        assert surf.get_width() > 0
        assert surf.get_height() == line_height
        assert pygame.mask.from_surface(surf).count() > 0

    lock = render_glyph(LOCK_GLYPH, color=lock_color, line_height=line_height)
    assert lock.get_width() > 0
    assert visibility_icon_prefix_width(line_height) > lock.get_width()
    assert track_header_lock_suffix_width(line_height) > lock.get_width()


def test_track_header_text_omits_enabled_status() -> None:
    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    text = _row_text(view, header_row)
    assert text.startswith("Layer ")
    assert "enabled" not in text.lower()
    assert "disabled" not in text.lower()


def test_track_header_expand_arrow() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    assert _row_text(view, header_row).endswith(" ▼")

    controls.session.layers["drums"].expanded = False
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    assert _row_text(view, header_row).endswith(" ▶")


def test_track_header_visibility_icon_color() -> None:
    line_height = 17
    enabled = render_glyph(
        VISIBILITY_GLYPH, color=CONFIG_HEADER_TEXT, line_height=line_height
    )
    disabled = render_glyph(
        VISIBILITY_OFF_GLYPH, color=TEXT_DIM, line_height=line_height
    )
    assert enabled.get_width() > 0
    assert disabled.get_width() > 0
    assert enabled.get_at((enabled.get_width() // 2, line_height // 2))[:3] != (
        0,
        0,
        0,
    )
    assert disabled.get_at((disabled.get_width() // 2, line_height // 2))[:3] != (
        0,
        0,
        0,
    )


def test_transport_icons_render() -> None:
    s = render_transport_icons(color=(255, 255, 255), line_height=17, paused=False)
    assert s.get_width() > 0
    assert s.get_height() == 17
    assert pygame.mask.from_surface(s).count() > 50


def test_transport_icons_play_vs_pause() -> None:
    playing = render_transport_icons(color=(255, 255, 255), line_height=17, paused=False)
    paused = render_transport_icons(color=(255, 255, 255), line_height=17, paused=True)
    assert playing.get_width() == paused.get_width()

    w, h = playing.get_size()
    x0 = w // 3
    x1 = 2 * w // 3
    region_w = x1 - x0
    play_middle = pygame.Surface((region_w, h), pygame.SRCALPHA)
    pause_middle = pygame.Surface((region_w, h), pygame.SRCALPHA)
    play_middle.blit(playing, (0, 0), (x0, 0, region_w, h))
    pause_middle.blit(paused, (0, 0), (x0, 0, region_w, h))
    play_mask = pygame.mask.from_surface(play_middle)
    pause_mask = pygame.mask.from_surface(pause_middle)
    assert play_mask.count() > 0
    assert pause_mask.count() > 0
    overlap_px = play_mask.overlap_area(pause_mask, (0, 0))
    assert overlap_px < play_mask.count() or overlap_px < pause_mask.count()


def test_transport_enter_toggles_pause() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    transport_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.TRANSPORT
    )
    controls.focus_index = transport_row
    assert controls.playback.paused is False

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.playback.paused is True

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.playback.paused is False


def test_space_toggles_pause_from_any_focus() -> None:
    controls = _make_controls(("drums",))
    assert controls.playback.paused is False
    assert controls.focus_index == 0

    controls.handle_keydown(_keydown(pygame.K_SPACE))
    assert controls.playback.paused is True

    controls.handle_keydown(_keydown(pygame.K_SPACE))
    assert controls.playback.paused is False


def test_quick_nav_row_indices_headers_and_transport_only() -> None:
    controls = _make_controls(("drums", "bass"))
    controls.session.layers["drums"].enabled = False
    view = controls.build_view_state(paused=False)

    quick = quick_nav_row_indices(view)
    assert len(quick) == 3
    for index in quick:
        kind = row_kind(view, index)
        assert kind in (RowKind.TRACK_HEADER, RowKind.TRANSPORT)

    drums_header = next(
        i
        for i in range(row_count(view))
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "drums"
    )
    bass_header = next(
        i
        for i in range(row_count(view))
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "bass"
    )
    transport_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.TRANSPORT
    )
    assert quick == [drums_header, bass_header, transport_row]


def test_ctrl_quick_nav_cycles_headers_and_transport() -> None:
    controls = _make_controls(("drums", "bass"))
    view = controls.build_view_state(paused=False)
    quick = quick_nav_row_indices(view)

    controls.focus_index = quick[0]
    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[1]

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[2]

    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[0]

    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[2]


def test_ctrl_quick_nav_from_sub_row_jumps_forward() -> None:
    controls = _make_controls(("drums", "bass"))
    view = controls.build_view_state(paused=False)
    quick = quick_nav_row_indices(view)
    preset_row = next(
        i for i in range(12) if row_kind(view, i) == RowKind.TRACK_PRESET
    )

    controls.focus_index = preset_row
    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[1]

    controls.focus_index = preset_row
    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[0]


def test_ctrl_quick_nav_from_save_row() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    quick = quick_nav_row_indices(view)
    save_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.SAVE_AS_NEW_CONFIG
    )

    controls.focus_index = save_row
    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[-1]

    controls.focus_index = save_row
    controls.handle_keydown(_keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL))
    assert controls.focus_index == quick[0]


def test_ctrl_quick_nav_does_not_affect_normal_up_down() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "drums", RowKind.TRACK_PRESET_DIR)
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == preset_dir_row


def _write_milk(path: Path) -> None:
    path.write_text("milk")


def _make_sibling_dir_tree(
    count: int,
    *,
    child_name: str = "child",
    child_preset_count: int = 1,
) -> tuple[Path, tuple[Path, ...]]:
    """Return (preset_root, sibling_dirs) each with at least one .milk file."""
    tmp = tempfile.mkdtemp()
    root = Path(tmp)
    siblings: list[Path] = []
    for i in range(count):
        sibling = root / f"dir-{i:02d}"
        sibling.mkdir()
        for j in range(child_preset_count):
            _write_milk(sibling / f"preset-{j}.milk")
        siblings.append(sibling)
    if child_name:
        child = siblings[0] / child_name
        child.mkdir()
        _write_milk(child / "nested.milk")
    return root, tuple(siblings)


def _controls_with_playlist(
    root: Path,
    current_dir: Path,
    *,
    index: int = 0,
    browse_floor: Path | None = None,
) -> TuningControls:
    anchor = current_dir / "preset-0.milk"
    floor = browse_floor if browse_floor is not None else preset_browse_floor(
        anchor, root
    )
    session = TuningSession(
        layer_z_order=["drums"],
        layers={
            "drums": LayerRuntime(
                playlist=playlist_at_dir(current_dir, index=index),
                browse_floor=floor,
                opacity_pct=50,
            )
        },
    )
    return TuningControls(
        session,
        preset_root=root,
        playback=PlaybackState(),
        duration_sec=120.0,
    )


def _preset_dir_row(controls: TuningControls) -> int:
    view = controls.build_view_state(paused=False)
    return _row(view, "drums", RowKind.TRACK_PRESET_DIR)


def _preset_row(controls: TuningControls) -> int:
    view = controls.build_view_state(paused=False)
    return _row(view, "drums", RowKind.TRACK_PRESET)


def test_directory_row_lr_changes_current_dir() -> None:
    root, siblings = _make_sibling_dir_tree(3)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_index = _preset_dir_row(controls)
    playlist = controls.session.layers["drums"].playlist

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert playlist.current_dir.resolve() == siblings[1].resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_enter_descends_backspace_goes_parent() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_index = _preset_dir_row(controls)
    playlist = controls.session.layers["drums"].playlist
    child = siblings[0] / "child"

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_directory_ctrl_arrows_descend_and_ascend() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_index = _preset_dir_row(controls)
    playlist = controls.session.layers["drums"].playlist
    child = siblings[0] / "child"

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_ctrl_left_at_preset_root_is_noop() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_index = _preset_dir_row(controls)
    playlist = controls.session.layers["drums"].playlist

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == root.resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == root.resolve()


def test_directory_ctrl_arrows_do_not_repeat_parent_climb() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_index = _preset_dir_row(controls)
    playlist = controls.session.layers["drums"].playlist
    child = siblings[0] / "child"

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == child.resolve()

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.current_dir.resolve() == siblings[0].resolve()

    for _ in range(20):
        controls.tick(0.5)
    assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_backspace_at_preset_root_is_noop() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    controls = _controls_with_playlist(root, siblings[0])
    controls.focus_index = _preset_dir_row(controls)
    playlist = controls.session.layers["drums"].playlist

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()


def test_directory_parent_round_trip_reaches_preset_root() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    child = siblings[0] / "child"
    controls = _controls_with_playlist(root, child)
    controls.focus_index = _preset_dir_row(controls)
    playlist = controls.session.layers["drums"].playlist

    for _ in range(3):
        controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert playlist.current_dir.resolve() != root.resolve()

    controls.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert playlist.current_dir.resolve() == root.resolve()


def test_preset_lr_noop_when_paths_empty() -> None:
    root, siblings = _make_sibling_dir_tree(2)
    empty_dir = root / "empty"
    empty_dir.mkdir()
    controls = _controls_with_playlist(root, empty_dir)
    changed: list[tuple[str, int]] = []
    controls._on_preset_change = lambda stem, pl: changed.append((stem, pl.index))
    controls.focus_index = _preset_row(controls)
    playlist = controls.session.layers["drums"].playlist
    assert playlist.paths == ()

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert changed == []
    assert playlist.index == 0


def test_track_preset_dir_in_repeat_row_kinds() -> None:
    assert RowKind.TRACK_PRESET_DIR in _REPEAT_ROW_KINDS


def test_ctrl_preset_steps_by_ten_wrapping() -> None:
    changed: list[tuple[str, int]] = []
    controls = _make_controls(("drums",))
    current_dir = Path("/tmp/presets/drums")
    paths = tuple(current_dir / f"preset-{i:02d}.milk" for i in range(12))
    controls.session.layers["drums"].playlist = PresetPlaylist(
        current_dir=current_dir, paths=paths, index=5
    )
    controls._on_preset_change = lambda stem, pl: changed.append((stem, pl.index))

    view = controls.build_view_state(paused=False)
    preset_row = _row(view, "drums", RowKind.TRACK_PRESET)
    controls.focus_index = preset_row
    playlist = controls.session.layers["drums"].playlist

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert playlist.index == 3
    assert changed == [("drums", 3)]

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.index == 5
    assert changed[-1] == ("drums", 5)


def test_empty_playlist_view_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty_dir = root / "empty"
        empty_dir.mkdir()
        controls = _controls_with_playlist(root, empty_dir)
        view = controls.build_view_state(paused=False)
        block = view.tracks["drums"]
        assert block.preset_label == "NO PRESETS FOUND"
        assert block.preset_empty is True


def test_move_mode_colors_focused_track_header() -> None:
    controls = _make_controls(("drums", "bass"))
    view = controls.build_view_state(paused=False)
    header_row = next(
        i
        for i in range(row_count(view))
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "bass"
    )
    controls.focus_index = header_row
    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True

    view = controls.build_view_state(paused=False)
    child_row = header_row + 1
    assert _row_text_color(view, header_row) == MOVE_MODE
    assert _row_bg_color(view, header_row) == MOVE_MODE
    assert _row_text_color(view, child_row) == MOVE_MODE
    assert _row_bg_color(view, child_row) == MOVE_MODE


def test_row_text_color_dim_for_focused_empty_preset() -> None:
    state = TuningViewState(
        layer_z_order=("drums",),
        tracks={
            "drums": TrackBlock(
                stem="drums",
                preset_dir_label="empty (1/1)",
                preset_label="NO PRESETS FOUND",
                blend_mode="alpha",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                preset_empty=True,
            )
        },
        paused=False,
        position_sec=0.0,
        focus_index=0,
        move_mode_stem=None,
        toast_message=None,
        toast_remaining_sec=0.0,
    )
    preset_row = _row(state, "drums", RowKind.TRACK_PRESET)
    state = TuningViewState(
        layer_z_order=state.layer_z_order,
        tracks=state.tracks,
        paused=state.paused,
        position_sec=state.position_sec,
        focus_index=preset_row,
        move_mode_stem=state.move_mode_stem,
        toast_message=state.toast_message,
        toast_remaining_sec=state.toast_remaining_sec,
    )
    assert _row_text_color(state, preset_row) == TEXT_DIM
    assert _row_bg_color(state, preset_row) == HIGHLIGHT


def test_preset_overlay_shows_directory_and_position() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    block = view.tracks["drums"]
    assert block.preset_dir_label == "drums/ (1/1)"
    assert block.preset_label == "preset-0.milk (1/3)"

    controls.session.layers["drums"].playlist.index = 1
    view = controls.build_view_state(paused=False)
    assert view.tracks["drums"].preset_label == "preset-1.milk (2/3)"


def test_scan_file_anchor_builds_parent_directory_playlist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack" / "Aurora"
        preset_dir.mkdir(parents=True)
        first = preset_dir / "alpha.milk"
        second = preset_dir / "beta.milk"
        first.write_text("milk")
        second.write_text("milk")

        playlist = scan_preset_playlist(second)
        assert playlist.current_dir == preset_dir.resolve()
        assert playlist.paths == (first.resolve(), second.resolve())
        assert playlist.index == 1
        assert preset_filename_display(playlist) == "beta.milk (2/2)"
        assert directory_display(playlist, root) == "pack/Aurora/ (1/1)"


def _header_row(
    controls: TuningControls,
    stem: str,
    *,
    paused: bool = False,
) -> int:
    view = controls.build_view_state(paused=paused)
    return next(
        i
        for i in range(row_count(view))
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == stem
    )


def _sub_rows_for_stem(view: TuningViewState, stem: str) -> list[int]:
    sub_kinds = (
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.TRACK_EFFECT,
    )
    return [
        i
        for i in range(row_count(view))
        if row_stem(view, i) == stem and row_kind(view, i) in sub_kinds
    ]


def test_ctrl_enter_toggles_lock() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    controls.focus_index = header_row
    assert controls.session.layers["drums"].locked is False

    controls.handle_keydown(_keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].locked is True

    controls.handle_keydown(_keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].locked is False


def test_locked_expanded_skips_sub_rows_in_nav() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].locked = True
    controls.session.layers["drums"].expanded = True
    view = controls.build_view_state(paused=False)

    sub_rows = _sub_rows_for_stem(view, "drums")
    assert sub_rows
    visible = visible_row_indices(view)
    navigable = navigable_row_indices(view)
    effects_header = _row(view, "drums", RowKind.TRACK_EFFECTS_HEADER)
    assert effects_header in navigable
    for row in sub_rows:
        assert row in visible
        if row == effects_header:
            continue
        assert row not in navigable


def test_locked_blocks_enable_disable() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].locked = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    controls.focus_index = header_row
    assert controls.session.layers["drums"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["drums"].enabled is True


def test_locked_blocks_move_mode() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].locked = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.move_mode_stem is None


def test_locked_header_still_expands() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].locked = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "drums", RowKind.TRACK_PRESET_DIR)
    controls.focus_index = header_row
    assert controls.session.layers["drums"].expanded is True

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["drums"].expanded is False

    view = controls.build_view_state(paused=False)
    assert preset_dir_row not in visible_row_indices(view)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].expanded is True

    view = controls.build_view_state(paused=False)
    assert preset_dir_row in visible_row_indices(view)


def test_locked_sub_rows_dimmed() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].locked = True
    controls.session.layers["drums"].expanded = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_HEADER)
    preset_dir_row = _row(view, "drums", RowKind.TRACK_PRESET_DIR)
    unfocused = TuningViewState(
        layer_z_order=view.layer_z_order,
        tracks=view.tracks,
        paused=view.paused,
        position_sec=view.position_sec,
        focus_index=row_count(view) - 1,
        move_mode_stem=view.move_mode_stem,
        toast_message=view.toast_message,
        toast_remaining_sec=view.toast_remaining_sec,
        active_config_label=view.active_config_label,
        allow_overwrite=view.allow_overwrite,
        confirm_message=view.confirm_message,
        confirm_focus_yes=view.confirm_focus_yes,
    )
    assert _row_text_color(unfocused, header_row) == TEXT
    assert _row_text_color(unfocused, preset_dir_row) == LOCK_TEXT

    focused_header = TuningViewState(
        layer_z_order=view.layer_z_order,
        tracks=view.tracks,
        paused=view.paused,
        position_sec=view.position_sec,
        focus_index=header_row,
        move_mode_stem=view.move_mode_stem,
        toast_message=view.toast_message,
        toast_remaining_sec=view.toast_remaining_sec,
        active_config_label=view.active_config_label,
        allow_overwrite=view.allow_overwrite,
        confirm_message=view.confirm_message,
        confirm_focus_yes=view.confirm_focus_yes,
    )
    assert _row_text_color(focused_header, header_row) == HIGHLIGHT
    assert _row_text_color(focused_header, preset_dir_row) == LOCK_TEXT


def test_locked_not_toggleable_during_move_mode() -> None:
    controls = _make_controls(("drums", "bass"))
    view = controls.build_view_state(paused=False)
    bass_header = _header_row(controls, "bass")
    controls.focus_index = bass_header
    assert controls.session.layers["bass"].locked is False

    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.move_mode_stem == "bass"

    controls.handle_keydown(_keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL))
    assert controls.session.layers["bass"].locked is False


def test_ctrl_quick_nav_blocked_during_move_mode() -> None:
    controls = _make_controls(("drums", "bass", "vocals"))
    view = controls.build_view_state(paused=False)
    bass_header = next(
        i
        for i in range(15)
        if row_kind(view, i) == RowKind.TRACK_HEADER and row_stem(view, i) == "bass"
    )
    controls.focus_index = bass_header
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.move_mode_stem == "bass"

    controls.handle_keydown(_keydown(pygame.K_UP, mod=pygame.KMOD_CTRL))
    assert controls.session.layer_z_order == ["bass", "drums", "vocals"]
    assert controls.focus_index == bass_header


def test_transport_seek_constants() -> None:
    seeks: list[float] = []
    controls = _make_controls(("drums",))
    controls._on_seek = lambda delta: seeks.append(delta)

    view = controls.build_view_state(paused=False)
    transport_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.TRANSPORT
    )
    controls.focus_index = transport_row

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))

    assert seeks == [SEEK_SHORT, -SEEK_SHORT, SEEK_LONG, -SEEK_LONG]


def test_effect_pulse_clamps() -> None:
    controls = _make_controls(("drums", "bass"))
    controls.session.layers["drums"].effects_expanded = True
    controls.session.layers["bass"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    pulse_row = _row(
        view, "drums", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    )
    bass_pulse_row = _row(
        view, "bass", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="sub_bass"
    )
    controls.focus_index = pulse_row

    for _ in range(120):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].effects["pulse"]["onset"] == 100

    for _ in range(120):
        controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert "pulse" not in controls.session.layers["drums"].effects

    controls.focus_index = bass_pulse_row
    for _ in range(20):
        controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["bass"].effects["pulse"]["sub_bass"] == 20


def test_effect_pulse_row_label() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].effects = {"pulse": {"onset": 35}}
    controls.session.layers["drums"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    pulse_row = _row(
        view, "drums", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    )
    assert _row_text(view, pulse_row) == "└─ pulse (onset): 35%"


def test_effects_header_expand_arrow() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_EFFECTS_HEADER)
    assert _row_text(view, header_row) == "└─ cleave effects ▶"

    controls.session.layers["drums"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    header_row = _row(view, "drums", RowKind.TRACK_EFFECTS_HEADER)
    assert _row_text(view, header_row) == "└─ cleave effects ▼"


def test_effect_row_nested_indent() -> None:
    controls = _make_controls(("drums",))
    controls.session.layers["drums"].effects_expanded = True
    view = controls.build_view_state(paused=False)
    effects_header = _row(view, "drums", RowKind.TRACK_EFFECTS_HEADER)
    pulse_row = _row(
        view, "drums", RowKind.TRACK_EFFECT, effect_id="pulse", driver_slug="onset"
    )
    assert _row_indent(view, effects_header) == TREE_INDENT
    assert _row_indent(view, pulse_row) == TREE_INDENT * 2


def test_format_mmss() -> None:
    assert format_mmss(0) == "00:00"
    assert format_mmss(42.7) == "00:42"
    assert format_mmss(222) == "03:42"
    assert format_mmss(-5) == "00:00"


def main() -> int:
    pygame.init()
    tests = [
        test_allow_overwrite_for_path_hides_repo_root_template_only,
        test_focus_navigation_wraps,
        test_opacity_clamps,
        test_beat_sensitivity_clamps,
        test_header_toggles_enabled,
        test_navigation_skips_sub_rows_when_collapsed,
        test_disabled_track_can_expand_sub_rows,
        test_re_enable_allows_sub_row_focus,
        test_header_collapses_and_expands_sub_rows,
        test_disable_auto_collapses_sub_rows,
        test_opacity_ctrl_step_is_ten_percent,
        test_effect_pulse_clamps,
        test_effect_pulse_row_label,
        test_move_mode_swaps_z_order,
        test_move_mode_esc_cancels_without_applying,
        test_move_mode_backspace_cancels_without_applying,
        test_move_mode_colors_focused_track_header,
        test_save_as_new_triggers_toast_and_blocks_input,
        test_config_header_shows_active_path,
        test_config_header_truncates_long_paths,
        test_preset_row_truncates_long_filenames,
        test_fit_row_text_config_and_preset_share_panel_width,
        test_save_as_new_updates_active_config_path,
        test_save_as_new_enables_overwrite_from_root_template,
        test_overwrite_after_save_uses_new_active_path,
        test_navigable_rows_without_overwrite,
        test_navigable_rows_with_overwrite,
        test_overwrite_shows_confirm_before_write,
        test_overwrite_confirm_yes_writes_launch_path,
        test_overwrite_confirm_esc_dismisses,
        test_esc_during_confirm_does_not_quit,
        test_ctrl_q_requests_quit,
        test_q_alone_does_not_quit,
        test_row_icons_render,
        test_track_header_icons_render,
        test_track_header_text_omits_enabled_status,
        test_track_header_expand_arrow,
        test_track_header_visibility_icon_color,
        test_transport_icons_render,
        test_transport_icons_play_vs_pause,
        test_format_mmss,
        test_transport_enter_toggles_pause,
        test_space_toggles_pause_from_any_focus,
        test_transport_seek_constants,
        test_quick_nav_row_indices_headers_and_transport_only,
        test_ctrl_quick_nav_cycles_headers_and_transport,
        test_ctrl_quick_nav_from_sub_row_jumps_forward,
        test_ctrl_quick_nav_from_save_row,
        test_ctrl_quick_nav_does_not_affect_normal_up_down,
        test_directory_row_lr_changes_current_dir,
        test_directory_enter_descends_backspace_goes_parent,
        test_directory_ctrl_arrows_descend_and_ascend,
        test_ctrl_left_at_preset_root_is_noop,
        test_directory_ctrl_arrows_do_not_repeat_parent_climb,
        test_backspace_at_preset_root_is_noop,
        test_directory_parent_round_trip_reaches_preset_root,
        test_preset_lr_noop_when_paths_empty,
        test_track_preset_dir_in_repeat_row_kinds,
        test_ctrl_preset_steps_by_ten_wrapping,
        test_empty_playlist_view_state,
        test_row_text_color_dim_for_focused_empty_preset,
        test_preset_overlay_shows_directory_and_position,
        test_scan_file_anchor_builds_parent_directory_playlist,
        test_ctrl_quick_nav_blocked_during_move_mode,
        test_ctrl_enter_toggles_lock,
        test_locked_expanded_skips_sub_rows_in_nav,
        test_locked_blocks_enable_disable,
        test_locked_blocks_move_mode,
        test_locked_header_still_expands,
        test_locked_sub_rows_dimmed,
        test_locked_not_toggleable_during_move_mode,
    ]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
