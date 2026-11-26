# Section intensity and recall (phase 2)

Status: **2a is done**, with a full rethink of Generate timeline (commit `6e70c37a` on `0.5.0`). **2b, recall, is not started** and is replanned below on the new generator.

## Done

### What 2a turned into

The original 2a (three intensities, a calm opacity pass, an icon button) shipped first and was then replaced. On buttercup it showed that the old layers generator was the problem: a chain of passes (motif picking, section fitting, build overwrite, accent, calm dimming) that each rewrote the last. Problems seen were a lone full-opacity layer before the first marker, builds restarting at every marker, no preset changes on held layers, layers stepping up together, dull dim solos, and four layers at 100%.

What is in the commit:

- **Intensity:** five values: `very calm`, `calm`, `normal` (default), `intense`, `very intense`. Stored per marker in `project.yaml` (`intensity`; missing means normal). It survives replace, snap and merge, which keeps the first non-normal value, and type change. Set from a second dropdown on the marker row (`RowSpec.second_choice`), the I key (opens that list), or the marker's Intensity submenu. The strip tint gets stronger with intensity.
- **First marker adds 0:00:** `place_marker` on an empty list also inserts a plain marker at `0.0`. It is an ordinary, deletable marker.
- **Glide** (`timeline.glide`, default 4 s, on Timeline > Clip Fades): in `lane_level_breakpoints`, an opacity change between two visible levels ramps whatever its cut. A rise ends on the cue and a fall starts there, so a drop still lands on its marker. It applies to all projects; 0 restores the old steps.
- **Characters removed.** Breathing, Dialogue, Arc and Pulse are gone from the dialog and the session.
- **New layers planner**, replacing `arrange.py`, `motifs.py`, `chords.py`, `characters.py`, `build.py`, `accent.py`, the calm pass, and `sections.py`:
  - [shapes.py](../../../cleave/timeline_presets/shapes.py): `SectionShape` per type (count at the run's start and end, pace, phrase bars, lead phrases, preset bars, swap chance). `plain_shape` is set by loudness rank. `INTENSITY_LAYERS` / `layer_bounds`, the `LEVELS` opacity table by intensity and layer count, and runs (`section_parts`, `Part`).
  - [plan.py](../../../cleave/timeline_presets/plan.py): one `Target` per phrase (levels by rank, lead, roles, how many moves may land together). A build's last bar gets a full-stack target.
  - [weave.py](../../../cleave/timeline_presets/weave.py): turns targets into single-layer moves a bar or two apart. A rise to full is grouped with a fall from full, so the lead crossfades. Leavers go first when over the count. It also places accents and the preset changes (recasts) at markers and on each layer's own clock.
  - [lanes.py](../../../cleave/timeline_presets/lanes.py): `compose_layers_timeline` and `lane_from_events`.
- **Runs:** back-to-back markers of one type share one shape (a build rises once across all of its markers). Each inner marker still changes layers and presets and keeps its own intensity. Plain markers are runs of one.
- **Pattern mask** uses the same shapes, runs and intensity bounds (`section_target_range`). Plain sections are bounded hard when their intensity is not normal. Opacity stays full.
- **Generate dialog:** `opacity` (keep / set to 100%), `change presets` (keep / each clip) and `preset list`, under a Layer settings section, are session-only (`layer_setup.py`). `preset list` (hidden unless some layer will change presets on each clip) keeps the current list by default (looped over the clips, deduplicated, an empty list falls back to shuffled; `kept_list_for_clips`) or builds a new one (shuffled, in order, by clip roles). Locked layers are skipped. `EditSnapshot.opacities` lets undo restore opacity without a later opacity edit blocking undo. The info under the title is one bracketed note per line (modal `form_info_lines`): clips replaced, lists kept or new, layers without preset changes, layers below 100%.
- **Fixes on the way:**
  - `apply_cut_to_lanes` dropped `recast`, `anchor` and `preset`, so cut types wiped each-clip presets. This bug predated this work.
  - An unused layer got a lane with no baseline and inherited its own on/off switch.
  - Moves after an off-grid marker could snap onto the marker's bar.

### Departures from the original 2a

- The rule "all normal with recall off is identical to the old output" no longer applies; the generator is new.
- Intensity sets opacity through the `LEVELS` table, not a 50% pass, and the conductor no longer sets levels. `StemConductor` keeps loudness, activity and roles only.
- The marker row has a second dropdown, not an icon button.

### How it was verified

- A buttercup report covered 450 runs (1, 2, 4, 6 and 8 layers; every density; conductor on and off).
  - Brightness and layer counts: no dim solo or duo at normal and above, never four layers at 100%, and layer counts inside the bounds outside swap overlaps.
  - Pacing: no simultaneous rises away from markers, and the longest held preset was about 42 s.
  - The report script was in the session scratchpad and is gone; `tests/cleave/test_timeline_plan.py` holds the same rules.
- All 720 dialog combinations ran through the controller with the snap passes, and no recasts were lost.
- The full suite passes.

### Still open from 2a

- Retake `docs/user-guide/images/song-markers.png` (the marker row now has two dropdowns).
- In the editor, the user has not yet checked:
  - whether the opacity tables look right, with the visual limiter on and off;
  - the two-dropdown row at narrow inspector widths.
- The tables in `shapes.py` are first guesses, meant to be tuned.

## 2b. Recall (to do)

Not started. The earlier design assumed `arrange.py` and replay of fitted states, so it is rewritten here for the planner.

### Decisions kept

- Recall is a Generate option, off by default. Field `repeated sections`, after density: **new each time** (default), **same look**, **same look, building**. Both modes. Session only. Hidden when no type comes back.
- It brings back which layers play, their timing, roles and blends, and presets on each-clip layers.
- A run is one or more consecutive markers of one type (now the same thing as a `Part` run in `shapes.py`). The first run of a type is the source. Later runs recall it part by part, by position in the run. A part with no source part is planned fresh and becomes a source. Plain markers never recall.
- Intensity is not part of the match: a recalled part uses its own marker's intensity and level table.
- **Building** adds one layer per recall, within the intensity bounds, unless that marker's intensity is not normal.
- Timing maps by bar offset from the part start. A shorter target truncates; a longer one loops the source. With no bars, map by seconds.

### Where it fits now

- **Planner level, not replay.** In `plan_timeline`, a recalled part copies its source part's `Target`s: the same phrase offsets mapped by bars, the same active layers and lead, and the same rank order. Levels come from the target's own intensity row in `LEVELS`, not copied, so an intensity change between the two still shows. Roles come from the source when the conductor is on. Then `weave` runs as usual, so spacing and crossfade rules still hold.
- **Recasts.** `weave._place_preset_changes` should mirror the source: the same marker recasts, and between-marker recasts at mapped bar offsets. The k-th preset start in a recalled part then pairs with the k-th in its source.
- **Shared helper.** A small `recall.py` holds run matching (`(source Part, target Part)` pairs from `section_parts`) and the bar-offset time map, used by both modes. Pattern mask copies its section-level counts and swaps the same way.
- **Presets.** After `repopulate` (`PresetListController.repopulate`, then `deal_list_onto_clips`), give the k-th switching clip of each recalled part the k-th preset of its source, by order rather than time, since snap moves edges. Then rebuild `preset_list` as clip order plus spares, so `sync_each_clip_layers` leaves it alone. This stays inside the Generate edit, so undo and rollback cover it. `on_repopulate` needs the pairs. With `preset list` on keep, this reorders the kept list but never changes which presets are in it.
- **Dialog note:** when no layer changes presets on each clip and `change presets` is on keep, say that only layers come back.

### Verification

- Equal, shorter and longer parts; runs of different lengths; off-grid markers; no bars; a source past the last bar.
- Building stops at the bounds; an explicit intensity beats building.
- Recalled clips get the source's presets; undo restores; locked layers refuse; layers that are not each-clip are untouched.
- Rerun the brightness and pacing rules in `test_timeline_plan.py` with recall on, since copying a source must not break them.
- Every dialog combination on buttercup through the controller with the snap passes.
- Update the changelog, guide (Generate and Song markers), and help.
