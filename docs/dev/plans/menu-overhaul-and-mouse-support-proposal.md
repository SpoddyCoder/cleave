# Menu overhaul and mouse support proposal

Replace the single scrollable tuning tree (expandable sections, one focus ring) with a conventional in-window shell: top menu bar, object navigator, property inspector, and the existing timeline strip. Ship keyboard-first navigation in the new shell, then add mouse hit-testing and interaction on the same layout rects.

Related: [editor-first.mdc](../../../.cursor/rules/editor-first.mdc), [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc), [architecture-principles.mdc](../../../.cursor/rules/architecture-principles.mdc), [roadmap.md](../roadmap.md) (menu and panel overhaul).

---

## Checking the work against the guide

The shell is specified in three places. Use them in this order when implementing or reviewing a phase.

1. This proposal: regions, focus scopes, command registry, phases, and what stays on `RowSpec`. The editor remains OpenGL chrome over projectM. Do not port the design page's DOM into the app.
2. [menu-overhaul-design.html](menu-overhaul-design.html): appearance and interaction. Open it in a browser. Named views are the pictures to match. Keyboard behaviour on that page is the interaction spec for the mock.
3. [menu-overhaul-design.md](menu-overhaul-design.md): which named view, still, or HTML section answers which question, and how the mock's colors map onto [theme.py](../../../cleave/viz/theme.py).

Stills in [menu-overhaul-stills/](menu-overhaul-stills/) are captures of those named views. Prefer the live page. If a still and the page disagree, the page wins; recapture the still using the steps in the design index.

### Inspect with the browser

The Cursor browser does not open `file://` URLs. Serve the plans directory, then open the page over HTTP:

```
/home/fernpa/anaconda3/envs/cleave/bin/python -m http.server 8765 --bind 127.0.0.1 --directory docs/dev/plans
```

Then open `http://127.0.0.1:8765/menu-overhaul-design.html`.

- A hash selects a view: `#shell-split`, `#shell-docked`, `#menu-layers`, `#inspector-locked`, `#inspector-card`, `#hit-rects`.
- From the page, or from browser automation via `Runtime.evaluate`: `cleaveDesign.apply("menu-layers")`. `cleaveDesign.views` lists the names.
- Click the mock window, then use the keys printed above it. The toolbar pills switch layout, timeline, and hit rects. Pill clicks do not change the hash; `cleaveDesign.apply` resets to the named view.
- The shell is `#win`. Static diagrams are `#taxonomy`, `#compare`, `#scopes`, `#registry`, and `#mouse`.
- An element screenshot of `#win` clips the inspector and the timeline. Capture the document rectangle instead: `getBoundingClientRect()` plus `scrollX` and `scrollY`, with `captureBeyondViewport`. The design index has the recapture steps.

Before coding a region, open the matching view and read the still named in the design index. After the region draws, compare the editor to that view: region placement, type roles, focus ring, and the behaviour listed for that view. Match structure and theme roles. Do not pixel-match the mock.

Illustrative shortcut strings, preset names, and field values in the mock are not product data. Menu shape (command vs jump, check mark, disabled) is. Long jobs started from a menu still use the in-window loading screen.

---

## Guiding principles

These override more conservative constraints later in this proposal when they conflict.

1. **Familiar creative-tool UX.** This is a major UI overhaul. Standardise Cleave on the conventions of other audio and video editors (menus, object navigator, property inspector, timeline) so a user feels comfortable immediately, without learning a Cleave-only tree.
2. **Rules follow the UX.** Existing project rules may be broken when principle 1 requires it. Rewrite those rules in the same change so they describe the new shell.
3. **Re-architect for a clean break.** Restructure modules when that keeps the new shell clear and maintainable. Leave as few references to the legacy tuning tree as possible in code, and none in the docs.
4. **Frame rate is a hard constraint.** The editor is unusable if the frame rate drops too low. Layout, hit-testing, and drawing must stay cheap enough for live playback at display rate.

---

## Problem

The live tuning overlay is one long `RowLayout` list. Focus moves through every navigable row (`focus_nav.py` `build_focus_ring`), including deeply nested expand sections (overlay card title/body/animation, post-FX fade in/out, per-layer preset switching). That works for power users who learn the tree, but it is hard to scan, slow to reach distant sections, and unlike familiar creative tools (outliner + properties + menus).

Mouse support is not wired today: drawing is text and icons in `tuning_panel_draw.py` / `row_present_renderers.py` without stable hit regions. Adding click-to-focus and drag-to-scrub on the current flat list would fight the expand/collapse model and duplicate navigation logic.

---

## Goals

- **Primary:** Keyboard-efficient editing in a menu + navigator + inspector layout without losing existing mutations (`RowSpec`, `*_controls`, session dirty tracking).
- **Secondary:** Layout that records `(id, rect)` per interactive item so mouse can attach later without another layout rewrite.
- **Tertiary:** Mouse: hover, click focus, wheel scroll, value drag, resizable splits between navigator and inspector.

### Non-goals (initially)

- OS-native menu bar (editor-first: in-window chrome only).
- Replacing modals, file picker, help overlay, or timeline strip interaction model in phase 1.
- Docking/floating panels like a full DAW; fixed regions with optional width split are enough.
- Rewriting config schema or persist; presentation and navigation only.

### Intent

- Commands and infrequent actions live in menus, not as rows in the object tree.
- The navigator stays shallow (project, render blocks, layers, markers).
- The inspector shows fields for the current selection only (no mile-long mixed list).
- Section locks, preset curation mode, conditional fields, and panel notifications behave as today.

### User effort

Learn menu shortcuts and `Tab` between regions once; layer and timeline workflows stay the same underneath. Mouse is optional until later phases.

---

## What to keep vs replace

| Keep | Replace or thin out |
| --- | --- |
| `RowKind`, `RowDescriptor`, `RowSpec`, domain `row_specs/*` (labels, mutations, help) | Single global focus ring over full `RowLayout` |
| `TuningSession`, `*_controls`, `layer_mutations`, validators, persist | Dozens of session `expanded` flags driving nested tree visibility |
| `SectionNode` / `ExpandSectionDef` as **data** for "which fields belong to which object" | `ExpandSectionDef` as **navigation** (Left/Right on every header in the list) |
| Timeline strip (`timeline_overlay.py`, `TimelineFocus`) | Quick-nav (`Ctrl+Up/Down`) as the main cross-section jump (replaced by menus + `Tab`) |
| `input_dispatch.py` layering (global, modal, context) | Context = one panel; becomes per **focus scope** |
| Theme (`theme.py`), UI fade/width settings | Tree branch glyphs and indent as the primary visual structure |

Mutations stay on `RowSpec.apply_horizontal`, `apply_action`, and controllers. The inspector maps focused field rows to the same descriptors the tree uses today.

---

## Target layout

```
+------------------------------------------------------------------+
|  File  Project  Layers  Render  Timeline  Settings  Help         |  menu bar
+----------+------------------------------+------------------------+
| Navigator|  (optional preview / transport) | Inspector           |
| tree     |                               | grouped fields        |
|          |                               | for selection         |
+----------+------------------------------+------------------------+
|  Timeline strip (when expanded; unchanged anchor semantics)       |
+------------------------------------------------------------------+
|  Visualiser (projectM + compositor)                               |
+------------------------------------------------------------------+
```

### Menu bar (commands)

Top-level menus group **actions** and **navigation jumps**, not every parameter.

| Menu | Examples (illustrative) |
| --- | --- |
| File | Open, Save, Quit (when mid-session open lands) |
| Project | Render job, backup-related actions exposed in UI |
| Layers | Add layer, delete layer, editor mode toggle entry points |
| Render | Toggle overlay/post-FX/pattern mask sections; render start |
| Timeline | Apply presets, reset, cut helpers that are actions today |
| Settings | Open settings inspector root |
| Help | Help overlay (`h`), shortcut reference |

Menu items call a **command registry** (see below). Shortcuts shown in menu labels match keyboard bindings.

Clarify [editor-first.mdc](../../../.cursor/rules/editor-first.mdc): "No native menu bar" means no Win32 menu; an OpenGL-drawn menu bar is intended.

### Navigator (objects)

Shallow tree, selection-driven:

- Settings, Project (optional sub-nodes: Milkdrop, compositor, render)
- Render: Overlays (cards as children), Post-FX, Pattern mask
- Layers: one node per slot (`layer_z_order`), optional child "Effects" list
- Song markers (list of markers as leaves or a single node that selects marker list in inspector)

Selecting a node sets **inspector root**; it does not inline all value rows in the navigator.

### Inspector (properties)

For the navigator selection, show the same leaf rows that today appear under expanded sections: labeled values, paths, toggles, actions that are contextual (not global menu commands). Use **collapsible groups** inside the inspector only (e.g. "Title", "Body" for an overlay card) without participating in the global vertical focus ring across the whole app.

Conditional rows (`ConditionalRowsDef` predicates) become inspector fields hidden when the predicate is false; predicates still belong in `view_state_structure_signature()` when they change which fields exist.

### Timeline strip (panel anchor)

Keep the timeline as a separate host ([live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc) panel anchor). `RENDER_TIMELINE_HEADER` opens the strip; timeline submenu focus (`TimelineFocus`) remains a scope. Do not fold cue editing into `RowLayout`.

### Transport

Transport row can sit above the inspector, in a slim bar under the menu, or pinned at the top of the navigator column. Pick one in phase 1 implementation; avoid duplicating transport in both menu and inspector.

---

## Focus scopes and keyboard

Replace one `MainFocus` ring with explicit scopes:

| Scope | Keys (initial) |
| --- | --- |
| Menu bar | `F10` or `Alt` focus; arrows move; Enter activates; `Esc` closes; `Alt+<letter>` opens menu |
| Navigator | Up/Down move; Left/Right collapse/expand; Enter selects / drills in |
| Inspector | Up/Down move fields; Left/Right step values; Enter action/modal |
| Timeline strip | Existing timeline key map when scope active |
| Modal / help | Unchanged precedence in `input_dispatch.py` |

**Region cycle:** `Tab` / `Shift+Tab` moves Menu -> Navigator -> Inspector -> Timeline (if strip open) -> wrap. Global shortcuts (`Ctrl+Q`, `h`, recording keys) stay global per current rules.

**Retire or remap:** `Ctrl+Up/Down` quick-nav (`move_quick_focus`); either remove or map to "previous/next navigator top-level section" for parity.

Document all bindings in [help_content.py](../../../cleave/viz/help_content.py) when behaviour changes.

---

## Command registry

Introduce a small registry (module under `cleave/viz/`, not in `row_specs`):

- `id`, `label`, `menu_path`, optional `shortcut`
- `enabled(state) -> bool`, `run(controls) -> None`
- Optional `checked(state) -> bool` for toggles mirrored in menus

Menus, future mouse clicks on menu items, and some keyboard shortcuts all invoke `run`. `RowSpec.apply_action` for global actions migrates to commands over time; contextual actions stay on row specs.

Help overlay can list commands grouped by menu for discoverability.

---

## Layout engine and mouse readiness

Even in keyboard-only phases, layout pass should output:

- `LayoutItem`: stable id (e.g. command id, `RowDescriptor`, tree node id), `rect` in panel space, `role` (menu_item, tree_node, field, scrollbar)

Drawing reads items; hit-test walks items top-to-bottom when mouse phases land.

**Mouse phases (later):**

1. Hover highlight (theme role for hover).
2. Click: focus scope + select node or field.
3. Wheel: scroll navigator/inspector lists.
4. Drag on value fields: repeat `apply_horizontal` with delta.
5. Splitter drag between navigator and inspector widths (session or settings-persisted width).

**Dear ImGui option:** [imgui-bundle](https://github.com/pthom/imgui_bundle) or pyimgui could host menu, tree, and widgets in OpenGL faster than bespoke mouse code. Trade-offs: replace much of `tuning_panel_draw.py`, adopt ImGui focus/keyboard (may be weaker than today), bundle size and font theming. Recommendation: spike one inspector page (e.g. Settings preview quality) before committing. If the spike is rejected, stay on custom draw + `LayoutItem` rects.

---

## Migration mapping (current roots)

Today [row_sections.py](../../../cleave/viz/row_sections.py) roots:

- `ROOT_SECTION_NODES`: Settings, Project
- Per-layer `TRACK_SECTION` under dynamic layer list
- `RENDER_SECTION_NODES`: overlays, post-FX, pattern mask, timeline anchor

Proposal mapping:

| Current | Navigator | Inspector |
| --- | --- | --- |
| `SETTINGS_SECTION` | Settings node | All settings fields (editor window / UI / latency as groups) |
| `PROJECT_SECTION` | Project node | Milkdrop, compositor, render children |
| `TRACK_SECTION` per slot | Layer node | Preset, switching, compositing, effects, delete |
| `RENDER_OVERLAYS_SECTION` | Overlays + card nodes | Per-card fields |
| `RENDER_POST_FX_SECTION` | Post-FX node | Nested groups as inspector sections |
| `RENDER_PATTERN_MASK_SECTION` | Pattern mask node | Mask fields |
| `TIMELINE_PANEL_ANCHOR` | Timeline node (opens strip) | Beat/bar grid, cuts, presets, markers in inspector when timeline root selected, or sub-nodes |

`RowLayout` may shrink to "inspector rows for selection" or split into `NavigatorModel` + `InspectorLayout` sharing `SectionNode` definitions.

---

## Phases

### Phase 0 -- Design lock (docs + spike)

- Design guide is locked. Check work against it using [Checking the work against the guide](#checking-the-work-against-the-guide).
- Optional: ImGui spike before committing to custom draw (see Layout engine and mouse readiness).
- When the shell lands, update [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc) and [change-touchpoints.mdc](../../../.cursor/rules/change-touchpoints.mdc) so they describe the new regions.
- Exit: an implementation pass can open each named view and point at the matching editor state.

### Phase 1 -- Menu bar shell (keyboard)

- Draw in-window menu bar; command registry with a subset of actions moved out of the tree.
- Filtering: opening a menu or shortcut jumps navigator/inspector to the right root (bridge from old mental model).
- No mouse required; rects for menu items still recorded.
- CHANGELOG under `### Changed` when user-visible.

### Phase 2 -- Navigator + inspector split

- Implement navigator tree and selection state in `tuning_view_state` (or adjacent).
- Inspector builds row list from existing `SectionNode` graphs for selected object.
- Remove or stop using global expand-in-list for migrated sections; drop redundant `expanded` flags when no longer needed.
- `Tab` scope switching; retire quick-nav or remap.
- Tests: structure signature tests move to inspector visibility; add selection-change tests.

### Phase 3 -- Commands and help parity

- Migrate remaining global `ACTION` rows to commands.
- Help overlay and notifications reference new navigation.
- Section lock and preset curation mode: verify inspector respects `section_locked` / `row_blocked_by_section_lock`.

### Phase 4 -- Mouse

- Hit-test, hover, click focus, wheel scroll.
- Drag-to-adjust on `VALUE_STEP` fields; splitter between columns.
- file-picker plan noted mouse for picker separately ([file-picker-plan.md](file-picker-plan.md)); align hit-test helpers if useful.

### Phase 5 -- Polish

- Persist navigator/inspector width; keyboard menu mnemonics; accessibility contrast pass on hover/focus rings.

---

## Risks and constraints

- **Large touch surface:** `tuning_panel_draw.py`, `row_layout.py`, `focus_nav.py`, `controls.py`, `input_dispatch.py`, `help_content.py`, and cursor rules. Plan phased merges to avoid a long broken branch.
- **Structure signature:** Inspector field visibility must still invalidate `RowLayout` / `view_state_structure_signature()` correctly ([live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc)).
- **Editor-first:** Render, separate, and backup started from menus must show in-window progress and errors, not console-only.
- **Frozen Windows:** No reliance on native menus; test menu keyboard on PyInstaller build when phase 1 ships.
- **AI / MCP later:** Command registry and stable object ids help an in-editor bridge invoke the same operations as the UI ([ai-integration-proposal.md](ai-integration-proposal.md) phase 3/4).

---

## Tests

Per [agent-environment.mdc](../../../.cursor/rules/agent-environment.mdc):

- Unit: command `enabled`/`run` wiring with fake `TuningControls` where patterns already exist for controls.
- `tests/cleave/viz/test_view_state_structure.py`: update for inspector-driven structure, not expand-in-list.
- Overlay/draw tests in `tests/cleave/viz/`: layout item counts or rects for a fixed view state where applicable.
- No routine full editor launch; avoid GL for pure layout logic tests if split from draw.

---

## Success criteria

- A user can complete core workflows (tune layer preset/opacity, edit timeline presets, start render, change settings) using only keyboard in the new shell without scrolling through unrelated sections.
- No regression in section lock, curation mode, or timeline strip behaviour.
- Phase 4: mouse can focus a field and scrub a numeric value without keyboard focus hacks.
- All user-visible changes noted under `## [Unreleased]` in [CHANGELOG.md](../../../CHANGELOG.md).

---

## Leave open (not initial work)

- Full docking, multiple floating panels, or user-rearrangeable workspaces.
- Touch / pen input.
- Replacing timeline strip with a full NLE timeline.
- Native Win32 menu fallback on Windows.
