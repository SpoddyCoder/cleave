"""Present-style row text/fit coverage and draw-module architecture guards."""

from __future__ import annotations

import pygame

from cleave.paths import repo_root
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import ROW_SPECS, RowPresentStyle
from cleave.viz.tuning_panel_draw import TuningOverlay, _row_text, fit_row_text
from cleave.viz.tuning_view_state import SettingsBlock, TuningViewState
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.viz import make_track_block, overlay_font


def _present_style_view_state() -> TuningViewState:
    from cleave.viz.row_layout import RowLayout, build_layout_frame

    from tests.cleave.viz.test_overlay import _mount_track_sections

    state = _minimal_view_state(
        tracks={
            "layer_1": make_track_block(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={"pulse": {"onset": 35}},
            )
        },
    )
    _mount_track_sections(state)
    rows = list(state.layout.rows)
    rows.append(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
    rows.append(RowDescriptor(RowKind.RENDER_SECTION_GAP))
    state.layout = RowLayout(
        rows=tuple(rows),
        descriptor_index={desc: index for index, desc in enumerate(rows)},
    )
    state.layout_frame = build_layout_frame(state.layout, state)
    return state


def _row_for_style(
    state: TuningViewState, style: RowPresentStyle
) -> tuple[int, str]:
    layout = state.layout
    if style == RowPresentStyle.LABELED_VALUE:
        index = layout.find("layer_1", RowKind.TRACK_STEM)
        return index, "driving stem: drums"
    if style == RowPresentStyle.EXPAND_SUBHEADER:
        index = layout.find("layer_1", RowKind.TRACK_EFFECTS_HEADER)
        return index, "cleave effects ▼"
    if style == RowPresentStyle.COMPOSITE_HEADER:
        index = layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER)
        return index, "Render: TIMELINE ▶"
    if style == RowPresentStyle.PATH_ICON:
        index = layout.find("layer_1", RowKind.TRACK_PRESET_DIR)
        return index, "dir"
    if style == RowPresentStyle.FULL_LINE:
        index = layout.find("layer_1", RowKind.LAYER_MANAGEMENT_DELETE)
        return index, "└─ Delete Layer"
    if style == RowPresentStyle.DYNAMIC:
        index = layout.find(
            "layer_1",
            RowKind.TRACK_EFFECT,
            effect_id="pulse",
            driver_slug="onset",
        )
        return index, "pulse (onset): 35%"
    if style == RowPresentStyle.TRACK_HEADER:
        index = layout.find("layer_1", RowKind.TRACK_HEADER)
        return index, "Layer 1: DRUMS ▼"
    if style == RowPresentStyle.SPACER:
        index = layout.find_by_kind(RowKind.RENDER_SECTION_GAP)
        return index, ""
    raise AssertionError(f"uncovered present style {style!r}")


def test_each_present_style_row_text_and_fit() -> None:
    state = _present_style_view_state()
    font = overlay_font()
    covered: set[RowPresentStyle] = set()
    for style in RowPresentStyle:
        index, expected = _row_for_style(state, style)
        field = ROW_SPECS[state.layout.kind(index)]
        assert field.present_style == style
        text = _row_text(state, index)
        assert text == expected
        fitted = fit_row_text(font, state, index, max_content_width=10_000)
        assert fitted == expected
        covered.add(style)
    assert covered == set(RowPresentStyle)


def test_tuning_panel_draw_has_no_rowkind_comparisons() -> None:
    source = (repo_root() / "cleave" / "viz" / "tuning_panel_draw.py").read_text(
        encoding="utf-8"
    )
    assert "RowKind" not in source


_OVERLAY_MODULES_WITHOUT_TUNING_DRAW = (
    "timeline_overlay.py",
    "help_column.py",
    "modal_overlay.py",
)


def test_notification_does_not_compose_tuning_panel() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _minimal_view_state(
        settings=SettingsBlock(ui_width_mode="flexible", ui_width=80, ui_min_width=40),
        notification_message="warning " * 40,
        notification_remaining_sec=5.0,
        persistent_notification_message="No presets in bed roles folder",
    )
    composed = overlay.compose_panel(
        state,
        viewport_width=1600,
        viewport_height=900,
    )
    assert state.layout.rows == ()
    assert composed is None


def test_peer_overlays_do_not_import_tuning_panel_draw() -> None:
    viz_dir = repo_root() / "cleave" / "viz"
    offenders: list[str] = []
    for name in _OVERLAY_MODULES_WITHOUT_TUNING_DRAW:
        path = viz_dir / name
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            if "tuning_panel_draw" in stripped:
                offenders.append(f"{name}:{lineno}: {stripped}")
    assert offenders == [], (
        "peer overlays must not import tuning_panel_draw: "
        + "; ".join(offenders)
    )
