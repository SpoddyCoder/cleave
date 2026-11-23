"""Layer YAML parse, serialize, and defaults."""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Any, Literal

from cleave.blend_modes import BlendMode
from cleave.config_schema.descriptors import ParseCtx, PersistCtx, as_mapping
from cleave.config_schema.editor import clamp_beat_sensitivity
from cleave.config_schema.validators import parse_blend_mode
from cleave.effects.constants import clamp_effect_pct
from cleave.effects.registry import validate_effect_entry
from cleave.paths import config_anchor_path, config_relative_path
from cleave.preset_list_entry import PresetListEntry
from cleave.stems import STEM_SOURCES, StemSource

PresetSwitchingMode = Literal["off", "on"]
PresetSwitchingTrigger = Literal["off", "timer", "projectm", "timeline"]
PRESET_SWITCHING_MODES: tuple[PresetSwitchingMode, ...] = ("off", "on")
PRESET_SWITCHING_TRIGGERS: tuple[PresetSwitchingTrigger, ...] = (
    "off",
    "timer",
    "projectm",
    "timeline",
)
PRESET_SWITCHING_TRIGGER_HELP_ENTRIES: tuple[
    tuple[PresetSwitchingTrigger, str], ...
] = (
    (
        "off",
        "the layer keeps its own preset.",
    ),
    (
        "timer",
        "the next preset in the list starts after each preset duration.",
    ),
    (
        "projectm",
        "projectM plays the list with its own timing and hard cuts on strong beats. It is live: each play, and each render, can switch at different moments, so the preview will not match a render exactly.",
    ),
    (
        "timeline",
        "every timeline clip holds its own preset. Choosing it turns the timeline on; from on a timer, the row is cut into clips where the presets change.",
    ),
)
DEFAULT_PRESET_SWITCHING: PresetSwitchingMode = "off"
DEFAULT_PRESET_SWITCHING_TRIGGER: PresetSwitchingTrigger = "off"
PRESET_SWITCHING_TRIGGER_WHEN_ON: PresetSwitchingTrigger = "timer"
DEFAULT_PRESET_DURATION = 30.0
DEFAULT_SOFT_CUT_DURATION = 0.0
DEFAULT_HARD_CUT_DURATION = 20.0
DEFAULT_HARD_CUT_SENSITIVITY = 2.0
DEFAULT_HARD_CUT_ENABLED = True
DEFAULT_EASTER_EGG = 1.0
EASTER_EGG_MIN = 0.1
EASTER_EGG_MAX = 5.0
DEFAULT_PRESET_START_CLEAN = False
DEFAULT_PRESET_SWITCHING_LIST: list[str] = []

MAX_LAYER_COUNT = 8
MIN_LAYER_COUNT = 1
DEFAULT_LAYER_SLOTS = ("layer_1", "layer_2", "layer_3", "layer_4")
DEFAULT_LAYER_Z_ORDER: list[str] = list(DEFAULT_LAYER_SLOTS)
DEFAULT_NEW_LAYER_STEM: StemSource = "full_mix"
DEFAULT_LAYER_ENABLED = True
DEFAULT_LAYER_OPACITY = 1.0
DEFAULT_LAYER_LOCKED = False

_SLOT_RE = re.compile(r"^layer_(\d+)$")


def _valid_slot(key: str) -> int | None:
    m = _SLOT_RE.match(key)
    if m:
        n = int(m.group(1))
        if 1 <= n <= MAX_LAYER_COUNT:
            return n
    return None


def next_layer_slot(existing_slots: list[str]) -> str:
    used = set(existing_slots)
    for i in range(1, MAX_LAYER_COUNT + 1):
        candidate = f"layer_{i}"
        if candidate not in used:
            return candidate
    raise ValueError(f"Maximum {MAX_LAYER_COUNT} layers already present")


DEFAULT_BLEND_MODE: dict[StemSource, BlendMode] = {
    "drums": "add",
    "other": "black-key",
    "bass": "black-key",
    "vocals": "black-key",
    "guitar": "black-key",
    "piano": "black-key",
    "full_mix": "black-key",
}


def _parse_preset_switching(raw: Any, label: str) -> PresetSwitchingMode:
    # YAML 1.1 loads unquoted on/off/yes/no as booleans.
    if isinstance(raw, bool):
        raw = "on" if raw else "off"
    mode = str(raw)
    if mode not in PRESET_SWITCHING_MODES:
        allowed = ", ".join(PRESET_SWITCHING_MODES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return mode  # type: ignore[return-value]


def _parse_preset_switching_trigger(
    raw: Any, label: str
) -> PresetSwitchingTrigger:
    # YAML 1.1 loads unquoted on/off/yes/no as booleans.
    if isinstance(raw, bool):
        raw = "on" if raw else "off"
    trigger = str(raw)
    if trigger not in PRESET_SWITCHING_TRIGGERS:
        allowed = ", ".join(PRESET_SWITCHING_TRIGGERS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return trigger  # type: ignore[return-value]


def preset_switching_mode_for_trigger(
    trigger: PresetSwitchingTrigger,
) -> PresetSwitchingMode:
    return "off" if trigger == "off" else "on"


def resolve_layer_preset_switching(
    layer_raw: dict[str, Any], slot: str
) -> tuple[PresetSwitchingMode, PresetSwitchingTrigger]:
    switching = _parse_preset_switching(
        layer_raw.get("preset_switching", DEFAULT_PRESET_SWITCHING),
        f"layers.{slot}.preset_switching",
    )
    if "preset_switching_trigger" in layer_raw:
        trigger = _parse_preset_switching_trigger(
            layer_raw["preset_switching_trigger"],
            f"layers.{slot}.preset_switching_trigger",
        )
    else:
        trigger = (
            DEFAULT_PRESET_SWITCHING_TRIGGER
            if switching == "off"
            else PRESET_SWITCHING_TRIGGER_WHEN_ON
        )
    if switching == "off" or trigger == "off":
        return "off", "off"
    return "on", trigger


def hard_cut_enabled_display(enabled: bool) -> str:
    return "enabled" if enabled else "disabled"


def preset_start_clean_display(enabled: bool) -> str:
    return "yes" if enabled else "no"


def clamp_easter_egg(value: float) -> float:
    return max(EASTER_EGG_MIN, min(EASTER_EGG_MAX, float(value)))


def preset_switching_trigger_display(trigger: PresetSwitchingTrigger) -> str:
    if trigger == "off":
        return "never"
    if trigger == "projectm":
        return "projectM decides"
    if trigger == "timeline":
        return "each clip"
    return "on a timer"


def _resolve_preset(preset: str | Path, preset_root: Path) -> Path:
    path = Path(os.path.expanduser(str(preset)))
    if path.is_absolute():
        return path.resolve()
    return (preset_root / path).resolve()


def resolve_user_preset(preset: str | Path, cfg_dir: Path) -> Path:
    """Resolve a preset path from a viz config relative to ``cfg_dir``."""
    path = Path(os.path.expanduser(str(preset)))
    if path.is_absolute():
        return path.resolve()
    return (cfg_dir / path).resolve()


def _parse_preset_switching_list(
    slot: str,
    layer_raw: dict[str, Any],
    ctx: ParseCtx,
) -> list[PresetListEntry]:
    raw = layer_raw.get("preset_switching_list")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"layers.{slot}.preset_switching_list must be a list")
    if ctx.cfg_dir is None:
        warnings.warn(
            f"layers.{slot}.preset_switching_list skipped: cfg_dir not set",
            stacklevel=2,
        )
        return []
    return [
        parse_preset_list_entry(
            item, f"layers.{slot}.preset_switching_list[{index}]", ctx.cfg_dir
        )
        for index, item in enumerate(raw)
    ]


def parse_preset_list_entry(
    item: Any, where: str, cfg_dir: Path
) -> PresetListEntry:
    """One ``{path, source}`` preset mapping, with ``path`` resolved from ``cfg_dir``."""
    if not isinstance(item, dict):
        raise ValueError(f"{where} must be a mapping with a path")
    path = item.get("path")
    if not isinstance(path, str):
        raise ValueError(f"{where}.path must be a string")
    source = item.get("source")
    if source is not None and not isinstance(source, str):
        raise ValueError(f"{where}.source must be a string")
    return PresetListEntry(
        path=resolve_user_preset(path, cfg_dir).as_posix(),
        source=(
            Path(os.path.expanduser(source)).as_posix()
            if source is not None
            else None
        ),
    )


def parse_layer_z_order_section(data: dict[str, Any], ctx: ParseCtx) -> list[str]:
    if ctx.layer_slots is None:
        raise ValueError("layer_slots required to parse layer_z_order")
    layer_slots = ctx.layer_slots
    raw = data.get("layer_z_order")
    if raw is None:
        return list(layer_slots)
    if not isinstance(raw, list):
        raise ValueError("layer_z_order must be a list")
    if len(raw) != len(layer_slots):
        raise ValueError(
            f"layer_z_order must contain exactly {len(layer_slots)} entries"
        )
    if set(raw) != set(layer_slots):
        raise ValueError(
            f"layer_z_order must contain each of {', '.join(layer_slots)} exactly once"
        )
    return list(raw)


def persist_layer_z_order(ctx: PersistCtx) -> list[str]:
    return list(ctx.session.layer_z_order)


def _parse_stem(slot: str, layer_raw: dict[str, Any]) -> StemSource:
    raw = layer_raw.get("stem")
    if raw is None:
        return DEFAULT_NEW_LAYER_STEM
    if raw not in STEM_SOURCES:
        allowed = ", ".join(STEM_SOURCES)
        raise ValueError(f"layers.{slot}.stem must be one of: {allowed}")
    return raw


def _parse_effects(
    slot: str,
    stem: StemSource,
    layer_raw: dict[str, Any],
) -> dict[str, dict[str, int]]:
    raw = layer_raw.get("effects")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"layers.{slot}.effects must be a mapping")

    effects: dict[str, dict[str, int]] = {}
    for effect_id, drivers_raw in raw.items():
        if not isinstance(effect_id, str):
            raise ValueError(f"layers.{slot}.effects keys must be strings")
        if not isinstance(drivers_raw, dict):
            raise ValueError(f"layers.{slot}.effects.{effect_id} must be a mapping")
        for driver_slug, value in drivers_raw.items():
            if not isinstance(driver_slug, str):
                raise ValueError(
                    f"layers.{slot}.effects.{effect_id} driver keys must be strings"
                )
            validate_effect_entry(slot, stem, effect_id, driver_slug)
            pct = clamp_effect_pct(value)
            if pct == 0:
                continue
            effects.setdefault(effect_id, {})[driver_slug] = pct
    return effects


def sparse_effects(
    effects: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]] | None:
    out: dict[str, dict[str, int]] = {}
    for effect_id, drivers in effects.items():
        sparse_drivers: dict[str, int] = {}
        for driver_slug, pct in drivers.items():
            clamped = clamp_effect_pct(pct)
            if clamped != 0:
                sparse_drivers[driver_slug] = clamped
        if sparse_drivers:
            out[effect_id] = sparse_drivers
    return out or None


def parse_layers_section(data: dict[str, Any], ctx: ParseCtx) -> dict[str, Any]:
    from cleave.config import LayerConfig

    if ctx.preset_root is None:
        raise ValueError("preset_root required to parse layers")
    preset_root = ctx.preset_root

    layers_raw = as_mapping(data.get("layers"), "layers")
    if not layers_raw:
        raise ValueError("layers section must contain at least one layer")
    for key in layers_raw:
        if _valid_slot(key) is None:
            raise ValueError(
                f"invalid layer key '{key}': must be layer_1 .. layer_{MAX_LAYER_COUNT}"
            )
    if len(layers_raw) < MIN_LAYER_COUNT:
        raise ValueError("layers section must contain at least one layer")
    if len(layers_raw) > MAX_LAYER_COUNT:
        raise ValueError(f"layers section must contain at most {MAX_LAYER_COUNT} layers")

    layer_keys = sorted(layers_raw, key=lambda k: _valid_slot(k) or 0)
    ctx.layer_slots = tuple(layer_keys)

    layers: dict[str, LayerConfig] = {}
    for slot in layer_keys:
        layer_raw = as_mapping(layers_raw[slot], f"layers.{slot}")
        preset_raw = layer_raw.get("preset")
        if not preset_raw:
            raise ValueError(f"layers.{slot}.preset is required")

        stem = _parse_stem(slot, layer_raw)
        beat_raw = layer_raw.get("beat_sensitivity")
        preset_switching, preset_switching_trigger = resolve_layer_preset_switching(
            layer_raw, slot
        )
        preset_duration = float(
            layer_raw.get("preset_duration", DEFAULT_PRESET_DURATION)
        )
        soft_cut_duration = float(
            layer_raw.get("soft_cut_duration", DEFAULT_SOFT_CUT_DURATION)
        )
        hard_cut_duration = float(
            layer_raw.get("hard_cut_duration", DEFAULT_HARD_CUT_DURATION)
        )
        hard_cut_sensitivity = float(
            layer_raw.get("hard_cut_sensitivity", DEFAULT_HARD_CUT_SENSITIVITY)
        )
        hard_cut_enabled = bool(
            layer_raw.get("hard_cut_enabled", DEFAULT_HARD_CUT_ENABLED)
        )
        easter_egg = clamp_easter_egg(
            float(layer_raw.get("easter_egg", DEFAULT_EASTER_EGG))
        )
        preset_start_clean = bool(
            layer_raw.get("preset_start_clean", DEFAULT_PRESET_START_CLEAN)
        )
        preset_switching_list = _parse_preset_switching_list(slot, layer_raw, ctx)
        layers[slot] = LayerConfig(
            preset=_resolve_preset(preset_raw, preset_root),
            stem=stem,
            enabled=bool(layer_raw.get("enabled", DEFAULT_LAYER_ENABLED)),
            opacity=float(layer_raw.get("opacity", DEFAULT_LAYER_OPACITY)),
            beat_sensitivity=clamp_beat_sensitivity(beat_raw)
            if beat_raw is not None
            else None,
            effects=_parse_effects(slot, stem, layer_raw),
            blend_mode=parse_blend_mode(slot, stem, layer_raw),
            locked=bool(layer_raw.get("locked", DEFAULT_LAYER_LOCKED)),
            preset_switching=preset_switching,
            preset_switching_trigger=preset_switching_trigger,
            preset_duration=preset_duration,
            soft_cut_duration=soft_cut_duration,
            hard_cut_duration=hard_cut_duration,
            hard_cut_sensitivity=hard_cut_sensitivity,
            hard_cut_enabled=hard_cut_enabled,
            easter_egg=easter_egg,
            preset_start_clean=preset_start_clean,
            preset_switching_list=preset_switching_list,
        )
    return layers


def persist_preset_list_entry(
    entry: PresetListEntry, cfg_dir: Path | None
) -> dict[str, str]:
    path = (
        entry.file.as_posix()
        if cfg_dir is None
        else config_relative_path(entry.file, cfg_dir)
    )
    out = {"path": path}
    if entry.source is not None:
        out["source"] = entry.source
    return out


def persist_layers(ctx: PersistCtx) -> dict[str, dict[str, Any]]:
    preset_root = ctx.cfg.paths.preset_root
    layers_out: dict[str, dict[str, Any]] = {}
    global_beat = ctx.session.project.milkdrop_beat_sensitivity

    for slot in ctx.session.layer_z_order:
        runtime = ctx.session.layers[slot]
        stem = runtime.stem
        if runtime.preset_switching == "on" and runtime.layer_preset is not None:
            # Browsing with switching on is a preview; the layer's preset stays.
            preset = config_anchor_path(runtime.layer_preset, preset_root)
        else:
            preset = runtime.playlist.config_preset_path(preset_root)
        opacity = runtime.opacity_pct / 100.0
        enabled = runtime.enabled
        blend_mode = runtime.blend_mode
        beat = runtime.beat_sensitivity
        effects = runtime.effects
        locked = runtime.locked
        preset_switching = runtime.preset_switching
        preset_switching_trigger = runtime.preset_switching_trigger
        preset_duration = runtime.preset_duration
        soft_cut_duration = runtime.soft_cut_duration
        hard_cut_duration = runtime.hard_cut_duration
        hard_cut_sensitivity = runtime.hard_cut_sensitivity
        hard_cut_enabled = runtime.hard_cut_enabled
        easter_egg = runtime.easter_egg
        preset_start_clean = runtime.preset_start_clean
        preset_switching_list = list(runtime.preset_list)

        layer_out: dict[str, Any] = {
            "stem": stem,
            "preset": preset,
            "enabled": enabled,
            "opacity": opacity,
            "blend_mode": blend_mode,
            "locked": locked,
        }
        beat = clamp_beat_sensitivity(beat)
        if beat != global_beat:
            layer_out["beat_sensitivity"] = beat
        sparse = sparse_effects(effects)
        if sparse is not None:
            layer_out["effects"] = sparse
        if preset_switching != DEFAULT_PRESET_SWITCHING:
            layer_out["preset_switching"] = preset_switching
        if preset_switching_trigger != DEFAULT_PRESET_SWITCHING_TRIGGER:
            layer_out["preset_switching_trigger"] = preset_switching_trigger
        if preset_duration != DEFAULT_PRESET_DURATION:
            layer_out["preset_duration"] = preset_duration
        if soft_cut_duration != DEFAULT_SOFT_CUT_DURATION:
            layer_out["soft_cut_duration"] = soft_cut_duration
        if hard_cut_duration != DEFAULT_HARD_CUT_DURATION:
            layer_out["hard_cut_duration"] = hard_cut_duration
        if hard_cut_sensitivity != DEFAULT_HARD_CUT_SENSITIVITY:
            layer_out["hard_cut_sensitivity"] = hard_cut_sensitivity
        if hard_cut_enabled != DEFAULT_HARD_CUT_ENABLED:
            layer_out["hard_cut_enabled"] = hard_cut_enabled
        if easter_egg != DEFAULT_EASTER_EGG:
            layer_out["easter_egg"] = easter_egg
        if preset_start_clean != DEFAULT_PRESET_START_CLEAN:
            layer_out["preset_start_clean"] = preset_start_clean
        if preset_switching_list:
            layer_out["preset_switching_list"] = [
                persist_preset_list_entry(entry, ctx.cfg_dir)
                for entry in preset_switching_list
            ]
        layers_out[slot] = layer_out

    return layers_out


def template_layer_entry(
    slot: str, stem: StemSource = DEFAULT_NEW_LAYER_STEM
) -> dict[str, Any]:
    return {
        "stem": stem,
        "preset": f"presets/{stem}/",
        "enabled": DEFAULT_LAYER_ENABLED,
        "opacity": DEFAULT_LAYER_OPACITY,
        "blend_mode": DEFAULT_BLEND_MODE[stem],
    }
