"""Timeline YAML parse, serialize, and defaults."""

from __future__ import annotations

from typing import Any, Literal

from cleave.blend_modes import BlendMode
from cleave.choice import step_choice
from cleave.config_schema.descriptors import (
    ParseCtx,
    PersistCtx,
    as_mapping,
    require_non_negative_number,
)
from cleave.config_schema.layers import (
    parse_preset_list_entry,
    persist_preset_list_entry,
)
from cleave.config_schema.validators import (
    validate_blend_mode,
    validate_cue_role,
    validate_cut_type,
)
from cleave.cue_roles import CueRole
from cleave.cut_types import CutType
from cleave.preset_list_entry import PresetListEntry
from cleave.timeline import SlotCue, TimelineLane, canonicalize, clamp_level

DEFAULT_TIMELINE_ENABLED = True
DEFAULT_TIMELINE_LOCKED = False

DEFAULT_TIMELINE_FADES_ENABLED = False
DEFAULT_TIMELINE_HARD_FADE_IN = 0.2
DEFAULT_TIMELINE_HARD_FADE_OUT = 0.2
DEFAULT_TIMELINE_SOFT_FADE_IN = 2.0
DEFAULT_TIMELINE_SOFT_FADE_OUT = 2.0
DEFAULT_TIMELINE_CROSSFADE = False
TIMELINE_FADE_DURATION_MIN = 0.0
TIMELINE_FADE_DURATION_MAX = 30.0
TIMELINE_FADE_DURATION_STEP = 0.1

TimelinePlacementSnap = Literal["off", "beat", "bar"]
TIMELINE_PLACEMENT_SNAP_OPTIONS: tuple[TimelinePlacementSnap, ...] = (
    "off",
    "beat",
    "bar",
)
DEFAULT_TIMELINE_PLACEMENT_SNAP: TimelinePlacementSnap = "beat"

TIMELINE_BAR_PHASE_BEATS = 4
DEFAULT_TIMELINE_BAR_PHASE = 0
DEFAULT_TIMELINE_SHOW_BAR_GRID = False
DEFAULT_TIMELINE_SHOW_PRESET_NAMES = True


def step_timeline_placement_snap(
    value: str, *, forward: bool
) -> TimelinePlacementSnap:
    options = TIMELINE_PLACEMENT_SNAP_OPTIONS
    current = value if value in options else DEFAULT_TIMELINE_PLACEMENT_SNAP
    return step_choice(options, current, 1 if forward else -1)  # type: ignore[arg-type]


def clamp_timeline_fade_duration(value: float) -> float:
    return max(
        TIMELINE_FADE_DURATION_MIN,
        min(TIMELINE_FADE_DURATION_MAX, float(value)),
    )


def parse_timeline_placement_snap(raw: Any, label: str) -> TimelinePlacementSnap:
    value = str(raw)
    if value not in TIMELINE_PLACEMENT_SNAP_OPTIONS:
        allowed = ", ".join(TIMELINE_PLACEMENT_SNAP_OPTIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def parse_timeline_bar_phase(raw: Any, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"{label} must be an integer")
    if not 0 <= raw < TIMELINE_BAR_PHASE_BEATS:
        raise ValueError(
            f"{label} must be between 0 and {TIMELINE_BAR_PHASE_BEATS - 1}"
        )
    return raw


















def timeline_crossfade_display(crossfade: bool) -> str:
    return "on" if crossfade else "off"


def _parse_timeline_fade_group(
    raw: Any,
    label: str,
    *,
    fade_in_default: float,
    fade_out_default: float,
) -> Any:
    from cleave.config import TimelineFadeGroupConfig

    if raw is None:
        return TimelineFadeGroupConfig(
            fade_in=fade_in_default,
            fade_out=fade_out_default,
        )
    group_map = as_mapping(raw, label)
    return TimelineFadeGroupConfig(
        enabled=bool(group_map.get("enabled", DEFAULT_TIMELINE_FADES_ENABLED)),
        fade_in=clamp_timeline_fade_duration(
            require_non_negative_number(
                group_map.get("fade_in", fade_in_default),
                f"{label}.fade_in",
            )
        ),
        fade_out=clamp_timeline_fade_duration(
            require_non_negative_number(
                group_map.get("fade_out", fade_out_default),
                f"{label}.fade_out",
            )
        ),
        crossfade=bool(group_map.get("crossfade", DEFAULT_TIMELINE_CROSSFADE)),
    )




def parse_timeline_section(data: dict[str, Any], ctx: ParseCtx) -> Any | None:
    from cleave.config import TimelineConfig, TimelineCutsConfig

    timeline = data.get("timeline")
    if timeline is None:
        return None
    timeline_map = as_mapping(timeline, "timeline")
    enabled = bool(timeline_map.get("enabled", DEFAULT_TIMELINE_ENABLED))
    locked = bool(timeline_map.get("locked", DEFAULT_TIMELINE_LOCKED))
    placement_snap = parse_timeline_placement_snap(
        timeline_map.get("placement_snap", DEFAULT_TIMELINE_PLACEMENT_SNAP),
        "timeline.placement_snap",
    )
    bar_phase = parse_timeline_bar_phase(
        timeline_map.get("bar_phase", DEFAULT_TIMELINE_BAR_PHASE),
        "timeline.bar_phase",
    )
    show_bar_grid = bool(
        timeline_map.get("show_bar_grid", DEFAULT_TIMELINE_SHOW_BAR_GRID)
    )
    show_preset_names = bool(
        timeline_map.get("show_preset_names", DEFAULT_TIMELINE_SHOW_PRESET_NAMES)
    )
    cuts_raw = timeline_map.get("cuts")
    if cuts_raw is None:
        cuts = TimelineCutsConfig()
    else:
        cuts_map = as_mapping(cuts_raw, "timeline.cuts")
        cuts = TimelineCutsConfig(
            hard=_parse_timeline_fade_group(
                cuts_map.get("hard"),
                "timeline.cuts.hard",
                fade_in_default=DEFAULT_TIMELINE_HARD_FADE_IN,
                fade_out_default=DEFAULT_TIMELINE_HARD_FADE_OUT,
            ),
            soft=_parse_timeline_fade_group(
                cuts_map.get("soft"),
                "timeline.cuts.soft",
                fade_in_default=DEFAULT_TIMELINE_SOFT_FADE_IN,
                fade_out_default=DEFAULT_TIMELINE_SOFT_FADE_OUT,
            ),
        )
    lanes_raw = timeline_map.get("lanes")
    if lanes_raw is None:
        return TimelineConfig(
            enabled=enabled,
            lanes={},
            locked=locked,
            cuts=cuts,
            placement_snap=placement_snap,
            bar_phase=bar_phase,
            show_bar_grid=show_bar_grid,
            show_preset_names=show_preset_names,
        )
    lanes_map = as_mapping(lanes_raw, "timeline.lanes")
    if ctx.layer_slots is None:
        raise ValueError("layer_slots required to parse timeline")
    allowed_slots = set(ctx.layer_slots)
    unknown_slots = sorted(set(lanes_map) - allowed_slots)
    if unknown_slots:
        raise ValueError(
            "unknown layer keys in timeline.lanes "
            f"(expected {', '.join(ctx.layer_slots)}): "
            + ", ".join(unknown_slots)
        )
    lanes: dict[str, TimelineLane] = {}
    for slot, lane_raw in lanes_map.items():
        lane_map = as_mapping(lane_raw, f"timeline.lanes.{slot}")
        baseline: float | None
        if "baseline" in lane_map:
            baseline = clamp_level(float(lane_map["baseline"]))
        else:
            baseline = None
        cues_raw = lane_map.get("cues", [])
        if cues_raw is None:
            cues_raw = []
        if not isinstance(cues_raw, list):
            raise ValueError(f"timeline.lanes.{slot}.cues must be a list")
        cues: list[SlotCue] = []
        for index, item in enumerate(cues_raw):
            cue_map = as_mapping(item, f"timeline.lanes.{slot}.cues[{index}]")
            if "level" not in cue_map:
                raise ValueError(
                    f"timeline.lanes.{slot}.cues[{index}] missing level"
                )
            t = float(
                require_non_negative_number(
                    cue_map.get("t"),
                    f"timeline.lanes.{slot}.cues[{index}].t",
                )
            )
            blend: BlendMode | None = None
            if "blend" in cue_map and cue_map["blend"] is not None:
                blend = validate_blend_mode(
                    cue_map["blend"],
                    path=f"timeline.lanes.{slot}.cues[{index}].blend",
                )
            role: CueRole | None = None
            if "role" in cue_map and cue_map["role"] is not None:
                role = validate_cue_role(
                    cue_map["role"],
                    path=f"timeline.lanes.{slot}.cues[{index}].role",
                )
            cut: CutType | None = None
            if "cut" in cue_map and cue_map["cut"] is not None:
                cut = validate_cut_type(
                    cue_map["cut"],
                    path=f"timeline.lanes.{slot}.cues[{index}].cut",
                )
            anchor = bool(cue_map.get("anchor", False))
            recast = bool(cue_map.get("recast", False))
            preset: PresetListEntry | None = None
            if cue_map.get("preset") is not None and ctx.cfg_dir is not None:
                preset = parse_preset_list_entry(
                    cue_map["preset"],
                    f"timeline.lanes.{slot}.cues[{index}].preset",
                    ctx.cfg_dir,
                )
            cues.append(
                SlotCue(
                    t=t,
                    level=clamp_level(float(cue_map["level"])),
                    blend=blend,
                    role=role,
                    cut=cut,
                    anchor=anchor,
                    recast=recast,
                    preset=preset,
                )
            )
        lanes[str(slot)] = TimelineLane(
            baseline=baseline,
            cues=canonicalize(baseline, cues),
        )
    return TimelineConfig(
        enabled=enabled,
        lanes=lanes,
        locked=locked,
        cuts=cuts,
        placement_snap=placement_snap,
        bar_phase=bar_phase,
        show_bar_grid=show_bar_grid,
        show_preset_names=show_preset_names,
    )


def _persist_timeline_fade_group(group: Any) -> dict[str, Any]:
    return {
        "enabled": group.enabled,
        "fade_in": group.fade_in,
        "fade_out": group.fade_out,
        "crossfade": group.crossfade,
    }


def persist_timeline(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.timeline
    out: dict[str, Any] = {
        "enabled": runtime.enabled,
        "locked": runtime.locked,
        "placement_snap": runtime.placement_snap,
        "bar_phase": runtime.bar_phase_offset,
        "show_bar_grid": runtime.show_bar_grid,
        "show_preset_names": runtime.show_preset_names,
        "cuts": {
            "hard": _persist_timeline_fade_group(runtime.hard_cut_fades),
            "soft": _persist_timeline_fade_group(runtime.soft_cut_fades),
        },
    }
    lanes_out: dict[str, Any] = {}
    for slot in sorted(runtime.lanes):
        lane = runtime.lanes[slot]
        if lane.baseline is None and not lane.cues:
            continue
        entry: dict[str, Any] = {}
        if lane.baseline is not None:
            entry["baseline"] = lane.baseline
        if lane.cues:
            cues_out: list[dict[str, Any]] = []
            for cue in lane.cues:
                cue_out: dict[str, Any] = {"t": cue.t, "level": cue.level}
                if cue.blend is not None:
                    cue_out["blend"] = cue.blend
                if cue.role is not None:
                    cue_out["role"] = cue.role
                if cue.cut is not None:
                    cue_out["cut"] = cue.cut
                if cue.anchor:
                    cue_out["anchor"] = True
                if cue.recast:
                    cue_out["recast"] = True
                if cue.preset is not None:
                    cue_out["preset"] = persist_preset_list_entry(
                        cue.preset, ctx.cfg_dir
                    )
                cues_out.append(cue_out)
            entry["cues"] = cues_out
        lanes_out[slot] = entry
    if lanes_out:
        out["lanes"] = lanes_out
    return out
