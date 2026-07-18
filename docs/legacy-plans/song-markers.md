# Song Markers

Manual markers at major song transitions. They solve a different problem from beat snap: **structure vs pulse**. Sparse, user-placed song markers for guaranteed pops at section changes, not rhythmic grid alignment.

Related: [timeline-idea.md](timeline-idea.md), [live-tuning-ui](../.cursor/rules/live-tuning-ui.mdc).

Naming: use **song markers** everywhere in UI, docs, and code identifiers. Reserve **cue** for per-lane timeline visibility transitions (`SlotCue`).

---

## Scope and persistence

**Project-scoped, not viz config.** Song markers are definitive information about the song. On disk they live in `project.yaml` (alongside `signals.json`) and persist across many viz YAML snapshots. They are not written into viz YAML and are not lost when saving `unnamed-N.yaml` or switching configs.

**Deferred write (session until Save).** Drop, replace, and delete update in-memory session state only. Markers are uncommitted until the user Saves (same Enter / config-row flow as viz config). A successful save writes the active viz YAML **and** flushes song markers to that project's `project.yaml`. Save-as-new still flushes markers to the same `project.yaml` (project-scoped). Marker edits mark the session dirty (config-row asterisk and quit-unsaved modal) the same way viz edits do.

v1 is **manual only** — user-driven placement with streamlined UX. No auto-suggestion in the first release.

---

## Phase 1 — UI / UX (done)

Build UI and editing only. No preset generation or beat-phase logic yet.

### Add a song marker

- Global shortcut **Ctrl+Enter** from the timeline strip or the main tuning panel.
- Drops a song marker at the current playhead time.
- Shows a toast and appends the marker to the list.

**When drop is allowed**

- Allowed from the timeline strip and the main tuning panel.
- **Not** while a centered modal is open (modals keep consuming keys).
- **Not** while the timeline is recording.

### Panel

- First expandable child under **Render: Timeline**: header label `song markers (N)` with expand arrow (e.g. `song markers (4)`).
- When expanded: list of marker times in `[mm:ss.ms]` format, then **snap to song markers** as the last row (green action row; no expand arrow).

### List interaction

- Focus on a song-marker list row highlights that row and the matching strip tick. Drop/replace does **not** move focus onto the new marker; if a marker row was already focused, that selection is remapped by time when the list shifts. Do **not** auto-follow the playhead.
- **Enter** on a focused song marker seeks the playhead to that time (audition / verify placement). Timeline row arm uses **a**, so **Enter** is free for seek-to-marker.
- **Delete** prompts a confirm modal, then removes the focused song marker.
- No nudge in v1 — delete and re-drop at the playhead is enough, with **Enter** to verify.

### Timeline display

- Song markers render as **red 2px vertical lines** spanning all lanes (global structure, not per-layer visibility cues).
- The **4px yellow/orange** strip highlight appears only while focus is on that marker's `SONG_MARKER_ITEM` list row. When focus is elsewhere (other panel rows, timeline strip lanes, etc.), all song markers draw as the normal red 2px lines.

### Placement rules

- If a new song marker falls within **2 seconds** of an existing song marker, **replace** the nearer existing marker (not both).
- When the new time is between two song markers, the **nearest** one is replaced.
- Show a warning toast on replace (include old and new times when practical).

### Phase 1 deliverable

Song markers, list editing, seek-to-marker, and timeline drawing only. Value on its own as a visual reference while editing lanes by hand.

---

## Phase 2 — Snap to song markers (done)

Add a **snap to song markers** action inside the song markers section (last row when that section is expanded).

Workflow:

1. Apply a preset to the timeline
2. Snap to bars (under beat / bar grid)
3. Expand song markers and run **snap to song markers**

### Behavior

For each song marker (ascending time), pull the **closest** unclaimed timeline cue within proximity onto that marker. Each cue moves at most once (**exclusive assignment**). If no unclaimed cue lies within proximity, that marker is a no-op. Visibility flags are preserved; only cue times change. Tracks are canonicalized after moves.

### Panel layout

Under **Render: TIMELINE** (strip open), order is song markers (expandable; marker items and **snap to song markers** when expanded), then beat / bar grid, then timeline fades, then apply a timeline preset, then reset timeline. **snap to song markers** is a green action row inside the song markers section (last child after marker items), same style as snap to beats / apply a timeline preset.

### Confirm (one modal step per parameter)

Enter on **snap to song markers** opens two choice modals in sequence:

1. **Snap proximity?** — choose maximum distance (`0.5s` … `30.0s`; default focus `5.0s`)
2. **Layer scope?** — choose which tracks snap:

- **layer 1** … **layer N** — only that track
- **closest wins** — for each marker, among cues in all tracks within proximity, move the single closest cue (tie: earlier cue time, then earlier layer in z-order)
- **all layers** (default focus) — for each track independently, each marker pulls that track's closest unclaimed cue within proximity (claims are per-track)

Cancel on either step aborts without changing cues. Choosing layer scope applies the snap.

---

## Phase 3 — Timeline preset generation

When song markers exist, applying a timeline preset (Breathing / Dialogue / Arc / Pulse) uses them at generation time:

1. **Section-driven phrases.** Markers are hard section walls. Phrases never cross a marker; each marker starts a new phrase (then the usual 4–8 bar / minimum-duration partitioning fills each section). Empty or out-of-range markers leave bar-only partitioning unchanged.
2. **Soft latch.** Planned motif switches still prefer the bar grid. If an unclaimed marker lies within **5.0s** of a planned switch and min switch gaps still hold, that switch moves onto the marker (exclusive: each marker claimed at most once). Soft latch does **not** invent extra transitions solely to hit a marker.

No new panel knobs. Phase 2 **snap to song markers** remains a separate manual polish step and is not run automatically after apply.

### Phase 3 deliverable

Preset apply reads `session.song_markers.times` and threads them into `compose_timeline`. Tests cover section walls, exclusive soft latch, and gap veto.

---

## Phase 4 — Beat / bar phase (open question)

Song markers might improve beat or bar offset if treated as downbeat hints.

**Caveat:** section hits are not always bar 1 (pickups, beat-3 crashes, early snares). Treating every song marker as a downbeat could harm phase accuracy. Keep language as **structure / section** until there is an explicit downbeat notion or a separate user action.

---

## Later — automation (v2+)

Auto-suggested song markers (energy, novelty, structure) with optional manual drop to correct or pin a few points. Out of scope for v1.
