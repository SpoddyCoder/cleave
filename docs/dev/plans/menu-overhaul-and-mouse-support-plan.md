# Menu overhaul and mouse support plan

Replace the single scrollable tuning tree with an in-window shell: menu bar, transport, object navigator, property inspector, and the existing timeline strip. Draw the new shell with Dear ImGui in the current OpenGL window. Move content across several playable commits. The last content commit deletes the old tree.

Related: [editor-first.mdc](../../../.cursor/rules/editor-first.mdc), [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc), [change-touchpoints.mdc](../../../.cursor/rules/change-touchpoints.mdc), [roadmap.md](../roadmap.md). Follow-up gaps and deferred items: [menu-overhaul-omissions-and-fixes.md](menu-overhaul-omissions-and-fixes.md).

---

## Checking the work against the guide

The shell is specified in three places. Use them in this order when implementing or reviewing a phase.

1. This plan: architecture, focus scopes, command registry, and phases. The editor remains OpenGL chrome over projectM. Do not port the design page's DOM into the app.
2. [menu-overhaul-design.html](menu-overhaul-design.html): appearance and interaction. Open it in a browser. Named views are the pictures to match. Keyboard behaviour on that page is the interaction spec for the mock. A few captions on that page still mention an older phase split and a `LayoutItem` hit-test list. This plan's phase list and the ImGui section below win.
3. [menu-overhaul-design.md](menu-overhaul-design.md): which named view answers which question, and how the mock's colors map onto [theme.py](../../../cleave/viz/theme.py).

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

Preset names, stem labels, and field values in the mock are sample content. Menu shape (command vs jump, check, disabled, shortcut column) matches the page's `MENUS` list, with one shortcut fix in [Locked decisions](#locked-decisions): `Ctrl+R` is only Project > Render project.... Long jobs that this plan actually starts from a menu use the in-window progress path that job already has.

---

## Guiding principles

These override more conservative constraints later in this plan when they conflict.

1. **Familiar creative-tool UX.** Standardise Cleave on menus, an object navigator, a property inspector, and a timeline so a user can scan the project without learning a Cleave-only tree.
2. **Rules follow the UX.** Rewrite a project rule in the same phase that breaks it, so the rule describes the shell.
3. **Re-architect for a clean break.** Restructure modules when that keeps the shell clear. The last content phase leaves no second navigation model in code or in the docs.
4. **Frame rate is a hard constraint.** The editor is unusable if live playback drops below display rate. ImGui is one frame per editor frame, on the existing GL context, with fonts built once.

---

## Problem

The live tuning overlay is one long `RowLayout` list. Focus moves through every navigable row (`focus_nav.py` `build_focus_ring`), including nested expand sections. That is hard to scan, slow across distant sections, and unlike other audio and video editors.

The window is already OpenGL: [loading.py](../../../cleave/viz/loading.py) `_set_gl_mode` uses `pygame.OPENGL | pygame.DOUBLEBUF`, and [app.py](../../../cleave/viz/app.py) `VisualizerApp.run` flips that display. The tuning UI is a pygame surface uploaded as a texture. It has no widget hit targets, so mouse-on-the-tree would invent a second interaction model.

---

## Goals

- Keyboard editing in a menu, navigator, and inspector without losing mutations (`RowSpec`, `*_controls`, session dirty tracking).
- Dear ImGui as the shell from the first commit, in the existing GL window.
- Mouse gestures the design specifies: hover, wheel scroll, sideways value drag, and column splitters. `shell-docked` and saved column widths land in polish.

### Non-goals

- A Win32 menu bar.
- Mid-session Open. That stays [file-picker-plan.md](file-picker-plan.md) phase 3.
- Replacing modals, the help overlay, or the timeline strip's cue editing.
- Full docking, floating panels, touch, or a second UI toolkit behind ImGui.
- Rewriting the config schema, except the polish-phase editor setting for column widths.
- Building in-window Separate, Backup, or Restore. Those commands stay on the CLI.

---

## Locked decisions

Do not re-open these in a later phase.

1. **One phase, one playable commit.** Sub-steps are the checklist inside that commit. Content moves in slices: menu bar while the current tree still works; then settings and project; then layers; then render blocks (overlays, post-FX, pattern mask); then timeline and song markers. The old list shrinks as each slice moves. The last content phase deletes the old tuning tree and the global focus ring. Do not keep two full navigation models.
2. **Dear ImGui from phase 1.** Not a spike and not a later option. Dependency is `imgui-bundle` (pthom). Nothing in [requirements.txt](../../../requirements.txt) or [requirements-freeze.txt](../../../requirements-freeze.txt) provides ImGui today. ImGui is in-window OpenGL chrome, not a Win32 menu. The design's hit-rects view still says what is clickable; those roles are ImGui items, not a custom `LayoutItem` hit-test engine. Keyboard scopes from the design still apply. ImGui's default Tab-between-widgets must not replace the region cycle.
3. **`shell-split` until polish.** `shell-docked` lands in phase 7. Default column widths are 230px (navigator) and 495px (inspector) until then. The mock's inspector column is 330px; the editor uses one and a half times that width so labels and stepped values fit.
4. **Quick-nav remap.** `Ctrl+Up` / `Ctrl+Down` become previous / next top-level navigator node (Settings, Project, Render, Layers, Song markers). Do this in phase 2, when the navigator appears, not before.
5. **File menu.** Save (`Ctrl+S`) and Quit (`Ctrl+Q`) call the existing commands. Open (`Ctrl+O`) stays disabled. Do not pull file-picker phase 3 into this plan.
6. **Same-phase removal.** When a command becomes reachable from the menu or the inspector, remove the matching old-tree row in that same phase. Menu and inspector may both call one command when the mock shows both (Add layer, Delete layer, timeline preset actions, Measure latency). Do not leave the tree row for a later parity pass.
7. **Column widths.** Fixed defaults until polish. Polish persists them in editor settings (same store as UI width: user config via [user_config.py](../../../cleave/user_config.py) and [editor.py](../../../cleave/config_schema/editor.py)), not in the project file.
8. **One render command.** Label like the mock's Project entry "Render project...", shortcut `Ctrl+R`, Project menu only. The Render menu is toggles and jumps. Do not bind `Ctrl+R` to a second "Start render..." item. The HTML mock still shows that duplicate; do not add it in the app.

---

## What stays

| Keep | Stop using as navigation |
| --- | --- |
| `RowKind`, `RowDescriptor`, `RowSpec`, domain `row_specs/*` | One global focus ring over the full list |
| `TuningSession`, `*_controls`, `layer_mutations`, validators, persist | Session `expanded` flags that only hide tree rows |
| `SectionNode` / `ExpandSectionDef` as which fields belong to which object | `ExpandSectionDef` as Left/Right on every header in one list |
| Timeline strip (`timeline_overlay.py`, `TimelineFocus`) | `Ctrl+Up` / `Ctrl+Down` as the main cross-section jump |
| `input_dispatch.py` layering (global, modal, context) | Context meaning "the whole panel" |
| Theme (`theme.py`), UI fade, help overlay, modals, loading screen | Tree branch glyphs as the primary structure |

Mutations stay on `RowSpec.apply_horizontal`, `apply_action`, and the controllers. The inspector presents the same descriptors. Dirty tracking stays computed.

---

## Target shell

`shell-split` from phase 2 through phase 6:

```
+------------------------------------------------------------------+
|  File  Project  Layers  Render  Timeline  Settings  Help         |
+------------------------------------------------------------------+
|  transport (play, time, bar, bpm, fps, record)                    |
+----------+------------------------------+------------------------+
| Navigator|  visualiser                  | Inspector              |
| 230px    |  projectM + compositor       | 495px                  |
+----------+------------------------------+------------------------+
|  Timeline strip (own focus scope; hidden when closed)            |
+------------------------------------------------------------------+
```

Phase 7 adds `shell-docked`: navigator and inspector stacked on the left, visualiser filling the rest. Same scopes, same timeline.

Unmigrated sections stay on the current tuning panel, drawn over the visualiser column, until their phase removes them. The panel must not cover the menu, navigator, or inspector. See [Migration bridge](#migration-bridge).

### Transport

A slim bar under the menu, fed by the existing transport and playback state. One transport. It is not repeated in the inspector. The transport row leaves the old list in phase 2.

### Navigator

Shallow tree. Selecting a node sets the inspector root. Value rows do not appear in the navigator.

From the mock's `TREE`, top to bottom:

- Settings
- Project
- Render
  - Overlays, with one child per overlay card (labels from the card row specs, not the mock's "Intro" / "Credits")
  - Post-FX
  - Pattern mask (show an off badge when the section is disabled)
  - Timeline
- Layers, one child per slot in `layer_z_order` (stem label from the slot; lock mark when the section is locked)
- Song markers, one node (badge is the marker count)

Effects, project subgroups, and timeline field groups are inspector groups. They are not navigator children.

Phase 2 introduces all five top-level nodes so `Ctrl+Up` / `Ctrl+Down` has somewhere to land. Only Settings and Project have inspectors then. Render, Layers, and Song markers gain children and inspectors in phases 3 to 5.

### Inspector

For the selection, show the leaf rows that today sit under that object's sections: labeled values, paths, toggles, and contextual actions. Collapsible groups stay inside the inspector (card title / body, post-FX fade, layer effects). They do not join a global vertical ring.

Group titles follow the mock's pages, populated from `row_specs/*` and `SectionNode` in [row_sections.py](../../../cleave/viz/row_sections.py):

| Node | Groups (source sections) |
| --- | --- |
| Settings | preview quality; Editor Window; UI; Latency Compensation (includes Measure latency) |
| Project | ProjectM; Compositor; Render Project (includes Render the Project) |
| Layer slot | preset directory and preset; preset switching; compositing; cleave effects; Delete Layer |
| Layers root | layer count; Add Layer |
| Overlays | enabled; cards; Add Card |
| Overlay card | animation; title; body; background; card time |
| Post-FX | fade; highlight rolloff; desaturation; chroma boost; visual limiter |
| Pattern mask | mask fields from `row_specs/pattern_mask.py` |
| Timeline | timeline preset; beat / bar grid; cue fades |
| Song markers | the marker list |

Conditional rows (`ConditionalRowsDef` predicates) stay hidden when the predicate is false. Predicates that change which fields exist stay in `view_state_structure_signature()`.

The timeline strip stays its own host. Cue blocks are edited on the strip. The timeline inspector is only the groups in the table above.

### Menu taxonomy

`MENUS` in the design page is the item list. Green in `menu-layers` means command. Plain means jump. A check mirrors `checked(state)`. Grey means disabled. The shortcut column is normative, except Render has no "Start render..." item and no second `Ctrl+R`.

| Menu | Item | Kind | Shortcut | When it runs |
| --- | --- | --- | --- | --- |
| File | Open project... | command | `Ctrl+O` | Stays disabled. [file-picker-plan.md](file-picker-plan.md) phase 3. |
| File | Save | command | `Ctrl+S` | Phase 1. `TuningControls.prompt_save_config`. |
| File | Quit | command | `Ctrl+Q` | Phase 1. `TuningControls.try_quit`. |
| Project | Project settings | jump | | Phase 2. Selects the Project node. |
| Project | Separate stems... | command | | Stays disabled. CLI `cleave separate` only. |
| Project | Render project... | command | `Ctrl+R` | Phase 1. `ProjectRenderController.prompt`. |
| Project | Backup... | command | | Stays disabled. CLI `cleave backup` only. |
| Project | Restore... | command | | Stays disabled. CLI `cleave restore` only. |
| Layers | Add layer | command | `Ctrl+L` | Phase 3. `LayerLifecycleControls.prompt_add`. |
| Layers | Delete layer | command | | Phase 3. `prompt_delete` for the selected slot. |
| Layers | one jump per slot | jump | `1` through `8` | Phase 3. Not while the timeline strip has scope (those keys already select lanes in `TimelineControls`). |
| Layers | Preset curation mode | check | | Phase 1. Existing editor-mode switch. |
| Render | Overlays | check | | Phase 4. Section enabled flag. |
| Render | Post-FX | check | | Phase 4. |
| Render | Pattern mask | check | | Phase 4. |
| Render | Edit overlays | jump | | Phase 4. |
| Render | Edit post-FX | jump | | Phase 4. |
| Timeline | Show timeline strip | check | `T` | Phase 5. Same open/close as today's `T`. |
| Timeline | Apply timeline preset | command | | Phase 5. Same action as the row. |
| Timeline | Reset timeline | command | | Phase 5. |
| Timeline | Snap cues | command | | Phase 5. |
| Timeline | Undo last cut | command | | Stays disabled. No cut-undo command exists. |
| Timeline | Song markers | jump | | Phase 5. |
| Settings | Editor settings | jump | `Ctrl+,` | Phase 2. Selects Settings. |
| Settings | Measure latency... | command | | Phase 1. Existing measure-latency action. |
| Help | Help overlay | command | `H` | Phase 1. Toggles `help_visible`. |
| Help | Keyboard shortcuts | command | | Phase 1. Opens that same help overlay. |
| Help | About Cleave | command | | Stays disabled. No about command exists. |

Layer jump labels and the number of layer rows come from `layer_z_order`, not from the four sample stems in the mock. `F3` (overlay profiler) stays a hidden global. It is not a menu item.

Bare `R` still starts and stops timeline recording when the strip has scope. `Ctrl+R` is only the render command, checked with `mod_ctrl` in `_handle_global_keydown`.

---

## Focus scopes

| Scope | Keys |
| --- | --- |
| Menu bar | `F10` or `Alt` focuses the bar. Arrows move. Enter activates. `Esc` closes. |
| Navigator | Up/Down move. Left/Right collapse or expand. Enter focuses the inspector when that node has one. |
| Inspector | Up/Down move fields and group headers. Left/Right step values (`apply_horizontal`). Enter runs the row action or opens the existing modal. |
| Timeline strip | Existing timeline key map when this scope is active. |
| Modal / help | Unchanged precedence in `input_dispatch.py`. |

**Region cycle:** `Tab` / `Shift+Tab` moves Menu -> Navigator -> Inspector -> Timeline when the strip is open, then wraps. When the strip is closed, Timeline is skipped. Global shortcuts (`Ctrl+Q`, `Ctrl+S`, `H`, recording keys, seek) stay global.

**ImGui keyboard:** leave `ImGuiConfigFlags_NavEnableKeyboard` off for the life of the context. Do not call `SetKeyboardFocusHere` to move between menu, navigator, and inspector. `input_dispatch.py` owns Tab, Shift+Tab, F10, Alt, and the arrows for the active scope, and it does not forward those keys into ImGui. Mouse events still go to the ImGui pygame backend so clicks hit menu items, nodes, and fields. Text entry stays on the existing modal `TEXTINPUT` path. Phase 7 adds Alt+letter mnemonics in that same dispatcher (underlined first letter on File, Project, Layers, Render, Timeline, Settings, Help). That is not ImGui's default menu navigation.

Help text in [help_content.py](../../../cleave/viz/help_content.py) changes only for bindings that already changed in that phase. Phase 5 rewrites the navigation section so it describes the shell.

---

## Command registry

New module `cleave/viz/commands.py` (not under `row_specs`):

- `id` (stable string, for example `file.save`, `project.render`)
- `label`, `menu_path`, optional `shortcut`
- `enabled(state) -> bool`
- `run(controls) -> None`
- optional `checked(state) -> bool` for menu checks

Menus, shortcuts, and clicks all call `run`. Contextual field edits stay on `RowSpec`. Global actions that move to a command lose their tree row in that phase (locked decision 6). Ids stay stable for a later in-editor bridge ([ai-integration-proposal.md](ai-integration-proposal.md)).

---

## ImGui host

Phase 1 adds `cleave/viz/shell_host.py`.

- Pin `imgui-bundle` in [requirements.txt](../../../requirements.txt) and [requirements-freeze.txt](../../../requirements-freeze.txt). [requirements-dev.txt](../../../requirements-dev.txt) already includes `requirements.txt`. Do not use `hello_imgui` to open a window.
- The pygame renderer attaches to the current display. Confirm `imgui_bundle.python_backends.pygame_backend.PygameRenderer` on first import; if that path has moved, use the pygame backend that draws into the current context. `imgui-bundle` is not installed in the checkout today.
- Create the ImGui context once the live GL window exists (`VisualizerApp.run`, after [loading.py](../../../cleave/viz/loading.py) has called `set_mode`). Destroy it in the existing `finally`, before `pygame.quit()`.
- Build the font atlas once. Do not clear or rebuild fonts per frame.
- The run loop already pumps `pygame.event.get()` once. Pass mouse and window events to the backend from that loop. Do not pump events a second time inside the backend.
- Draw one ImGui frame per editor frame, after the overlay textures in `_tick_frame_live_overlay` / [overlay_draw.py](../../../cleave/viz/overlay_draw.py), and before `pygame.display.flip()`.
- Save and restore GL state around the ImGui render. Post passes in [gl_post_process.py](../../../cleave/gl_post_process.py) already do this because the compositor and ImGui share the pygame context. A dirty VAO, shader, scissor, or viewport will blank the next visualiser frame.
- Map colors from existing [theme.py](../../../cleave/viz/theme.py) roles (`LABEL`, `VALUE`, `ACTION`, `DISABLED`, `LOCKED`, `HIGHLIGHT`, `CONFIG_DIRTY`, and the timeline accents). Add a hover role only in phase 6.

Help, modals, and the timeline strip stay on the pygame overlay path. The shell does not reimplement them as ImGui windows.

Watch the existing `FrameRateMeter` with the shell up. One ImGui frame, one context, fonts once. If display fps falls, the first place to look is an extra `new_frame`, a font rebuild, or GL state leaked into projectM.

### Migration bridge

Phases 2 to 4 keep a shrinking tuning panel so unmigrated sections stay editable.

- The panel draws over the visualiser only.
- Its focus ring contains only rows that have not moved yet.
- `Tab` does not enter the panel. The cycle is the design cycle.
- Choosing an unmigrated top-level node (Render before phase 4, Layers before phase 3, Song markers before phase 5) focuses that section on the leftover panel.
- `Esc` from the navigator returns to the leftover panel only when leftover rows exist.
- Phase 5 deletes the panel, `build_focus_ring`, expand-in-list navigation, and `expanded` flags that nothing else reads.

---

## Phases

Each phase is one commit a person can play. User-visible phases add one `### Changed` bullet under `## [Unreleased]` in [CHANGELOG.md](../../../CHANGELOG.md). Do not bump `cleave.__version__`.

Tests use `/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py`. Prefer `-k`. No routine editor launch ([agent-environment.mdc](../../../.cursor/rules/agent-environment.mdc)).

### Phase 1: Menu bar

**Goal.** ImGui menu bar on the live window, full taxonomy visible, commands that already work turned on, old tree still usable.

**Sub-steps.**

- Dependencies and `shell_host.py` as in [ImGui host](#imgui-host).
- `commands.py` and a menu draw (`BeginMainMenuBar`) of every item in the taxonomy table. Disabled items stay visible.
- Wire Save, Quit, Help overlay, Keyboard shortcuts (same overlay), Render project (`Ctrl+R`), Measure latency, and Preset curation mode. Each `run` calls the controller named in the table.
- Remove the matching tree rows in this commit: the project save row (`CONFIG_HEADER`), `PROJECT_RENDER_ACTION`, `SETTINGS_MEASURE_LATENCY`, and `SETTINGS_EDITOR_MODE`. Leave every other row.
- Leave Open, Separate, Backup, Restore, About, Undo last cut, and every jump disabled.
- Keyboard nav flag off, as in [Focus scopes](#focus-scopes). `F10` / `Alt` and arrows operate the bar. Alt+letter waits for phase 7.
- Update [editor-first.mdc](../../../.cursor/rules/editor-first.mdc): "No native menu bar" means no Win32 menu. An ImGui menu bar in the OpenGL window is the intended chrome.
- Help: add `F10` / `Alt` and `Ctrl+R` only. Leave the tree navigation lines until the keys they describe have changed.

**Exit.** Play: open each menu, Save, Quit (including the unsaved prompt), Help, start the render confirm modal, measure latency, toggle preset curation. Edit a layer preset from the old tree. The visualiser still advances at display rate after the menu has drawn.

**Tests.** New registry tests under `tests/cleave/viz/`: `enabled` / `run` with the same fake controls patterns the suite already uses; taxonomy covers every id; a single item owns `Ctrl+R`; Open, Separate, Backup, Restore, About, and jumps report disabled. `tests/run_unit_tests.py -k commands`. No GL window.

**Compare.** `menu-layers`, `#taxonomy`, `#registry`. Ignore the mock's Render > "Start render..." row.

### Phase 2: Shell, settings, and project

**Goal.** `shell-split` chrome. Settings and Project edit in the inspector. Those sections leave the old tree.

**Sub-steps.**

- Layout regions: menu, transport under the menu, navigator, visualiser, inspector, timeline strip anchor. Widths fixed at 230 and 495. Do not draw `shell-docked`. Splitters are not draggable yet.
- Move the transport readout into the bar. Remove the transport row from `RowLayout`.
- Navigator: five top-level nodes. Settings and Project inspectors built from `SETTINGS_SECTION` and `PROJECT_SECTION` (`SectionNode` children become inspector groups). Render, Layers, and Song markers select the matching leftover header via the [migration bridge](#migration-bridge).
- Drop Settings and Project from the old list, including rows already removed in phase 1.
- `Tab` / `Shift+Tab` region cycle in `input_dispatch.py`.
- Replace `move_quick_focus` (`Ctrl+Up` / `Ctrl+Down`) with previous / next top-level node.
- Enable Project settings and Editor settings jumps. Measure latency and Render the Project appear on the inspectors as well as the menus, one `run` each.
- Style ImGui from theme roles. No new color.
- Help: document Tab and the new `Ctrl+Up` / `Ctrl+Down`. Do not yet describe layer or render navigation as the shell.

**Exit.** Play: Tab around the four regions (three when the strip is closed). Edit a settings field and a project field in the inspector. `Ctrl+Up` / `Ctrl+Down` visit Settings, Project, Render, Layers, Song markers. Render and Layers still edit on the leftover panel. Save still works. Column edges sit at 230 and 495 and do not drag.

**Tests.** `tests/run_unit_tests.py -k "structure_signature or navigator or shell_focus"`. Extend `tests/cleave/viz/test_view_state_structure.py` so settings and project field visibility follows the inspector, and those sections are absent from the leftover `RowLayout`. Selection-change test: Project node builds the project groups. Quick-nav test: the five top-level ids, in order.

**Compare.** `shell-split` for chrome, transport placement, and column widths. The still's Layer 2 selection is phase 3; do not match that inspector yet. `#scopes`. Do not match `shell-docked`.

### Phase 3: Layers

**Goal.** One navigator node per layer slot, with inspector groups. Layer rows leave the old tree.

**Sub-steps.**

- Children of Layers from `layer_z_order`. Lock mark on the node when the section is locked. Labels from the slot, not the mock stems.
- Inspector groups: preset directory and preset, preset switching, compositing, cleave effects (effects stay a group, not navigator children), Delete Layer. Layers root: count and Add Layer.
- Add layer and Delete layer commands, menu and inspector, both calling `LayerLifecycleControls`. `Ctrl+L` for Add. Delete uses the selected slot.
- Layer jumps `1` through `8` when the timeline strip does not have scope. Inside timeline scope, `TimelineControls` keeps those keys.
- Remove per-slot `TRACK_SECTION` rows and `LAYER_MANAGEMENT_ADD` from the leftover list.
- Section lock: inspector rows use `section_lock_blocks_mutation` the same way the tree did. Preset curation mode still limits which layer rows exist, now on the inspector.
- Enable the Layers menu jumps and the curation check's navigator effect (the check itself was wired in phase 1).

**Exit.** Play: pick each layer from the navigator and from the Layers menu. Change preset, opacity, and an effect. Lock a layer and confirm the inspector refuses edits and shows the locked role. Add and delete a layer from both the menu and the inspector. Curate presets. Render sections still edit on the leftover panel.

**Tests.** `tests/run_unit_tests.py -k "layer or section_lock or curation"`. Nodes match `layer_z_order`. Locked slot does not apply a step. Add and delete call one command from menu and inspector. Leftover `RowLayout` has no track rows.

**Compare.** `inspector-locked`, `menu-layers`. Layer names in the still are sample stems.

### Phase 4: Render blocks

**Goal.** Overlays (with card nodes), Post-FX, and pattern mask live under Render. Those sections leave the old tree.

**Sub-steps.**

- Navigator children from `RENDER_OVERLAYS_SECTION`, `RENDER_POST_FX_SECTION`, and `RENDER_PATTERN_MASK_SECTION`. One card node per card. Pattern mask badge when disabled.
- Inspectors from those section graphs, including nested groups (card title/body, post-FX fade and rolloff). Conditional rows still follow their predicates and `view_state_structure_signature()`.
- Render menu checks toggle overlays, post-FX, and pattern mask `enabled`. Edit overlays and Edit post-FX jump to those nodes. No "Start render..." item.
- Remove those three sections from the leftover list. Leave the timeline anchor and song markers.
- `enabled=False` still skips that block on the frame path, not only in the inspector.

**Exit.** Play: toggle overlays, post-FX, and pattern mask from the Render menu and see the check, the badge, and the frame path follow. Edit one overlay card, including a collapsed group. Edit a conditional post-FX field and confirm it hides when the predicate is false. `Ctrl+R` still starts render and does not appear under Render. Timeline fields still edit on the leftover panel.

**Tests.** `tests/run_unit_tests.py -k "structure_signature or overlay or post_fx or pattern_mask"`. Card count drives navigator children. A predicate that hides rows changes the signature. Those three sections are absent from the leftover layout. Render menu checks map to the enabled flags.

**Compare.** `inspector-card`, `#taxonomy` (Render menu, minus "Start render...").

### Phase 5: Timeline, song markers, and the old tree

**Goal.** Timeline and song markers have inspectors. The leftover panel, global focus ring, and unused expand flags are gone.

**Sub-steps.**

- Timeline child under Render. Inspector groups: timeline preset, beat / bar grid, cue fades. Actions (Apply, Reset, Snap cues, Apply to Cues, Remove from Cues) call the existing row actions. Menu and inspector share `run` where the mock shows both.
- Song markers node. Inspector is the marker list. The menu jump selects it.
- Show timeline strip (`T`) calls the same open/close as today. Timeline scope, cue editing, and `timeline_overlay.py` stay as they are. Do not fold cue blocks into the inspector.
- Enable the Timeline menu commands except Undo last cut.
- Delete the leftover tuning panel, `build_focus_ring` for the main list, expand-in-list Left/Right, and session `expanded` flags that only served that list. Inspector group open/closed state is view state, not those flags.
- Remove the migration bridge (`Esc` to the leftover panel, unmigrated-node handoff).
- Rewrite [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc) and [change-touchpoints.mdc](../../../.cursor/rules/change-touchpoints.mdc) so new fields go to an inspector group or a command, conditional rows and the structure signature stay, and the timeline strip stays a panel anchor.
- Rewrite the help navigation section for the shell: region cycle, navigator, inspector, menu, timeline scope.

**Exit.** Play: edit a timeline preset field, apply it, toggle the strip, edit a song marker, and scrub cues on the strip with the timeline keys. There is no second list anywhere. `Tab` never lands on a tree. Help text matches the keys.

**Tests.** `tests/run_unit_tests.py -k "structure_signature or focus_nav or timeline or song_marker or help_content"`. No main-list focus ring. Timeline and marker rows are absent from any leftover layout. Help navigation mentions the region cycle and does not tell the user to walk one tree.

**Compare.** `shell-split` with the Timeline node and the Song markers node selected. `#compare`, `#scopes`. Cue blocks on the strip, not in the inspector.

### Phase 6: Mouse gestures

**Goal.** The pointer behaviour the design adds beyond ImGui's default click-to-activate.

Clicks on menu items, nodes, and fields already work once those widgets exist. This phase does not add `shell-docked`.

**Sub-steps.**

- Add one hover role in [theme.py](../../../cleave/viz/theme.py) and use it for the translucent label wash. No one-off color in the draw path.
- Wheel scrolls the navigator and the inspector.
- Sideways drag on a numeric value repeats the same step as Left/Right (`apply_horizontal` with delta). Locked rows do not change. This is not an ImGui slider widget with a different scale.
- Drag the boundary between navigator and visualiser, and between visualiser and inspector. Widths stay session-only until phase 7. Defaults remain 230 and 495 when the user has not dragged.
- Hit targets match the roles on `hit-rects`: `menu`, `menu_item`, `tree_node`, `field`, `group`, `toggle`, `splitter`, `timeline_lane`, `transport`.

**Exit.** Play: hover a row and see the new role. Scroll both columns with the wheel. Drag a numeric value sideways and match Left/Right. Drag both splitters. Keyboard scopes still work, including Tab. The layout is still `shell-split`.

**Tests.** `tests/run_unit_tests.py -k "shell_mouse or apply_horizontal or theme"`. Drag delta calls the same mutation as a horizontal step. Locked drag does not. Theme exports the hover role. No editor launch.

**Compare.** `hit-rects`, `#mouse`. Drag a value and a splitter on the mock before copying the gesture.

### Phase 7: Polish

**Goal.** `shell-docked`, remembered column widths, menu mnemonics, focus-ring contrast.

**Sub-steps.**

- `shell-docked` layout mode: navigator and inspector on the left, visualiser in the remaining space. Same scopes and timeline. Switching mode does not move selection.
- Persist navigator and inspector widths in user editor settings, next to `ui_width`, through [user_config.py](../../../cleave/user_config.py) and [editor.py](../../../cleave/config_schema/editor.py). Absent keys mean 230 and 495. Do not write them into the project file.
- Mnemonics: underline the first letter. `Alt` plus that letter opens the menu (F, P, L, R, T, S, H), handled in `input_dispatch.py` with keyboard nav still off.
- Focus ring contrast against the theme highlight so the active field is readable on the inspector wash and on the hover wash.

**Exit.** Play: switch to docked and back. Resize both columns, quit, relaunch, and see the widths return. `Alt+F` opens File. The focus ring is visible on a hovered row. Project YAML does not gain a column-width field.

**Tests.** `tests/run_unit_tests.py -k "user_config or editor_settings or shell_layout"`. Round-trip widths in user config. Missing keys use 230 and 495. Project persist payload has no column widths. Mnemonic letters match the seven menus.

**Compare.** `shell-split` and `shell-docked`. Underlined menu letters. Focus ring on `inspector-card` and `inspector-locked`.

---

## Risks

- **Structure signature.** Inspector visibility has to invalidate `view_state_structure_signature()` the same way expand-in-list did ([live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc)). A predicate that adds or removes fields belongs in that signature.
- **Editor-first progress.** Render already uses `ProjectRenderController` (confirm modal, then in-window progress, window stays up). Keep that path. Separate, Backup, and Restore stay disabled here. If a later change enables them from the menu, they need the loading screen and a modal on failure, not stdout.
- **Windows freeze, phase 1 only.** After the menu bar works on checkout, try keyboard menu use once on the PyInstaller build ([windows-freeze.md](../windows-freeze.md)). That check is not a gate on phases 2 to 7.
- **GL state.** ImGui and moderngl share one context. Phase 1 is where a leaked viewport or shader will show up as a blank visualiser. Fix it there.
- **Command ids.** Registry ids are the handle a later AI or MCP bridge should call. Do not rename them casually ([ai-integration-proposal.md](ai-integration-proposal.md)).
- **Frame rate.** One ImGui frame per editor frame, no extra context, fonts once. Confirm with `FrameRateMeter` at the phase 1 exit.

---

## Tests

Per phase above. Shared rules:

- Pure registry, navigator, and signature tests stay off the GL window.
- `tests/cleave/viz/` mirrors `cleave/viz/`.
- Do not launch the editor for routine verification.

---

## Success criteria

- Core workflows (layer preset and opacity, timeline preset, render, settings) work from the keyboard in the shell without scrolling a mixed list.
- Section lock, preset curation, conditional rows, and the timeline strip behave as they do today.
- Phase 6: the pointer can scroll, scrub a numeric value through `apply_horizontal`, and resize the two columns.
- Phase 7: docked layout and widths survive a restart in user config only.
- Each user-visible phase has a `### Changed` bullet under `## [Unreleased]`.

---

## Leave open

- Full docking, floating panels, and user-rearranged workspaces beyond `shell-split` and `shell-docked`.
- Touch and pen.
- Replacing the timeline strip with a full NLE.
- A native Win32 menu.
- Mid-session Open (`Ctrl+O`), which remains [file-picker-plan.md](file-picker-plan.md) phase 3.
- Swapping ImGui for another widget backend.
- In-window Separate, Backup, Restore, About, and Undo last cut.
