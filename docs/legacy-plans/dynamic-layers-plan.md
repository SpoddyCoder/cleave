# Dynamic layers plan

**Status:** All phases complete as of June 2026.

## Overview

Remove the hardcoded four-layer ceiling. Layers become first-class runtime objects that can
be added and removed through the live tuning UI. The default starting config remains four
layers but the schema accepts 1-8. All existing layer semantics (expand/collapse, show/hide,
solo, lock, effects, timeline, preset browsing, stem, blend, opacity, beat sensitivity,
z-order reorder, save/snapshot) carry over unchanged to dynamically added layers.

The implementation is split into eight phases that can be developed and reviewed incrementally.

---

## Decisions

| Question | Answer |
|---|---|
| Default stem for new layer | `full_mix` |
| Default blend mode | `black-key` |
| Default dimensions | 1280x720 |
| Default preset | Random from preset root |
| Max layers | 8 |
| Min layers | 1 |
| Timeline cues for deleted layer | Discarded silently |
| GL rebuild on add/remove | Acceptable (brief freeze) |
| Timeline num keys | 1-8, including numpad 1-8 |
| New layer z-order position | Appended (bottom of compositor stack; user reorders in move mode) |

---

## Phase 1 — Config schema

**Files:** `cleave/config_schema.py`, `cleave/config.py`

### 1.1 Replace the `LAYER_SLOTS` constant

- [x]

Remove:
```python
LAYER_SLOTS: tuple[str, ...] = ("layer_1", "layer_2", "layer_3", "layer_4")
DEFAULT_LAYER_Z_ORDER = LAYER_SLOTS
DEFAULT_STEM_FOR_SLOT: dict[str, StemSource] = { ... }
```

Add:
```python
MAX_LAYER_COUNT = 8
MIN_LAYER_COUNT = 1
DEFAULT_LAYER_SLOTS = ("layer_1", "layer_2", "layer_3", "layer_4")
DEFAULT_LAYER_Z_ORDER: list[str] = list(DEFAULT_LAYER_SLOTS)
DEFAULT_NEW_LAYER_STEM: StemSource = "full_mix"

def next_layer_slot(existing_slots: list[str]) -> str:
    """Return the lowest unused layer_N slot name."""
    used = set(existing_slots)
    for i in range(1, MAX_LAYER_COUNT + 1):
        candidate = f"layer_{i}"
        if candidate not in used:
            return candidate
    raise ValueError(f"Maximum {MAX_LAYER_COUNT} layers already present")

def new_layer_config(slot: str, preset: Path, preset_root: Path) -> LayerConfig:
    """Factory for a fresh LayerConfig with new-layer defaults."""
    from cleave.config import LayerConfig
    w, h = LAYER_DEFAULT_SIZE[DEFAULT_NEW_LAYER_STEM]
    return LayerConfig(
        preset=preset,
        stem=DEFAULT_NEW_LAYER_STEM,
        enabled=True,
        opacity=1.0,
        width=w,
        height=h,
        blend_mode=DEFAULT_BLEND_MODE[DEFAULT_NEW_LAYER_STEM],
        locked=False,
    )
```

`DEFAULT_STEM_FOR_SLOT` had no live runtime use after variable-stems; remove it. Any
remaining reference (only `wiring.py` stub) is updated in Phase 3.

### 1.2 Relax `parse_layers_section`

- [x]

- Accept any number of `layer_N` keys where 1 ≤ N ≤ 8, so count in range [1, 8].
- Reject keys not matching `layer_\d+`, N out of [1, 8], or duplicate N.
- Reject an empty `layers` block.
- Retain all per-layer field validation unchanged.

Replace the fixed missing/unknown check with:

```python
import re

_SLOT_RE = re.compile(r"^layer_(\d+)$")

def _valid_slot(key: str) -> int | None:
    m = _SLOT_RE.match(key)
    if m:
        n = int(m.group(1))
        if 1 <= n <= MAX_LAYER_COUNT:
            return n
    return None

# inside parse_layers_section:
for key in layers_raw:
    if _valid_slot(key) is None:
        raise ValueError(f"invalid layer key '{key}': must be layer_1 .. layer_{MAX_LAYER_COUNT}")
if not layers_raw:
    raise ValueError("layers section must contain at least one layer")
```

### 1.3 Relax `parse_layer_z_order_section`

- [x]

Currently validates permutation of fixed `LAYER_SLOTS`. Change to validate:
- Is a list.
- All entries appear in `layers` keys (the parsed layer set, passed in).
- No duplicates.
- Length matches the parsed layer set.

The parsed layer set is available as `ctx.layer_slots` — add this field to `ParseCtx`.

### 1.4 Update `persist_layers`

- [x]

Replace the `for slot in LAYER_SLOTS` loop with `for slot in ctx.session.layer_z_order`.
For newly added layers that have no entry in `ctx.cfg.layers` (see Phase 3), read all values
from `ctx.session.layers[slot]` and from `slot_layer_config(slot)` (a new helper that returns
the `LayerConfig` from cfg or synthesises defaults from session runtime).

Actually, by the time persist runs, `cfg.layers` includes the new slot (Phase 3 keeps cfg and
session in sync). No special case needed.

### 1.5 Update `parse_timeline_section`

- [x]

Cue `layers` sub-keys are validated against the actual layer set in the config (not
`LAYER_SLOTS`). Pass the parsed layer slots through `ParseCtx` and use them here.

### 1.6 `CleaveConfig` — un-freeze and use `list`

- [x]

`CleaveConfig` is `frozen=True` with `layer_z_order: tuple[str, ...]`. Dynamic add/remove
requires mutating both fields. Changes:

- Remove `frozen=True` from `CleaveConfig`.
- Change `layer_z_order: tuple[str, ...]` → `layer_z_order: list[str]`.
- Audit all call sites that construct `CleaveConfig` or read `layer_z_order` expecting a
  tuple; update to list.
- `layers_in_z_order` is unaffected (returns a list already).
- `LayerConfig` stays `frozen=True` (individual layer configs are immutable values).

---

## Phase 2 — GL lifecycle helpers

**Files:** `cleave/gl_compositor.py`, `cleave/viz/layer_pipeline.py`,
`cleave/preset_playlist.py`

### 2.1 `GlCompositor.remove_layer_fbo(name: str)`

- [x]

The compositor's `_layers` list already has no fixed capacity. Add:

```python
def remove_layer_fbo(self, name: str) -> None:
    """Destroy the named FBO and remove it from the compositor stack."""
    self._layers = [fbo for fbo in self._layers if fbo.name != name]
    # Release GL resources for the removed FBO.
```

### 2.2 `LayerFramePipeline.build_single`

- [x]

Build exactly one layer (ProjectM + FBO) and return a `StemLayer`:

```python
@staticmethod
def build_single(
    slot: str,
    layer_cfg: LayerConfig,
    compositor: GlCompositor,
    playlist: PresetPlaylist,
    fps: int,
    texture_paths: list[Path],
) -> StemLayer:
```

Reuses the same logic as the inner loop body in `build`. No warmup is applied; the new
layer starts from frame zero (same behaviour as any fresh projectM instance).

### 2.3 `LayerFramePipeline.destroy_single`

- [x]

```python
@staticmethod
def destroy_single(
    slot: str,
    layers: list[StemLayer],
    layers_by_slot: dict[str, StemLayer],
    compositor: GlCompositor,
) -> None:
    """Destroy the GL resources for one slot and remove it from both collections."""
    layer = layers_by_slot.pop(slot)
    layers.remove(layer)
    layer.pm.destroy()
    compositor.remove_layer_fbo(slot)
```

### 2.4 `scan_single_layer`

- [x]

New function in `preset_playlist.py`:

```python
def scan_single_layer(
    slot: str,
    preset_root: Path,
    project_dir: Path,
) -> PresetPlaylist:
    """Scan and return a playlist for a single slot, seeding a random preset."""
```

Same logic as `scan_all_layers` for one slot. Picks a random preset as initial current.

---

## Phase 3 — Session + wiring

**Files:** `cleave/viz/session.py`, `cleave/viz/wiring.py`

### 3.1 `session.py` — add/remove helpers

- [x]

```python
def add_layer_to_session(
    session: TuningSession,
    slot: str,
    runtime: LayerRuntime,
) -> None:
    session.layers[slot] = runtime
    session.layer_z_order.append(slot)

def remove_layer_from_session(session: TuningSession, slot: str) -> None:
    session.layer_z_order.remove(slot)
    del session.layers[slot]
    if session.solo_slot == slot:
        session.solo_slot = None
```

`session_from_cfg` already iterates `cfg.layers.items()` — no change needed there.

### 3.2 `wiring.py` — `LayerManager`

- [x]

Add a `LayerManager` class that holds the mutable GL collections and exposes the add/remove
operations. `TuningControls` receives a `LayerManager` and calls it on modal confirm.

```python
class LayerManager:
    def __init__(
        self,
        cfg: CleaveConfig,
        session: TuningSession,
        compositor: GlCompositor,
        layers: list[StemLayer],
        layers_by_slot: dict[str, StemLayer],
        playlists: dict[str, PresetPlaylist],
        pcm_bank: StemPcmBank,
        preset_root: Path,
        fps: int,
        texture_paths: list[Path],
    ) -> None: ...

    def can_add(self) -> bool:
        return len(self.session.layer_z_order) < MAX_LAYER_COUNT

    def can_remove(self) -> bool:
        return len(self.session.layer_z_order) > MIN_LAYER_COUNT

    def add_layer(self) -> str:
        """Create a new layer, update cfg/session/GL, return the new slot name."""
        slot = next_layer_slot(self.session.layer_z_order)
        playlist = scan_single_layer(slot, self.preset_root, project_dir=...)
        layer_cfg = new_layer_config(slot, playlist.current_path, self.preset_root)
        self.cfg.layers[slot] = layer_cfg
        stem_layer = LayerFramePipeline.build_single(
            slot, layer_cfg, self.compositor, playlist, self.fps, self.texture_paths
        )
        self.layers.append(stem_layer)
        self.layers_by_slot[slot] = stem_layer
        self.playlists[slot] = playlist
        runtime = LayerRuntime(
            playlist=playlist,
            browse_floor=self.preset_root,
            stem=DEFAULT_NEW_LAYER_STEM,
        )
        add_layer_to_session(self.session, slot, runtime)
        self.cfg.layer_z_order.append(slot)
        return slot

    def remove_layer(self, slot: str) -> None:
        """Destroy a layer and remove it from cfg/session/GL."""
        # Clear timeline records for this slot (cues are in session, not cfg)
        _discard_timeline_slot(self.session, slot)
        LayerFramePipeline.destroy_single(
            slot, self.layers, self.layers_by_slot, self.compositor
        )
        del self.cfg.layers[slot]
        self.cfg.layer_z_order.remove(slot)
        del self.playlists[slot]
        remove_layer_from_session(self.session, slot)
```

`_discard_timeline_slot` clears `session.timeline` records (armed slot, override stems,
record buffer, monitor) for the deleted slot — cues committed to the timeline are simply
orphaned (ignored by `layer_visible_at` since the slot is gone).

Remove `_stub_cfg_for_session`. Tests that needed it should build a minimal `CleaveConfig`
directly with an explicit slot list.

### 3.3 `make_tuning_controls` / `make_timeline_controls`

- [x]

Pass `LayerManager` into `make_tuning_controls`; store it on `TuningControls` for use in
`_add_layer` / `_delete_layer` handlers (Phase 5).

---

## Phase 4 — UI rows

**Files:** `cleave/viz/row_semantics.py`, `cleave/viz/overlay.py`

### 4.1 New `RowKind` values

- [x]

```python
class RowKind(Enum):
    ...
    LAYER_MANAGEMENT_ADD = auto()     # "ADD NEW LAYER" — one row, below all track blocks
    LAYER_MANAGEMENT_DELETE = auto()  # "Delete Layer" — one per track block, last sub-row
```

### 4.2 `RowBehavior` entries

- [x]

```python
RowKind.LAYER_MANAGEMENT_ADD: RowBehavior(
    RowAffordance.ACTION,
    help_title="Add new layer",
    navigable=True,
),
RowKind.LAYER_MANAGEMENT_DELETE: RowBehavior(
    RowAffordance.ACTION,
    help_title="Delete layer",
    navigable=True,
    blocked_by_layer_lock=False,   # always accessible
),
```

`LAYER_MANAGEMENT_DELETE` carries a `slot` in its `RowDescriptor` (same pattern as
`TRACK_EFFECT`). `LAYER_MANAGEMENT_ADD` has no slot.

Add both kinds to `TRACK_SUB_ROW_KINDS` (or a new `LAYER_MANAGEMENT_ROW_KINDS`) as
appropriate for navigation and group membership.

### 4.3 `build_row_layout` in `overlay.py`

- [x]

**Delete Layer** row: appended as the last sub-row of each track block, after the cleave
effects header (and any visible effect sub-rows). It is only included when the track is
expanded (follows the same expand gate as other sub-rows). Descriptor:
`RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot=slot)`.

**ADD NEW LAYER** row: inserted as the first row after the last track block, before
`RENDER_SECTION_GAP`. Descriptor: `RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD)`. Always
visible (not gated on any expand state).

### 4.4 Drawing in `overlay.py`

- [x]

**ADD NEW LAYER:** Draw with `_render_label_value_row` using label `ADD NEW LAYER` in
`LABEL` color. No eye, no expand arrow.

**Delete Layer:** Draw with `_render_label_value_row` using label `Delete Layer` in `LABEL`
color. No eye, no expand arrow. If `len(session.layer_z_order) == 1`, draw in `DISABLED`
color to signal the action is blocked (even though it is still navigable so the user can
receive the "must have at least 1 layer" notification).

---

## Phase 5 — Controls

**Files:** `cleave/viz/controls.py`

### 5.1 Constructor

- [x]

Accept `layer_manager: LayerManager` (may be `None` for headless tests).

### 5.2 `_add_layer`

- [x]

Called when Enter is pressed on `LAYER_MANAGEMENT_ADD`:

```python
def _add_layer(self) -> None:
    if self._layer_manager is None:
        return
    if not self._layer_manager.can_add():
        self.show_toast(f"Maximum {MAX_LAYER_COUNT} layers")
        return
    self._modal_host.prompt_yes_no(
        "Add new Milkdrop visualisation layer?",
        on_confirm=self._confirm_add_layer,
    )

def _confirm_add_layer(self) -> None:
    if self._layer_manager is None:
        return
    self._layer_manager.add_layer()
    self._rebuild_view()   # refresh the bindings / navigable rows
```

### 5.3 `_delete_layer`

- [x]

Called when Enter is pressed on `LAYER_MANAGEMENT_DELETE` (slot from `row_slot()`):

```python
def _delete_layer(self, slot: str) -> None:
    if self._layer_manager is None:
        return
    if not self._layer_manager.can_remove():
        self.show_toast("Must have at least 1 layer")
        return
    self._modal_host.prompt_yes_no(
        "Delete this Milkdrop visualisation layer?",
        on_confirm=lambda: self._confirm_delete_layer(slot),
    )

def _confirm_delete_layer(self, slot: str) -> None:
    if self._layer_manager is None:
        return
    current_focus = self._focus_row_index
    self._layer_manager.remove_layer(slot)
    self._rebuild_view()
    # Clamp focus to new row count
    self._focus_row_index = min(current_focus, len(navigable_row_indices(self._state)) - 1)
```

### 5.4 `_rebuild_view`

- [x]

After add/remove, the number of navigable rows changes. Call:
```python
self._state = TuningViewStateBuilder(self._session, self._cfg).build()
```
(or however the view state is currently rebuilt on other mutations that change row count).
Any z-order move mode is exited before the rebuild.

### 5.5 Key dispatch

- [x]

In the existing Enter handler, add cases for the two new row kinds before falling through to
existing cases:

```python
if kind == RowKind.LAYER_MANAGEMENT_ADD:
    self._add_layer()
    return
if kind == RowKind.LAYER_MANAGEMENT_DELETE:
    self._delete_layer(row_slot(self._state, self._focus_row_index))
    return
```

---

## Phase 6 — Timeline

**Files:** `cleave/timeline.py`, `cleave/viz/timeline_controls.py`,
`cleave/viz/timeline_overlay.py`, `cleave/viz/layer_visibility.py`

### 6.1 `timeline.py` — remove `LAYER_SLOTS` dependency

- [x]

`visible_state_at` currently iterates `LAYER_SLOTS`. Change signature to accept
`slots: list[str]` and iterate that instead. All callers pass `session.layer_z_order`.

### 6.2 `timeline_controls.py` — extend num keys to 1-8

- [x]

```python
_LAYER_KEY_INDEX: dict[int, int] = {
    pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3,
    pygame.K_5: 4, pygame.K_6: 5, pygame.K_7: 6, pygame.K_8: 7,
    pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2, pygame.K_KP4: 3,
    pygame.K_KP5: 4, pygame.K_KP6: 5, pygame.K_KP7: 6, pygame.K_KP8: 7,
}
```

Guard the index against `len(session.layer_z_order)` before using it (already implicit
in `_slot_for_layer_index` — keep that guard).

### 6.3 `timeline_overlay.py` — dynamic width probe

- [x]

Replace `layer_num_prefix(4)` with `layer_num_prefix(max(len(layer_z_order), 1))`. Since
max is 8, the column never needs more than one digit plus a space — the probe just needs to
match the widest label that will actually appear.

### 6.4 `layer_visibility.py`

- [x]

Any hardcoded slot references are replaced with `session.layer_z_order` iteration.

### 6.5 `controls.py` — clamp timeline focus on delete

- [x]

After `remove_layer`, clamp `timeline.focus_row` to `len(layer_z_order) - 1` (or clear
`submenu_focused` when no layers remain).

---

## Phase 7 — Snapshot and dirty tracking

**File:** `cleave/config_snapshot.py`

### 7.1 `persist_layers`

- [x]

The current loop is `for slot in LAYER_SLOTS`. Change to `for slot in ctx.session.layer_z_order`.

Since Phase 3 keeps `cfg.layers` and `session.layer_z_order` in sync (add/remove updates
both), `ctx.cfg.layers[slot]` is always present for every session slot. No special fallback
needed.

### 7.2 `persist_layer_z_order`

- [x]

Already reads `session.layer_z_order` — no change.

### 7.3 Dirty tracking

- [x]

`persisted_session_signature` computes the hash of `persisted_session_payload`. Because that
payload is built from the actual session + cfg (both updated on add/remove), dirtiness is
detected correctly with no extra logic.

Adding a layer marks the config dirty (the new layer is in the payload but was not in the
last-saved signature). Removing a layer similarly. The user is prompted to save on quit as
usual.

---

## Phase 8 — Tests and docs

### 8.1 Unit tests

- [x]

Update any test that hard-codes `LAYER_SLOTS`, constructs a `CleaveConfig` with exactly
four layers, or uses `DEFAULT_STEM_FOR_SLOT`:

- Replace `LAYER_SLOTS` references with the explicit list or the test's own slot set.
- Remove `_stub_cfg_for_session` and inline equivalent construction.
- Add tests:
  - `next_layer_slot` returns correct names and raises at capacity.
  - `parse_layers_section` accepts 1-layer and 8-layer configs; rejects 0 and 9.
  - `persist_layers` round-trips a 3-layer and a 6-layer session.
  - Timeline `visible_state_at` with 6 slots.

### 8.2 `cleave-viz.yaml` template

- [x]

No change to the default content (still four layers). The template is not a constraint; the
schema now accepts any count. Remove any comment that says "must have exactly four."

### 8.3 `.cursor/rules/project-context.mdc`

- [x]

Remove "four libprojectM layers". Update to "up to eight Milkdrop layers" or equivalent.

### 8.4 `.cursor/rules/live-tuning-ui.mdc`

- [x]

- Remove `layer_1`..`layer_4` enumeration where it implies a fixed count.
- Document the two new row kinds: `LAYER_MANAGEMENT_ADD` and `LAYER_MANAGEMENT_DELETE`.
- Note num keys 1-8.
- Update timeline strip focus-ring `0..3` comment to `0..N-1`.

### 8.5 `docs/roadmap.md` / `docs/todos.md`

- [x]

Remove or mark done any item about dynamic layers or the four-layer cap. Remove references
to four layers as the permanent stack size.

---

## File change summary

| File | Change |
|---|---|
| `cleave/config_schema.py` | Remove `LAYER_SLOTS`; add `MAX_LAYER_COUNT`, `MIN_LAYER_COUNT`, `DEFAULT_LAYER_SLOTS`, `next_layer_slot`, `new_layer_config`, `DEFAULT_NEW_LAYER_STEM`; relax parse; iterate session in persist |
| `cleave/config.py` | Un-freeze `CleaveConfig`; `layer_z_order: list[str]` |
| `cleave/gl_compositor.py` | Add `remove_layer_fbo` |
| `cleave/viz/layer_pipeline.py` | Add `build_single`, `destroy_single` |
| `cleave/preset_playlist.py` | Add `scan_single_layer` |
| `cleave/viz/session.py` | Add `add_layer_to_session`, `remove_layer_from_session` |
| `cleave/viz/wiring.py` | Add `LayerManager`; remove `_stub_cfg_for_session` |
| `cleave/viz/row_semantics.py` | Add `LAYER_MANAGEMENT_ADD`, `LAYER_MANAGEMENT_DELETE` kinds and behaviors |
| `cleave/viz/overlay.py` | Insert new rows in `build_row_layout`; add drawing for both |
| `cleave/viz/controls.py` | Accept `LayerManager`; add `_add_layer`, `_delete_layer`, `_rebuild_view` |
| `cleave/timeline.py` | Replace `LAYER_SLOTS` with caller-supplied slot list |
| `cleave/viz/timeline_controls.py` | Extend `_LAYER_KEY_INDEX` to 1-8 + numpad 1-8 |
| `cleave/viz/timeline_overlay.py` | Dynamic width probe |
| `cleave/viz/layer_visibility.py` | Remove any `LAYER_SLOTS` references |
| `cleave/config_snapshot.py` | `persist_layers` iterates `session.layer_z_order` |
| `cleave/viz/app.py` | Construct and pass `LayerManager` in `init_gl_resources_heavy` |
| `.cursor/rules/project-context.mdc` | Remove four-layer cap language |
| `.cursor/rules/live-tuning-ui.mdc` | Update row docs, num keys, slot refs |
| `docs/roadmap.md` / `docs/todos.md` | Remove fixed-layer entries |

---

## Architectural notes

**Why un-freeze `CleaveConfig`?** The frozen dataclass was a style choice, not a correctness
requirement. The `layers` dict field was already mutable even under `frozen=True`. Un-freezing
lets `layer_z_order` (previously a tuple) become a list, allowing in-place append/remove
without constructing a new `CleaveConfig` instance on every layer operation. Since `cfg` is
never used as a dict key or set member, the hashability guarantee of `frozen=True` is unused.

**Why mutate `cfg` on add/remove?** `persist_layers` cross-references `cfg.layers` for
width/height (values not on `LayerRuntime`). Keeping `cfg.layers` in sync with the live
layer set means persist, dirty tracking, and the GL pipeline all use a single coherent view.
The alternative (a parallel "live layer config" dict) duplicates state and divergence risk.

**Why incremental GL build?** Full pipeline teardown and rebuild on each add/remove would
disrupt all existing projectM waveforms and FBO state. `build_single`/`destroy_single`
leave untouched layers running continuously; only the added/removed FBO and projectM instance
are created/destroyed. The brief freeze is limited to one projectM init (roughly the same
as a preset load).

**Why no warm-up for new layers?** The projectM warm-up in `LayerFramePipeline.warmup` is a
startup optimisation to avoid the white frame-zero flash before the first real frame. A
layer added mid-session will fade in from black naturally (its FBO starts opaque black) and
reaches a stable visual within a few frames. A per-add warm-up would require pausing
playback, which outweighs the cosmetic benefit.
