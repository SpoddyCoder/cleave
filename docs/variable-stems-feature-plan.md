# Variable stems feature plan

## Goal

Each compositor layer slot (currently hard-wired to one stem) becomes independently
re-assignable to any of five audio sources: `drums`, `bass`, `vocals`, `other`,
or `full_mix`. The assignment is surfaced as a new "Stem:" control row, one row
above the blend mode. Layer names and timeline initials update to reflect the
assigned source. PCM fed to the projectM instance follows the assignment.


## Decisions (agreed)

| Question | Answer |
|---|---|
| Stable layer identity | Numeric slots: `layer_1`..`layer_4` |
| full-mix timeline initial | `M` |
| Effects follow stem | Yes - roster and signal reads use the assigned stem |
| full-mix PCM | Load `mix.wav` into `StemPcmBank` as the `full_mix` key |
| full-mix signals | Analyse mix audio; add `full_mix` section to `signals.json` |
| Timeline cue layer refs | Slot keys (`layer_1`..`layer_4`) |
| Preset playlists | Per slot, independent of assigned stem |


---

## New concepts

### `StemSource`

```python
# cleave/extract.py
StemSource = Literal["drums", "bass", "vocals", "other", "full_mix"]
STEM_SOURCES: tuple[StemSource, ...] = ("drums", "bass", "vocals", "other", "full_mix")
```

`STEM_NAMES` stays as `("drums", "bass", "vocals", "other")` - it describes the
four Demucs output files. `STEM_SOURCES` is the superset exposed to the user.

### Layer slots

```python
# cleave/config_schema.py
LAYER_SLOTS: tuple[str, ...] = ("layer_1", "layer_2", "layer_3", "layer_4")

DEFAULT_STEM_FOR_SLOT: dict[str, StemSource] = {
    "layer_1": "drums",
    "layer_2": "bass",
    "layer_3": "vocals",
    "layer_4": "other",
}
```

Everywhere that previously used a stem name as a layer key (config, session,
view state, GL pipeline, timeline cues, effects runtime) switches to slot keys.


---

## Display mapping

| `StemSource` | Overlay header | Timeline strip | Stem row value |
|---|---|---|---|
| `drums` | `DRUMS` | `D` | `drums` |
| `bass` | `BASS` | `B` | `bass` |
| `vocals` | `VOCALS` | `V` | `vocals` |
| `other` | `OTHER` | `O` | `other` |
| `full_mix` | `MIX` | `M` | `full-mix` |

The "Stem row value" is what the live tuning control row shows (lowercase, hyphen
for full-mix). The overlay header continues to show the short uppercase form.


---

## File-by-file changes

### `cleave/extract.py`

- Add `StemSource` type alias and `STEM_SOURCES` tuple.
- Keep `STEM_NAMES` (Demucs stems, used by separation pipeline).
- `stem_paths()` continues to map only the four Demucs stems.

### `cleave/stem_pcm.py`

- `load_stem_pcm()` loads all five sources: four stem wavs plus the project mix
  wav (`project.mix_path(project_dir)`) stored under the `"full_mix"` key.
- Update docstring from "four stem wavs" to "five audio sources".
- `slice_pcm(stem: StemSource, ...)` - the type hint becomes `StemSource`.

### `cleave/analyse.py` and `cleave/extract.py`

- `run_analyse()` adds a `full_mix` section to `signals.json`:
  ```json
  "full_mix": {
    "onset_strength": [...],
    "rms": [...]
  }
  ```
- `onset_strength` reuses `extract_mix_onset(mix_path)`.
- `rms` uses a new `extract_mix_rms(mix_path)` helper (plain RMS envelope on mix
  wav, same approach as `extract_bass` but without band splitting).
- Remove `mix_onset_strength` from the `drums` section (it moves to `full_mix`).
  Update `_DRIVER_SIGNAL_KEYS` and signals fixtures accordingly.
- `signals.json` version bump to `2`.
- `Signals` loader in `cleave/signals.py` updated for version 2 keys.

### `cleave/effects/registry.py`

- `_DRIVER_SIGNAL_KEYS` global map stays for the four original stems.
- Add a `full_mix` roster using explicit `EffectDef` construction (signal_stem is
  `"full_mix"`, not derived from the global map):
  ```python
  "full_mix": (
      EffectDef("pulse", "onset", "full_mix", "onset_strength"),
      EffectDef("flare", "onset", "full_mix", "onset_strength"),
      EffectDef("flash", "onset", "full_mix", "onset_strength"),
      EffectDef("grit",  "onset", "full_mix", "onset_strength"),
  )
  ```
- `effect_roster(stem: StemSource)` - parameter type updated.
- `validate_effect_entry(slot, stem, effect_id, driver_slug)` - add `slot` arg
  for error messages; validate against the roster for the given stem.
- `all_stem_sources() -> tuple[StemSource, ...]` replaces `all_stems()`.

### `cleave/effects/runtime.py`

- `EffectRuntime._states` key changes from `(stem, effect_id, driver_slug)` to
  `(slot, effect_id, driver_slug)` (effects state is per slot, not per stem).
- `update()` and `modifiers()` iterate `session.layers` by slot key; retrieve
  `layer_runtime.stem` to look up the roster:
  ```python
  for slot, layer in session.layers.items():
      for row in effect_roster(layer.stem):
          ...
  ```
- Output dict of `modifiers()` keyed by slot (was stem).

### `cleave/config.py`

- `LayerConfig` gains `stem: StemSource` field.
- Remove any stem-as-key assumptions from config dataclasses.

### `cleave/config_schema.py`

- `DEFAULT_LAYER_Z_ORDER = ("layer_1", "layer_2", "layer_3", "layer_4")`.
- `DEFAULT_STEM_FOR_SLOT` added (see above).
- `DEFAULT_BLEND_MODE` keyed by stem source; applied at parse time based on the
  layer's `stem` field.
- `LAYER_DEFAULT_SIZE` keyed by stem source; same application pattern.
- `layers` parse: four required keys `layer_1`..`layer_4`; each entry requires a
  `stem` field (valid `StemSource`); default stem from `DEFAULT_STEM_FOR_SLOT`.
- `layer_z_order` parse: must be a permutation of `LAYER_SLOTS`.
- Timeline cue `layers` field: keys validated as slot keys.
- `template_layer_entry(slot)` updated: takes a slot and uses
  `DEFAULT_STEM_FOR_SLOT[slot]` for the stem default.
- `persisted_session_payload` serialises each layer entry with `stem:` field.

### `cleave-viz.yaml`

Full rewrite of the `layers` and `layer_z_order` sections:

```yaml
layer_z_order: [layer_1, layer_2, layer_3, layer_4]

layers:
  layer_1:
    stem: drums
    preset: ...
    blend_mode: add
    ...
  layer_2:
    stem: bass
    ...
  layer_3:
    stem: vocals
    ...
  layer_4:
    stem: other
    ...
```

### `cleave/timeline.py`

- `_STEM_ABBREVIATIONS` -> `_STEM_SOURCE_ABBREVIATIONS`; add `"full_mix": "M"`.
- `stem_abbreviation(stem: StemSource) -> str` parameter type updated; error
  message updated.
- `TimelineCue.layers: dict[str, bool]` keys are now slot keys (`layer_1`..`4`).
- `layer_visible_at(cues, defaults, slot, t_sec)` - parameter renamed to `slot`.
- `visible_state_at` and any other cue-query helpers: slot-keyed.
- Module docstring updated.

### `cleave/viz/session.py`

- `LayerRuntime` gains `stem: StemSource` field.
- `TuningSession.layers: dict[str, LayerRuntime]` keyed by slot.
- `TuningSession.layer_z_order: list[str]` contains slot keys.
- `TuningSession.solo_stem: str | None` renamed `solo_slot: str | None`.
- `TimelineRuntime.armed_stems: set[str]` renamed `armed_slots: set[str]`.
- `TimelineRuntime.override_stems: set[str]` renamed `override_slots: set[str]`.
- `session_from_cfg()` uses slot keys from `LAYER_SLOTS`; reads `cfg.layers[slot].stem`.
- `_default_browse_floor()`: if it has stem-specific logic, switch to slot-based or
  make it stem-source-agnostic.

### `cleave/viz/layer.py`

- `StemLayer.name: str` -> `StemLayer.slot: str` (GL/compositor identity).
- Add `StemLayer.stem: StemSource` (audio source; used for PCM and effects lookup).
- Remove the single `name` field; callers that need GL identity use `.slot`, those
  that need audio source use `.stem`.

### `cleave/viz/layer_pipeline.py`

- All `layers_by_name` dicts become `layers_by_slot`.
- `LayerFramePipeline.build()`: slot key from config; `stem` from `cfg.layers[slot].stem`;
  pass both to `StemLayer(slot=..., stem=..., ...)`.
- PCM lookup: `pcm_bank.slice_pcm(layer.stem, t_sec, n_pcm)`.
- `apply_effect_modifiers()`: iterate by slot; modifiers dict keyed by slot.
- `LayerFramePipeline.composite()`: `layers_by_slot[slot]` order from `session.layer_z_order`.
- `_beat_sensitivity(cfg, slot)` parameter name updated.

### `cleave/viz/layer_visibility.py`

- Signatures updated to use slot keys throughout.
- `effective_layer_enabled(session, slot, t_sec)`.
- `apply_layer_visibility(session, layers_by_slot, t_sec)`.
- Timeline cue lookup: `layer_visible_at(cues, defaults, slot, t_sec)`.

### `cleave/viz/tuning_view_state.py`

- `TuningViewState.tracks: dict[str, TrackBlock]` keyed by slot.
- `TrackBlock` gains `stem: StemSource` field.
- `TuningViewStateBuilder.build()`: use slot keys; populate `TrackBlock.stem` from
  `session.layers[slot].stem`.

### `cleave/viz/overlay.py`

- `TrackBlock.stem: StemSource` added.
- Overlay header label: `"Layer N: "` prefix + display name from stem source.
  `full_mix` -> `"MIX"` in the overlay header (the display map above).
- `_fit_track_header_stem()` handles the display name mapping.
- All `stem` variables in this file that were layer keys are renamed to `slot`
  where they carry slot identity, not source identity.
- `_render_track_header_label()` reads `TrackBlock.stem` for the display name.

### `cleave/viz/controls.py`

New `RowKind.TRACK_STEM` row, inserted **between the preset row and the blend
mode row** (matching "1 line above blend mode"):

```
header
preset dir
preset
stem       <-- new
blend
opacity
beat sensitivity
cleave effects header
```

- Left/Right on the stem row cycles through `STEM_SOURCES` in order.
- On change:
  - Write `session.layers[slot].stem = new_stem`.
  - Clear `session.layers[slot].effects` (old effects config is invalid for the new
    roster; user starts fresh).
  - Mark config dirty via existing dirty-tracking mechanism.
- The row is never locked (stem can always be changed).
- Display: `"Stem: drums"` / `"Stem: full-mix"` in label/value style.

### `cleave/viz/row_semantics.py`

- Add `RowKind.TRACK_STEM` to the enum and to the per-track base rows tuple.
- Update `TRACK_BASE_ROW_KINDS`, interaction groups, repeat-key sets, and help
  affordance strings.

### `cleave/viz/help_overlay.py`

- Add "Stem:" entry to the layer/track controls section: "Left/Right - cycle stem
  source; effects reset on change".

### `cleave/viz/timeline_controls.py`

- `_stem_for_layer_index()` -> `_slot_for_layer_index()`.
- All references to `armed_stems`, `override_stems` updated to `armed_slots`,
  `override_slots`.

### `cleave/viz/timeline_overlay.py`

- `stem_abbrev_label(stem: StemSource)` - uses the new abbreviation map including
  `full_mix` -> `" M "`.
- Row label logic reads `layer_runtime.stem` from session rather than inferring
  the abbreviation from the slot position.

### `cleave/preset_playlist.py`

- `scan_all_layers(cfg)` iterates slot keys from `LAYER_SLOTS` (or `cfg.layers.keys()`);
  uses `cfg.layers[slot].preset` as before. No stem-directory logic needed since
  playlists are per slot.

### `cleave/viz/app.py`

- Where `layers_by_name` is referenced at module level, rename to `layers_by_slot`.
- Solo display (if it reads `solo_stem`) updated to `solo_slot`.


---

## `signals.json` schema (version 2)

```json
{
  "version": 2,
  "sample_rate_hz": 100,
  "duration_sec": 123.4,
  "drums":    { "onset_strength": [...] },
  "bass":     { "rms": [...], "sub_bass": [...], "mid_bass": [...] },
  "vocals":   { "rms": [...], "pitch_hz": [...] },
  "other":    { "spectral_centroid": [...] },
  "full_mix": { "onset_strength": [...], "rms": [...] }
}
```

`mix_onset_strength` is removed from `drums`; it is replaced by
`full_mix.onset_strength`. Any existing `signals.json` files must be regenerated
(`python -m cleave analyse <project>`).


---

## YAML config migration

No migration path. Existing project YAML files with stem-keyed layers sections
are invalid after this change. Users must re-save their config via the save
control or copy the new `cleave-viz.yaml` template into their project and
re-enter settings.


---

## Effects config on stem change

When a user changes a layer's stem source via the Stem: control:

1. `session.layers[slot].effects` is reset to `{}`.
2. The UI shows the new roster with all effects at 0%.
3. Config is marked dirty.

No attempt is made to carry over effect entries that happen to exist in both
rosters (clean break).


---

## Test changes

`tests/cleave/viz/test_controls.py` (2530 lines) and `tests/cleave/test_config.py`
(594 lines) are the heaviest tests. Every fixture, assertion, and parametrize
that uses stem names as layer keys must switch to slot keys. Key changes:

- Session builder helpers: `layers={"drums": ...}` -> `layers={"layer_1": ...}`.
- Config YAML fixtures: slot-keyed layers with `stem:` field.
- New tests for `RowKind.TRACK_STEM` cycling, effects-clear-on-change,
  and full-mix PCM/signal coverage.
- Signals fixture `tests/fixtures/minimal_signals.json`: add `full_mix` section,
  remove `mix_onset_strength` from `drums`, bump version to 2.
- Effects tests: state key assertions use slot, not stem.
- Timeline tests: cue `layers` dict uses slot keys.


---

## Implementation order

1. `cleave/extract.py` - add `StemSource`, `STEM_SOURCES`.
2. `cleave/analyse.py` / `cleave/extract.py` - add mix RMS, full_mix signals section,
   version bump.
3. `cleave/signals.py` - version 2 loader.
4. `cleave/stem_pcm.py` - load mix wav as `full_mix`.
5. `cleave/effects/registry.py` - full_mix roster, updated types.
6. `cleave/config.py` / `cleave/config_schema.py` - slot keys, `stem` field, new
   defaults.
7. `cleave-viz.yaml` - template rewrite.
8. `cleave/timeline.py` - slot-keyed cues, full_mix abbreviation.
9. `cleave/viz/session.py` - slot keys, `stem` on `LayerRuntime`, renames.
10. `cleave/viz/layer.py` + `layer_pipeline.py` - slot/stem split.
11. `cleave/viz/layer_visibility.py` - slot keys.
12. `cleave/effects/runtime.py` - slot-keyed state.
13. `cleave/viz/tuning_view_state.py` + `overlay.py` - stem display, `TrackBlock.stem`.
14. `cleave/viz/row_semantics.py` - `RowKind.TRACK_STEM`.
15. `cleave/viz/controls.py` - stem cycling, effects clear.
16. `cleave/viz/timeline_controls.py` + `timeline_overlay.py` - slot/abbreviation.
17. `cleave/viz/help_overlay.py` - new help text.
18. `cleave/preset_playlist.py` - slot key iteration.
19. Test updates (fixtures, assertions, new stem-row tests).
