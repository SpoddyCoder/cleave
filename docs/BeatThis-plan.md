# Beat This! beat and downbeat plan

High-level plan for stronger automatic beat and bar grids. Detail and implementation in a later session.

Tracked as must-do in [todos.md](todos.md) (Stronger beat and downbeat detection).

## Goal

Replace librosa drum-stem beat tracking with a trained beat and downbeat model so timeline snap lands on the pulse and bar 1 more reliably. Existing projects re-run analyse (rewrite `signals.json`); Demucs stems stay. No backward compatibility.

## Choice: Beat This!

Prefer [Beat This!](https://github.com/CPJKU/beat_this) (ISMIR 2024, CPJKU) over [madmom](https://github.com/CPJKU/madmom).

- Current SOTA beat **and** native downbeat output (`File2Beats` → beats, downbeats).
- PyTorch stack fits the cleave env (already used for Demucs).
- Installs on modern Python / numpy; madmom does not fit cleanly (legacy PyPI, numpy constraints).
- Optional madmom DBN postprocessing is not needed for v1.

Clean swapover: implement on a branch; compare by checking out the other branch and re-running analyse.

## Current state

- Analyse: [cleave/extract.py](../cleave/extract.py) `extract_drums_beats` uses librosa with a per-frame tempo curve on the **drum stem**.
- Persist: `beat_times` only in `signals.json` ([cleave/analyse.py](../cleave/analyse.py), [cleave/signals.py](../cleave/signals.py)).
- Bars: not detected. [cleave/viz/wiring.py](../cleave/viz/wiring.py) invents 4/4 phase by maximizing drum `onset_strength` at every Nth beat ([cleave/timeline.py](../cleave/timeline.py) `bar_times_from_beats`).
- Timeline snap uses those grids ([cleave/viz/timeline_snap_controls.py](../cleave/viz/timeline_snap_controls.py)).

## Separation of concerns

Beat This! owns the **timeline grid only**. Leave onset envelopes alone for cleave effects.

| Consumer | Need | Source today | After swap |
| --- | --- | --- | --- |
| Timeline snap | Sparse event times (beat / bar 1) | `beat_times` + onset-derived bars | `beat_times` + persisted downbeats from Beat This! |
| Effects (`pulse` / `flash` / `grit`) | Dense continuous energy | librosa `onset_strength` (drums / full_mix) at 100 Hz | Unchanged |

Effects sample normalized envelopes every frame. Beat This! outputs event times (and beat/downbeat logits), not a general transient driver. Do not replace `onset_strength` with Beat This! output.

The only current coupling is the bar-phase heuristic that samples onset at beat times. With real downbeats persisted, drop that bridge. Analyse still writes one `signals.json`; two field families, two consumers.

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

## Recommended approach (v1)

1. **Spike** on a few real projects: Beat This! on mix vs drums vs current librosa; listen for snap-to-kick and bar-1 feel; note CPU/GPU analyse time.
2. **Replace** `extract_drums_beats` with Beat This! in analyse. Default input: **mix** (models train on full music; drum-only can hurt sparse intros).
3. **Persist** both grids in `signals.json` (bump version): keep `beat_times`, add `downbeat_times` (or equivalent). Load on `Signals`; wiring/snap use persisted bars, not runtime onset phase.
4. **Dependency**: add `beat-this` (and its small torch extras). No madmom. Analyse stays offline/heavy; live play only reads JSON.
5. **Ship bar accuracy first.** Do not solve half-time flips, unusual meters, or sparse song anchors in this pass.

## Out of scope / known limits

- Quiet intros, drum-sparse sections, half-time and double-time flips, unusual meters: better models help; they do not remove the need for later sparse song anchors ([todos.md](todos.md)).
- New effect drivers keyed to beats (e.g. explicit beat flash): possible later as a separate roster entry, not part of this swap.
- Manual dense cueing: not the goal; automation first.

## Next session

Dig into API wiring, `signals.json` schema bump, dependency pinning, tests, and the concrete extract/analyse/signals/wiring change set.
