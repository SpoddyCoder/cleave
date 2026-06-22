"""Row layout and visibility/navigability for the live tuning overlay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cleave.effects.registry import effect_roster
from cleave.viz.row_semantics import (
    RENDER_OVERLAY_BODY_NESTED_KINDS,
    RENDER_OVERLAY_SUB_ROW_KINDS,
    RENDER_OVERLAY_TITLE_NESTED_KINDS,
    RENDER_POST_FX_SUB_ROW_KINDS,
    SETTINGS_SUB_ROW_KINDS,
    RowDescriptor,
    RowKind,
    TRACK_EFFECT_SUB_ROW_KINDS,
    TRACK_SUB_ROW_KINDS,
    row_behavior,
    row_is_pinned,
    row_navigable_when_layer_locked,
    section_header_descriptor,
)

if TYPE_CHECKING:
    from cleave.viz.tuning_view_state import TuningViewState


def _sub_row_expanded(state: TuningViewState, desc: RowDescriptor) -> bool:
    kind = desc.kind
    if kind in SETTINGS_SUB_ROW_KINDS:
        return state.settings.expanded
    if kind in RENDER_OVERLAY_SUB_ROW_KINDS:
        return state.render_overlay.expanded
    if kind in RENDER_OVERLAY_TITLE_NESTED_KINDS:
        return state.render_overlay.expanded and state.render_overlay.title_expanded
    if kind in RENDER_OVERLAY_BODY_NESTED_KINDS:
        return state.render_overlay.expanded and state.render_overlay.body_expanded
    if kind in RENDER_POST_FX_SUB_ROW_KINDS:
        return state.render_post_fx.expanded
    slot = desc.slot
    if slot is not None and kind in TRACK_SUB_ROW_KINDS:
        block = state.tracks[slot]
        if not block.expanded:
            return False
        if kind in TRACK_EFFECT_SUB_ROW_KINDS:
            return block.effects_expanded
    return True


def row_draw_visible(state: TuningViewState, desc: RowDescriptor) -> bool:
    if desc.kind in {RowKind.PANEL_NOTIFICATION, RowKind.RENDER_SECTION_GAP}:
        return True
    return _sub_row_expanded(state, desc)


def row_navigable(state: TuningViewState, desc: RowDescriptor) -> bool:
    if not row_behavior(desc.kind).navigable:
        return False
    if not _sub_row_expanded(state, desc):
        return False
    slot = desc.slot
    if slot is not None and desc.kind in TRACK_SUB_ROW_KINDS:
        block = state.tracks[slot]
        if block.locked and not row_navigable_when_layer_locked(desc.kind):
            return False
    return True


@dataclass(frozen=True)
class RowLayout:
    rows: tuple[RowDescriptor, ...]

    @classmethod
    def build(cls, state: TuningViewState) -> RowLayout:
        row_list: list[RowDescriptor] = [
            RowDescriptor(RowKind.SETTINGS_HEADER),
        ]
        if state.settings.expanded:
            row_list.append(RowDescriptor(RowKind.SETTINGS_RENDER_MODE))
        row_list.extend(
            [
                RowDescriptor(RowKind.CONFIG_HEADER),
                RowDescriptor(RowKind.TRANSPORT),
            ]
        )
        if state.notification_message and state.notification_remaining_sec > 0:
            row_list.append(RowDescriptor(RowKind.PANEL_NOTIFICATION))
        for slot in state.layer_z_order:
            row_list.append(RowDescriptor(RowKind.TRACK_HEADER, slot=slot))
            row_list.append(RowDescriptor(RowKind.TRACK_PRESET_DIR, slot=slot))
            row_list.append(RowDescriptor(RowKind.TRACK_PRESET, slot=slot))
            row_list.append(RowDescriptor(RowKind.TRACK_STEM, slot=slot))
            row_list.append(RowDescriptor(RowKind.TRACK_BLEND, slot=slot))
            row_list.append(RowDescriptor(RowKind.TRACK_OPACITY, slot=slot))
            row_list.append(RowDescriptor(RowKind.TRACK_BEAT, slot=slot))
            row_list.append(RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot=slot))
            block = state.tracks[slot]
            if block.effects_expanded:
                for effect_def in effect_roster(block.stem):
                    row_list.append(
                        RowDescriptor(
                            RowKind.TRACK_EFFECT,
                            slot=slot,
                            effect_id=effect_def.effect_id,
                            driver_slug=effect_def.driver_slug,
                        )
                    )
            if block.expanded:
                row_list.append(
                    RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot=slot)
                )
        row_list.append(RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD))
        row_list.append(RowDescriptor(RowKind.RENDER_SECTION_GAP))
        row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_HEADER))
        if state.render_overlay.expanded:
            row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_POSITION))
            row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY))
            row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_BORDER_WIDTH))
            row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_START_DELAY))
            row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_DISPLAY_TIME))
            row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_HEADER))
            if state.render_overlay.title_expanded:
                row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT))
                row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE))
                row_list.append(
                    RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM)
                )
            row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_BODY_HEADER))
            if state.render_overlay.body_expanded:
                row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_BODY_FONT))
                row_list.append(RowDescriptor(RowKind.RENDER_OVERLAY_BODY_FONT_SIZE))
        row_list.append(RowDescriptor(RowKind.RENDER_POST_FX_HEADER))
        if state.render_post_fx.expanded:
            row_list.append(RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN))
            row_list.append(RowDescriptor(RowKind.RENDER_POST_FX_FADE_OUT))
        row_list.append(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
        return cls(tuple(row_list))

    def __len__(self) -> int:
        return len(self.rows)

    def count(self) -> int:
        return len(self.rows)

    def descriptor(self, index: int) -> RowDescriptor:
        if index < 0 or index >= len(self.rows):
            raise IndexError(index)
        return self.rows[index]

    def kind(self, index: int) -> RowKind:
        return self.descriptor(index).kind

    def slot(self, index: int) -> str | None:
        return self.descriptor(index).slot

    def find(
        self,
        slot: str,
        kind: RowKind,
        *,
        effect_id: str | None = None,
        driver_slug: str | None = None,
    ) -> int:
        for index, desc in enumerate(self.rows):
            if desc.kind != kind or desc.slot != slot:
                continue
            if kind == RowKind.TRACK_EFFECT:
                if desc.effect_id != effect_id or desc.driver_slug != driver_slug:
                    continue
            return index
        raise ValueError(f"no row for slot={slot!r} kind={kind!r}")

    def find_by_kind(self, kind: RowKind) -> int:
        for index, desc in enumerate(self.rows):
            if desc.kind == kind:
                return index
        raise ValueError(f"no row for kind={kind!r}")

    def find_descriptor(self, desc: RowDescriptor) -> int:
        for index, row in enumerate(self.rows):
            if row == desc:
                return index
        raise ValueError(f"descriptor not in layout: {desc!r}")

    def contains_descriptor(self, desc: RowDescriptor) -> bool:
        return desc in self.rows

    def navigable_descriptors(self, state: TuningViewState) -> list[RowDescriptor]:
        return [self.descriptor(index) for index in self.navigable_indices(state)]

    def resolve_navigable(
        self, desc: RowDescriptor, state: TuningViewState
    ) -> RowDescriptor:
        navigable = self.navigable_descriptors(state)
        if desc in navigable:
            return desc
        header = section_header_descriptor(desc)
        if header in navigable:
            return header
        return RowDescriptor(RowKind.TRANSPORT)

    def header_row_count(self) -> int:
        count = 0
        for row in self.rows:
            if row_is_pinned(row.kind):
                count += 1
            else:
                break
        return count

    def track_row_count(self) -> int:
        """Count of scrollable content rows (all rows except pinned header rows)."""
        return sum(1 for row in self.rows if not row_is_pinned(row.kind))

    def sub_row_visible(self, state: TuningViewState, index: int) -> bool:
        return row_draw_visible(state, self.descriptor(index))

    def visible_indices(self, state: TuningViewState) -> list[int]:
        """Row indices drawn in the panel (sub-rows hidden when collapsed)."""
        return [
            index
            for index in range(len(self))
            if row_draw_visible(state, self.descriptor(index))
        ]

    def navigable_indices(self, state: TuningViewState) -> list[int]:
        """Row indices reachable via Up/Down (sub-rows skipped when collapsed)."""
        return [
            index
            for index in range(len(self))
            if row_navigable(state, self.descriptor(index))
        ]

    def quick_nav_indices(self) -> list[int]:
        """Row indices for Ctrl+Up/Down: settings, transport, layer, and render headers."""
        return [
            index
            for index in range(len(self))
            if row_behavior(self.kind(index)).quick_nav_target
        ]
