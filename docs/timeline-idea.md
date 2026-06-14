# Timeline (layer visibility automation)

Sparse cue list that drives per-stem show/hide over playback time. Saved at the bottom of [cleave-viz.yaml](../cleave-viz-default.yaml) under `timeline:`.

## Enable

1. In the main tuning panel, focus **Render: TIMELINE** and press **Ctrl+Right** to enable (eye on).
2. Press **t** to open the bottom timeline strip.

When timeline is enabled, stem layer eyes in the main panel are ignored; visibility follows the rules below.

## Timeline panel

Bottom overlay (~20% of window height). Four rows in `layer_z_order` with stem abbreviations (D/B/V/O). Each row has a monitor eye beside the label, a cue bar across the middle, and a committed-timeline eye at the far right; orange playhead tracks playback; ticks mark cue times.

| Eye | Position | Meaning |
| --- | --- | --- |
| Left | Beside stem label | Monitor / output (what is on screen; gold override styling on the left eye when that stem is in override) |
| Right | Far right of row | Committed timeline automation at the playhead (saved cues only; ignores record buffer and monitor preview) |

While paused with monitor preview active, seeking updates the right eye only; the left eye stays on the monitor dict until you change it with num keys or resume.

## Transport and visibility

Output priority: main-panel solo (if set) beats recording rules, then paused monitor preview, then timeline manual override, then committed timeline eval. During recording, armed stems follow the record buffer; unarmed stems in override keep `override_visible`; other unarmed stems follow committed timeline.

| Transport | Num keys 1-4 | Layer output | Left eye | Right eye |
| --- | --- | --- | --- | --- |
| Playing | Toggle manual on/off for override stems only | Manual override for overridden stems; others follow committed timeline | Same as output; gold override styling when stem is in override | Committed at playhead |
| Paused (preview) | Toggle monitor preview (all stems) | `monitor` dict | Monitor preview | Committed at playhead |
| Paused (override) | Toggle override visibility (same as preview: flip that stem) | `override_visible` for override stems | Same as output; gold override styling when stem is in override | Committed at playhead |
| Recording | Armed rows only (record buffer) | Armed: record baseline + buffer toggles; unarmed in override: `override_visible`; other unarmed: committed timeline | Live output; gold override styling on armed rows and override stems | Committed at playhead |

Override (`override_stems` / `override_visible` on `TimelineRuntime`) is separate from main-panel global solo (`session.solo_stem`). Multiple stems can be in override at once; others keep following the committed timeline.

Monitor preview state (`preview_active`, `monitor`) is session-only and is not written to YAML.

## Keys

| Key | Action |
| --- | --- |
| `t` / `Esc` | Close panel |
| Up / Down | Focus layer row |
| Left / Right | Previous / next cue |
| Enter | Arm / disarm focused row (red background when armed) |
| Backspace | Delete focused cue |
| Space | Pause / resume. While recording and playing: stop record and pause (no preview). Otherwise pause snapshots current output at the playhead into `monitor` and enables preview; resume clears preview and `monitor`. |
| Ctrl+Space | Start record (same as `r` start). While recording: stop record, pause at playhead (no preview). |
| Ctrl+Left / Right | Seek 10s / 30s (blocked while recording) |
| `r` | Start / stop record. Start applies WYSIWYG baseline for armed stems (see below), clears preview, and unpauses if paused. Override is preserved. Stop leaves playback running. |
| `1`-`4` | Paused + preview: toggle that stack layer in `monitor` (bottom = 1). Paused + override: toggle that layer in `override_visible` (adds stem to override if needed). Recording: toggle armed layer into record buffer at playhead. Playing (not recording): toggle manual on/off for that layer when it is in override. |
| Shift+Enter | Toggle override on focused row (manual override; does not write cues). On enter, snapshots current output into `override_visible` and clears monitor preview. On exit, removes stem from `override_stems`. Ignored when recording. |
| Ctrl+Enter | Recording only: toggle focused row at playhead (armed rows only) |

## Record workflow

Typical pass starting from 0:00:

1. Open panel (`t`). Seek to **0:00** if needed (**Ctrl+Left** / **Ctrl+Right**).
2. **Space** to pause. Committed visibility at the playhead is copied into monitor preview.
3. Up/Down to each row; **Enter** to arm layers you will record (red row). Repeat for each layer.
4. Optional: while still paused, **1**-**4** adjust monitor preview so the left eyes match the mix you want at record start (right eyes still show committed cues).
5. **r** to start record. For each armed stem, current output at the playhead is stored as a record baseline (not shown on the timeline bar). Preview clears and playback resumes if it was paused. Override on unarmed stems is preserved (use **Shift+Enter** to hide other layers before recording).
6. On the beat, press **1**-**4** (stack position) or **Ctrl+Enter** (focused armed row) to toggle visibility for armed layers only.
7. **r** or **Ctrl+Space** again to stop (**Ctrl+Space** also pauses). Armed-layer cues in that pass replace the previous take for that time range (punch overwrite). Unarmed stems are untouched.
8. **SAVE CONFIG** in the main panel writes cues to YAML.

While playing or paused (not recording), **Shift+Enter** puts the focused row into override (manual override; left monitor eye uses gold override styling; clears monitor preview on enter). Press again on the same row to exit. **1**-**4** toggle manual on/off for layers while paused (preview or override) or for override stems while playing. That does not affect cues or main-panel solo. Override persists through record (frozen until record stops).

## YAML shape

```yaml
timeline:
  enabled: true
  cues:
    - t: 12.4
      layers:
        vocals: true
    - t: 48.02
      layers:
        bass: false
```

Before the first cue, visibility uses each stem's `layers.*.enabled` default. Partial `layers` maps leave other stems unchanged.

## v2 (not implemented)

- Fade in/out on layer transitions
- Beat snap for cue placement
- External timeline file for very long cue lists
