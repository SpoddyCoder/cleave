# Menu overhaul design index

How to use [menu-overhaul-design.html](menu-overhaul-design.html) while building the shell in [menu-overhaul-and-mouse-support-plan.md](menu-overhaul-and-mouse-support-plan.md).

The HTML page is the visual and interaction contract. This file is the map. The plan is the architecture and the phases. The editor stays OpenGL chrome; do not port the page's DOM.

## Named views

Open the HTML and append the hash, or evaluate `cleaveDesign.apply(name)`. `cleaveDesign.views` lists the names. Applying a view scrolls to the shell, resets the mock, then sets that state. Toolbar pills do not update the hash.

| View | Still | What to match |
| --- | --- | --- |
| `shell-split` | [shell-split.png](menu-overhaul-stills/shell-split.png) | Default chrome. Menu, transport under the menu, navigator, visualiser, inspector, timeline strip. Navigator focused on Layer 2. Columns start at 230px and 330px. |
| `shell-docked` | [shell-docked.png](menu-overhaul-stills/shell-docked.png) | Navigator and inspector docked left; visualiser fills the rest. Same scopes and timeline. |
| `menu-layers` | [menu-layers.png](menu-overhaul-stills/menu-layers.png) | Layers menu open. Green items are commands. Plain items jump to a navigator node. Check mark mirrors `checked(state)`. Grey text is disabled. Shortcut column on the right. |
| `inspector-locked` | [inspector-locked.png](menu-overhaul-stills/inspector-locked.png) | Layer 3 selected, inspector focused. Locked rows and the lock control use the locked role. The navigator shows the lock mark. |
| `inspector-card` | [inspector-card.png](menu-overhaul-stills/inspector-card.png) | One overlay card. Collapsible groups stay inside the inspector. Dirty fields show an asterisk. Focus ring is on the dirty field, not on a global tree. |
| `hit-rects` | [hit-rects.png](menu-overhaul-stills/hit-rects.png) | Dashed outlines are the clickable roles (`data-role` on the mock): `menu`, `menu_item`, `tree_node`, `field`, `group`, `toggle`, `splitter`, `timeline_lane`, `transport`. The plan draws these as ImGui items. |

`#win` is the shell. Screenshot that element when recapturing a still.

## Static sections

These are text and diagrams. Read the HTML section. A still is only a reminder of the picture.

| Section | Id | Still | Question it answers |
| --- | --- | --- | --- |
| Menu taxonomy | `#taxonomy` | | Full menu list: command vs jump, checks, disabled, shortcuts. Same items as the `MENUS` array in the page script, except the plan drops Render > Start render... so `Ctrl+R` is only Project > Render project.... |
| Before and after | `#compare` | [compare.png](menu-overhaul-stills/compare.png) | Why the global focus ring goes away. |
| Focus scopes and keyboard | `#scopes` | | Tab order, per-scope keys, input precedence, selection driving the inspector. |
| Command registry | `#registry` | | One `run` path for menu, shortcut, click, and a later help or MCP caller. |
| Mouse phases | `#mouse` | [mouse.png](menu-overhaul-stills/mouse.png) | Hover, click, wheel, value drag, splitter. The picture is what must be clickable. Phase 6 implements those gestures on ImGui items. |

## Theme roles

Mock CSS variables are appearance targets. Draw with the existing constants in [theme.py](../../../cleave/viz/theme.py). Do not add a color for a role that already exists.

| Mock | Theme |
| --- | --- |
| `--label` | `LABEL` |
| `--value` | `VALUE` |
| `--action` | `ACTION` |
| `--disabled` | `DISABLED` |
| `--locked` | `LOCKED` |
| `--lock-icon` | `LOCK_ICON` |
| `--highlight` | `HIGHLIGHT` |
| `--dirty` | `CONFIG_DIRTY` |
| `--bar-on` | `TIMELINE_BAR_ON` |
| `--bar-grid` | `BAR_GRID` |
| `--playhead` | `PLAYHEAD` |
| `--marker` | `SONG_MARKER` |

Hover in the mock is a translucent label wash. `theme.py` has no hover color yet. Add one role when phase 6 starts, and use it for that wash. Do not pick a one-off color in the draw path.

## What is illustrative

Preset names, stem labels, numeric values, and the transport readout are sample content so the layout is readable. Implement from `row_specs/*`, the command registry, and [help_content.py](../../../cleave/viz/help_content.py). The mock's menu shape is normative: which entries are commands, jumps, checks, or disabled, and the shortcut column. `Ctrl+R` belongs only to Project > Render project..., as the plan states. The mock's Render menu still shows a second Start render item; do not implement that item.

## Recapture stills

After a visual change to the HTML:

1. Serve the plans directory (the Cursor browser rejects `file://`):

```
/home/fernpa/anaconda3/envs/cleave/bin/python -m http.server 8765 --bind 127.0.0.1 --directory docs/dev/plans
```

2. Open `http://127.0.0.1:8765/menu-overhaul-design.html` at about a 1440px viewport.
3. For each named view, evaluate `cleaveDesign.apply(name)`.
4. Capture the document rectangle of the element, not an element screenshot. Element screenshots clip `#win` and drop the timeline and the right side of the inspector. Use `Page.captureScreenshot` with `captureBeyondViewport: true` and a clip of `getBoundingClientRect()` plus `scrollX` and `scrollY`.
5. Save `#win` as `menu-overhaul-stills/<name>.png`. Save `#compare` and `#mouse` the same way. Those two do not depend on the hash.

## Confirming a phase

Open the views for the phase, then compare the editor to the live page.

| Phase | Views and sections |
| --- | --- |
| 1 Menu bar | `menu-layers`, `#taxonomy`, `#registry` |
| 2 Shell, settings, project | `shell-split` for chrome and the 230 / 330 widths, `#scopes`. The still's Layer 2 inspector is phase 3. Not `shell-docked`. |
| 3 Layers | `inspector-locked`, `menu-layers` |
| 4 Render blocks | `inspector-card`, `#taxonomy` for the Render menu |
| 5 Timeline and song markers | `shell-split` on the Timeline and Song markers pages, `#compare`, `#scopes` |
| 6 Mouse | `hit-rects`, `#mouse`. Drag a numeric value in the mock (sideways on the value) and drag a column splitter before copying the gesture. |
| 7 Polish | `shell-split` and `shell-docked`, menu mnemonics (underlined first letter), focus ring contrast. |
