# UI Performance Results
Consistent test case with 2 layers and user-presets. UI gradually opens all leaves of the tree...

## Phase 1
Baseline, just the profiler built in this phase.

```
overlay profiler: on (logging to terminal every 30 frames; latest on panel when open)
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
overlay profiler: on (logging to terminal every 30 frames; latest on panel when open)
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

```

```

## Phase 4

```

```

## Phase 5

```

```
