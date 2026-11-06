---
description: Live tuning overlay layout, row registry, typography, and keyboard dispatch
paths:
  - "cleave/viz/**/*.py"
  - "tests/cleave/viz/**/*.py"
globs:
  - "cleave/viz/**/*.py"
  - "tests/cleave/viz/**/*.py"
alwaysApply: false
---

# Live tuning overlay

The shell is a menu bar, a navigator stacked on an inspector in one side column, an optional help column, and a timeline strip. The menu lists commands and checks. All navigation lives in the navigator, and the inspector holds only the settings rows of the selected page. Roots are Settings, Project, Overlay, Post-FX, Pattern Mask, Timeline, and Layers. Each layer has Preset Switching, Compositing, and Cleave Effects pages. The user opens and closes navigator nodes with the twisty, Left/Right, and a click on the label. Selecting a node only opens its ancestors, and Layers starts open. A click on an expandable label selects it and toggles it. Settings and Project have no page of their own, so Enter opens their first child. Overlay, Post-FX, Pattern Mask, Timeline, and layer rows carry clickable on/off and lock icons (`NavNode.toggles`), plus solo on Overlay and layers, and each card row has its own on/off icon. Those pages list the same switches as value rows (`SECTION_SWITCH_KINDS`), and each card page opens with its own on/off row; other child pages have none. A click on an icon selects its row without opening or closing it. Preset curation has no icons and keeps the layer's text badge and lock mark. A child page's E, S, and L keys act on the parent that owns it (`node_control_descriptor`). Settings chooses a side for the navigator column and a side for help. The default puts the navigator column on the left and help on the right. When they share a side, help sits at the window edge and the navigator column stays against the visualiser. The navigator is only as tall as its rows. The inspector fills the rest of the column and keeps at least half the band. Help is an ImGui column. It does not cover the visualiser. Column sides, stack width, and help width are editor preferences. Layer number keys and Ctrl+, select the matching navigator row. Session state becomes view state; inspector pages come from section defs in `row_sections.py`. Warning and error toasts draw centered on the transport bar, only as wide as the message plus a space on each side. Enter, or a click on the toast, clears a timed toast. A pinned error has no click. Overlay Latin text uses bundled DejaVu Sans Mono; icons use Material Icons in `assets/fonts/`.

## Where new fields go

A new field is a page child or a command. Pages are `SectionDef`s in `row_sections.py`, mapped to navigator ids in `inspector.py` (`_PAGE_SECTIONS`, `_LAYER_PAGE_SECTIONS`):

- Settings: `SETTINGS_EDITOR_WINDOW_SECTION`, `SETTINGS_UI_SECTION`, `SETTINGS_LATENCY_COMPENSATION_SECTION`
- Project: `PROJECT_MILKDROP_SECTION`, `PROJECT_COMPOSITOR_SECTION`, `PROJECT_RENDER_SECTION`
- Overlay: `OVERLAY_PAGE_SECTION`, `OVERLAY_OPENING_CARD_SECTION`, `OVERLAY_CLOSING_CARD_SECTION`
- Post-FX: `POST_FX_PAGE_SECTION`, `POST_FX_FADE_SECTION`, `POST_FX_HIGHLIGHT_ROLLOFF_SECTION`, `POST_FX_CHROMA_BOOST_SECTION`, `POST_FX_LIMITER_SECTION`
- Pattern Mask: `PATTERN_MASK_SECTION`
- Timeline: `TIMELINE_PAGE_SECTION`, `BEAT_BAR_GRID_SECTION`, `TIMELINE_CUTS_SECTION`, `SONG_MARKERS_SECTION`, `TIMELINE_PRESETS_SECTION`
- Layers: `LAYERS_SECTION`, and per layer `TRACK_SECTION` (preset curation uses `CURATION_LAYER_SECTION`), `TRACK_PRESET_SWITCHING_SECTION`, `TRACK_COMPOSITING_SECTION`, `TRACK_EFFECTS_SECTION`

A new page needs a navigator entry in `navigator.py`, a section mapping in `inspector.py`, and a header mapping in `row_hotkeys.py`.

The inspector has no open or closed state. A block nested in a page through `SectionNode.subsection` draws a static, non-navigable heading with its rows indented under it.

Conditional rows are siblings shown or hidden by a value predicate. The view-state structure includes or omits them at build time and rebuilds only when `view_state_structure_signature()` changes. A field that gates row presence belongs in that signature; leave value-only fields out. Add a `test_structure_signature_invalidates_on_*` test in `tests/cleave/viz/test_view_state_structure.py`.

New rows use `RowKind`, `RowSpec`, and `SectionNode`. Do not add a per-`RowKind` label or mutation branch in `controls.py`. Overlay chrome lives in `overlay_primitives`. `render_visibility_icon` stays in `row_present_renderers.py`.

The timeline strip stays its own host in `timeline_overlay.py`. Cue blocks are edited on the strip, not in the inspector.

## Parameterized actions

When an action needs parameters, keep the inspector row as a plain `ACTION` line. On Enter, chain one modal per parameter, then apply.

Exception: timeline preset parameters live as value rows on the Timeline Preset page. Apply confirms with Yes/Cancel and lists staged choices as `labeled_lines`.

## Enabled gates the frame path

`enabled=False` on an Overlay, Post-FX, or Pattern Mask header must skip that block in the frame path, not only dim the inspector row. Overlay cards gate per card. Post-FX children must check `session.post_fx.enabled`. New post-FX subsections need an `enabled=False` test.

## Typography

Colors live in `cleave/viz/theme.py`. Use existing roles (`LABEL`, `VALUE`, `ACTION`, `DISABLED`, `MUTED`, `LOCKED`) plus the accent constants already there. Do not invent a new color without adding a theme constant.

Label+value rows: prefix in `LABEL`, value in the row value color. Exceptions (single-color action rows, settings and project headers, transport, notifications, modals) are deliberate; match nearby rows.

## Keyboard dispatch

Layered in `input_dispatch.py`. Modal keys first. Then Tab / Shift+Tab cycles Menu, Navigator, Inspector, and Timeline. Timeline is skipped when the strip is closed. Then the menu bar, command shortcuts, and Ctrl+Up / Ctrl+Down (previous / next top-level navigator node; no effect while the menu bar is focused). Navigator and inspector own their arrows, Enter, Esc, and PageUp/PageDown. An open strip does not take keys. Timeline takes arrows, Enter, Esc, and cue keys only while that region is active. `h` toggles the help column and stays global. Opening or closing help does not move focus. The help column is not a Tab stop, and a click in it does not move focus. There is no panel region and no main-list focus ring.

`row_hotkeys.handle_row_hotkey` is the per-descriptor path for letter, Delete, and Backspace keys, used by the navigator and the inspector.
