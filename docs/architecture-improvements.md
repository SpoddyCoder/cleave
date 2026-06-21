# Architecture improvements

Five sequenced phases drawn from the review in [architecture-principles.mdc](../.cursor/rules/architecture-principles.mdc).
Each phase is independently shippable. Phases 1 and 2 fix the two active bugs.
Phases 3-5 harden the foundation against recurrence.

---

## Phase 1 - Cache `build_row_layout` per frame

**Why.** `build_row_layout` rebuilds the full row list on every call: `row_descriptor`, `row_count`, `find_row`, `find_row_by_kind`, `track_row_count`, `_sub_row_visible`, and `visible_row_indices` all call it independently. A single `draw()` + input dispatch cycle can trigger a dozen rebuilds. This scatters allocation cost across the call stack and, more importantly, creates a correctness hazard: if state mutates mid-frame (unlikely now, but possible during timeline or modal transitions), callers within the same tick see different layouts.

**What to do.** Introduce a `RowLayout` wrapper (a frozen list of `RowDescriptor` plus the helpers that operate on it). `TuningViewState` holds one `RowLayout` instead of allowing callers to rebuild on demand. `build_row_layout` becomes an internal constructor; the public surface is `state.layout`. All helpers (`row_descriptor`, `find_row`, `navigable_row_indices`, etc.) become methods or free functions on `RowLayout`. `TuningViewStateBuilder.build()` calls `build_row_layout` exactly once.

**Scope.** `overlay.py` (layout functions), `tuning_view_state.py` (builder), any caller in `controls.py` and `overlay.py` that currently imports raw layout helpers. No behavior change; it is a mechanical refactor.

---

## Phase 2 - Decouple FPS from transport color; route fps through the view builder

**Why.** FPS is drawn at `y = padding` (top of the panel, physically on the Settings row), but its color is computed as `_row_value_color(state, transport_index)`. When the transport row is focused the FPS text turns the highlight color despite being in a different region -- this is Bug 1. The coupling exists because FPS was originally on the same Y as transport; after layout moved it, the color callback was not updated. A secondary issue: `TuningViewStateBuilder` does not set `fps`; `app.py` patches it in via `dataclasses.replace` after the builder runs, so the builder does not represent the full view state.

**What to do.** Remove the `_row_value_color(state, transport_index)` call for FPS. Use a fixed theme constant (e.g. `DISABLED` or a dedicated `FPS_COLOR`). Move `fps` population into `TuningViewStateBuilder.build()`, passing the current fps value in at construction or as a build argument (the same way `paused` is passed today). Remove the `dataclasses.replace` patch in `app.py`.

**Scope.** `overlay.py` (FPS draw path), `tuning_view_state.py`, `app.py` (or wherever `dataclasses.replace` lives). Small and isolated.

---

## Phase 3 - Use `RowDescriptor` as the focus cursor

**Why.** `TuningControls.focus_index` is an integer. Integer indices are unstable: adding a layer, expanding effects, or toggling settings shifts every index below the insertion point. The codebase has accumulated several repair paths to compensate (`_restore_focus`, `_refocus_track_header_if_sub_row`, arithmetic adjustments after add/delete). These are fragile and drift-prone.

**What to do.** Replace `focus_index: int` with `focus_descriptor: RowDescriptor`. `RowDescriptor` is already a frozen dataclass with `__eq__` and identity that survives layout changes (kind + slot + effect_id + driver_slug). Navigation computes the new layout, resolves the current descriptor to its new index, applies delta or modulo, and stores the resulting descriptor. The resolved `int` is needed only for scroll math and highlight -- produce it lazily from the layout for those purposes.

Remove `_restore_focus`, `_refocus_track_header_if_sub_row`, and the index arithmetic in add/delete handlers; they become no-ops because descriptors are stable by construction.

**Scope.** `controls.py` (focus field + all navigation methods), `tuning_view_state.py` (view state carries `focus_descriptor`; `focus_index` becomes a derived property for callers that still need it temporarily), `overlay.py` (`_row_has_tree_focus` resolves descriptor to index via the layout). The helpers in Phase 1 make this straightforward because `RowLayout` already materializes the index→descriptor map.

---

## Phase 4 - Unified focus model for the timeline bridge

**Why.** There are two parallel focus systems: `TuningControls.focus_index` (main tree) and `session.timeline.focus_row + submenu_focused` (timeline strip). The bridge in `_move_focus` stitches them with special cases for Up-from-TRANSPORT and Down-from-RENDER_TIMELINE_HEADER. The bridge consumes both endpoints of the modulo ring, stranding `SETTINGS_HEADER` at the top of the navigable list: you can never reach Settings by wrapping from below when the timeline is open -- this is Bug 2. The asymmetric exit logic (Down past last timeline row exits to TRANSPORT, not modulo) also means the two systems have different wrap semantics.

**What to do.** Model focus as a discriminated union:

```
FocusCursor = MainFocus(descriptor: RowDescriptor) | TimelineFocus(row: int)
```

Navigation produces a new `FocusCursor` from the old one plus a delta. Flatten the combined navigable sequence -- main navigable rows followed by timeline rows 0..N-1 -- into a single ordered list of `FocusCursor` values and apply uniform modulo wrap. The bridge special-cases disappear; the ring closes naturally. `submenu_focused` becomes a property: `isinstance(cursor, TimelineFocus)`. `session.timeline.focus_row` is written from the cursor when the cursor is a `TimelineFocus`.

Move `FocusCursor` and the combined navigation function into `focus_context.py` (already exists for typed dependency injection) or a new `focus_nav.py`. `_move_focus` in `controls.py` becomes a one-liner delegating to it.

**Scope.** `controls.py` (focus field, `_move_focus`, `_move_quick_focus`, timeline bridge branches), `session.py` (`timeline.submenu_focused` becomes derived), `tuning_view_state.py` (view state carries `FocusCursor`), `timeline_controls.py` (reads `TimelineFocus.row`), `overlay.py` highlight check.

---

## Phase 5 - Split `overlay.py` into layout/nav and draw modules

**Why.** `overlay.py` is ~1 800 lines combining: layout construction (`build_row_layout`), navigability rules (`navigable_row_indices`, `quick_nav_row_indices`), visibility rules (`_sub_row_visible`), label and color computation, scroll metrics, and pygame draw calls. Navigability logic duplicates visibility logic (`_sub_row_visible` and `navigable_row_indices` share the same expand/collapse branches and can drift). `RowBehavior.navigable` in `row_semantics.py` is the intended source of truth for navigability but is not consulted by the actual navigation path. Changing navigation requires reading through draw code and vice versa.

**What to do.** Extract three modules:

- `row_layout.py` -- `RowLayout` (from Phase 1), `build_row_layout`, `navigable_row_indices`, `quick_nav_row_indices`, `visible_row_indices`. Navigability derived from `RowBehavior.navigable` and expand/collapsed state, not from hardcoded kind sets. `_sub_row_visible` and `navigable_row_indices` share one visibility predicate.
- `overlay_draw.py` -- pygame draw logic, color computation, scroll, font, glyph calls. Consumes `RowLayout` and `TuningViewState`; imports nothing from `controls.py`.
- `overlay.py` -- thin re-export shim until call sites are updated, then removed.

The result: adding a new row kind means updating `row_semantics.py` (descriptor) and `row_layout.py` (layout order and visibility predicate). Draw code is untouched unless the row has novel visual treatment.

**Scope.** Large but mechanical. Phases 1-4 should land first: Phase 1 already introduces `RowLayout` as the natural home for the layout module, and Phase 3 makes navigability use descriptors rather than raw index queries, making the split cleaner.
