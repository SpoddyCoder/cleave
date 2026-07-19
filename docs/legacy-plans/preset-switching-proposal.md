# Preset switching proposal

Proposal for per-layer automatic preset rotation. Supersedes the [Auto-switching presets (projectM mode)](roadmap.md#auto-switching-presets-projectm-mode) roadmap item; Cleave-native preset cycling is out of scope (see [Decisions](#decisions)).

**Status:** Implemented through v2 (none, projectM, user-defined list with add/remove UI). Shuffle toggle shipped; v3 subtree rotation set and filters not scheduled.

## Overview

Today each layer loads one Milkdrop preset and holds it until the user browses to another. Cleave locks the preset and disables hard cuts on every `ProjectM` instance:

```137:139:cleave/viz/layer_pipeline.py
        playlist.load_into(pm)
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
```

Cleave's [cleave/preset_playlist.py](cleave/preset_playlist.py) `PresetPlaylist` is a **browsing** model (directory navigation, sibling stepping). It is not projectM's rotation engine.

This proposal adds a per-layer **preset switching** mode with three values:

| Mode | Summary |
| --- | --- |
| **none** (default) | Current behavior. Fixed preset until manual browse. |
| **projectM** | libprojectM drives when and how to transition; rotation set filled automatically from the browse directory. |
| **user-defined** | Same transition engine as **projectM**; rotation set is an explicit user-curated list. |

## How libprojectM preset switching works

projectM splits responsibility into two parts. Cleave must implement both sides for any non-**none** mode.

### When and how (core engine)

With `projectm_set_preset_locked(false)`, the engine runs an internal timer and beat watcher. Relevant parameters (libprojectM defaults in parentheses):

| Parameter | Default | Role |
| --- | --- | --- |
| `preset_duration` | 30s | Max time on a preset; then request a soft cut |
| `soft_cut_duration` | 3s | Crossfade blend time between presets |
| `hard_cut_enabled` | false | Whether beat-driven instant cuts are allowed |
| `hard_cut_duration` | 20s | Minimum time before a hard cut can fire |
| `hard_cut_sensitivity` | 2.0 | Volume spike threshold for hard cuts |
| `beat_sensitivity` | 1.0 | Beat detection scale (Cleave already exposes this per layer) |
| `easter_egg` | 1.0 | Randomizes effective duration (gaussian multiplier; Milkdrop legacy) |

- **Soft cut:** both presets render; projectM blends over `soft_cut_duration`.
- **Hard cut:** instant switch on a beat spike. Only fires when hard cuts are enabled and `hard_cut_duration` is less than `preset_duration`.

`projectm_set_preset_locked(true)` disables automatic transitions. Programmatic loads still work.

### What to switch to (host / playlist)

The core holds one active preset (plus transition state). When it wants to advance, it fires a `preset_switch_requested` callback with `is_hard_cut` indicating soft vs hard. The host must load the next preset (`smooth=true` for soft, `smooth=false` for hard).

**Integration: libprojectM playlist library (chosen)**

Separate shared library from the core. Per layer:

1. `projectm_playlist_create(pm_handle)` and `projectm_playlist_connect(...)`
2. Populate via `projectm_playlist_add_path` (directory scan) or `projectm_playlist_add_preset` / `add_presets` (explicit paths)
3. Connected playlist answers switch requests via `projectm_playlist_play_next(playlist, hard_cut)`

Also provides shuffle, history, gitignore-style filters, retry on load failure, and switched/failed callbacks.

Cleave today binds only core libprojectM symbols in [cleave/projectm.py](cleave/projectm.py). It does not link or wrap the playlist library yet.

## Proposed modes (detail)

### none

No change from today. Locked preset, hard cuts off, manual browse via preset dir / preset file rows.

### projectM

Unlock preset. Enable projectM's transition engine. Connect a libprojectM playlist populated automatically from the layer's browse directory.

| Rotation set | Playlist API | Behavior |
| --- | --- | --- |
| **directory** (default; v1) | `add_path(current_dir, recurse=false)` | Siblings in the layer's current preset directory |
| **subtree** | `add_path(browse_floor, recurse=true)` | All `.milk` files under the layer browse floor |

Optional: `projectm_playlist_set_filter` for gitignore-style exclusion patterns (could be a later sub-feature).

projectM decides timing and soft/hard blending. The playlist decides which preset is next (sequential or shuffle via `projectm_playlist_set_shuffle`).

### user-defined

Same timing and blending as **projectM** (unlock, projectM duration/hard-cut parameters). Rotation set is an explicit list of presets chosen in the UI.

Implementation: playlist library + `add_presets(paths)` for switch wiring, shuffle, history, and retry.

Persist as config-relative paths under `preset_root`. Store the ordered path list only; playlist position is runtime state and is not persisted (see [Decisions](#decisions)).

## UI

New sub-row under the existing preset controls (alongside preset dir and preset file), per layer:

```
preset switching: none | projectM | user-defined
```

| Mode | Additional UI (sketch) |
| --- | --- |
| **none** | None |
| **projectM** | Child row for rotation set (`directory` in v1; `subtree` later); shuffle toggle in a later phase. Timing parameters in v1.1+ (see phasing). |
| **user-defined** | Expandable sub-row listing selected presets; affordances to add (from current browse position) and remove entries |

Row placement follows [live-tuning-ui](.cursor/rules/live-tuning-ui.mdc): insert after preset file, before stem row.

**v1 UI:** preset switching row plus rotation set child row for **projectM** (`directory` only).

Layer lock rules should match other preset sub-rows (blocked when layer locked). Preset dir and preset file rows are also locked while **projectM** or **user-defined** is active (see [Decisions](#decisions)).

## Runtime behavior

| Mode | `lock_preset` | `hard_cut_enabled` | Switch handler | Population |
| --- | --- | --- | --- | --- |
| none | true | false | n/a | Cleave browse only |
| projectM | false | true | connected playlist lib | auto from rotation set |
| user-defined | false | true | connected playlist lib + `add_presets` | persisted path list |

**Mode change:** rebuild playlist state, load current preset, apply lock/hard-cut settings.

**Per frame:** no extra Cleave rotation logic. projectM evaluates timing during `render_to_fbo` and fires callbacks as needed. PCM feeding and `set_frame_time` continue as today.

**Manual preset browse while auto mode is active:** preset dir and preset file rows are locked. User must switch to **none** to browse manually.

**Empty rotation set:** keep the active mode, stay on the current preset, and show a panel notification via `TuningControls.show_notification` / [cleave/viz/panel_notification.py](cleave/viz/panel_notification.py).

**Offline render:** same code path as live; projectM user frame time is already set per frame in [cleave/viz/layer_pipeline.py](cleave/viz/layer_pipeline.py).

## Config (sketch)

New fields per layer, parsed and persisted through [cleave/config_schema.py](cleave/config_schema.py) / `persisted_session_payload`:

```yaml
layers:
  layer_1:
    preset: presets/drums/some-preset.milk
    preset_switching: none          # none | projectm
    # when projectm:
    preset_switching_rotation_set: directory   # directory | user_defined
    preset_switching_shuffle: false
    # when rotation set is user_defined:
    preset_switching_presets:
      - presets/drums/a.milk
      - presets/drums/b.milk
    # v1.1+ (projectM timing overrides; v1 uses libprojectM defaults):
    # preset_duration: 30.0
    # soft_cut_duration: 3.0
    # hard_cut_duration: 20.0
    # hard_cut_sensitivity: 2.0
```

Defaults: `preset_switching: none`, `preset_switching_rotation_set: directory`. Omit optional keys when they match defaults. Timing/hard-cut apply whenever mode is **projectM**.

## Feature scope

Mode is on/off (`none` | `projectM`); `preset_switching_rotation_set` selects the playlist source (`directory` | `user-defined`). There is no fourth Cleave-native cycling mode; instant stepping without Milkdrop blends is out of scope.

## Implementation notes

### Dependencies

- Bind libprojectM **playlist** shared library (separate from core; verify soname on the dev machine).
- Extend [cleave/projectm.py](cleave/projectm.py): unlock, duration/hard-cut getters and setters, playlist library wrappers.
- Playlist switched/failed callbacks (if used) require stable ctypes references per layer. Callbacks fire on the render thread; no extra GIL assumptions beyond normal ctypes usage.

### Architecture alignment

- New persisted fields through `persisted_session_payload` in [cleave/config_schema.py](cleave/config_schema.py).
- Per-layer session state in [cleave/viz/session.py](cleave/viz/session.py); view model in [cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py); row in [cleave/viz/row_layout.py](cleave/viz/row_layout.py); input in [cleave/viz/controls.py](cleave/viz/controls.py).
- Layer build and preset-change wiring in [cleave/viz/layer_pipeline.py](cleave/viz/layer_pipeline.py) and [cleave/viz/wiring.py](cleave/viz/wiring.py) (`on_preset_change` currently re-locks after every manual pick).

### Suggested phasing

| Phase | Scope |
| --- | --- |
| **v1** | **none** + **projectM**; preset switching row and rotation set child row (`directory` only); hard cuts enabled; libprojectM default timing; shuffle off |
| **v1.1** | Expose the most important timing parameters in the tuning panel (`preset_duration`, `soft_cut_duration`, hard-cut duration/sensitivity) |
| **v2** (done) | **user-defined** list + UI to add/remove presets |
| **v3** | `subtree` rotation set, shuffle toggle, gitignore-style filter patterns |
| **v4** | Remaining optional timing parameters (e.g. `easter_egg`) |

## Decisions

1. **Manual browse while auto mode is on.** Preset dir and preset file rows are locked while **projectM** or **user-defined** is active. Switch to **none** to browse.

2. **Hard cuts in auto modes.** Enable hard cuts when entering **projectM** or **user-defined** (Cleave overrides libprojectM's default of off).

3. **Timing parameters.** v1 uses libprojectM defaults only. v1.1 exposes the most important overrides in the panel. v4 covers remaining optionals.

4. **Feature scope.** **none**, **projectM**, and **user-defined** are the only modes. Cleave-native preset cycling is dropped; no fourth mode.

5. **Playlist integration.** Use libprojectM playlist library + `add_presets` for **user-defined** (and `add_path` for **projectM** directory rotation set).

6. **Rotation set UI in v1.** Ship the rotation set child row in v1; only `directory` is available until a later phase adds `subtree`.

7. **Empty rotation set.** Keep the mode, stay on the current preset, notify via `show_notification` / `PanelNotificationHost`.

8. **Config round-trip for user-defined list.** Persist the ordered path list only; playlist index/position is runtime state rebuilt on load.

9. **Shuffle and repeat.** Strict sequential order when shuffle is off is acceptable. No "no repeat until all played" requirement.

10. **Layer add/remove.** New layers default to **none**. Deleting a layer drops its playlist handle with the `ProjectM` instance; no cross-layer handle leaks.


## Persistent hard to solve whitescreen on transition bug
The white screen was a GL state leak: libprojectM's transition pass left the active texture unit non-zero, and Cleave's fixed-function compositor sampled an empty unit (which reads as white). Fixed by resetting glActiveTexture(GL_TEXTURE0) in the compositor's bind helpers.