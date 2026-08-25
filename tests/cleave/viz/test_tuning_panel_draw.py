"""Present-style row text/fit coverage and draw-module architecture guards."""

from __future__ import annotations

from cleave.paths import repo_root
from cleave.viz.row_fields import ROW_FIELDS, RowPresentStyle
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.tuning_panel_draw import _row_text, fit_row_text
from cleave.viz.tuning_view_state import SettingsBlock, TuningViewState
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.viz import make_track_block, overlay_font


def _present_style_view_state() -> TuningViewState:
    return _minimal_view_state(
        settings=SettingsBlock(expanded=True),
        tracks={
            "layer_1": make_track_block(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={"pulse": {"onset": 35}},
                effects_expanded=True,
                expanded=True,
            )
        },
        notification_message="timeline enabled",
        notification_remaining_sec=5.0,
        active_config_label="cleave-viz.yaml",
    )


def _row_for_style(
    state: TuningViewState, style: RowPresentStyle
) -> tuple[int, str]:
    layout = state.layout
    if style == RowPresentStyle.LABELED_VALUE:
        index = layout.find("layer_1", RowKind.TRACK_STEM)
        return index, "└─ driving stem: drums"
    if style == RowPresentStyle.ACTION_PARAMETER:
        index = layout.find_by_kind(RowKind.SETTINGS_EDITOR_MODE)
        return index, "└─ editor mode: visualizer"
    if style == RowPresentStyle.EXPAND_SUBHEADER:
        index = layout.find("layer_1", RowKind.TRACK_EFFECTS_HEADER)
        return index, "└─ cleave effects ▼"
    if style == RowPresentStyle.COMPOSITE_HEADER:
        index = layout.find_by_kind(RowKind.SETTINGS_HEADER)
        return index, "Editor Settings ▼"
    if style == RowPresentStyle.PATH_ICON:
        index = layout.find_by_kind(RowKind.CONFIG_HEADER)
        return index, "cleave-viz.yaml"
    if style == RowPresentStyle.FULL_LINE:
        index = layout.find_by_kind(RowKind.LAYER_MANAGEMENT_ADD)
        return index, "Add Layer"
    if style == RowPresentStyle.DYNAMIC:
        index = layout.find(
            "layer_1",
            RowKind.TRACK_EFFECT,
            effect_id="pulse",
            driver_slug="onset",
        )
        return index, "  └─ pulse (onset): 35%"
    if style == RowPresentStyle.TRACK_HEADER:
        index = layout.find("layer_1", RowKind.TRACK_HEADER)
        return index, "Layer 1: DRUMS ▼"
    if style == RowPresentStyle.NOTIFICATION:
        index = layout.find_descriptor(
            RowDescriptor(RowKind.PANEL_NOTIFICATION, marker_index=1)
        )
        return index, "timeline enabled"
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
        field = ROW_FIELDS[state.layout.kind(index)]
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
