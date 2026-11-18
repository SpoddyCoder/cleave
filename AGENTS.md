# AGENTS.md

Shared agent instructions for Claude Code and Cursor. Path-scoped rules live in `.claude/rules/` (symlinked into `.cursor/rules/`); task skills live in `.claude/skills/` (symlinked into `.cursor/skills/`).

## Cleave

Live Milkdrop/libprojectM editor. Windows app is the product; CLI is for checkout, scripts, and CI.

- Entry: `python -m cleave play`. Commands: `separate`, `play`, `render`, `backup`, `restore`.
- Layers: up to eight, default four. Live at display rate; offline fps from `render.fps`.
- Data: `projects/<slug>/`. Override with `CLEAVE_DATA`. Config: `cleave/config_schema/`. Template: `assets/cleave-viz.yaml`.
- Stem PCM stays native mono/stereo for projectM; mix playback is stereo; analysis is mono.
- Work list: [docs/dev/todos.md](docs/dev/todos.md).
- User-visible change: same-edit bullet under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) (`### Added` / `Changed` / `Fixed` / `Removed`). Skip refactors, tests, and docs. Do not bump `cleave.__version__` or cut a tag unless asked.
- User-visible change: in the same edit, update [README.md](README.md) and [docs/user-guide/README.md](docs/user-guide/README.md) wherever they describe what changed, and add a guide section for a new feature. Fix any statement the change makes wrong (menu paths, key names, labels, defaults). Keep the guide in end-user language ([.claude/rules/documentation-style.md](.claude/rules/documentation-style.md)). If a screenshot in `docs/user-guide/images/` no longer matches the UI, say so in your reply; do not launch the editor to retake it unless asked.

### Locate, then search

Do not glob `**/*.py`, grep the repo root, or spawn an explore subagent to find a home. `docs/dev/plans-completed/` is ignored (`.cursorignore`, and denied in `.claude/settings.json`). Open the files below, then grep only that directory. Tests: `tests/cleave/` mirrors `cleave/`; overlay tests are `tests/cleave/viz/`.

- Panel row: `cleave/viz/row_kinds.py`, `row_specs/<domain>.py` (settings, project, track, overlays, post_fx, pattern_mask, timeline), `row_sections.py`
- Mutation / input: `cleave/viz/layer_mutations.py`, matching `*_controls.py`, `wiring.py`
- Shell draw: `cleave/viz/shell_host.py` (layout, mouse events, context menus), then one module per region: `shell_menu_bar.py`, `shell_transport.py`, `shell_navigator.py`, `shell_inspector.py` (rows), `shell_inspector_values.py` (steppers, choices, colour), `shell_inspector_title.py`, `shell_splitters.py`, `shell_strip.py`; shared helpers in `shell_widgets.py` and `shell_windows.py`
- Draw / type: `overlay_primitives.py`, `theme.py`, `imgui_theme.py`; `row_present_renderers.py` holds inspector value colours and the strip visibility icon
- Live state / YAML: `cleave/viz/session.py`, `cleave/config.py`, `config_schema/<section>.py`, `config_schema/persist.py`
- Frame / GPU: `cleave/viz/layer_pipeline.py`, `frame_finish.py`, `cleave/gl_*.py`, `layer_composite.py`
- Effect: `cleave/effects/registry.py`, `handlers.py`, handler module
- Timeline generate: `cleave/timeline_presets/`
- Timeline strip UI: `cleave/viz/timeline_overlay.py` (compose and caches), then `timeline_strip_state.py` (view state, per-row data), `timeline_strip_layout.py` (geometry, row header buttons), `timeline_strip_static.py` (cached panel), `timeline_strip_live.py` (playhead, flashes, transport, role glyphs), `timeline_strip_flash.py` (blink timing), `timeline_strip_hit.py` (hit testing)
- Context menu: `cleave/viz/context_menu.py` (state), `menu_rows.py` (draw), provider modules (`timeline_context_menu.py`)
- Runtime / window: `cleave/viz/app.py` (runtime, setup, teardown), `live_frame_loop.py` (per-frame loop), `shell_prompts.py` (modal, picker, tap sync on the top layer), `bootstrap.py`, `loading.py`
- CLI / IO: `cleave/cli.py`, `paths.py`, `stems.py`, `separate.py`

## Agent environment

- Python: `/home/fernpa/anaconda3/envs/cleave/bin/python` (same path for `pip`). Never bare `python` / `python3` / `pip`. Never create another env.
- Do not `pip install` unless asked or `requirements.txt` changed in this task. FFmpeg and libprojectM are already installed.
- Tests: `/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py` (pass `-k <name>` for a local change; full suite only when the change is cross-cutting).
- Do not launch the editor for routine verification (needs display and OpenGL).

## Editor first

Windows users run the frozen editor (Start Menu, desktop, drop on `cleave.exe`) with no terminal. CLI remains for checkout, scripts, and CI.

- Design the in-window path first (overlay, centered modal, or loading screen). No native menu bar means no Win32 menu. An ImGui menu bar in the OpenGL window is the intended chrome.
- Share logic outside viz; the editor presents. CLI may print to stderr when a console exists.
- Do not ship a feature whose only progress or error channel is stdout/stderr.
- Long jobs (stem split, weight download, offline render, backup) show named status in the window, plus a progress bar when the work reports fraction. Failures use a modal or panel notification.
- CLI-only is fine for CI, `--help` / `--version`, and headless smoke. That does not replace the editor path for the same job.

Open the window first, then run work with progress into the loading screen. Do not finish Demucs (or similar) in the console, then launch the editor.

## No backward compatibility (default)

Unless the user asks for compatibility or a migration path, implement the current design only.

- Rename identifiers, files, functions, and docs to match; update all references in the same change.
- Remove superseded code, config keys, and docs. No aliases, wrappers, parallel paths, or commented-out old code.
- Do not add "previously" / "formerly" prose, dual naming, or deprecated aliases.

Phrases like "no backward compatibility", "clean break", or "full rename" are confirmation: replace fully without asking again.

Ask first only when a large change would drop existing project YAML or user files and the user has not already waived compatibility.

## Concise responses

Lead with the outcome or answer. Skip preamble, tool narration, and recap unless asked.

Include blockers, trade-offs, commands the user needs, and warnings. Scale length to the task: a few sentences for a simple question; what changed and where for an implementation.

## Versioned releases

`main` holds releases only: every commit on `main` is a tagged release (`vX.Y.Z`, including patch cuts such as `v0.3.1`). All work before a release happens on a pre-release branch (for example `ui-refactor`), which merges into `main` only when a release is cut. Process: [docs/dev/structured-releases.md](docs/dev/structured-releases.md). When asked to cut a release, follow the `cut-release` skill ([.claude/skills/cut-release/SKILL.md](.claude/skills/cut-release/SKILL.md)) (prepare changelog, version, and docs; do not commit, merge, or tag unless the user asks).

- Commit work to the current pre-release branch. Never commit work straight to `main`; if HEAD is `main` and there is no pre-release branch, ask which branch to create. Unreleased bullets: "Cleave" above.
- Do not bump `cleave.__version__`, add a dated `## [X.Y.Z]` section, tag, merge into `main`, or create a GitHub Release unless asked to cut a release. `__version__` is last-shipped until a cut.
- The README version badge moves with every commit. On `main` (and on the cut commit itself) it shows the release, such as `v0.3.0`. On a pre-release branch it shows the dev build the Help > About Cleave dialog reports, minus the hash a commit cannot know about itself, such as `v0.3.0-13 (dev build)`. [scripts/version_badge.py](scripts/version_badge.py) writes it for the commit about to be made; run it immediately before every `git commit` (the [scripts/git-hooks/pre-commit](scripts/git-hooks/pre-commit) hook runs it when `core.hooksPath` is `scripts/git-hooks`). Never hand-edit the badge. `--check` exits 1 if the staged badge is stale.
