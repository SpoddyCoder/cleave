# Context menus plan

Right-click menus are in place for timeline strip rows, timeline cues, the ruler and empty strip area, navigator rows, and inspector preset rows, with one level of submenu. This plan lists what is left. How the framework works: [live-tuning-ui](../../../.claude/rules/live-tuning-ui.md) (Context menus).

Related: [editor-first](../../../AGENTS.md), [todos.md](../todos.md).

---

## Shipped

- Framework: `ContextMenuState` and `ContextSubmenu` in [context_menu.py](../../../cleave/viz/context_menu.py); `ContextMenuSurface`, `ContextSubmenuSurface`, and `_FittedWindow` in [menu_rows.py](../../../cleave/viz/menu_rows.py). A new menu draws one frame off-screen to measure its rows, then opens at its final size and edge-clamped spot.
- Timeline strip row: show / hide, override visibility, release all overrides, arm ([timeline_context_menu.py](../../../cleave/viz/timeline_context_menu.py)).
- Timeline cue: right-click selects the cue; Go to cue, and Cut / Blend / Role submenus ([cue_context_menu.py](../../../cleave/viz/cue_context_menu.py)).
- Navigator row: expand / collapse, on/off, solo, lock, Add layer; layer rows add Go to page, Move up / down, and Delete layer ([navigator_context_menu.py](../../../cleave/viz/navigator_context_menu.py)).
- Empty strip area and ruler: Seek here, Play from here, Drop song marker here, and Delete marker when one is under the pointer ([timeline_time_menu.py](../../../cleave/viz/timeline_time_menu.py)). The ruler adds Undo / Redo (named from `TimelineHistory.undo_label`) and Generate, Snap cues, Snap cues to markers, Set cut type, and Reset timeline. A row away from any cue leads with the time items.
- `command_menu_item` in [commands.py](../../../cleave/viz/commands.py): a context menu item from a menu-bar `Command`, sharing its label, shortcut, and enabled state.
- Preset rows: a preset list entry offers Audition, Move up / down, Remove from list..., Add current preset, Populate..., and a Curate submenu (Favourite, Blacklist, Cast as role, Restore); the current preset row offers Add to preset list and Curate ([preset_context_menu.py](../../../cleave/viz/preset_context_menu.py)).
- Inspector plumbing: `ShellHost` records inspector row rects by descriptor while drawing, and `_inspector_menu` maps a row kind to its provider. A right-click focuses the row first.
- Shift+F10 / Menu key opens the focused item's menu in the Timeline, Navigator, and Inspector regions (`ShellHost._focus_context_menu`).

---

## Next: needs new plumbing

### Reset to default on value rows

Desktop apps put this on every slider and choice. It needs a per-row default lookup from `cleave/config_schema/`, which viz rows do not expose. Build it once on `RowSpec` (a `default` reader next to `choice`), then one inspector provider covers every numeric and choice row; hook it into `ShellHost._inspector_menu`. Copy value / Paste value can follow.

### Visualiser canvas

A fallback menu so right-click never does nothing: Fullscreen, Show timeline strip, Help, Render..., Save. All existing `Command`s.

---

## Framework follow-ups

- Navigator layer menu: Arm for recording and Override visibility, the same items as the strip row menu. Needs the strip's `TimelineControls` reachable from the navigator provider (it is wired in `wiring.py`, not on `TuningControls`).
- Delete cue: no cue-delete action exists. Add one in [timeline_cue_edits.py](../../../cleave/viz/timeline_cue_edits.py) (with a key) before adding it to the cue menu.
- Cue edits from the menu (and the cue keys) are not undoable. Decide whether single cue edits should record through `TimelineHistory`.
- Submenu x sits about 4px over the parent menu's right edge; it anchors on the row rect, not the window rect. Anchor on the parent window's right edge.
- Navigator child pages with no twisty and no icons (Post-FX > Fade, a layer's Compositing page) have no menu, so right-click does nothing there. They pick up items once Reset to default or page-level commands exist.
- Song markers have no hit target of their own: Delete marker shows when a right-click lands within cue tolerance of one, and a cue at the same spot wins. Revisit if markers get their own ruler glyph.
- Check the menus on the Windows freeze: the Menu key, high DPI, and UI scale 200%.
