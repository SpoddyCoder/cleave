"""Row layout and visibility/navigability for the live tuning overlay."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cleave.config_schema import MAX_LAYER_COUNT
from cleave.viz.row_sections import (
    CURATION_LAYER_SECTION,
    SETTINGS_SECTION,
    append_expand_section_rows,
    append_render_section_rows,
    append_track_section_rows,
    sub_row_expand_visible,
)
from cleave.viz.row_semantics import (
    RowDescriptor,
    RowKind,
    row_behavior,
    row_is_pinned,
    row_navigable_when_section_locked,
    section_header_descriptor,
    section_locked,
)

if TYPE_CHECKING:
    from cleave.viz.tuning_view_state import TuningViewState


def _sub_row_expanded(state: TuningViewState, desc: RowDescriptor) -> bool:
    return sub_row_expand_visible(state, desc)


def row_draw_visible(state: TuningViewState, desc: RowDescriptor) -> bool:
    if desc.kind in {RowKind.PANEL_NOTIFICATION, RowKind.RENDER_SECTION_GAP}:
        return True
    return _sub_row_expanded(state, desc)


def row_navigable(state: TuningViewState, desc: RowDescriptor) -> bool:
    if not row_behavior(desc.kind).navigable:
        return False
    if not _sub_row_expanded(state, desc):
        return False
    if section_locked(state, desc) and not row_navigable_when_section_locked(desc.kind):
        return False
    return True


def _quick_nav_section_open(state: TuningViewState, desc: RowDescriptor) -> bool:
    """Whether a skippable quick-nav header is currently expanded/open."""
    if desc.kind == RowKind.TRACK_HEADER:
        if desc.slot is None:
            return False
        return state.tracks[desc.slot].expanded
    if desc.kind == RowKind.RENDER_POST_FX_HEADER:
        return state.render_post_fx.expanded
    if desc.kind == RowKind.RENDER_TIMELINE_HEADER:
        return state.render_timeline.expanded
    return True


def quick_nav_stop_included(state: TuningViewState, desc: RowDescriptor) -> bool:
    """Whether Ctrl+Up/Down should land on this main-panel descriptor.

    Section tops (Settings, Transport, Layer 1, Render: OVERLAY) always stop.
    Other quick-nav headers stop only when open.
    """
    behavior = row_behavior(desc.kind)
    if not behavior.quick_nav_target:
        return False
    if behavior.quick_nav_always:
        return True
    if (
        desc.kind == RowKind.TRACK_HEADER
        and state.layer_z_order
        and desc.slot == state.layer_z_order[0]
    ):
        return True
    return _quick_nav_section_open(state, desc)


def resolve_navigable_descriptor(
    desc: RowDescriptor,
    navigable_descriptors: tuple[RowDescriptor, ...] | list[RowDescriptor],
) -> RowDescriptor:
    if desc in navigable_descriptors:
        return desc
    header = section_header_descriptor(desc)
    if header in navigable_descriptors:
        return header
    return RowDescriptor(RowKind.TRANSPORT)


@dataclass(frozen=True)
class RowLayoutFrame:
    visible_indices: tuple[int, ...]
    navigable_indices: tuple[int, ...]
    navigable_descriptors: tuple[RowDescriptor, ...]
    descriptor_index: dict[RowDescriptor, int]
    resolved_focus_index: int


def build_layout_frame(layout: RowLayout, state: TuningViewState) -> RowLayoutFrame:
    from cleave.viz.focus_nav import cursor_main_descriptor

    visible_indices = tuple(
        index
        for index in range(len(layout))
        if row_draw_visible(state, layout.descriptor(index))
    )
    navigable_indices = tuple(
        index
        for index in range(len(layout))
        if row_navigable(state, layout.descriptor(index))
    )
    navigable_descriptors = tuple(
        layout.descriptor(index) for index in navigable_indices
    )
    focus_desc = cursor_main_descriptor(state.focus_cursor)
    resolved = resolve_navigable_descriptor(focus_desc, navigable_descriptors)
    resolved_focus_index = layout.find_descriptor(resolved)
    return RowLayoutFrame(
        visible_indices=visible_indices,
        navigable_indices=navigable_indices,
        navigable_descriptors=navigable_descriptors,
        descriptor_index=layout.descriptor_index,
        resolved_focus_index=resolved_focus_index,
    )


@dataclass(frozen=True)
class RowLayout:
    rows: tuple[RowDescriptor, ...]
    descriptor_index: dict[RowDescriptor, int] = field(default_factory=dict)

    @classmethod
    def build(cls, state: TuningViewState) -> RowLayout:
        row_list: list[RowDescriptor] = []
        curation = state.settings.editor_mode == "preset_curation"
        append_expand_section_rows(row_list, SETTINGS_SECTION, state)
        if not curation:
            row_list.append(RowDescriptor(RowKind.CONFIG_HEADER))
        row_list.append(RowDescriptor(RowKind.TRANSPORT))
        if state.notification_message and state.notification_remaining_sec > 0:
            row_list.append(RowDescriptor(RowKind.PANEL_NOTIFICATION))
        if curation:
            if state.layer_z_order:
                append_expand_section_rows(
                    row_list,
                    CURATION_LAYER_SECTION,
                    state,
                    state.layer_z_order[0],
                )
        else:
            for slot in state.layer_z_order:
                append_track_section_rows(row_list, state, slot)
            if len(state.layer_z_order) < MAX_LAYER_COUNT:
                row_list.append(RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD))
            row_list.append(RowDescriptor(RowKind.RENDER_SECTION_GAP))
            append_render_section_rows(row_list, state)
        rows = tuple(row_list)
        return cls(
            rows=rows,
            descriptor_index={desc: index for index, desc in enumerate(rows)},
        )

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
        if self.descriptor_index:
            try:
                return self.descriptor_index[desc]
            except KeyError:
                pass
        for index, row in enumerate(self.rows):
            if row == desc:
                return index
        raise ValueError(f"descriptor not in layout: {desc!r}")

    def contains_descriptor(self, desc: RowDescriptor) -> bool:
        if self.descriptor_index:
            return desc in self.descriptor_index
        return desc in self.rows

    def navigable_descriptors(self, state: TuningViewState) -> list[RowDescriptor]:
        frame = state.layout_frame
        if frame is not None:
            return list(frame.navigable_descriptors)
        return [self.descriptor(index) for index in self.navigable_indices(state)]

    def resolve_navigable(
        self, desc: RowDescriptor, state: TuningViewState
    ) -> RowDescriptor:
        frame = state.layout_frame
        if frame is not None:
            return resolve_navigable_descriptor(desc, frame.navigable_descriptors)
        return resolve_navigable_descriptor(desc, self.navigable_descriptors(state))

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
        frame = state.layout_frame
        if frame is not None:
            return list(frame.visible_indices)
        return [
            index
            for index in range(len(self))
            if row_draw_visible(state, self.descriptor(index))
        ]

    def navigable_indices(self, state: TuningViewState) -> list[int]:
        """Row indices reachable via Up/Down (sub-rows skipped when collapsed)."""
        frame = state.layout_frame
        if frame is not None:
            return list(frame.navigable_indices)
        return [
            index
            for index in range(len(self))
            if row_navigable(state, self.descriptor(index))
        ]

    def quick_nav_indices(self, state: TuningViewState) -> list[int]:
        """Main-panel row indices for Ctrl+Up/Down section jumps.

        Always includes section tops (Settings, Transport, Layer 1,
        Render: OVERLAY). Other quick-nav headers are included only when
        open. The open timeline strip is appended separately in
        ``focus_nav.build_quick_nav_ring``.
        """
        return [
            index
            for index in range(len(self))
            if quick_nav_stop_included(state, self.descriptor(index))
        ]
