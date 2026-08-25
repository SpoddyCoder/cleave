"""Timeline YAML parse, serialize, and defaults."""

from __future__ import annotations

from typing import Any, Literal

from cleave.blend_modes import BlendMode
from cleave.config_schema.descriptors import (
    ParseCtx,
    PersistCtx,
    as_mapping,
    require_non_negative_number,
)
from cleave.config_schema.validators import (
    validate_blend_mode,
    validate_cue_role,
    validate_cut_type,
)
from cleave.cue_roles import CueRole
from cleave.cut_types import CutType
from cleave.timeline import SlotCue, TimelineLane, canonicalize, clamp_level
from cleave.timeline_presets.characters import (
    DEFAULT_TIMELINE_PRESET_KIND,
    TIMELINE_PRESET_KIND_OPTIONS,
)
from cleave.timeline_presets.conductor import DEFAULT_TIMELINE_PRESET_CONDUCTOR
from cleave.timeline_presets.cue_snap import (
    DEFAULT_TIMELINE_PRESET_CUE_SNAP,
    TIMELINE_PRESET_CUE_SNAP_OPTIONS,
    TimelinePresetCueSnap,
)
from cleave.timeline_presets.density import (
    DEFAULT_TIMELINE_PRESET_DENSITY,
    TIMELINE_PRESET_DENSITY_OPTIONS,
    TimelinePresetDensity,
)
from cleave.timeline_presets.mode import (
    DEFAULT_TIMELINE_PRESET_MODE,
    TIMELINE_PRESET_MODE_OPTIONS,
    TimelinePresetMode,
)
from cleave.timeline_presets.repopulate import (
    DEFAULT_TIMELINE_PRESET_REPOPULATE,
    TIMELINE_PRESET_REPOPULATE_OPTIONS,
    TimelinePresetRepopulate,
)
from cleave.timeline_presets.song_marker_snap import (
    DEFAULT_TIMELINE_PRESET_SONG_MARKER_SNAP,
    TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS,
    TimelinePresetSongMarkerSnap,
)
from cleave.timeline_presets.timeline_cuts import (
    DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS,
    TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS,
    TimelinePresetTimelineCuts,
)

DEFAULT_TIMELINE_ENABLED = True
DEFAULT_TIMELINE_LOCKED = False

DEFAULT_TIMELINE_FADES_ENABLED = False
DEFAULT_TIMELINE_FADE_IN = 2.0
DEFAULT_TIMELINE_FADE_OUT = 2.0
DEFAULT_TIMELINE_CROSSFADE = False
TIMELINE_FADE_DURATION_MIN = 0.0
TIMELINE_FADE_DURATION_MAX = 30.0
TIMELINE_FADE_DURATION_STEP = 0.1

DEFAULT_VISUAL_LIMITER_ENABLED = True
DEFAULT_VISUAL_LIMITER_THRESHOLD = 0.65
DEFAULT_VISUAL_LIMITER_RATIO = 3.0
DEFAULT_VISUAL_LIMITER_RELEASE = 0.45
VISUAL_LIMITER_THRESHOLD_MIN = 0.30
VISUAL_LIMITER_THRESHOLD_MAX = 0.95
VISUAL_LIMITER_THRESHOLD_STEP = 0.01
VISUAL_LIMITER_RATIO_MIN = 1.5
VISUAL_LIMITER_RATIO_MAX = 8.0
VISUAL_LIMITER_RATIO_STEP = 0.5
VISUAL_LIMITER_RELEASE_MIN = 0.2
VISUAL_LIMITER_RELEASE_MAX = 3.0
VISUAL_LIMITER_RELEASE_STEP = 0.1

TimelinePlacementSnap = Literal["off", "beat", "bar"]
TIMELINE_PLACEMENT_SNAP_OPTIONS: tuple[TimelinePlacementSnap, ...] = (
    "off",
    "beat",
    "bar",
)
DEFAULT_TIMELINE_PLACEMENT_SNAP: TimelinePlacementSnap = "beat"


def clamp_visual_limiter_threshold(value: float) -> float:
    return max(
        VISUAL_LIMITER_THRESHOLD_MIN,
        min(VISUAL_LIMITER_THRESHOLD_MAX, float(value)),
    )


def clamp_visual_limiter_ratio(value: float) -> float:
    return max(
        VISUAL_LIMITER_RATIO_MIN,
        min(VISUAL_LIMITER_RATIO_MAX, float(value)),
    )


def clamp_visual_limiter_release(value: float) -> float:
    return max(
        VISUAL_LIMITER_RELEASE_MIN,
        min(VISUAL_LIMITER_RELEASE_MAX, float(value)),
    )


def cycle_timeline_placement_snap(
    value: str, *, forward: bool
) -> TimelinePlacementSnap:
    options = TIMELINE_PLACEMENT_SNAP_OPTIONS
    try:
        index = options.index(value)  # type: ignore[arg-type]
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PLACEMENT_SNAP)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


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


def parse_timeline_preset_character(raw: Any, label: str) -> str:
    value = str(raw)
    if value not in TIMELINE_PRESET_KIND_OPTIONS:
        allowed = ", ".join(TIMELINE_PRESET_KIND_OPTIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def parse_timeline_preset_density(raw: Any, label: str) -> TimelinePresetDensity:
    value = str(raw)
    if value not in TIMELINE_PRESET_DENSITY_OPTIONS:
        allowed = ", ".join(TIMELINE_PRESET_DENSITY_OPTIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def parse_timeline_preset_cue_snap(raw: Any, label: str) -> TimelinePresetCueSnap:
    value = str(raw)
    if value not in TIMELINE_PRESET_CUE_SNAP_OPTIONS:
        allowed = ", ".join(TIMELINE_PRESET_CUE_SNAP_OPTIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


_SONG_MARKER_SNAP_PROXIMITY_SET = frozenset(
    float(opt)
    for opt in TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS
    if opt is not None
)


def parse_timeline_preset_song_marker_snap(
    raw: Any, label: str
) -> TimelinePresetSongMarkerSnap:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"{label} must be a number of seconds, or null")
    value = float(raw)
    if value not in _SONG_MARKER_SNAP_PROXIMITY_SET:
        allowed = ", ".join(
            "null" if opt is None else str(opt)
            for opt in TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS
        )
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def parse_timeline_preset_timeline_cuts(
    raw: Any, label: str
) -> TimelinePresetTimelineCuts:
    value = str(raw)
    if value not in TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS:
        allowed = ", ".join(TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def parse_timeline_preset_repopulate(
    raw: Any, label: str
) -> TimelinePresetRepopulate:
    value = str(raw)
    if value not in TIMELINE_PRESET_REPOPULATE_OPTIONS:
        allowed = ", ".join(TIMELINE_PRESET_REPOPULATE_OPTIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def parse_timeline_preset_conductor(raw: Any, label: str) -> bool:
    if not isinstance(raw, bool):
        raise ValueError(f"{label} must be true or false")
    return raw


def parse_timeline_preset_mode(raw: Any, label: str) -> TimelinePresetMode:
    value = str(raw)
    if value not in TIMELINE_PRESET_MODE_OPTIONS:
        allowed = ", ".join(TIMELINE_PRESET_MODE_OPTIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def timeline_crossfade_display(crossfade: bool) -> str:
    return "on" if crossfade else "off"


def cycle_timeline_crossfade(value: bool, *, forward: bool) -> bool:
    options = (False, True)
    try:
        index = options.index(bool(value))
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_CROSSFADE)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


def _parse_timeline_fade_group(raw: Any, label: str) -> Any:
    from cleave.config import TimelineFadeGroupConfig

    if raw is None:
        return TimelineFadeGroupConfig()
    group_map = as_mapping(raw, label)
    return TimelineFadeGroupConfig(
        enabled=bool(group_map.get("enabled", DEFAULT_TIMELINE_FADES_ENABLED)),
        fade_in=clamp_timeline_fade_duration(
            require_non_negative_number(
                group_map.get("fade_in", DEFAULT_TIMELINE_FADE_IN),
                f"{label}.fade_in",
            )
        ),
        fade_out=clamp_timeline_fade_duration(
            require_non_negative_number(
                group_map.get("fade_out", DEFAULT_TIMELINE_FADE_OUT),
                f"{label}.fade_out",
            )
        ),
        crossfade=bool(group_map.get("crossfade", DEFAULT_TIMELINE_CROSSFADE)),
    )


def _parse_timeline_preset(raw: Any) -> Any:
    from cleave.config import TimelinePresetConfig

    if raw is None:
        return TimelinePresetConfig()
    preset_map = as_mapping(raw, "timeline.preset")
    return TimelinePresetConfig(
        character=parse_timeline_preset_character(
            preset_map.get("character", DEFAULT_TIMELINE_PRESET_KIND),
            "timeline.preset.character",
        ),
        density=parse_timeline_preset_density(
            preset_map.get("density", DEFAULT_TIMELINE_PRESET_DENSITY),
            "timeline.preset.density",
        ),
        cue_snap=parse_timeline_preset_cue_snap(
            preset_map.get("cue_snap", DEFAULT_TIMELINE_PRESET_CUE_SNAP),
            "timeline.preset.cue_snap",
        ),
        song_marker_snap=parse_timeline_preset_song_marker_snap(
            preset_map.get(
                "song_marker_snap", DEFAULT_TIMELINE_PRESET_SONG_MARKER_SNAP
            ),
            "timeline.preset.song_marker_snap",
        ),
        timeline_cuts=parse_timeline_preset_timeline_cuts(
            preset_map.get(
                "timeline_cuts", DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS
            ),
            "timeline.preset.timeline_cuts",
        ),
        repopulate=parse_timeline_preset_repopulate(
            preset_map.get("repopulate", DEFAULT_TIMELINE_PRESET_REPOPULATE),
            "timeline.preset.repopulate",
        ),
        conductor=parse_timeline_preset_conductor(
            preset_map.get("conductor", DEFAULT_TIMELINE_PRESET_CONDUCTOR),
            "timeline.preset.conductor",
        ),
        mode=parse_timeline_preset_mode(
            preset_map.get("mode", DEFAULT_TIMELINE_PRESET_MODE),
            "timeline.preset.mode",
        ),
    )


def _parse_timeline_limiter(raw: Any) -> Any:
    from cleave.config import TimelineLimiterConfig

    if raw is None:
        return TimelineLimiterConfig()
    limiter_map = as_mapping(raw, "timeline.limiter")
    return TimelineLimiterConfig(
        enabled=bool(
            limiter_map.get("enabled", DEFAULT_VISUAL_LIMITER_ENABLED)
        ),
        threshold=clamp_visual_limiter_threshold(
            require_non_negative_number(
                limiter_map.get("threshold", DEFAULT_VISUAL_LIMITER_THRESHOLD),
                "timeline.limiter.threshold",
            )
        ),
        ratio=clamp_visual_limiter_ratio(
            require_non_negative_number(
                limiter_map.get("ratio", DEFAULT_VISUAL_LIMITER_RATIO),
                "timeline.limiter.ratio",
            )
        ),
        release=clamp_visual_limiter_release(
            require_non_negative_number(
                limiter_map.get("release", DEFAULT_VISUAL_LIMITER_RELEASE),
                "timeline.limiter.release",
            )
        ),
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
    cuts_raw = timeline_map.get("cuts")
    if cuts_raw is None:
        cuts = TimelineCutsConfig()
    else:
        cuts_map = as_mapping(cuts_raw, "timeline.cuts")
        cuts = TimelineCutsConfig(
            hard=_parse_timeline_fade_group(
                cuts_map.get("hard"),
                "timeline.cuts.hard",
            ),
            soft=_parse_timeline_fade_group(
                cuts_map.get("soft"),
                "timeline.cuts.soft",
            ),
        )
    preset = _parse_timeline_preset(timeline_map.get("preset"))
    limiter = _parse_timeline_limiter(timeline_map.get("limiter"))
    lanes_raw = timeline_map.get("lanes")
    if lanes_raw is None:
        return TimelineConfig(
            enabled=enabled,
            lanes={},
            locked=locked,
            cuts=cuts,
            placement_snap=placement_snap,
            preset=preset,
            limiter=limiter,
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
            cues.append(
                SlotCue(
                    t=t,
                    level=clamp_level(float(cue_map["level"])),
                    blend=blend,
                    role=role,
                    cut=cut,
                    anchor=anchor,
                    recast=recast,
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
        preset=preset,
        limiter=limiter,
    )


def _persist_timeline_fade_group(group: Any) -> dict[str, Any]:
    return {
        "enabled": group.enabled,
        "fade_in": group.fade_in,
        "fade_out": group.fade_out,
        "crossfade": group.crossfade,
    }


def _persist_timeline_limiter(limiter: Any) -> dict[str, Any]:
    return {
        "enabled": limiter.enabled,
        "threshold": limiter.threshold,
        "ratio": limiter.ratio,
        "release": limiter.release,
    }


def persist_timeline(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.timeline
    out: dict[str, Any] = {
        "enabled": runtime.enabled,
        "locked": runtime.locked,
        "placement_snap": runtime.placement_snap,
        "cuts": {
            "hard": _persist_timeline_fade_group(runtime.hard_cut_fades),
            "soft": _persist_timeline_fade_group(runtime.soft_cut_fades),
        },
        "preset": {
            "character": runtime.timeline_preset_kind,
            "density": runtime.timeline_preset_density,
            "cue_snap": runtime.timeline_preset_cue_snap,
            "song_marker_snap": runtime.timeline_preset_song_marker_snap,
            "timeline_cuts": runtime.timeline_preset_timeline_cuts,
            "repopulate": runtime.timeline_preset_repopulate,
            "conductor": runtime.timeline_preset_conductor,
            "mode": runtime.timeline_preset_mode,
        },
        "limiter": _persist_timeline_limiter(runtime.limiter),
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
                cues_out.append(cue_out)
            entry["cues"] = cues_out
        lanes_out[slot] = entry
    if lanes_out:
        out["lanes"] = lanes_out
    return out
