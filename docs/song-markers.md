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

## Phase 1 — UI / UX

Build UI and editing only. No snap, preset generation, or beat-phase logic yet.

### Add a song marker

- Global shortcut **Ctrl+Enter** from the timeline strip or the main tuning panel.
- Drops a song marker at the current playhead time.
- Shows a toast and appends the marker to the list.

**When drop is allowed**

- Allowed from the timeline strip and the main tuning panel.
- **Not** while a centered modal is open (modals keep consuming keys).
- **Not** while the timeline is recording.

### Panel

- First expandable child under **Render: Timeline** (above apply a preset): header label `song markers (N)` with expand arrow (e.g. `song markers (4)`).
- List of marker times in `[mm:ss.ms]` format.

### List interaction

- **Sticky selection:** the highlighted list row stays put until the user moves focus (Up/Down) or deletes it. Drop/replace does **not** select the new marker; prior selection is preserved (remapped by time if the list shifts). Do **not** auto-follow the playhead.
- **Enter** on a highlighted song marker seeks the playhead to that time (audition / verify placement). Timeline row arm uses **a**, so **Enter** is free for seek-to-marker.
- **Delete** prompts a confirm modal, then removes the highlighted song marker.
- No nudge in v1 — delete and re-drop at the playhead is enough, with **Enter** to verify.

### Timeline display

- Song markers render as **red 2px vertical lines** spanning all lanes (global structure, not per-layer visibility cues).
- The highlighted song marker uses a **4px yellow/orange** line on the strip.

### Placement rules

- If a new song marker falls within **2 seconds** of an existing song marker, **replace** the nearer existing marker (not both).
- When the new time is between two song markers, the **nearest** one is replaced.
- Show a warning toast on replace (include old and new times when practical).

### Phase 1 deliverable

Song markers, list editing, seek-to-marker, and timeline drawing only. Value on its own as a visual reference while editing lanes by hand.

---

## Phase 2 — Snap to song markers

Add a **snap to song markers** action (button or row under the timeline section).

### Behavior

For **each song marker**, pull the **closest** timeline lane cue on the selected layer(s) toward that song marker.

- If no lane cue lies within the proximity window, **no-op** for that song marker.
- Default proximity window: **5 seconds** (configurable).

### UI

Modal with layer scope:

- Layer 1, Layer 2, … (per active layer)
- All layers
- Cancel

Include proximity (and any other snap options) in the modal or an adjacent control so users can tune behavior before applying. Destructive multi-lane moves should be explicit; no silent wide snaps.

---

## Phase 3 — Timeline preset generation

Update preset generation so new timeline presets can **latch onto** song markers where appropriate. Details TBD when Phase 1 song markers exist in projects.

---

## Phase 4 — Beat / bar phase (open question)

Song markers might improve beat or bar offset if treated as downbeat hints.

**Caveat:** section hits are not always bar 1 (pickups, beat-3 crashes, early snares). Treating every song marker as a downbeat could harm phase accuracy. Keep language as **structure / section** until there is an explicit downbeat notion or a separate user action.

---

## Later — automation (v2+)

Auto-suggested song markers (energy, novelty, structure) with optional manual drop to correct or pin a few points. Out of scope for v1.
