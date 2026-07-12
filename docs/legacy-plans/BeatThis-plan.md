# Beat This! beat and downbeat plan

Stronger automatic beat and bar grids via [Beat This!](https://github.com/CPJKU/beat_this).

Tracked under [todos.md](todos.md) (Stronger beat and downbeat detection).

## Goal

Replace librosa drum-stem beat tracking with a trained beat and downbeat model so timeline snap lands on the pulse and bar 1 more reliably. Existing projects re-run analyse (rewrite `signals.json`); Demucs stems stay. No backward compatibility.

## Choice: Beat This!

Prefer [Beat This!](https://github.com/CPJKU/beat_this) (ISMIR 2024, CPJKU) over [madmom](https://github.com/CPJKU/madmom).

- Current SOTA beat **and** native downbeat output (`File2Beats` → beats, downbeats).
- PyTorch stack fits the cleave env (already used for Demucs).
- Installs on modern Python / numpy; madmom does not fit cleanly (legacy PyPI, numpy constraints).
- Optional madmom DBN postprocessing is not needed for v1.

## Implemented

- Analyse: [cleave/extract.py](../cleave/extract.py) `extract_beats_downbeats` runs Beat This! on a configurable source (default mix; `--beat-detection-stem` / `-bds`).
- Persist: `signals.json` version 3 with `beat_times` and `downbeat_times` ([cleave/analyse.py](../cleave/analyse.py), [cleave/signals.py](../cleave/signals.py)). Non-v3 is stale for `separate.signals_complete`.
- Wiring: [cleave/viz/wiring.py](../cleave/viz/wiring.py) sets `bar_times` from `signals.downbeat_times`.
- Bar snap nudge: [cleave/timeline.py](../cleave/timeline.py) `shift_bars_by_beats` shifts each downbeat by N beats on the beat grid; [cleave/viz/timeline_snap_controls.py](../cleave/viz/timeline_snap_controls.py) offers `+0`/`+1`/`+2`/`+3`.

Re-analyse: `cleave separate <slug>` or `cleave play` (stems reused).

## Separation of concerns

Beat This! owns the **timeline grid only**. Leave onset envelopes alone for cleave effects.

| Consumer | Need | Source |
| --- | --- | --- |
| Timeline snap | Sparse event times (beat / bar 1) | `beat_times` + `downbeat_times` from Beat This! |
| Effects (`pulse` / `flash` / `grit`) | Dense continuous energy | librosa `onset_strength` (drums / full_mix) at 100 Hz |

Effects sample normalized envelopes every frame. Beat This! outputs event times, not a general transient driver.

```
Demucs stems + mix
        |
        +-- Beat This! on mix --> beat_times, downbeat_times   (timeline / future MIDI)
        |
        +-- librosa (etc.) -----> onset_strength, rms, ...    (effect drivers)
                |
                v
           signals.json
                |
        +-------+--------+
   timeline snap      effects runtime
   (discrete grids)   (continuous curves)
```

## Out of scope / known limits

- Quiet intros, drum-sparse sections, half-time and double-time flips, unusual meters: better models help; they do not remove the need for later sparse song anchors ([todos.md](todos.md)).
- New effect drivers keyed to beats (e.g. explicit beat flash): possible later as a separate roster entry, not part of this swap.
- Manual dense cueing: not the goal; automation first.
