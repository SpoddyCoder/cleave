# UI Performance Results

Consistent test case with 2 layers and user-presets. UI gradually opens all leaves of the tree...

## Phase 1
Baseline, just the profiler built in this phase.

```
overlay profiler: on (logging to terminal every 30 frames)
overlay: vs=6.8ms draw=4.7ms surf=11 font=31 up=0.3ms
overlay: vs=6.0ms draw=18.5ms surf=18 font=48 up=0.5ms
overlay: vs=6.4ms draw=58.3ms surf=30 font=73 up=0.7ms
overlay: vs=6.6ms draw=54.2ms surf=30 font=72 up=0.6ms
overlay: vs=6.3ms draw=72.3ms surf=34 font=80 up=0.5ms
overlay: vs=5.8ms draw=139.9ms surf=51 font=115 up=0.5ms
overlay: vs=5.6ms draw=151.8ms surf=53 font=120 up=0.6ms
overlay: vs=5.5ms draw=162.3ms surf=57 font=128 up=0.5ms
overlay: vs=5.8ms draw=170.0ms surf=57 font=128 up=0.6ms
overlay profiler: off
```

## Phase 2

Structural view-state cache (`view_state_structure_signature` + `_ViewStateStructure`),
single `RowLayoutFrame` per frame (`visible_indices`, `navigable_indices`,
`resolved_focus_index`, `descriptor_index`), and `PresetPlaylist.directory_display_label`
memoization with invalidation on navigation mutators.

```
overlay profiler: on (logging to terminal every 30 frames)
overlay: vs=1.6ms draw=1.6ms surf=11 font=31 up=0.3ms
overlay: vs=1.3ms draw=1.5ms surf=10 font=31 up=0.3ms
overlay: vs=1.6ms draw=1.8ms surf=10 font=31 up=0.5ms
overlay: vs=1.5ms draw=2.7ms surf=18 font=48 up=0.6ms
overlay: vs=1.9ms draw=3.5ms surf=27 font=66 up=0.5ms
overlay: vs=1.9ms draw=3.4ms surf=27 font=65 up=0.6ms
overlay: vs=2.0ms draw=4.3ms surf=30 font=72 up=0.6ms
overlay: vs=2.2ms draw=4.6ms surf=30 font=72 up=0.6ms
overlay: vs=2.0ms draw=4.9ms surf=30 font=72 up=0.9ms
overlay: vs=2.2ms draw=4.3ms surf=30 font=72 up=0.6ms
overlay: vs=2.1ms draw=4.3ms surf=30 font=72 up=0.6ms
overlay: vs=2.0ms draw=5.2ms surf=34 font=80 up=0.6ms
overlay: vs=2.1ms draw=5.0ms surf=34 font=80 up=0.7ms
overlay: vs=2.0ms draw=5.4ms surf=34 font=80 up=0.7ms
overlay: vs=2.5ms draw=6.3ms surf=42 font=97 up=0.7ms
overlay: vs=3.5ms draw=7.2ms surf=51 font=115 up=0.8ms
overlay: vs=2.8ms draw=7.3ms surf=53 font=120 up=0.8ms
overlay: vs=2.8ms draw=7.4ms surf=53 font=120 up=0.7ms
overlay: vs=2.9ms draw=7.2ms surf=53 font=120 up=0.7ms
overlay: vs=2.7ms draw=7.9ms surf=53 font=120 up=0.8ms
overlay: vs=2.8ms draw=7.5ms surf=53 font=120 up=0.7ms
overlay: vs=2.9ms draw=8.1ms surf=57 font=128 up=0.7ms
overlay: vs=2.8ms draw=8.2ms surf=57 font=128 up=0.7ms
overlay: vs=2.7ms draw=8.4ms surf=57 font=128 up=0.7ms
overlay: vs=2.9ms draw=8.0ms surf=57 font=128 up=0.5ms
overlay: vs=2.8ms draw=8.2ms surf=57 font=128 up=0.6ms
overlay: vs=3.0ms draw=8.0ms surf=57 font=128 up=0.6ms
```

## Phase 3

`TuningPanelCache` with computed `panel_signature` and per-row surfaces keyed by
`(kind, slot, display_text, color_state, max_width, line_h)`. Transport and FPS
sit outside the static signature; the incremental compose path patches those rows
each frame.
Full recompose runs when structure, focus, scroll, or any static row content
changes.

```
overlay profiler: on (logging to terminal every 30 frames; latest on panel when open)
overlay: vs=1.8ms draw=2.5ms surf=11 font=30 rcache=0/13 up=0.4ms
overlay: vs=1.4ms draw=1.2ms surf=0 font=2 rcache=0/1 up=0.4ms
overlay: vs=1.3ms draw=1.0ms surf=0 font=2 rcache=0/1 up=0.3ms
overlay: vs=1.7ms draw=1.4ms surf=0 font=2 rcache=0/1 up=0.5ms
overlay: vs=1.7ms draw=1.4ms surf=0 font=2 rcache=0/1 up=0.5ms
overlay: vs=2.0ms draw=2.0ms surf=0 font=2 rcache=0/1 up=0.6ms
overlay: vs=2.1ms draw=2.7ms surf=0 font=2 rcache=0/1 up=0.7ms
overlay: vs=2.1ms draw=2.7ms surf=0 font=2 rcache=0/1 up=0.7ms
overlay: vs=2.1ms draw=2.7ms surf=0 font=2 rcache=0/1 up=0.7ms
overlay: vs=2.1ms draw=2.7ms surf=0 font=2 rcache=0/1 up=0.7ms
overlay: vs=2.0ms draw=2.7ms surf=0 font=2 rcache=0/1 up=0.6ms
overlay: vs=2.1ms draw=2.7ms surf=0 font=2 rcache=0/1 up=0.6ms
overlay: vs=2.3ms draw=2.8ms surf=0 font=2 rcache=0/1 up=0.7ms
overlay: vs=2.4ms draw=4.0ms surf=0 font=2 rcache=0/1 up=0.9ms
overlay: vs=2.2ms draw=3.1ms surf=0 font=2 rcache=0/1 up=0.7ms
overlay: vs=2.4ms draw=3.9ms surf=0 font=2 rcache=0/1 up=0.8ms
overlay: vs=3.1ms draw=4.5ms surf=0 font=2 rcache=0/1 up=0.8ms
overlay: vs=3.0ms draw=4.1ms surf=0 font=2 rcache=0/1 up=0.8ms
overlay: vs=2.9ms draw=9.5ms surf=2 font=7 rcache=40/3 up=0.8ms
overlay: vs=3.0ms draw=9.4ms surf=1 font=5 rcache=41/2 up=0.8ms
overlay: vs=3.3ms draw=5.4ms surf=0 font=2 rcache=0/1 up=0.9ms
overlay: vs=3.0ms draw=4.9ms surf=0 font=2 rcache=0/1 up=0.6ms
overlay: vs=3.0ms draw=10.8ms surf=1 font=6 rcache=41/2 up=0.6ms
overlay: vs=3.1ms draw=5.2ms surf=0 font=2 rcache=0/1 up=0.7ms
overlay: vs=3.0ms draw=5.3ms surf=0 font=2 rcache=0/1 up=0.6ms
overlay: vs=3.3ms draw=5.4ms surf=0 font=2 rcache=0/1 up=1.0ms
overlay: vs=3.3ms draw=5.2ms surf=0 font=2 rcache=0/1 up=1.0ms
overlay: vs=3.2ms draw=5.3ms surf=0 font=2 rcache=0/1 up=1.0ms
overlay: vs=3.3ms draw=5.3ms surf=0 font=2 rcache=0/1 up=1.0ms
```

## Phase 4

Stable-size GPU upload via `OverlayUploadCoordinator` and per-slot textures
(`OverlayTextureSlot.TUNING`, `HELP`, `TIMELINE`). Each overlay frame picks
`skip`, `partial`, or `full` from `UploadPlan.mode`; skip reuses the last
uploaded texture when the content signature is unchanged.

```
overlay profiler: on (logging to terminal every 30 frames; latest on panel when open)
overlay: vs=4.6ms draw=12.2ms surf=38 font=87 rcache=0/43 up=0.6ms ufull=1
overlay: vs=3.0ms draw=3.7ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=1
overlay: vs=2.9ms draw=3.3ms surf=0 font=2 rcache=0/1 up=0.1ms upart=1/2
overlay: vs=2.8ms draw=3.3ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=1
overlay: vs=2.8ms draw=3.3ms surf=0 font=2 rcache=0/1 up=0.1ms upart=1/2
overlay: vs=3.1ms draw=4.2ms surf=0 font=2 rcache=0/1 up=0.3ms upart=1/2
overlay: vs=3.2ms draw=4.0ms surf=0 font=2 rcache=0/1 up=0.1ms upart=1/2
overlay: vs=3.4ms draw=4.4ms surf=0 font=2 rcache=0/1 up=0.1ms upart=1/2
overlay: vs=3.3ms draw=11.6ms surf=1 font=6 rcache=40/3 up=0.7ms ufull=1
overlay: vs=3.9ms draw=5.1ms surf=0 font=2 rcache=0/1 up=0.1ms upart=1/2
overlay: vs=3.3ms draw=4.8ms surf=0 font=2 rcache=0/1 up=0.1ms upart=1/2
overlay: vs=3.4ms draw=11.6ms surf=1 font=7 rcache=40/3 up=0.6ms ufull=1
overlay: vs=3.8ms draw=4.8ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=1
overlay: vs=3.5ms draw=4.8ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=1
overlay: vs=3.5ms draw=4.8ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=1
overlay: vs=3.8ms draw=5.1ms surf=0 font=2 rcache=0/1 up=0.2ms uskip=1 upart=1/4
overlay: vs=3.5ms draw=5.4ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=3
overlay: vs=3.5ms draw=3.9ms surf=0 font=2 rcache=0/1 up=0.2ms uskip=2 upart=1/4
overlay: vs=3.4ms draw=4.0ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=3
overlay: vs=3.4ms draw=3.9ms surf=0 font=2 rcache=0/1 up=0.0ms uskip=3
overlay: vs=3.5ms draw=4.1ms surf=0 font=2 rcache=0/1 up=0.1ms uskip=2 upart=1/2
```

## Phase 5

```

```
