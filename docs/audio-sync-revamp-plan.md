# Audio sync revamp plan

Make timeline sync to audio consistent and repeatable across sessions and machines. Song markers, timeline cues, and offline render must all align to the same true, file-relative audio position. Measurable buffer latency is automatic; beat snap covers most wireless residual; an optional machine-local delay compensates free-form placement and live monitoring when the user needs it.

Related: [song-markers.md](song-markers.md), [timeline-idea.md](timeline-idea.md), [architecture-principles](../.cursor/rules/architecture-principles.mdc), [project-context](../.cursor/rules/project-context.mdc).

---

## Problem

Markers placed in one session drift by up to a second or two after closing and reopening the project.

Root cause: the live clock reports the wrong position. [cleave/viz/mix_player.py](../cleave/viz/mix_player.py) sets `_samples_played` inside the SDL audio callback and `current_sec()` returns `_samples_played / sample_rate`. That value is:

- The decode or queue position, ahead of what is actually audible by the full output latency `L` (SDL buffer plus OS mixer plus Bluetooth codec delay).
- A staircase that only updates about every 93ms (one 4096-frame chunk), with no interpolation.

Both marker placement (`drop_song_marker` in [cleave/viz/controls.py](../cleave/viz/controls.py)) and the live playhead ([cleave/viz/app.py](../cleave/viz/app.py)) read this same biased clock, so placement and review cancel out within one session (they share the same `L`). Across sessions the drift equals `L1 - L2`, the difference in output latency. Bluetooth or a changed output device makes that difference large, which matches the observed one to two seconds.

Render ([cleave/viz/render.py](../cleave/viz/render.py)) is already sample-accurate: it evaluates cues at `t = frame / fps` and muxes source audio on the same file timeline. It only looks off because the stored marker time carries the live latency `L`. So the fix is entirely on the authoring and live side: store true, file-relative times and render is tight automatically.

---

## Principles

Split the clock into two concerns and never mix them:

- Authoring truth: the true, file-relative audio position. This is what gets stored and what render consumes. Deterministic, device-independent; never stores a latency field on the cue.
- Live audible clock: the estimate of what the user is hearing, used for the playhead, live cue comparison, and tap capture. Corrected by measurable buffer latency (Phase 2) plus an optional machine-local residual delay (Phase 5). Beat snap (Phase 3) snaps that capture onto the offline grid when enabled.

Confirmed decisions:

- The user uses Bluetooth or varying output devices, so true acoustic latency is not measurable in software.
- Hybrid placement: audible clock plus an optional beat or bar snap toggle (default beat).
- Stored values are plain file times. Latency compensation happens in the live clock at write and live read, not by rewriting or tagging saved cues.
- Phase 5 residual delay, when non-zero, is factored into new placements and live monitoring. Changing it never moves already-saved markers or cues. Render never applies it.
- No migration. Existing projects will be re-recorded.

---

## Phase 1 - Interpolated, latency-aware transport clock

Replace the staircase decode clock with a smooth, file-relative clock.

- Add a pure, SDL-free `TransportClock` in a new module [cleave/viz/transport_clock.py](../cleave/viz/transport_clock.py). It holds `anchor_frame`, `anchor_wall_time`, `sample_rate`, `latency_frames`, `paused`, and `total_frames`, and computes position by interpolating with `time.perf_counter()` between anchors. Clamp so it never overshoots past the next expected callback or `total_frames`. Pure math, fully unit-testable, in line with the typed and testable architecture rules.
- Rework [cleave/viz/mix_player.py](../cleave/viz/mix_player.py) to update the clock anchor inside the audio callback (record `_samples_played` and `perf_counter()` under the lock) and to re-anchor exactly on `seek` and `pause`.
- Expose two positions on `MixPlayer`:
  - `file_position_sec()`: interpolated consumed position, the authoring truth reference.
  - `audible_position_sec()`: `file_position_sec()` minus `latency_frames / sample_rate`, for live display and tap capture.
- Route `current_sec()` in [cleave/viz/playback.py](../cleave/viz/playback.py) to `audible_position_sec()`, so `drop_song_marker` and the live playhead both use one source of truth.

Outcome: no staircase quantisation, no decode-versus-audible confusion, exact seek and pause, and a single time source.

---

## Phase 2 - Automatic latency estimation (zero config)

- On device open, read the SDL obtained buffer size or device period and set `latency_frames` from it, falling back to `chunksize` if the wrapper does not expose it. Optionally add a small conservative platform constant.
- This is automatic and portable for the measurable part (SDL and driver buffer, tens of milliseconds).
- Known limit: OS mixer, Bluetooth codec, and Bluetooth input delay are not reportable in software, so on wireless setups a free-form tap can still carry residual error. Phase 3 removes that residual when snap is on. Phase 5 lets the user dial in the remainder for free-form placement and live monitoring.
- No user-facing offset is required when snap is on; free-form on wireless may need Phase 5.

---

## Phase 3 - Hybrid beat and onset snapping (exactness backbone)

[signals.json](song-markers.md) already carries sample-accurate `beat_times` and `downbeat_times` (offline, latency-free), and snap primitives exist (`_nearest_beat_index`, `snap_lane_to_beats` in [cleave/timeline.py](../cleave/timeline.py)).

- Add a snap toggle for song-marker placement, mirroring the existing timeline snap UI in [cleave/viz/timeline_snap_controls.py](../cleave/viz/timeline_snap_controls.py). When on, `drop_song_marker` snaps the captured audible time to the nearest beat or downbeat before `place_marker` (see [cleave/song_markers.py](../cleave/song_markers.py)).
- Apply the same snap to live timeline cue writes and record stop in [cleave/viz/timeline_controls.py](../cleave/viz/timeline_controls.py) so recorded cues are equally exact.
- Because snapping resolves to offline grid times, snapped markers and cues are exact file time, so render is perfect and reproducible on any device including Bluetooth. This is the reliable default path for wireless setups. Free-form placement (snap off) is as good as the audible clock (Phase 2 plus any Phase 5 residual delay).
- Persist the toggle through the descriptor system in [cleave/config_schema.py](../cleave/config_schema.py), with session state in [cleave/viz/session.py](../cleave/viz/session.py) and a panel row registered via the manifest ([cleave/viz/row_fields.py](../cleave/viz/row_fields.py), [cleave/viz/row_sections.py](../cleave/viz/row_sections.py), [cleave/viz/tuning_view_state.py](../cleave/viz/tuning_view_state.py)).
- Suggested default: snap on to nearest beat, given the Bluetooth reality.

---

## Phase 4 - Render verification (no clock change)

- Render needs no clock change; it already uses the file timeline.
- Add a regression test: a marker or cue at a known beat time `t` drives a transition at frame `round(t * fps)` and aligns with the muxed audio (`t = frame / fps` and ffmpeg `-ss` and `-t` on the same file timeline in [cleave/viz/render.py](../cleave/viz/render.py)).
- Purpose: lock the guarantee so future edits cannot reintroduce a render offset.

---

## Phase 5 - Machine-local residual delay and tap to sync

Optional compensation for unmeasurable residual delay (Bluetooth headphones, OS mixer, Bluetooth keyboard, and similar). It adjusts the **live audible clock** used for playhead, live cue comparison, and new marker/cue capture. It is not a per-cue or per-project field.

### Model

- Phase 2 covers measurable SDL/driver buffer latency.
- This control covers the remainder the OS cannot report. One number is "total residual for this setup," not headphones alone.
- Apply the offset in the audible clock:
  - **Write:** new song markers and timeline cues capture `audible_position` (buffer latency plus residual delay), then optional snap. What is stored is a plain file time.
  - **Live read:** compare saved file times to the same audible clock so cues fire when the user hears that file time.
  - **Render:** always uses saved file times on the file timeline. Never applies this offset.
- Changing the offset never rewrites already-saved markers or cues. Old times keep playing at the file positions they were recorded with. Only new placements use the new value.
- Tap to sync sets this live offset only; it must not batch-shift existing markers or cues.

### UX

- Optional, default 0. Calibrate before free-form authoring when wireless gear needs it; snap-on remains the robust default.
- Machine-scoped, not project-scoped. Residual delay is a property of the current devices, not the song, so it must not live in per-project [cleave-viz.yaml](../cleave-viz.yaml). It persists in `~/.config/cleave/config.yaml` under `editor.residual_delay_ms`.
- Help copy: "Wireless delay the OS cannot report. Affects live playhead and new placements only. Saved markers, cues, and renders do not move when you change this. Typical Bluetooth output is 150 to 300ms; some devices exceed 500ms. Bluetooth keyboards add input lag too. Or use Sync by ear."
- If the value changes while a project already has markers or cues, a short note is enough: existing times unchanged; re-record if placement used a different delay.
- Calibrate to the sound (or click track), not to existing free-form marks that may have been captured under a wrong delay.

### Gotchas

- Free-form takes recorded under the wrong delay stay wrong until re-tapped; fixing the knob later does not heal history.
- Mixing free-form takes under different delay values in one project yields inconsistent file times; render will honour that inconsistency.
- Snap-on placements are usually unaffected by residual delay; prefer snap when the beat grid is trusted.
- Another machine needs its own delay for monitoring and new taps; already-saved file times remain valid for render everywhere.

### Tap to sync

Cleave plays a fixed 140 BPM metronome only (song and visuals pause): a loud downbeat on beat 1 of each bar and quieter quarter-note clicks on beats 2 to 4. The user taps Space on each loud beat (beat 1); other panels hide while detection runs. A centered progress panel shows streak (0 to 4), spread, and estimate. When four consecutive loud-beat tap deltas are consistent (within 30 ms), calibration pauses, panels restore, and a confirm modal proposes the detected delay. Apply persists the offset; Cancel exits without changing it. Esc cancels during tapping. No song beat grid is required. Manual override remains available for users who know their device.

Typical A2DP output latency for reference:

- SBC: about 150 to 250ms (commonly about 200ms)
- AAC: about 150 to 200ms
- aptX: about 70 to 150ms; aptX Low Latency: about 40ms
- Cheap or variable Bluetooth: can exceed 300 to 500ms

---

## Testing plan

- `TransportClock` units: monotonic, no overshoot beyond bounds, exact after seek, pause, and resume, latency subtraction, determinism (same consumed-sample sequence gives the same output regardless of device).
- Marker and cue snapping units: nearest beat and nearest downbeat, tie behaviour, snap-off passthrough.
- Render alignment test (Phase 4).
- Residual delay units: offset is included in the audible clock for display and new capture; changing it does not mutate existing saved times; render paths ignore it; tap to sync inference from tap timestamps.
- Update existing tests in [tests/cleave/test_song_markers.py](../tests/cleave/test_song_markers.py) and the timeline and overlay tests for the new placement path.
- Run headless with [tests/run_unit_tests.py](../tests/run_unit_tests.py); the clock, snapping, and offset logic need no editor or GL.

---

## Files in scope

- New: [cleave/viz/transport_clock.py](../cleave/viz/transport_clock.py)
- Clock and playback: [cleave/viz/mix_player.py](../cleave/viz/mix_player.py), [cleave/viz/playback.py](../cleave/viz/playback.py)
- Placement and cues: [cleave/viz/controls.py](../cleave/viz/controls.py), [cleave/viz/timeline_controls.py](../cleave/viz/timeline_controls.py), [cleave/song_markers.py](../cleave/song_markers.py), [cleave/timeline.py](../cleave/timeline.py)
- Snap toggle and residual-delay UI and config: [cleave/config_schema.py](../cleave/config_schema.py), [cleave/viz/session.py](../cleave/viz/session.py), [cleave/viz/row_fields.py](../cleave/viz/row_fields.py), [cleave/viz/row_sections.py](../cleave/viz/row_sections.py), [cleave/viz/tuning_view_state.py](../cleave/viz/tuning_view_state.py), [cleave/viz/timeline_snap_controls.py](../cleave/viz/timeline_snap_controls.py), machine-local `editor.residual_delay_ms` in `~/.config/cleave/config.yaml`
- Render test only: [cleave/viz/render.py](../cleave/viz/render.py)

---

## Limitations

- With Phase 5 at 0, live playhead and free-form taps can still lead or lag the sound by the unmeasurable residual. Snap-on placements and render of already-correct file times stay exact.
- Changing the residual delay does not migrate old free-form times; recovery is re-record or replace.
- Fully automatic true acoustic latency needs mic loopback calibration, which is out of scope unless requested later.
- No migration. Existing projects re-recorded.

---

## Open decisions

- Default snap target: beat or bar (implementation currently defaults to beat).
- Whether the snap toggle defaults on (implementation currently defaults to beat snap).

Machine-local residual delay persists in `~/.config/cleave/config.yaml` under `editor.residual_delay_ms` (default 0).

---

## Related consideration (out of scope)

The visualizer audio-reactivity feed advances PCM by wall-clock `dt` (`samples_for_dt` in [cleave/viz/app.py](../cleave/viz/app.py)), independent of this transport clock. It does not affect marker or cue sync. If reactivity drift appears on long songs, re-anchor it to the same clock.