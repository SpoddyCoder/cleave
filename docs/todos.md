# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

## Pipeline

- **Stereo stem audio end-to-end.** Demucs already writes stereo stem WAVs when the source mix is stereo; Cleave currently collapses to mono on load. Preserve stereo through the PCM pipeline: feed libprojectM as stereo where the source has two channels, route stereo in mix-player solo playback, and keep mono sources on the existing mono path (no forced downmix when stereo is available).

