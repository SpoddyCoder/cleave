# Timeline (layer visibility automation)

Sparse cue list that drives per-stem show/hide over playback time. Saved at the bottom of [cleave-viz.yaml](../cleave-viz-default.yaml) under `timeline:`.

## Enable

1. In the main tuning panel, focus **Render: TIMELINE** and press **Ctrl+Right** to enable (eye on).
2. Press **t** to open the bottom timeline strip.

When timeline is enabled, stem layer eyes in the main panel are ignored; visibility follows cues.

## Timeline panel

Bottom overlay (~20% of window height). Four rows in `layer_z_order` with stem abbreviations (D/B/V/O). Horizontal bars show on/off regions; orange playhead tracks playback; ticks mark cue times.

| Key | Action |
| --- | --- |
| `t` / `Esc` | Close panel |
| Up / Down | Focus layer row |
| Left / Right | Previous / next cue |
| Enter | Arm / disarm focused row (red background when armed) |
| Backspace | Delete focused cue |
| Ctrl+Enter | Toggle focused layer at playhead (manual cue) |
| Space | Pause / resume |
| Ctrl+Left / Right | Seek 10s / 30s (blocked while recording) |
| `r` | Start / stop record |
| `1`–`4` | Toggle armed layer at stack position (record only; bottom = 1) |

## Record workflow

1. Open panel (`t`).
2. Up/Down to a row; **Enter** to arm (red row). Repeat for each layer to record.
3. **r** to start record and playback. Press **1**–**4** on the beat for armed layers only.
4. **r** again to stop. Armed-layer cues in that pass replace the previous take for that time range (punch overwrite). Unarmed stems are untouched.
5. **SAVE CONFIG** in the main panel writes cues to YAML.

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
