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
)
from cleave.viz_tuning_overlay import (
    RowKind,
    TuningOverlay,
    _glyph_renders_real_shape,
    _resolve_transport_icons,
    _row_text,
    _unicode_transport_available,
    navigable_row_indices,
    quick_nav_row_indices,
    row_count,
    row_kind,
    row_stem,
)


def _keydown(key: int, *, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def _make_playlist(name: str, count: int = 3) -> PresetPlaylist:
    anchor = Path(f"/tmp/presets/{name}")
    paths = tuple(anchor / f"preset-{i}.milk" for i in range(count))
    return PresetPlaylist(anchor=anchor, paths=paths, index=0)


def _make_controls(
    stems: tuple[str, ...] = ("drums", "bass"),
    *,
    allow_overwrite: bool = True,
) -> TuningControls:
    session = TuningSession(
        layer_z_order=list(stems),
        layers={
            stem: LayerRuntime(playlist=_make_playlist(stem), opacity_pct=50)
            for stem in stems
        },
    )
    return TuningControls(
        session,
        preset_root=Path("/tmp/presets"),
        playback=PlaybackState(),
        duration_sec=120.0,
        allow_overwrite=allow_overwrite,
    )


def test_focus_navigation_wraps() -> None:
    controls = _make_controls(("a", "b"))
    total = 2 * 6 + 3
    assert controls.focus_index == 0

    for _ in range(total - 1):
        assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
    assert controls.focus_index == total - 1

    assert controls.handle_keydown(_keydown(pygame.K_DOWN)) is True
    assert controls.focus_index == 0

    assert controls.handle_keydown(_keydown(pygame.K_UP)) is True
    assert controls.focus_index == total - 1


def test_opacity_clamps() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    opacity_row = next(
        i
        for i in range(6)
        if row_kind(view, i) == RowKind.TRACK_OPACITY
    )
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
    header_row = next(
        i for i in range(6) if row_kind(view, i) == RowKind.TRACK_HEADER
    )
    controls.focus_index = header_row
    assert controls.session.layers["drums"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].enabled is False
    assert enabled_events == [("drums", False)]
    assert controls.session.layers["drums"].opacity_pct == 50

    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.layers["drums"].enabled is True
    assert enabled_events == [("drums", False), ("drums", True)]
    assert controls.session.layers["drums"].opacity_pct == 50


def test_navigation_skips_sub_rows_when_disabled() -> None:
    controls = _make_controls(("drums", "bass"))
    controls.session.layers["drums"].enabled = False
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
    view = controls.build_view_state(paused=False)
    header_row = next(
        i for i in range(6) if row_kind(view, i) == RowKind.TRACK_HEADER
    )
    preset_dir_row = next(
        i for i in range(6) if row_kind(view, i) == RowKind.TRACK_PRESET_DIR
    )
    transport_row = next(
        i for i in range(9) if row_kind(view, i) == RowKind.TRANSPORT
    )
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == transport_row

    controls.focus_index = header_row
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.layers["drums"].enabled is True

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == preset_dir_row


def test_beat_sensitivity_clamps() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    beat_row = next(
        i for i in range(6) if row_kind(view, i) == RowKind.TRACK_BEAT
    )
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
    opacity_row = next(i for i in range(6) if row_kind(view, i) == RowKind.TRACK_OPACITY)
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


def test_navigable_rows_without_overwrite() -> None:
    controls = _make_controls(("drums",), allow_overwrite=False)
    view = controls.build_view_state(paused=False)
    assert view.allow_overwrite is False
    assert row_count(view) == 8

    kinds = {row_kind(view, i) for i in range(row_count(view))}
    assert RowKind.SAVE_AS_NEW_CONFIG in kinds
    assert RowKind.OVERWRITE_CONFIG not in kinds

    navigable = navigable_row_indices(view)
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
    controls = _make_controls(("drums",), allow_overwrite=True)
    view = controls.build_view_state(paused=False)
    assert view.allow_overwrite is True
    assert row_count(view) == 9

    overwrite_row = next(
        i for i in range(row_count(view)) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
    )
    assert overwrite_row in navigable_row_indices(view)


def test_overwrite_shows_confirm_before_write() -> None:
    launch_path = Path("/tmp/cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("drums",))
    controls._launch_config_path = launch_path
    controls._on_overwrite_config = lambda: (
        writes.append(launch_path) or launch_path.name
    )

    view = controls.build_view_state(paused=False)
    overwrite_row = next(
        i for i in range(9) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
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
    controls._launch_config_path = launch_path
    controls._on_overwrite_config = lambda: (
        writes.append(launch_path) or launch_path.name
    )

    view = controls.build_view_state(paused=False)
    overwrite_row = next(
        i for i in range(9) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
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
    launch_path = Path("/tmp/cleave.config.yaml")
    writes: list[Path] = []
    controls = _make_controls(("drums",))
    controls._launch_config_path = launch_path
    controls._on_overwrite_config = lambda: (
        writes.append(launch_path) or launch_path.name
    )

    view = controls.build_view_state(paused=False)
    overwrite_row = next(
        i for i in range(9) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
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
        i for i in range(9) if row_kind(view, i) == RowKind.OVERWRITE_CONFIG
    )
    controls.focus_index = overwrite_row
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is True


def test_esc_requests_quit() -> None:
    controls = _make_controls()
    assert controls.handle_keydown(_keydown(pygame.K_ESCAPE)) is False


def _skip_glyph_has_opaque_pixels(font: pygame.font.Font, ch: str) -> bool:
    """Skip icons must render visible ink, not hollow missing-glyph boxes."""
    ref_px = pygame.mask.from_surface(font.render("A", True, (255, 255, 255))).count()
    min_px = max(8, int(ref_px * 0.15))
    surf = font.render(ch, True, (255, 255, 255))
    opaque = pygame.mask.from_surface(surf).count()
    if opaque < min_px:
        return False

    width, height = surf.get_size()
    interior_opaque = 0
    for y in range(height):
        for x in range(width):
            if surf.get_at((x, y))[3] > 128 and 1 < x < width - 2 and 2 < y < height - 3:
                interior_opaque += 1
    return interior_opaque / opaque >= 0.35


def test_transport_row_icons() -> None:
    overlay = TuningOverlay()
    font = overlay._transport_font_get()
    prev_u, play_u, pause_u, nxt_u = _resolve_transport_icons(overlay._font_size)

    if _unicode_transport_available():
        if _glyph_renders_real_shape(font, "▶"):
            assert play_u == "▶"
        else:
            assert play_u == ">"
        if _glyph_renders_real_shape(font, "⏸"):
            assert pause_u == "⏸"
        else:
            assert pause_u == "||"
        if _glyph_renders_real_shape(font, "⏮"):
            assert prev_u == "⏮"
        else:
            assert prev_u == "<<"
        if _glyph_renders_real_shape(font, "⏭"):
            assert nxt_u == "⏭"
        else:
            assert nxt_u == ">>"
    else:
        assert (prev_u, play_u, pause_u, nxt_u) == ("<<", ">", "||", ">>")

    prev, play, nxt = overlay._transport_icon_set(paused=False)
    assert (prev, play, nxt) == (prev_u, play_u, nxt_u)
    playing = font.render(f"{prev}  {play}  {nxt}", True, (255, 255, 255))
    assert playing.get_width() > 0
    assert _skip_glyph_has_opaque_pixels(font, prev)
    assert _skip_glyph_has_opaque_pixels(font, play)
    assert _skip_glyph_has_opaque_pixels(font, nxt)

    prev, play, nxt = overlay._transport_icon_set(paused=True)
    assert (prev, play, nxt) == (prev_u, pause_u, nxt_u)
    paused = font.render(f"{prev}  {play}  {nxt}", True, (255, 255, 255))
    assert paused.get_width() > 0
    assert _skip_glyph_has_opaque_pixels(font, prev)
    assert _skip_glyph_has_opaque_pixels(font, play)
    assert _skip_glyph_has_opaque_pixels(font, nxt)


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
    header_row = next(
        i for i in range(6) if row_kind(view, i) == RowKind.TRACK_HEADER
    )
    preset_dir_row = next(
        i for i in range(6) if row_kind(view, i) == RowKind.TRACK_PRESET_DIR
    )
    controls.focus_index = header_row

    controls.handle_keydown(_keydown(pygame.K_DOWN))
    assert controls.focus_index == preset_dir_row


def test_ctrl_preset_steps_by_ten_wrapping() -> None:
    changed: list[tuple[str, int]] = []
    controls = _make_controls(("drums",))
    anchor = Path("/tmp/presets/drums")
    paths = tuple(anchor / f"preset-{i:02d}.milk" for i in range(12))
    controls.session.layers["drums"].playlist = PresetPlaylist(
        anchor=anchor, paths=paths, index=5
    )
    controls._on_preset_change = lambda stem, pl: changed.append((stem, pl.index))

    view = controls.build_view_state(paused=False)
    preset_row = next(
        i for i in range(6) if row_kind(view, i) == RowKind.TRACK_PRESET
    )
    controls.focus_index = preset_row
    playlist = controls.session.layers["drums"].playlist

    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert playlist.index == 3
    assert changed == [("drums", 3)]

    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert playlist.index == 5
    assert changed[-1] == ("drums", 5)


def test_preset_overlay_shows_directory_and_position() -> None:
    controls = _make_controls(("drums",))
    view = controls.build_view_state(paused=False)
    block = view.tracks["drums"]
    assert block.preset_dir_label == "drums"
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
        assert playlist.anchor == preset_dir.resolve()
        assert playlist.paths == (first.resolve(), second.resolve())
        assert playlist.index == 1
        assert preset_filename_display(playlist) == "beta.milk (2/2)"
        assert directory_display(playlist, root) == "pack/Aurora"


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
    transport_row = next(i for i in range(9) if row_kind(view, i) == RowKind.TRANSPORT)
    controls.focus_index = transport_row

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))

    assert seeks == [SEEK_SHORT, -SEEK_SHORT, SEEK_LONG, -SEEK_LONG]


def test_format_mmss() -> None:
    assert format_mmss(0) == "00:00"
    assert format_mmss(42.7) == "00:42"
    assert format_mmss(222) == "03:42"
    assert format_mmss(-5) == "00:00"


def main() -> int:
    pygame.init()
    tests = [
        test_focus_navigation_wraps,
        test_opacity_clamps,
        test_beat_sensitivity_clamps,
        test_header_toggles_enabled,
        test_navigation_skips_sub_rows_when_disabled,
        test_re_enable_allows_sub_row_focus,
        test_opacity_ctrl_step_is_ten_percent,
        test_move_mode_swaps_z_order,
        test_save_as_new_triggers_toast_and_blocks_input,
        test_navigable_rows_without_overwrite,
        test_navigable_rows_with_overwrite,
        test_overwrite_shows_confirm_before_write,
        test_overwrite_confirm_yes_writes_launch_path,
        test_overwrite_confirm_esc_dismisses,
        test_esc_during_confirm_does_not_quit,
        test_esc_requests_quit,
        test_transport_row_icons,
        test_format_mmss,
        test_transport_enter_toggles_pause,
        test_space_toggles_pause_from_any_focus,
        test_transport_seek_constants,
        test_quick_nav_row_indices_headers_and_transport_only,
        test_ctrl_quick_nav_cycles_headers_and_transport,
        test_ctrl_quick_nav_from_sub_row_jumps_forward,
        test_ctrl_quick_nav_from_save_row,
        test_ctrl_quick_nav_does_not_affect_normal_up_down,
        test_ctrl_preset_steps_by_ten_wrapping,
        test_preset_overlay_shows_directory_and_position,
        test_scan_file_anchor_builds_parent_directory_playlist,
        test_ctrl_quick_nav_blocked_during_move_mode,
    ]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
