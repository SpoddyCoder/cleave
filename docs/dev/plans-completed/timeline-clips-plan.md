# Timeline clips

Replaces the remaining steps of the cue management overhaul (backlog item 1 in [todos.md](../todos.md)). Steps 1 (cue undo) and 2 (add/delete cues) are on `ui-refactor` as `9ca9881` and `ae6d997`. This plan reworks Step 2's add/delete and replaces Steps 3-4.

## Context

The strip edits cues: an on cue (start) turns a layer on and carries its look, and an off cue (end) turns it off. The inspector splits them the same way. That reflects how lanes are stored, not how people think about a layer ("visible from 0:32 to 0:48"), and it leaves gaps such as no way to turn an off cue into an on cue.

Video editors (Premiere, Resolve, Final Cut) show a track's visible spans as **clips**. Users select, add, delete, move, trim, and split clips, and the gaps between them are off. Cleave's lanes already have that shape:

- An on cue up to the next cue (or the song end) is a clip; any span not covered by a clip is off.
- Blend, role, and cut-in belong to the on cue, so they are clip properties. An off cue's cut is the clip's cut-out.
- An on cue right after another on cue (a level change, an `anchor` hold, a `recast` preset switch) is two clips that butt together.

Result: the strip and inspector work in clips. Storage stays as cues, so project YAML, Generate, Snap, Set cut type, record, fades, preset-switch triggers, and the frame path are unchanged. Clips are derived from lanes, and each clip edit becomes cue operations recorded in `TimelineHistory`.

## Behaviour

| Action | Result |
|---|---|
| Click a clip | Select it (flash, as cues do now). The inspector shows the clip page |
| Left / Right | Previous / next clip on the focused row |
| Enter | Seek to the clip start |
| Double-click empty row space, or Add clip here | New clip from the click (snapped) to the next clip's start or one bar later, whichever is sooner. Level: the lane's last on level (`lane_last_on_level`), else 100% |
| Drag a clip body | Move it, length fixed. The start snaps; the clip stops at its neighbours |
| Drag a clip edge | Trim that edge, snapped, clamped between the neighbour and a minimum length. A shared edge between butted clips rolls the boundary (both clips change) |
| Esc during a drag | Restore the clip |
| Delete, or Delete clip | That span becomes off |
| Ctrl+K, or Split at playhead | Split the clip under the playhead in two (same look, no preset switch) |
| `,` / `.` (Ctrl for 10%) | Clip opacity, 10-100% |
| B / O / C / Shift+C | Cycle blend / role / cut in / cut out |
| Pointer | Move over a clip body; Resize EW over an edge and during a trim; Arrow when locked or recording |

Gating: every edit needs `clip_edits_allowed` (unlocked, not recording), the same as cue edits now. Selection pauses while recording. A double-click while edits are blocked still seeks.

Split creates an `anchor` boundary (same preset carries on). Recast boundaries from Generate are kept and drawn as clip boundaries; this plan adds no recast control.

## Stage A: Clip model (pure, `cleave/timeline.py`)

- `TimelineClip` (frozen dataclass): `start`, `end`, `level`, `blend`, `role`, `cut_in`, `cut_out`, `butts_next` (the end is another clip's start), `recast`.
- `lane_clips(lane, *, inherit, duration_sec) -> list[TimelineClip]`.
  - Walks the canonical cues. An opening baseline that is on, or an inherited on, gives a clip from 0 (reuse the `opening_cue` idea).
  - The last clip ends at `duration_sec`.
- `clip_at(clips, t)`, `clip_starting_at(clips, start)`.
- Edit helpers. Each returns a canonical lane and folds an inherit baseline first (move `_fold_lane_baseline` in `layer_visibility.py` into a public `fold_lane_baseline(lane, inherit)` here):
  - `add_clip(lane, start, end, level)`: writes an on cue at `start` and, unless the span runs into the next clip, an off cue at `end`.
  - `remove_clip(lane, clip)`: off over `[start, end)`.
    - Its start cue becomes an off cue, or is dropped if the span before it is already off.
    - A butted next clip keeps its start cue.
  - `move_clip(lane, clip, new_start)`: both edges move, and every property is kept (cut-in on the start cue, cut-out on the end cue).
  - `trim_clip(lane, clip, edge, t)`: moves one edge. On a butted edge it moves the shared cue (a roll).
  - `split_clip(lane, clip, t)`: an `anchor` on cue at `t` copying level, blend, and role.
  - `update_clip(lane, clip, *, level, blend, role, cut_in, cut_out)`: built on `update_lane_cue` for the start cue. Cut-out writes the end cue's cut, and only when `not butts_next`.
  - `clip_move_bounds(clips, clip)`, `clip_trim_bounds(clips, clip, edge, min_len)`.
- Constant `MIN_CLIP_SEC = 0.1`.
- Remove what clips replace: `remove_lane_cue`. Keep `lane_last_on_level`.
- Tests in `tests/cleave/test_timeline.py`:
  - derivation: opening baseline, inherit, butted clips, recast, last clip to the song end;
  - each edit helper, including butted neighbours, rolls, and the merges canonicalize does;
  - round trip: `lane_clips` after each edit.

## Stage B: Selection, editor, inspector, menus, keys (replaces Step 2's add/delete)

**Rename to clips (no backward compatibility):**
- `selected_cue_t` -> `selected_clip_t` (keyed by clip start) and `selected_cue_flash_start_ms` -> `selected_clip_flash_start_ms` in `session.py`, `timeline_overlay.py` (`TimelineViewState`, flash helpers), `layer_visibility.py`, `tuning_view_state.py` (`selected_cues` -> `selected_clips`, the signature key `selected_cue_kinds` -> `selected_clip_cut_out` (whether Cut out is available)), and `timeline_history.py` (snapshot field).
- `timeline_cue_edits.py` -> `timeline_clip_edits.py`, `CueEditor` -> `ClipEditor` (`controls.clip_editor`), `cue_context_menu.py` -> `clip_context_menu.py`. Update every import, test, and doc.

**`ClipEditor`:**
- `add_clip_at`, `delete_selected`, `split_at`, `nudge_level`, `set_blend`, `set_role`, `set_cut_in`, `set_cut_out`, and the drag session `begin_drag(slot, edge|None)` / `update_drag(t)` / `end_drag()` / `cancel_drag()`.
- History labels: "Add clip", "Delete clip", "Split clip", "Move clip", "Trim clip", "Clip level", "Clip blend", "Clip role", "Clip cut". Merge keys follow Step 1's pattern.
- Clips are derived from the lane on demand, with `inherit` from the layer's enabled switch and the duration passed in at construction. No clip cache in session state.

**Snapping and time:**
- Snapping goes through one public helper, `snap_for_session(session, beat_times, bar_times)` (or the existing `_snap_placement` made public). `TimelineControls` and `ClipEditor` share it.
- One bar length is the median bar interval; with no grid, 2 s.

**Selection helpers** (`select_clip`, `step_clip_selection`, `selected_clip`): selection follows a clip's new start after a move, trim, or split, and goes to the next clip after a delete (else the previous).

**Inspector:**
- `row_sections.py`: `TIMELINE_CUE_SECTION` -> `TIMELINE_CLIP_SECTION`. The heading is "Clip 0:32-0:48", or "No clip selected".
- Rows: Start, End, Opacity, Blend, Role, Cut in, Cut out.
  - Start and End are `< time >` steppers that trim by one snap step (Ctrl: one bar), which gives the keyboard path for trimming.
  - Cut out is unavailable on a butted clip ("Butts the next clip; set its Cut in").
- `row_specs/timeline.py`: rename the RowKinds to `TIMELINE_CLIP_*` and update the help text.

**Menus:**
- `clip_context_menu.py`: Go to clip start, Cut in (submenu), Cut out (submenu), Blend (submenu), Role (submenu), Split at playhead (Ctrl+K), Delete clip (Delete).
- Row menu away from a clip: Add clip here (Double-click), then the time items.

**Keys** (`timeline_controls.py`): Left/Right, Enter, `,` `.`, B, O, C, Shift+C, Delete, Ctrl+K. The locked-allowed list stays selection and seek only.

**Help** (`help_content.timeline_strip_section`): clip wording and the new keys.

**Tests:** move and rename the Step 1-2 tests, plus split, cut-in/out, butted Cut out unavailable, and the structure signature (`test_view_state_structure.py`: Cut out row appears/disappears).

## Stage C: Strip hit test, drag, draw

**`timeline_overlay.py`:**
- `StripHit` gains `clip_start: float | None` and `clip_edge: Literal["start", "end"] | None`.
- `hit_at` derives the row's clips from the lanes it last drew. An edge within `CLIP_EDGE_HIT_PX` of the pointer wins over the body. Retire `cue_tolerance_sec` once nothing reads it.
- Draw:
  - the selected clip gets an outline in the selection accent, with the flash replacing the cue tick flash;
  - the hovered or selected clip's edges get edge handles;
  - butted boundaries get a thin divider.

  Keep within the existing per-row compose; check `timeline_panel_cache.py` invalidation for the selection and hover.

**`timeline_pointer.py`:**
- Press on a clip: select it, and set a pending drag (body or edge). Motion past `PAN_DRAG_PX` -> `begin_drag`; motion -> `update_drag(time_at_x)`, setting `view.held`.
- Release -> `end_drag`; Esc or cancel -> `cancel_drag`.
- Press on empty row space keeps its current behaviour: select nothing, and pan while zoomed.
- Double-click: empty space -> `add_clip_at`; on a clip, or when edits are blocked, seek as now.

**Pointer shapes:** `ShellHost._request_gesture_pointer`: Move over a clip body, Resize EW over an edge and during a trim. Arrow when `strip_target_pressable` says edits are blocked.

**Tests (`test_timeline_pointer.py`, overlay hit tests):**
- body vs edge hits at the threshold;
- press -> drag -> release gives one history entry;
- Esc restores;
- clamping and snapping;
- roll on a butted edge;
- zoomed empty-space pan still works.

## Stage D: Record keeps authored levels

- `_toggle_armed_layer_at`: an on punch writes `lane_last_on_level(committed lane, t)` instead of `1.0`.
- `_start_record`: `record_baseline` for an on slot uses `timeline_committed_level`, not `1.0`.
- Check that `armed_recording_level` and `effective_layer_enabled` still treat `> LEVEL_EPS` as on.
- A test for a take over a 60% lane: a rise writes 0.6, and untouched spans stay as they were.
- Remove the "Record still writes 0/1" bullet and backlog item 1 from `todos.md`.

## Docs and changelog

- `CHANGELOG.md` `## [Unreleased]`:
  - Rewrite Step 2's Added bullet (add/delete cues) and Changed bullet (double-click) for clips.
  - Reword Step 1's undo bullet from "cue" to "clip" edits.
  - Add bullets for move, trim, split, cut in/out, and record levels.
- `.claude/rules/live-tuning-ui.md`:
  - timeline row page: the clip section, `ClipEditor`;
  - context menus: the clip menu, Add clip here;
  - keyboard dispatch: the clip keys;
  - mouse pointer: Move and Resize EW on clips.
- Each module docstring touched (`timeline_pointer.py`, `timeline_context_menu.py`, `timeline_history.py`).

## Order and commits

One commit per stage, A -> D. A is pure and testable alone; B keeps the strip's current pointer behaviour working (clicks select clips, the double-click adds clips); C adds dragging; D is independent of C.

## Verification

- Per stage: `/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py -k "timeline or clip"`. Full suite after B and C (they rename across modules).
- Manual check in the editor:
  1. Click a clip: it's selected and the inspector shows its page.
  2. Double-click a gap: a clip appears.
  3. Drag it: it stops at its neighbours.
  4. Trim both edges.
  5. Roll a butted edge.
  6. Ctrl+K splits under the playhead.
  7. Delete clears the span.
  8. Esc mid-drag restores the clip.
  9. Ctrl+Z walks back each step.
  10. Locked: no edits, a double-click seeks.
  11. Record over a 60% lane keeps 60%.

## Left for later

- User-facing names of the bulk commands that still say "cues": Snap cues, Snap cues to markers, Set cut type on cues. They act on clip edges now; rename them in a follow-up if you want consistent wording.
- A recast toggle on butted clips.
- Multi-select, ripple delete, copy/paste of clips.
