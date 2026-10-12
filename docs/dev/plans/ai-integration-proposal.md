# AI integration proposal

Let external agents (Cursor, Claude Desktop, custom scripts) create and refine Cleave visualisations using the same data the editor already relies on: stems, `signals.json`, song markers, timeline presets, layer YAML, and optional preview renders.

Related: [editor-first.mdc](../../../.cursor/rules/editor-first.mdc), [architecture-principles.mdc](../../../.cursor/rules/architecture-principles.mdc), [roadmap.md](../roadmap.md) (AI-assisted visual authoring).

---

## Problem

Today, authoring is manual: pick presets, tune effects, run timeline Apply, scrub the strip. That is appropriate for craft, but slow for exploration ("make something energetic in the chorus that matches the drums") and opaque for newcomers who do not know which knobs matter.

The product already computes rich audio features and encodes visual state in validated YAML. An agent does not need to invent a new format; it needs **curated read APIs** (summaries, not raw 100 Hz series) and **validated write APIs** (patches, compose, render snippets) that stay consistent with the editor and CLI.

---

## Goals

- **Primary:** AI can produce a credible first-pass viz from an existing project (post-`separate` / analyse) without driving the GL window by hand.
- **Secondary:** Power users can iterate from an IDE via MCP; Windows users eventually get an in-editor prompt path (same tool layer, no terminal).
- **Non-goals (initially):** Generating Milkdrop preset source, real-time co-editing at frame rate, or replacing timeline Apply heuristics with unconstrained free-form cue spam.

### Intent

- First-pass viz from an analysed project without manual scrubbing of every layer and cue.
- Validated writes only: patches and `compose_timeline` params, not raw invalid YAML.
- Small model context: bar/section signal summaries, not 100 Hz stem series.
- Visual feedback via short `render` previews when preset names are ambiguous.

### User effort

Run `separate` (or open an existing project). Agent or MCP client proposes changes; user opens `cleave play` to refine. No requirement to use a terminal on Windows once the in-editor path exists.

---

## Design sketch

1. **`cleave/ai_tools`** (outside viz): summarise signals, list presets, get/patch config, wrap timeline compose, preview render.
2. **Phase 0:** Cursor skill + manual summary script on real projects; prove quality before shipping code.
3. **Phase 2:** MCP stdio server over those tools (`describe_signals`, `patch_config`, `compose_timeline`, `render_preview`).
4. **Later:** live editor bridge or in-window BYOK prompt sharing the same tool layer; handle YAML write conflicts with reload or main-thread queue.

Couples naturally with [preset reactivity fingerprints](../roadmap.md#preset-reactivity-fingerprints) (smarter preset lists for agents) and [reprise and auto form](../roadmap.md#reprise-and-auto-form) (richer section context in summaries).

See [Phases](#phases) for Phase 1 (`ai_tools` implementation) and Phase 3/4 breakdown.

---

## What already exists

| Asset | Role for AI |
| --- | --- |
| `signals.json` | Beats, bars, per-stem envelopes and onsets at 100 Hz ([cleave/analyse.py](../../../cleave/analyse.py)) |
| `project.yaml` | Song markers, mix metadata |
| Project viz YAML | Layers, timeline lanes, effects, post-FX, overlays ([assets/cleave-viz.yaml](../../../assets/cleave-viz.yaml), [cleave/config_schema/](../../../cleave/config_schema/)) |
| `compose_timeline` | Deterministic generator from profile, density, bars, markers, signals ([cleave/timeline_presets/arrange.py](../../../cleave/timeline_presets/arrange.py)) |
| Validators | Reject invalid patches before persist ([cleave/config_schema/validators.py](../../../cleave/config_schema/validators.py)) |
| `cleave render` | Offline frames for visual feedback (needs GL; verify headless on CI / WSL) |

The editor path ([cleave/viz/session.py](../../../cleave/viz/session.py), [layer_mutations.py](../../../cleave/viz/layer_mutations.py)) and persist ([config_schema/persist.py](../../../cleave/config_schema/persist.py)) are the source of truth for what "correct" state means.

---

## Architecture sketch

Share logic **outside** viz; adapters are thin.

```
cleave/ai_tools/          # headless: summarise, list presets, patch, compose, preview
    |
    +-- MCP stdio server   # Phase 2: python -m cleave mcp (or dedicated entry)
    +-- Editor bridge      # Phase 4: optional HTTP/queue on main loop
    +-- In-app prompt UI   # Phase 4: BYOK, calls same tools
```

**Signal summarisation** is the highest-leverage design task: per-bar or per-section energy, onset density, which stems dominate, marker-aligned slices. Never dump full 100 Hz arrays into model context.

**Preset choice** is weak from filenames alone. Mitigations: reuse [preset_curation.py](../../../cleave/preset_curation.py), optional tags/thumbnails, or a tight render-preview loop so the model sees frames.

---

## Integration options

| Option | Audience | Effort | Notes |
| --- | --- | --- | --- |
| 1. Cursor skill + YAML/CLI | Developers | Low | Document schema, summary script, validate + short `render`. Proves quality before code. |
| 2. Headless MCP (stdio) | IDE agents | Medium | Tools: `list_projects`, `describe_signals`, `list_presets`, `get_config` / `patch_config`, `compose_timeline`, `render_preview`. |
| 3. Live bridge in editor | Power users | High | Commands queued per frame; mutations via existing viz paths; undo-friendly. |
| 4. In-editor AI panel | Windows product | High | Editor-first; BYOK; no stdout-only progress. |
| 5. User Python generators | Researchers | Medium-high | Agent writes timeline generator plugins; sandbox and trust issues. |

Recommended sequence: **1 -> 2** on `ai_tools`, then choose **3 vs 4** from product priority.

---

## Proposed MCP tool surface (Phase 2 target)

Rough contract; names are illustrative.

- **Project discovery:** resolve `CLEAVE_DATA`, list slugs, load project + viz paths.
- **`describe_signals`:** JSON summary (duration, bpm, sections from markers, per-bar stem activity, climax hints).
- **`list_presets`:** roots, favourites, optional role pools when [preset reactivity fingerprints](../roadmap.md#preset-reactivity-fingerprints) exist.
- **`get_config` / `patch_config`:** read or merge validated partial YAML (layers, timeline, one section at a time).
- **`compose_timeline`:** expose generator params (profile, density, seed) matching Apply in the panel.
- **`render_preview`:** `t0`, `t1`, few frames or a contact sheet; return image paths or bytes for the client.

Transport: MCP over stdio for dev; document frozen-Windows constraints ([win_console.py](../../../cleave/win_console.py), [windows-freeze.md](../windows-freeze.md)) -- may need a console helper exe or HTTP MCP for windowed `cleave.exe`.

---

## Risks and constraints

- **Two writers:** Agent patching YAML while the editor is open requires reload-on-change or routing writes through the live bridge; otherwise last-writer wins.
- **Context size:** Summaries are mandatory; consider caching summaries on disk next to `signals.json` after analyse.
- **Visual grounding:** Without previews, agents guess preset mood; budget short renders in the tool loop.
- **Editor-first:** Long jobs (separate, full render) still show in-window progress for product users; MCP can report progress for headless clients but must not be the only path for shipped UX.
- **Security:** `patch_config` and any plugin path must stay validation-bound; no arbitrary code execution in v1.

---

## Phases

### Phase 0 -- Feasibility (no product code)

- Hand-written or script summariser for one or two real projects.
- Agent (Cursor) edits YAML + runs unit-validators / short render; evaluate chorus/verse contrast and preset fit.
- Exit: go/no-go on Phase 1.

### Phase 1 -- `cleave/ai_tools`

- `summarise_signals(project_dir) -> dict`
- `list_preset_candidates(...)`, `read_config`, `apply_patch` (validators + persist helpers)
- `invoke_compose_timeline(...)` wrapping [arrange.py](../../../cleave/timeline_presets/arrange.py)
- `render_preview(...)` wrapping existing render path with tight defaults
- Unit tests only; no editor launch.

### Phase 2 -- MCP server

- Stdio MCP exposing Phase 1 functions.
- CLI entry documented for Cursor / Claude Desktop config.
- CHANGELOG when user-visible.

### Phase 3 -- Editor integration (pick one or both)

- **Bridge:** optional local port, main-thread mutation queue.
- **Panel:** prompt + status in loading or settings; failures as modal per editor-first rule.

### Phase 4 -- Smarter casting (optional coupling)

- When preset fingerprints and reprise land on the roadmap, extend `list_presets` and compose defaults so agents inherit automatic bed/pulse/lead casting without hand-picking every milk file.

---

## Leave open (not initial work)

- Fine-tuned models choosing preset **source** (`.milk` editing).
- Cloud-hosted Cleave MCP as a service.
- Automatic full-track render and upload; human still reviews in editor.
- Replacing [timeline_presets/](../../../cleave/timeline_presets/) with LLM-only cue placement.

---

## Tests

Per [agent-environment.mdc](../../../.cursor/rules/agent-environment.mdc): unit tests for summarisation, patch validation, and compose wrappers. No routine editor smoke. Preview render tests may be skipped on hosts without GL if already the pattern for render tests.

---

## Success criteria

- From a analysed project, an agent can produce a valid viz YAML and a 10--30 s preview that a human rates as "reasonable first pass" without manual cue editing.
- Same mutations opened in `cleave play` match what the agent wrote (no schema drift).
- MCP tool count stays small; complex edits go through `compose_timeline` and validated patches, not raw text dumps.
