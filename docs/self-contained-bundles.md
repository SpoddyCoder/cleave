# Self-contained project bundles

`cleave backup` archives the full project directory (mix, stems, configs, `presets/`, `textures/`, renders, and so on) into a `.cleave-tar.gz` file. `cleave restore` unpacks it back into `projects/<slug>/`.

Preset switching lists are project-local: add, populate, and timeline repopulate copy `.milk` files into `presets/` and playback loads those paths. After restore, the switching sequence itself does not depend on the original preset packs still being installed.

Four edge cases still matter for portability.

---

## 1. Layer browse anchors point at `preset_root`

Each layer has a `preset:` field in `cleave-viz.yaml` (for example `presets-cream-of-the-crop/Dancer/Aurora/`). It resolves against `paths.preset_root`, not the project directory.

On `play` and `render`, [cleave/preset_playlist.py](../cleave/preset_playlist.py) `scan_preset_playlist` runs on that anchor before switching applies. If the pack is missing, Cleave still opens the project with an empty browse playlist for that layer and shows a panel toast (`Missing preset anchor(s): ...`). Offline `render` prints the same message as a stderr warning. Switching lists under `presets/` keep working when switching is on.

## 2. Switching off uses the browse preset, not the list

When `preset_switching` is `off`, playback uses the layer anchor under `preset_root`, not entries in `preset_switching_list` / `presets/`.

Only layers with switching on (`timer`, `timeline`, or `projectm`) load from the ordered list. A restored project with switching disabled still needs the browse packs.

## 3. Textures are bundled on save

Milkdrop presets often reference image assets. Cleave resolves those via `paths.texture_paths` (default `~/.local/share/cleave/textures`), which lives outside the project.

On config save, [cleave/milk_textures.py](../cleave/milk_textures.py) parses `.milk` files under `presets/`, copies only referenced images into `projects/<slug>/textures/`, and removes orphans. At load time the project `textures/` directory is prepended to the search paths so bundled copies take priority.

If a preset references a texture that cannot be resolved at save time, the existing project copy is kept when present. Textures added only through manual edits outside save are not synced until the next save.

## 4. Role pools are populate-time sources only

Cue `role` fields and `preset_root/roles/<role>/` pools feed **populate** and timeline **re-populate preset lists** ([cleave/viz/preset_list_populate.py](../cleave/viz/preset_list_populate.py)). Picks are copied into `presets/` before playback.

At runtime, timeline switching indexes `preset_switching_list`, not the role pools. Restored projects do not need role directories unless you populate or repopulate again. Cast (**c** on a preset file) still writes to `preset_root/roles/`, not `presets/`.

---

## Practical checklist after restore

| Need | In the bundle? | Notes |
| --- | --- | --- |
| Audio, stems, signals, configs | Yes | Full project tree |
| Preset switching list (`.milk`) | Yes | Under `presets/` when populated via the editor |
| Referenced textures | Yes | Under `textures/` after a config save |
| Layer `preset:` browse anchors | No | Missing packs: empty browse + toast/warn; edit YAML or install packs |
| Role pools | Only for repopulate | Not required for playback of an existing list |

Related: [README.md](../README.md) (backup/restore commands, project layout), [cleave/archive.py](../cleave/archive.py).
