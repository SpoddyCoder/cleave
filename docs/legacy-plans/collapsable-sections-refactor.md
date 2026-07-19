# Collapsible sections refactor

Implementation guide for unifying expand/collapse and value-gated rows in the live tuning panel. Use the lexicon below in issues, rules, and feature requests.

Related: [docs/todos.md](docs/todos.md) ("Review Child Menus"), [.cursor/rules/live-tuning-ui.mdc](.cursor/rules/live-tuning-ui.mdc).

---

## Lexicon

Three terms cover all collapsible and gated UI in the main tuning tree.

### Expandable section

A **header row** with `RowAffordance.EXPAND` and a `▶` / `▼` arrow. Left/Right toggles a **session-only** expanded flag. When collapsed, **child rows** in the main `RowLayout` tree are hidden (not drawn, not navigable). Children may themselves be expandable sections (unlimited depth).

Examples: layer header, preset switching, cleave effects, Settings, render overlay / post-FX, overlay title/body.

Not: value toggles without an arrow (hard cut enabled), mode cycling rows.

### Conditional rows

**Sibling rows** at the current tree level that appear or disappear based on a **value predicate** on session or view state. No expand arrow; no separate expanded flag. The driving row stays visible (e.g. switching mode, hard cut enabled).

Examples: projectm-only preset switching params; hard-cut duration/sensitivity when hard cut is on; highlight rolloff params when mode is not `off`.

**Structure signature:** predicates run when `RowLayout.build()` runs, which happens only when `view_state_structure_signature()` changes ([cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py)). If the gating field is missing from the signature, sibling rows stay stale until some unrelated change forces a rebuild. Add every field that controls conditional row presence to the signature; add a matching test in [tests/cleave/viz/test_view_state_structure.py](tests/cleave/viz/test_view_state_structure.py).

### Panel anchor (exception)

A header row that **looks** like an expandable section (arrow, Left/Right) but **does not** host children in `RowLayout`. Content lives in a **separate panel host** (timeline bottom strip). State uses `panel_open` on `TimelineRuntime`; view state aliases it as `render_timeline.expanded` for drawing and focus ring.

Scope: share arrow UX and toggle wiring helpers only. Do not fold timeline strip focus, recording, or `TimelineControls` into the expandable-section tree.

---

## Inventory

Every collapsible or gated instance in the live tuning UI today, mapped to the lexicon.

**Depth** is section-tree depth (0 = top-level header in its region). **Mechanism**: how visibility is enforced today.

| UI label / row | Type | Session state field | `RowKind` | Depth | Mechanism |
| --- | --- | --- | --- | --- | --- |
| Editor Settings | Expandable section | `session.settings.expanded` | `SETTINGS_HEADER` | 0 (pinned header) | Toggle in [cleave/viz/controls.py](cleave/viz/controls.py); children **build-time** omit |
| render mode | Child (expandable) | (parent gate only) | `SETTINGS_RENDER_MODE` | 1 | Section tree under `SETTINGS_SECTION` |
| UI fade | Child (expandable) | (parent gate only) | `SETTINGS_UI_FADE` | 1 | Section tree under `SETTINGS_SECTION` |
| Layer N: STEM | Expandable section | `LayerRuntime.expanded` | `TRACK_HEADER` | 0 (per slot) | Toggle `_set_expanded`; children via `TRACK_SECTION` tree walk |
| preset switching | Expandable section | `LayerRuntime.preset_switching_expanded` | `TRACK_PRESET_SWITCHING` | 1 | Toggle `_set_preset_switching_expanded`; submenu **build-time** omit |
| switching mode | Child (expandable) | (parent gates) | `TRACK_PRESET_SWITCHING_MODE` | 2 | Build-time when `preset_switching_expanded`; runtime track ancestor gate |
| rotation set | Conditional | `LayerRuntime.preset_switching` | `TRACK_PRESET_SWITCHING_ROTATION_SET` | 2 | Build-time `preset_switching == "projectm"` |
| user presets | Conditional | `LayerRuntime.preset_switching_rotation_set` | `TRACK_USER_PRESETS` | 2 | Build-time `preset_switching_rotation_set == "user_defined"` |
| preset duration | Conditional | `LayerRuntime.preset_switching` | `TRACK_PRESET_DURATION` | 2 | Build-time `preset_switching == "projectm"` |
| soft cut | Conditional | `LayerRuntime.preset_switching` | `TRACK_SOFT_CUT_DURATION` | 2 | Build-time `preset_switching == "projectm"` |
| easter egg | Conditional | `LayerRuntime.preset_switching` | `TRACK_EASTER_EGG` | 2 | Build-time `preset_switching == "projectm"` |
| start clean | Conditional | `LayerRuntime.preset_switching` | `TRACK_PRESET_START_CLEAN` | 2 | Build-time `preset_switching == "projectm"` |
| hard cut enabled | Conditional | `LayerRuntime.preset_switching` | `TRACK_HARD_CUT_ENABLED` | 2 | Build-time `preset_switching == "projectm"` |
| hard cut min | Conditional | `LayerRuntime.hard_cut_enabled` | `TRACK_HARD_CUT_DURATION` | 3 | Build-time `hard_cut_enabled` (under projectm branch) |
| hard cut sens | Conditional | `LayerRuntime.hard_cut_enabled` | `TRACK_HARD_CUT_SENSITIVITY` | 3 | Build-time `hard_cut_enabled` (under projectm branch) |
| cleave effects | Expandable section | `LayerRuntime.effects_expanded` | `TRACK_EFFECTS_HEADER` | 1 | Toggle `_set_effects_expanded`; effect rows **build-time** omit |
| effect depth rows | Child (expandable) | (parent gates) | `TRACK_EFFECT` | 2 | Build-time when `effects_expanded`; runtime track + effects ancestor gate |
| Delete layer | Child (expandable) | `LayerRuntime.expanded` | `LAYER_MANAGEMENT_DELETE` | 1 | **Build-time** when `block.expanded` |
| Render: OVERLAY | Expandable section | `RenderOverlayRuntime.expanded` | `RENDER_OVERLAY_HEADER` | 0 (render) | `RenderOverlayControls.set_expanded`; children **build-time** omit |
| position, opacity, border, delays | Child (expandable) | (parent gate) | `RENDER_OVERLAY_*` (non-title/body) | 1 | `RENDER_OVERLAY_SECTION` tree walk |
| title | Expandable section | `RenderOverlayRuntime.title_expanded` | `RENDER_OVERLAY_TITLE_HEADER` | 1 | `set_title_expanded`; nested rows in section tree |
| title font / size / margin | Child (expandable) | (parent gates) | `RENDER_OVERLAY_TITLE_*` | 2 | Nested under `RENDER_OVERLAY_TITLE_SECTION` |
| body | Expandable section | `RenderOverlayRuntime.body_expanded` | `RENDER_OVERLAY_BODY_HEADER` | 1 | `set_body_expanded`; nested rows in section tree |
| body font / size | Child (expandable) | (parent gates) | `RENDER_OVERLAY_BODY_*` | 2 | Nested under `RENDER_OVERLAY_BODY_SECTION` |
| Render: POST FX | Expandable section | `RenderPostFxRuntime.expanded` | `RENDER_POST_FX_HEADER` | 0 (render) | `RenderPostFxControls.set_expanded`; `RENDER_POST_FX_SECTION` tree walk |
| fade in / fade out | Child (expandable) | (parent gate) | `RENDER_POST_FX_FADE_IN`, `RENDER_POST_FX_FADE_OUT` | 1 | `RENDER_POST_FX_SECTION` tree walk |
| Render: TIMELINE | Panel anchor | `TimelineRuntime.panel_open` (view: `render_timeline.expanded`) | `RENDER_TIMELINE_HEADER` | 0 (render) | `_open_timeline_panel` / `close_timeline_panel`; **no** `RowLayout` children; content in [cleave/viz/timeline_overlay.py](cleave/viz/timeline_overlay.py) |

**`parent_group`** on `RowBehavior` in [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py) remains for layer-lock rules. **`TRACK_SUB_ROW_KINDS`** is still derived from `parent_group == "track"` for lock checks in [cleave/viz/row_layout.py](cleave/viz/row_layout.py). Focus fallback and draw indent come from the section tree in [cleave/viz/row_sections.py](cleave/viz/row_sections.py) (`section_header_from_section_tree`, `row_tree_indent_depth`, `kinds_in_expand_section`).

**Hybrid visibility today:** track-block sub-rows (preset dir through effects header) are always present in `RowLayout.build()` but hidden when the layer is collapsed via `_sub_row_expanded` / `row_draw_visible`. Preset-switching submenu, effect rows, settings/render children, and layer delete use **build-time omission**. Target: one tree walk with **build-time omission** everywhere.

---

## Current state summary

The live tuning panel has **partial** sharing, not a single composition layer.

| Mechanism | Location | Role today |
| --- | --- | --- |
| `RowAffordance.EXPAND` | [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py) | Marks arrow headers; `expandable_row_kinds()` |
| `parent_group` on `RowBehavior` | [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py) | Layer-lock grouping (`TRACK_SUB_ROW_KINDS`) |
| `sub_row_expand_visible()` | [cleave/viz/row_sections.py](cleave/viz/row_sections.py) | Tree-walk visibility for expand sections |
| `expand_arrow_for_header()` | [cleave/viz/row_sections.py](cleave/viz/row_sections.py) | Shared expand arrow for `EXPAND_HEADER_KINDS` draw and help text |
| `RowLayout.build()` | [cleave/viz/row_layout.py](cleave/viz/row_layout.py) | Walks root section tree; build-time omission for collapsed/conditional rows |
| Per-section bools | [cleave/viz/session.py](cleave/viz/session.py) | `expanded`, `effects_expanded`, `preset_switching_expanded`, `title_expanded`, `body_expanded`, `panel_open`, etc. |
| Bespoke toggles | [cleave/viz/controls.py](cleave/viz/controls.py) | Long `_apply_horizontal` if-chain per `RowKind` |
| Duplicated arrow draw | [cleave/viz/tuning_panel_draw.py](cleave/viz/tuning_panel_draw.py) | `_track_header_expand_suffix` for width budgeting; per-kind value labels |

View-state mirrors session expand flags in [cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py) (`TrackBlock`, `RenderOverlayBlock`, `SettingsBlock`, etc.). Timeline `panel_open` is exposed as `RenderTimelineBlock.expanded` for draw only.

Nesting works (layer → preset switching → params; overlay → title/body → font rows) but each new level adds manual frozensets, build branches, toggle handlers, and draw paths.

---

## Target architecture overview

Introduce a small **section composition** layer in [cleave/viz/row_sections.py](cleave/viz/row_sections.py) between semantics and layout.

### `ExpandSectionDef`

Declarative registry entry per expandable header:

- `header_kind: RowKind`
- `context: "global" | "per_slot"` (Settings vs layer-scoped preset switching)
- `state_accessor: (session, slot?) -> (get_expanded, set_expanded)` — maps to existing session bools initially (no session schema churn in v1)
- `children: tuple[SectionNode, ...]` — nested sections and leaf row kinds
- Optional `collapse_on_disable: bool` (overlay/post-FX/settings already collapse when disabled)

**Visibility rule:** a row is visible iff every ancestor expandable section on the path is expanded **and** every conditional predicate on the path passes.

**Nesting:** modeled as nested `ExpandSectionDef` nodes, not flat `parent_group` frozensets. `parent_group` on `RowBehavior` can remain for layer-lock and focus fallback during migration, then shrink to derived metadata.

### `ConditionalRowsDef`

Separate registry (same module):

- `predicate: (TuningViewState, RowDescriptor) -> bool`
- `child_kinds` or nested `SectionNode` list

Predicates replace ad-hoc `if block.preset_switching == "projectm"` and `if block.hard_cut_enabled` blocks in `RowLayout.build`. Named predicates (e.g. `preset_switching_projectm`, `hard_cut_enabled`) become the shared lexicon for conditional rows.

### `PanelAnchorDef`

Minimal struct:

- `header_kind`
- open/close accessors on session
- `content_host: Literal["timeline_strip"]` (extensible later if another bottom panel appears)

Shared helpers: `toggle_panel_anchor(forward: bool)` from `_apply_horizontal`; arrow drawing via one `expand_arrow_glyph(expanded: bool) -> str`.

### Controls dispatch

Replace per-kind expand branches with registry lookup:

```python
if kind in EXPAND_SECTION_BY_HEADER:
    EXPAND_SECTION_BY_HEADER[kind].set_expanded(session, slot, forward)
    return
if kind in PANEL_ANCHOR_BY_HEADER:
    PANEL_ANCHOR_BY_HEADER[kind].set_open(session, forward)
    return
```

Existing control classes (`RenderOverlayControls.set_expanded`, etc.) can remain as thin wrappers called from accessors.

### Layout build

`RowLayout.build()` walks the **root section tree** (settings, track blocks per slot, render blocks, timeline header as panel anchor). `_sub_row_expanded()` derives from the same tree (walk ancestors) and deletes parallel frozenset logic once migrated.

### Draw

Single `expand_arrow_glyph()` in [cleave/viz/tuning_panel_draw.py](cleave/viz/tuning_panel_draw.py) or [cleave/viz/theme.py](cleave/viz/theme.py). Section label helpers consult registry for indent depth (`└─` prefix level) instead of hard-coded per-kind strings.

---

## Implementation steps checklist

Execute in order; keep unit tests green after each step.

- [x] **Step 0 — Write the doc and inventory**  
  Create this file: lexicon, inventory table, how-to recipes, non-goals.

- [x] **Step 1 — Shared draw + toggle primitives**  
  Add `expand_arrow_glyph(expanded: bool) -> str`. Add `apply_expand_toggle(session, header_kind, slot, forward)` and `apply_panel_anchor_toggle(session, header_kind, forward)` delegating to registries (initially hard-coded maps mirroring today's behavior). Wire [cleave/viz/controls.py](cleave/viz/controls.py) `_apply_horizontal` through these helpers. No layout changes; behavior identical.

- [x] **Step 2 — Introduce `row_sections.py` with expand registry**  
  Define `SectionNode`, `ExpandSectionDef`, root tree constant. First migration: **Settings** (smallest: one level, global context). Replace Settings branches in `RowLayout.build` and `_sub_row_expanded` with tree walk.

- [x] **Step 3 — Migrate render post-FX and render overlay**  
  Post-FX: flat expandable section. Overlay: nested expandable sections (title, body). Keep `RenderOverlayControls` collapse-on-disable via `collapse_on_disable` hook.

- [x] **Step 4 — Migrate layer-scoped expandable sections**  
  Per-slot tree under `TRACK_HEADER`: layer header, preset switching subsection, cleave effects subsection. Remove redundant `if block.effects_expanded` / `if block.preset_switching_expanded` build branches. Confirm layer collapse still cascades (disable layer sets `expanded = False`).

- [x] **Step 5 — Conditional rows registry**  
  Extract predicates:

  | Predicate name | Condition |
  | --- | --- |
  | `preset_switching_submenu_open` | `preset_switching_expanded` (expand gate, not value) |
  | `preset_switching_projectm` | `preset_switching == "projectm"` (rotation set and timing children) |
  | `preset_switching_user_defined` | `preset_switching_rotation_set == "user_defined"` |
  | `preset_switching_auto` | `preset_switching == "projectm"` (shuffle + timing) |
  | `hard_cut_enabled` | `hard_cut_enabled` |

  Attach to preset switching and hard-cut row groups in the section tree. Delete duplicated `if` blocks in `RowLayout.build`. Extend `section_header_descriptor()` to derive from tree parent pointers where possible.

- [x] **Step 6 — Panel anchor documentation and thin wiring**  
  Register `RENDER_TIMELINE_HEADER` as `PanelAnchorDef`; keep `_open_timeline_panel` / `close_timeline_panel`. Document panel anchor vs expandable section in this doc and [.cursor/rules/live-tuning-ui.mdc](.cursor/rules/live-tuning-ui.mdc). Do **not** move timeline rows into `RowLayout`.

- [x] **Step 7 — Cleanup and conventions**  
  Remove dead frozensets (`RENDER_OVERLAY_TITLE_NESTED_KINDS`, etc.) once tree is source of truth. Add focused unit tests for `row_sections`: visibility with nested expand + conditional predicates; focus fallback parent resolution. Update [tests/cleave/viz/test_config_dirty.py](tests/cleave/viz/test_config_dirty.py) helpers if expand paths change.

- [x] **Step 8 — Update project docs**  
  Resolve [docs/todos.md](docs/todos.md) "Review Child Menus" (done or link here). Keep how-to recipes in this doc current.

---

## Refinement pass

Phases 1-2 introduced the section tree, registries, and layout walk. Phases 3-5 tighten semantics and draw:

### `append_dynamic_children`

Roster-driven rows (e.g. cleave effects per stem) attach via `ExpandSectionDef.append_dynamic_children` instead of a manual loop in `RowLayout.build`. The callback receives the row list, view state, and slot; `append_expand_section_rows` invokes it after static `children` when the section is expanded.

### `read_expanded` and `toggle` on `ExpandSectionDef`

Each expandable section declares:

- `read_expanded(state, slot?) -> bool` — view-state accessor for the arrow and visibility walk
- `toggle(controls, slot?, forward)` — Left/Right handler (usually a thin wrapper on existing control methods)

`expand_section_expanded` is the single gate for layout omission, `sub_row_expand_visible`, and draw arrows (via `expand_arrow_for_header`).

### `collapse_on_disable`

When `collapse_on_disable` is true (render overlay and post-FX today), `expand_section_expanded` returns false if the block is disabled, before `read_expanded`. Sub-rows stay hidden and arrows show collapsed even if the session bool is still true. Disable handlers should still clear the bool; this hook covers visibility and draw consistently.

### Draw: panel fields vs expand arrows

Panel labels, value strings, and tree branch glyphs come from [cleave/viz/row_fields.py](cleave/viz/row_fields.py) (`panel_label`, `format_value`, `labeled_row_prefix`). Branch text is `tree_branch_prefix(row_tree_indent_depth(kind))`; `panel_label` holds human text only (no embedded `└─`). Pixel indent comes from `row_tree_indent_depth()` in [cleave/viz/row_sections.py](cleave/viz/row_sections.py). [cleave/viz/tuning_panel_draw.py](cleave/viz/tuning_panel_draw.py) dispatches on `RowPresentStyle`; expand arrows for expandable headers use `expand_arrow_for_header` or `format_value` on `EXPAND_SUBHEADER` kinds. Panel anchor `RENDER_TIMELINE_HEADER` stays separate (`state.render_timeline.expanded`).

### Root section lists

Top-level global expand sections are derived from `ROOT_SECTION_NODES` and `RENDER_SECTION_NODES` (not a parallel manual tuple). Nested sections are reached through the tree walk.

---

## Panel field manifest

Three registries split tuning panel concerns:

| Registry | Module | Owns |
| --- | --- | --- |
| Semantics | [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py) | affordance, navigation, help |
| Structure | [cleave/viz/row_sections.py](cleave/viz/row_sections.py) | tree nesting, expand/collapse, visibility, `row_tree_indent_depth` |
| Fields | [cleave/viz/row_fields.py](cleave/viz/row_fields.py) | `panel_label`, `format_value`, `apply_horizontal`, `present_style` |

Each `RowKind` in the layout (except `RENDER_SECTION_GAP`) registers a `RowFieldDef`. Tree chrome is `tree_branch_prefix(row_tree_indent_depth(kind))`; labels in `panel_label` have no embedded `└─`.

`RowPresentStyle` drives draw dispatch:

- **LABELED_VALUE** — branch + label + formatted value (most parameter rows)
- **EXPAND_SUBHEADER** — branch + label + expand arrow (preset switching, cleave effects, overlay title/body)
- **COMPOSITE_HEADER** — split-color header with visibility eye (layer, render blocks, Settings)
- **PATH_ICON** — config path, preset dir/file with Material icons
- **FULL_LINE** — transport, layer management, notifications
- **DYNAMIC** — roster-driven rows (`TRACK_EFFECT`; label from descriptor)

Left/Right mutations register `apply_horizontal` on the field def; expand toggles and panel anchors stay in `row_sections.py`.

---

## How to add new UI

### New expandable section

1. Add `RowKind` header with `RowAffordance.EXPAND` in [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py).
2. Add session bool (session-only; list in dirty-test exclusions if applicable) in [cleave/viz/session.py](cleave/viz/session.py).
3. Register `ExpandSectionDef` in [cleave/viz/row_sections.py](cleave/viz/row_sections.py):
   - `read_expanded` and `toggle` wired to session/view state
   - `children` as `SectionNode` leaves and nested `expand` / `conditional` nodes
   - optional `collapse_on_disable` when disable should hide children and show a collapsed arrow
   - optional `append_dynamic_children` for roster-driven leaf rows
4. Attach the section under the correct parent in the section tree (`ROOT_SECTION_NODES`, `TRACK_SECTION`, `RENDER_SECTION_NODES`, or a nested `SectionNode(expand=...)`).
5. Register `RowFieldDef` in [cleave/viz/row_fields.py](cleave/viz/row_fields.py) with `EXPAND_SUBHEADER` (nested subsection) or `COMPOSITE_HEADER` (top-level render/layer header) as appropriate; set `panel_label` (and `header_prefix` / `header_suffix` for composite headers). Expand arrows are automatic via `format_value` or `expand_arrow_for_header`.
6. Ensure the section `*_expanded` flag (or disable state when using `collapse_on_disable`) is in `view_state_structure_signature()` so child rows appear and disappear immediately.
7. No new branches in [cleave/viz/tuning_panel_draw.py](cleave/viz/tuning_panel_draw.py) or [cleave/viz/controls.py](cleave/viz/controls.py) (`apply_expand_toggle` handles expand input).

### New conditional rows

1. Add `RowKind` leaf rows with `RowBehavior` in [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py).
2. Define a `ConditionalRowsDef` with a named predicate; attach as `SectionNode(conditional=...)` under the correct parent in the section tree.
3. Register `RowFieldDef` in [cleave/viz/row_fields.py](cleave/viz/row_fields.py) with `LABELED_VALUE`, `format_value`, and `apply_horizontal`.
4. Add each predicate input field to `view_state_structure_signature()` in [cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py) (layer fields under `layers`, render fields under `render_post_fx` / `render_overlay`, etc.). Without this, show/hide lags until another structural change rebuilds the layout.
5. Add `test_structure_signature_invalidates_on_*` (and optionally a layout row-presence test) in [tests/cleave/viz/test_view_state_structure.py](tests/cleave/viz/test_view_state_structure.py).
6. No arrow, no expanded bool, no parallel predicate map, no new draw or control branches.

### New value row

Standard leaf row (parameter, toggle display, or step value):

1. Add `RowKind` and `RowBehavior` in [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py).
2. Add session or config field if persisted ([cleave/viz/session.py](cleave/viz/session.py) / [cleave/config_schema.py](cleave/config_schema.py)).
3. Attach as a `SectionNode` leaf under the correct parent in [cleave/viz/row_sections.py](cleave/viz/row_sections.py) (or under a `ConditionalRowsDef` when value-gated).
4. Register `RowFieldDef` in [cleave/viz/row_fields.py](cleave/viz/row_fields.py): `panel_label`, `present_style` (usually `LABELED_VALUE`), `format_value`, `apply_horizontal`.
5. No new branches in `tuning_panel_draw.py` or `controls.py`.

### New panel anchor

Rare. Register `PanelAnchorDef` in `row_sections.py` with `content_host`; implement the separate panel host (like timeline strip). Register `RowFieldDef` with `COMPOSITE_HEADER` or appropriate style; arrow uses view-state open flag (not `expand_arrow_for_header`). Do not add `RowLayout` children for strip content.

---

## Non-goals

- **Timeline strip internals:** focus ring with main tree, recording, cue bars, `TimelineControls` key routing stay in timeline modules.
- **Persisting expand state:** all expand flags remain session-only (existing `_SESSION_ONLY_MUTATIONS` pattern).
- **Renaming `panel_open`:** optional `strip_open` rename is out of scope unless explicitly requested later.

---

## Risks and constraints

- **Focus fallback:** `section_header_descriptor()` must stay correct when conditional rows disappear; tree parent pointers should drive this.
- **Build vs runtime visibility:** unify on tree walk with **build-time omission** to match current focus/index behavior.
- **Layer lock:** expandable sub-headers remain navigable when locked; conditional/leaf rules unchanged; verify after migration.
- **No persistence:** expand flags are UI-only and excluded from config snapshots.

## Success criteria

1. Shared vocabulary (expandable section, conditional rows, panel anchor) used in docs and rules.
2. Adding a nested expandable subsection requires section-tree registry, session bool, row kinds, and `RowFieldDef` in [cleave/viz/row_fields.py](cleave/viz/row_fields.py) only (no new control/draw branches).
3. Nesting depth limited only by the section tree, not special-case code paths.
4. Timeline behavior unchanged; documented as panel anchor exception.
