# Context menus plan

Right-click menus are in place for timeline strip rows, timeline cues, and navigator rows, with one level of submenu. This plan lists what is left. How the framework works: [live-tuning-ui](../../../.claude/rules/live-tuning-ui.md) (Context menus).

Related: [editor-first](../../../AGENTS.md), [todos.md](../todos.md).

---

## Shipped

- Framework: `ContextMenuState` and `ContextSubmenu` in [context_menu.py](../../../cleave/viz/context_menu.py); `ContextMenuSurface`, `ContextSubmenuSurface`, and `_FittedWindow` in [menu_rows.py](../../../cleave/viz/menu_rows.py). A new menu draws one frame off-screen to measure its rows, then opens at its final size and edge-clamped spot.
- Timeline strip row: show / hide, override visibility, release all overrides, arm ([timeline_context_menu.py](../../../cleave/viz/timeline_context_menu.py)).
- Timeline cue: right-click selects the cue; Go to cue, and Cut / Blend / Role submenus ([cue_context_menu.py](../../../cleave/viz/cue_context_menu.py)).
- Navigator row: expand / collapse, on/off, solo, lock, Add layer; layer rows add Go to page, Move up / down, and Delete layer ([navigator_context_menu.py](../../../cleave/viz/navigator_context_menu.py)).
- Shift+F10 / Menu key opens the focused item's menu in the Timeline and Navigator regions (`ShellHost._focus_context_menu`).

---

## Next: high value

### Empty strip area and ruler

Right-click on the ruler, or on a row away from any cue, has no time-based items yet. Add a menu (or a group above the row items) with:

- Seek here, Play from here (`TimelineControls.seek_to`, `toggle_transport`).
- Drop song marker here (`SongMarkerController.drop` at the clicked time; it drops at the playhead today, so it needs a time argument).
- Undo / Redo with the history label (`TimelineHistory.can_undo`, `undo`, `redo`; menu-bar commands `_UNDO`, `_REDO`).
- Generate..., Snap to markers, Set cut type..., Reset timeline... (existing `Command`s in [commands.py](../../../cleave/viz/commands.py)).

A right-click on a song marker on the ruler: Delete marker (`SongMarkerController.prompt_delete`), Snap cues to markers. Needs a ruler marker hit in `TimelineOverlay.hit_at`.

`TimelinePointer.context_menu_at` returns None for the ruler today; extend it there.

### Preset list items

A list of files is where users right-click by reflex. On a `TRACK_PRESET_LIST_ITEM` row in the inspector:

- Audition (`PresetListController.audition`).
- Move up / Move down (`move_item_to`), Remove from list... (`prompt_delete`).
- Add current preset (`add_current`), Populate... (`prompt_populate`).

Curation (Favourite, Cast as role, Blacklist, Restore in [preset_curation_controls.py](../../../cleave/viz/preset_curation_controls.py)) fits here and on the current-preset row; it is hard to find outside curation mode today.

This is the first inspector menu: it needs inspector row rects recorded while drawing (as `_nav_row_rects` does for the navigator), a hit in `ShellHost._context_menu_at`, and the `ShellRegion.INSPECTOR` branch in `_focus_context_menu`.

---

## Next: needs new plumbing

### Reset to default on value rows

Desktop apps put this on every slider and choice. It needs a per-row default lookup from `cleave/config_schema/`, which viz rows do not expose. Build it once on `RowSpec` (a `default` reader next to `choice`), then one inspector provider covers every numeric and choice row. Copy value / Paste value can follow.

### Visualiser canvas

A fallback menu so right-click never does nothing: Fullscreen, Show timeline strip, Help, Render..., Save. All existing `Command`s.

---

## Framework follow-ups

- `ContextMenuItem.from_command(command, ctx)`: one adapter so menu items built from menu-bar `Command`s share label, shortcut, and enabled state. Several items above are commands; avoid redefining them by hand.
- Navigator layer menu: Arm for recording and Override visibility, the same items as the strip row menu. Needs the strip's `TimelineControls` reachable from the navigator provider (it is wired in `wiring.py`, not on `TuningControls`).
- Delete cue: no cue-delete action exists. Add one in [timeline_cue_edits.py](../../../cleave/viz/timeline_cue_edits.py) (with a key) before adding it to the cue menu.
- Cue edits from the menu (and the cue keys) are not undoable. Decide whether single cue edits should record through `TimelineHistory`.
- Submenu x sits about 4px over the parent menu's right edge; it anchors on the row rect, not the window rect. Anchor on the parent window's right edge.
- Navigator child pages with no twisty and no icons (Post-FX > Fade, a layer's Compositing page) have no menu, so right-click does nothing there. They pick up items once Reset to default or page-level commands exist.
- Check the menus on the Windows freeze: the Menu key, high DPI, and UI scale 200%.
