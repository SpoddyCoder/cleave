# Config and save improvements

Make Cleave's three config files feel like a normal desktop app: machine preferences, one project document, and a hidden template. Stop leftover "the YAML is the app" save verbs that let users lose work.

Related: [user-data-and-config-plan.md](user-data-and-config-plan.md), [cleave/user_config.py](../cleave/user_config.py), [cleave/project.py](../cleave/project.py), [cleave/viz/config_save.py](../cleave/viz/config_save.py), [architecture principles](../../.cursor/rules/architecture-principles.mdc), [editor-first](../../.cursor/rules/editor-first.mdc).

The older user-data plan still holds for install vs user data vs per-track creative config. Field ownership has already moved (window size is user config; beat sensitivity and render size are `project.yaml`). This plan is about save verbs, the repo-root template, and the mistakes those create.

---

## Problem

Cleave used to be a one-config app. The live editor still saves as if `cleave-viz.yaml` were the document: overwrite vs Save As New, a filename in the Project row, and a checkout-root example that can become the active file.

There are three durable files:

| File | Where | Role |
| --- | --- | --- |
| User config | Linux `~/.config/cleave/config.yaml`; Windows `%APPDATA%\cleave\config.yaml` | Editor prefs: window size, UI fade/width, preview quality, residual latency. Optional default `paths`. |
| `project.yaml` | `projects/<slug>/` | Song identity: mix/ingest, song markers, ProjectM beat sensitivity, compositor HDR, render width/height/fps. |
| Creative YAML | `projects/<slug>/cleave-viz.yaml` (also repo-root template) | Layers, timeline, overlay and post-FX. |

The bundled [assets/cleave-viz.yaml](../../assets/cleave-viz.yaml) is the shipped example. New projects copy it via [ensure_project_viz_config](../cleave/config.py). [find_config_path](../cleave/config.py) still falls back to that bundled file as a live session when the project has no copy.

Users should not have to know which file holds which knob. Today they must, because Save, Settings, and the example template each behave differently.

---

## How save works today

### User config (not on Ctrl+S)

Settings never set the dirty asterisk. They are not written by Save.

[persist_editor_settings](../cleave/user_config.py) writes the `editor:` section (dict-merge into the existing user YAML) in three places:

- Confirm **change window size** (restart still required to apply).
- Apply tap-sync residual latency.
- App shutdown in [VisualizerApp.run](../cleave/viz/app.py) `finally`.

Panel nudges (UI fade, preview quality, latency, unconfirmed window size) stay in memory until quit. A crash before shutdown drops them.

### Creative YAML (Ctrl+S / dirty `*`)

[ConfigSaveController](../cleave/viz/config_save.py) compares [persisted_session_payload](../cleave/config_schema/persist.py) (layers, render overlays/post-FX, timeline) to the last saved signature.

Save offers Overwrite vs Save As New. Overwrite is hidden when the active path is the repo-root template ([allow_overwrite_for_path](../cleave/viz/session.py)). Save As New writes `unnamed-N.yaml` in the project folder via [next_unnamed_path](../cleave/config_snapshot.py) and switches the in-session active path. The next `play` of that project still loads `cleave-viz.yaml`.

Choosing Overwrite does not write yet. [ConfigSaveController._prompt_overwrite](../cleave/viz/config_save.py) opens a second Yes/No: `Overwrite {basename}?`. Ctrl+S on a normal project is always two modals. Save on unsaved quit is worse: Save / Don't Save, then the same two.

The Project row help still says "Active config file."

### `project.yaml` (flushed on successful Save)

Live-edited fields (song markers, beat sensitivity, HDR, render size/fps) stay in the session until `_commit_save`. One Save writes both the creative YAML and those `project.yaml` keys. Mix/ingest metadata is written at separate/restore time, not from the editor.

Those helpers rewrite the whole file from [ProjectManifest.to_dict](../cleave/project.py). Keys the dataclass does not know are dropped. That is the [todos.md](../todos.md) unknown-key wipe.

---

## User mistakes this causes

- **Save As New looks saved and is gone next session.** `unnamed-N.yaml` is not the file `play` opens. Song markers still flush to `project.yaml`, so half the work sticks and the arrangement does not.
- **Editing the example.** Checkout `find_config_path` / [resolve_config_path](../cleave/viz/bootstrap.py) can open the repo-root template. Overwrite is blocked; Save As New still runs. Frozen users are less exposed; checkout users are not.
- **Thinking Settings need Save.** They do not. Window size also needs a separate confirm plus restart.
- **Crash loses prefs.** UI fade, preview quality, and latency wait for quit.
- **One dirty flag, two files, a filename in the UI.** Changing only markers still opens the viz-YAML overwrite dialog. The user sees a YAML basename, not "the project."
- **Ctrl+S confirms twice.** Overwrite vs Save As New, then `Overwrite filename?`. The second prompt exists only because Overwrite was a destructive choice among two destinations. With one project file it is noise.

---

## Target mental model

Match a DAW or video editor:

1. **Preferences** are machine-wide. They stick. No asterisk. No Save.
2. **The project is the folder** you opened (`project.yaml`, stems, mix, one creative YAML). Save / Don't Save / Cancel on quit.
3. **The template is not a document.** It ships with the app, is copied into new projects, and is never the active file.

Internally two project YAML files can remain. The UI must not mention both names, and must not offer a second creative filename.

---

## Principles

- **Prefs write when committed.** Debounce panel nudges, or write on each change. Keep the window-size confirm only because the GL window cannot resize live. Do not wait until quit.
- **One creative file per project.** Always `projects/<slug>/cleave-viz.yaml` (or a later rename). Ctrl+S writes that file immediately. No Overwrite vs Save As New. No second `Overwrite filename?` confirm.
- **Confirm only when discarding work.** Unsaved quit is Save / Don't Save / Cancel. Picking Save from that dialog writes immediately; do not chain into another save modal.
- **The folder is the document.** Duplicate looks via Duplicate Project / [backup](../cleave/archive.py), not sibling YAML names.
- **Never open the template as the live session.** If there is no project, show the picker ([file-picker-plan.md](../file-picker-plan.md)).
- **Do not autosave the project over itself.** Explicit Save is correct for a live experiment. A crash-recovery sidecar can wait.
- **Dict-merge `project.yaml`.** Each helper touches only the keys it owns. Same idea as [write_user_config](../cleave/user_config.py).
- **Keep current field ownership.** Window/UI/preview/latency in user config; ingest/markers/beat/HDR/output size in `project.yaml`; layers/timeline/overlays in the creative YAML. Do not put editor prefs back on the Save path.

---

## Locked

| Question | Answer |
| --- | --- |
| Merge `project.yaml` and creative YAML into one file | No. The folder is the portable unit. Backup already zips it. |
| Autosave creative edits onto the project file | No. Keep explicit Save. Optional recovery sidecar later, not this work. |
| Save As New / `unnamed-N.yaml` | Remove. Footgun. |
| Confirm on Ctrl+S | No. Write immediately. Toast is enough. |
| Confirm on unsaved quit | Yes. One dialog only. Save from it writes immediately. |
| Multiple named arrangements per song | Out. Revisit later as a first-class picker, not raw YAML filenames. |
| Repo-root `cleave-viz.yaml` as a live file | Stop. Bundle as a resource; copy into new projects only. |
| User prefs on Ctrl+S | No. Persist on change (and still on quit as a safety net). |
| Window size apply-and-restart | Keep until live resize exists. Persist the values on confirm (and on change if unconfirmed values should survive quit: pick one and document it). |
| Dirty asterisk | Unsaved **project** (creative YAML plus `project.yaml` session fields), not a YAML basename. |
| Project row copy | "Save", not "active config file." |
| Unknown keys in `project.yaml` | Preserve via dict-merge. |
| Backward compatibility for `unnamed-N.yaml` as the launch file | No. Existing sibling files stay on disk; `play` keeps loading `cleave-viz.yaml`. |

---

## Leave open

- Rename `cleave-viz.yaml` inside the project folder (`session.yaml`, `visual.yaml`, or similar). Nice once the UI no longer shows the filename; not required to fix save.
- Crash-recovery sidecar for unsaved project edits.
- Live window resize so the apply-and-restart modal can go.
- Named arrangements / scenes per project, with an in-window picker.
- Last-opened project and last browse directory in user config (also in [file-picker-plan.md](../file-picker-plan.md)).
- Whether unconfirmed window-size nudges persist on quit. Today they do, because shutdown dumps all of `cfg.editor`.

---

## Recommended work

### 1. Hide the template

Move [assets/cleave-viz.yaml](../../assets/cleave-viz.yaml) out of the repo root into a bundled resource path that [resource_dir](../cleave/paths.py) already serves in the freeze. [ensure_project_viz_config](../cleave/config.py) already copies from there.

Stop [find_config_path](../cleave/config.py) and [resolve_config_path](../cleave/viz/bootstrap.py) from returning the template as the active session. Tests that assert repo-root and resource path are the same file need to follow the new location. CLI `--config` override can stay for CI.

If a launch has no project, the picker is the fallback, not the example YAML.

### 2. One Save, one creative file

Remove Save As New, [next_unnamed_path](../cleave/config_snapshot.py), `prompt_save_choice` / `prompt_save_as_new`, `_prompt_overwrite`, and the overwrite-blocked-for-template branch once the template cannot be active.

Ctrl+S / Enter on the Project save row writes that project's creative YAML immediately, then flushes `project.yaml` session fields (same `_commit_save` as today). No modal. Quit stays one Save / Don't Save / Cancel dialog; Save from it takes the same immediate write, not the old two-step overwrite chain.

Relabel the row and help to Save. Drop the path-as-value presentation, or show the project slug, not a YAML basename.

### 3. Persist prefs on change

Call `persist_editor_settings` when a Settings value is committed (each nudge, or a short debounce). Keep the window-size modal as the restart warning; that confirm already writes.

Leave the shutdown write as a belt-and-braces flush. Prefs still never participate in `config_dirty`.

### 4. Dict-merge `project.yaml`

Change `write_manifest`, `save_song_markers`, `save_milkdrop_settings`, `save_compositor_settings`, `save_render_settings`, and `rewrite_manifest_slug` so they load YAML as a dict, patch only owned keys, and write the dict back. Stops Save (and separate/restore) from wiping unknown or future keys.

### 5. Copy and tests

Update overlay help, README project-layout notes, and [song-markers.md](song-markers.md) (it still describes Save As New). Extend tests that cover dirty tracking, overwrite, double-confirm (`test_overwrite_shows_confirm_before_write`), and `unnamed-N.yaml` so they assert immediate Save and that prefs still do not mark dirty.

---

## Suggested order

1. Bundle the template; never open it as the live file.
2. One creative file per project; remove Save As New.
3. Persist prefs on change.
4. Dict-merge `project.yaml`.
5. Relabel Save so the UI talks about the project, not a config filename.

(1) and (2) remove the two ways a user edits the wrong YAML. (3) and (4) make the remaining writes match desktop norms. (5) is copy once the verbs are honest.

---

## Out of scope

- Moving `projects/` out of a checkout (`CLEAVE_DATA` / Documents) beyond what [user-data-and-config-plan.md](user-data-and-config-plan.md) and the freeze already do.
- Merging the two project YAML files.
- Undo/redo ([roadmap.md](../roadmap.md)).
- Mid-session Open ([file-picker-plan.md](../file-picker-plan.md) Phase 3). That work should reuse the same unsaved-project prompt once this plan lands.
