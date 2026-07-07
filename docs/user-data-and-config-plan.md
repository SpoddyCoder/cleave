# User data and config plan

High-level plan for separating application install, user preferences, and per-track creative config. Intended as direction for future work; backward compatibility is not required.

Related: [cleave/paths.py](../cleave/paths.py), [cleave/config.py](../cleave/config.py), [architecture principles](../.cursor/rules/architecture-principles.mdc).

---

## Problem

Cleave today mixes three concerns in one checkout:

1. **Application** (code, bundled assets, preset pack submodules)
2. **User state** (projects, quarantined presets, editor preferences, custom data roots)
3. **Per-track creative config** (layers, timeline, render overlay, effects)

`projects/` under the repo root (gitignored) and planned preset quarantine under [assets/milkdrop-presets/](../assets/milkdrop-presets/) both put user-mutable data beside the install tree. That is workable for local dev but is an anti-pattern for re-cloning, zip installs, and "delete the app folder without losing my work."

The goal is a layout where the install is read-only and all durable user data lives outside it by default.

---

## Current state (partial hooks)

| Mechanism | Location | Role today |
| --- | --- | --- |
| `data_dir()` | [cleave/paths.py](../cleave/paths.py) | `CLEAVE_DATA` override, else **repo root** |
| `projects_dir()` | [cleave/paths.py](../cleave/paths.py) | `data_dir() / "projects"` |
| `GLOBAL_CONFIG_PATH` | [cleave/config.py](../cleave/config.py) | `~/.config/cleave/cleave-viz.yaml` as fallback in `find_config_path` |
| `DEFAULT_PRESET_ROOT` | [cleave/config_schema.py](../cleave/config_schema.py) | `~/.local/share/cleave/presets` when `paths` omitted |
| Repo template | [cleave-viz.yaml](../cleave-viz.yaml) | Example project config; copied into new projects |

Gaps:

- Default `data_dir()` is still the repo root, so new users get `projects/` in the checkout unless they set `CLEAVE_DATA`.
- `GLOBAL_CONFIG_PATH` uses the same filename and shape as project config; there is no layered merge (user defaults + project overrides).
- Editor settings (`preview_quality`, `ui_width`, `ui_width_mode`, `ui_fade`) live under `visualizer:` in project yaml and are persisted with the track via [persisted_session_payload](../cleave/config_schema.py).
- Preset quarantine was sketched under shipped assets; quarantine is user curation of a preset library, not app content.

---

## Target layout

Default to XDG-style paths on Linux. Map to platform equivalents when Cleave ships beyond WSL/Linux (macOS Application Support, Windows `%APPDATA%`).

```
~/.config/cleave/config.yaml       # user preferences and default paths
~/.local/share/cleave/             # CLEAVE_DATA default (create on first use)
  projects/<slug>/                 # per-track data (see below)
  presets/                         # user preset packs (or symlink elsewhere)
  quarantine/                      # quarantined .milk files (see Quarantine)
```

Keep `CLEAVE_DATA` as an override for power users and optional portable mode (e.g. `CLEAVE_DATA=./data` next to a dev checkout).

### Per-project directory

Unchanged conceptually; only the root moves out of the repo:

```
projects/<slug>/
  project.yaml          # manifest (audio, stems, signals)
  signals.json
  stems/
  cleave-viz.yaml       # track creative config
  mix audio (as today)
```

---

## Three buckets

### 1. Application (read-only)

Ships with Cleave. Never written at runtime.

- Python package, shaders, fonts
- Default config template ([cleave-viz.yaml](../cleave-viz.yaml))
- Bundled preset submodules under [assets/milkdrop-presets/](../assets/milkdrop-presets/) for tests, golden scan, and optional seed content

Runtime preset browsing should use the user's preset tree (`paths.preset_root`), not mutate files under `assets/`.

### 2. User / machine

Persists across re-clone and app updates.

| Item | Notes |
| --- | --- |
| Editor settings | `preview_quality`, `ui_width`, `ui_width_mode`, `ui_fade` |
| Default `paths.preset_root` | Fallback when project yaml omits `paths` |
| Default `projects_dir` | Optional; normally `data_dir() / "projects"` |
| Preset quarantine | Moves presets out of rotation (see Quarantine) |
| Future | Recent projects, window geometry, last-opened config |

Stored in `~/.config/cleave/config.yaml` (name can stay `config.yaml` even if project files remain `cleave-viz.yaml`).

### 3. Project / track

Portable creative artifact tied to one song.

| Item | Notes |
| --- | --- |
| `layers`, `layer_z_order`, `timeline` | Stem mapping, presets, effects, cues |
| `render` | Output size, fps, post-fx, overlay copy and styling |
| `visualizer` (subset) | Track-relevant live window size, beat sensitivity defaults, etc. |
| `paths` (optional) | Per-track override when a project needs a different preset pack |

Not stored in the repo checkout by default.

---

## Config layering

Replace single-file fallback with explicit merge order:

1. **Code defaults** ([cleave/config_schema.py](../cleave/config_schema.py))
2. **User config** (`~/.config/cleave/config.yaml`)
3. **Project config** (`projects/<slug>/cleave-viz.yaml`) — wins for creative fields

Implementation sketch:

- Split parse/persist descriptors into **user** vs **project** sections (or tag existing `VISUALIZER_FIELDS` entries).
- `load_config(project_dir)` loads user file first, then overlays project file into a single `CleaveConfig` used at runtime.
- `persisted_session_payload` writes only project-owned fields; editor settings mutations update user config (or an in-memory user layer flushed on quit).

### Field ownership (initial split)

| User config | Project config |
| --- | --- |
| `visualizer.preview_quality` | `layers`, `layer_z_order` |
| `visualizer.ui_width_mode` | `timeline` |
| `visualizer.ui_width` | `render` (including overlay and post-fx) |
| `visualizer.ui_fade` | `visualizer.name`, `width`, `height`, `upscale`, `beat_sensitivity` |
| `paths.preset_root` (default) | `paths` (optional per-track override) |
| `paths.texture_paths` (default) | Per-layer `preset`, effects, switching |

Revisit `visualizer.width` / `height`: treat as project if tied to export intent, user if treated as "my monitor preference." Default: project for anything that affects offline render parity.

---

## Preset quarantine

**Intent:** hotkey moves a preset out of the active directory into quarantine so projectM rotation and browsing skip it (too dark, broken, etc.).

**Do not** implement quarantine under [assets/milkdrop-presets/](../assets/milkdrop-presets/). That tree is shipped app content.

**Recommended location:**

```
~/.local/share/cleave/quarantine/<preset-root-id>/<relative-path>.milk
```

or a hidden sibling of the preset root:

```
<preset_root>/.cleave-quarantine/...
```

Pick one scheme and document it. Centralized under `data_dir()` keeps all Cleave-side mutations in one place; sibling under `preset_root` keeps quarantine visually tied to the pack the user is browsing.

**Behavior:**

- Move (or copy + delete) the `.milk` file; update playlist state if the quarantined file was current.
- Exclude quarantine paths from `cleave scan` targets the same way live rotation excludes them.
- Optional later: metadata file (original path, timestamp) for restore / un-quarantine.

---

## Distribution (zip / install)

Read-only install directory plus writable user dirs on first run:

1. Create `~/.config/cleave/config.yaml` from a minimal user template if missing.
2. Create `~/.local/share/cleave/projects/` (and presets dir if bundled seed is offered).
3. First-run or CLI prompts: "Where are your Milkdrop presets?" (default `~/.local/share/cleave/presets`).

Bundled submodule packs remain useful for CI and `cleave scan-golden`, not as the default runtime preset root.

Dev checkout: document `CLEAVE_DATA=./data` for co-located test projects; do not default the main code path to repo-root `projects/`.

---

## Implementation phases

Ordered for incremental delivery; each phase can land independently.

### Phase 1: Data root default

- Change `data_dir()` default from `repo_root()` to `~/.local/share/cleave`.
- Create directory on first use (`projects/`, etc.).
- Update README and [.gitignore](../.gitignore) (repo `projects/` becomes dev-only via explicit `CLEAVE_DATA`).
- Migrate or ignore existing repo-root test projects (no compatibility layer required).

### Phase 2: User config file

- Introduce `~/.config/cleave/config.yaml` with a dedicated schema section (e.g. `user:` or top-level editor fields).
- Implement merge in `load_config`.
- Stop persisting editor settings from [cleave/viz/settings_controls.py](../cleave/viz/settings_controls.py) into project yaml.
- Trim editor fields from project template and golden project configs.

### Phase 3: Quarantine

- Add `quarantine_dir()` (or per-root helper) in [cleave/paths.py](../cleave/paths.py).
- Hotkey handler in live tuning; playlist / scan exclusion.
- Tests for move + rotation skip (no GL).

### Phase 4: Polish

- CLI `cleave doctor` or startup log: print resolved `data_dir`, user config path, preset root.
- Optional: `projects_dir` key in user config.
- Platform path helpers when targeting macOS/Windows.

---

## Non-goals (for this plan)

- Migrating existing yaml from old layouts (breaking change is acceptable).
- Storing projects inside the git repo by default.
- Quarantine as git-tracked app assets.
- Cloud sync or multi-machine merge of user config.

---

## Open questions

- **Quarantine scope:** one global quarantine vs one per `preset_root`?
- **`visualizer.width` / `height`:** user preference vs per-track export setting?
- **Config filename:** keep `cleave-viz.yaml` for projects only and use `config.yaml` for user file (recommended), or unify names?
- **Portable mode:** first-class CLI flag vs env-only `CLEAVE_DATA`?

Resolve these when implementing Phase 2–3; defaults above are the recommended starting point.
