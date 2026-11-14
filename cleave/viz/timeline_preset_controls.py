"""Generate and Reset timeline dialogs and their clear+apply orchestration."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence

from cleave.signals import Signals
from cleave.timeline import (
    TimelineLane,
    copy_lane,
    empty_lane,
    shift_bars_by_beats,
    snap_lane_to_beats,
    snap_lanes_to_song_markers,
)
from cleave.timeline_presets import (
    build_arc_cues,
    build_breathing_cues,
    build_dialogue_cues,
    build_pulse_cues,
    compose_pattern_mask_timeline,
)
from cleave.timeline_presets.characters import (
    CHARACTER_HELP,
    TIMELINE_PRESET_KIND_OPTIONS,
    timeline_preset_kind_display,
)
from cleave.timeline_presets.conductor import timeline_preset_conductor_display
from cleave.timeline_presets.mode import (
    TIMELINE_PRESET_MODE_OPTIONS,
    timeline_preset_mode_display,
)
from cleave.timeline_presets.accent import apply_accent
from cleave.timeline_presets.crescendo import apply_crescendo
from cleave.timeline_presets.cue_snap import (
    TIMELINE_PRESET_CUE_SNAP_OPTIONS,
    timeline_preset_cue_snap_display,
)
from cleave.timeline_presets.density import (
    TIMELINE_PRESET_DENSITY_OPTIONS,
    density_bias_for,
    timeline_preset_density_display,
)
from cleave.timeline_presets.repopulate import (
    TIMELINE_PRESET_REPOPULATE_OPTIONS,
    timeline_preset_repopulate_display,
)
from cleave.timeline_presets.song_marker_snap import (
    TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS,
    timeline_preset_song_marker_snap_display,
)
from cleave.timeline_presets.timeline_cuts import (
    TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS,
    TimelinePresetTimelineCuts,
    timeline_preset_timeline_cuts_display,
)
from cleave.viz.modal import (
    FormField,
    FormSpec,
    FormValues,
    ModalHost,
)
from cleave.viz.session import TuningSession
from cleave.viz.timeline_cut_controls import apply_cut_to_lanes
from cleave.viz.timeline_history import TimelineHistory

_GENERATE_TITLE = "Generate timeline"
_RESET_TITLE = "Reset timeline?"
_CONDUCTOR_OPTIONS = (False, True)
_RESET_LAYER_OPTIONS = ("off", "on")
_PATTERN_MASK_TRANSITION_SEC = 1.0

_KIND_BUILDERS = {
    "breathing": (build_breathing_cues, "Applied Breathing timeline preset"),
    "dialogue": (build_dialogue_cues, "Applied Dialogue timeline preset"),
    "arc": (build_arc_cues, "Applied Arc timeline preset"),
    "pulse": (build_pulse_cues, "Applied Pulse timeline preset"),
}


_GENERATE_HELP = (
    "Makes a new timeline from these settings.",
    "This replaces the current cues.",
    "In layers mode, each crescendo song marker gets a crescendo.",
    "The project keeps these settings.",
)
_CHARACTER_HELP = ("The shape of the arrangement: which layers play together, and when.",)
_DENSITY_HELP = (
    "How many layers tend to play at once.",
    "Sparse favours solos; dense keeps more of the stack on.",
)
_CUE_SNAP_HELP = ("Moves every generated cue onto the beat or bar grid.",)
_CUE_SNAP_OPTION_HELP = {
    "none": "keep the generated cue times.",
    "beats": "move each cue to the nearest beat.",
    "bars": "move each cue to the nearest bar.",
}
_SONG_MARKER_SNAP_HELP = (
    "Moves the closest cue on each layer onto each song marker,",
    "when it is no further away than this.",
    "none leaves the cues where they are.",
)
_TIMELINE_CUTS_HELP = (
    "The cut type each generated cue gets.",
    "The timeline's cue fades set the fade for each type.",
)
_TIMELINE_CUTS_OPTION_HELP = {
    "by marker": "hard cuts on song markers, soft cuts elsewhere.",
    "all soft": "every cue is a soft cut.",
    "all hard": "every cue is a hard cut.",
    "none": "keep the cut each cue was made with.",
}
_REPOPULATE_HELP = (
    "Refills the preset list of each layer whose preset switching is on",
    "with the timeline trigger.",
)
_REPOPULATE_OPTION_HELP = {
    "no": "keep the preset lists.",
    "cue roles": "one preset per on-cue, picked for that cue's role.",
    "directory random": "fill from the layer's preset directory, shuffled.",
    "directory sequential": "fill from the layer's preset directory, in order.",
}
_CONDUCTOR_HELP = (
    "Uses the stems' audio to choose which layers lead each phrase",
    "and how bright each one is.",
    "In layers mode, standard song markers also get an accent.",
    "Needs analysed signals; without them it is skipped.",
)
_CONDUCTOR_OPTION_HELP = {
    False: "levels come from the character alone.",
    True: "levels follow the music.",
}
_MODE_HELP = ("How the layers are staged.",)
_MODE_OPTION_HELP = {
    "layers": "cues turn whole layers on and off, shaped by the character.",
    "pattern_mask": (
        "short sections swap layers through the pattern mask; "
        "turns the mask on with strips. Ignores the character."
    ),
}
_RESET_HELP = ("Removes every cue on the timeline.",)
_RESET_LAYERS_HELP = ("What every layer does for the whole song after the reset.",)
_RESET_LAYERS_OPTION_HELP = (
    "every layer stays off.",
    "every layer stays on.",
)


def _choice_field(
    field_id: str,
    label: str,
    options: Sequence[object],
    current: object,
    display: Callable[..., str],
    *,
    help: tuple[str, ...] = (),
    option_help: Mapping[object, str] | None = None,
) -> FormField:
    return FormField(
        field_id,
        label,
        tuple(display(option) for option in options),
        options.index(current),
        help=help,
        option_help=()
        if option_help is None
        else tuple(option_help[option] for option in options),
    )


def _cues_label(count: int) -> str:
    return "1 cue" if count == 1 else f"{count} cues"


class TimelinePresetController:
    """Prompt for and apply procedural timeline presets from the tuning panel."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        beat_times: Sequence[float] = (),
        bar_times: Sequence[float] = (),
        *,
        signals: Signals | None = None,
        on_notification: Callable[[str], None] | None = None,
        on_repopulate: Callable[[], None] | None = None,
        history: TimelineHistory | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._history = history if history is not None else TimelineHistory(session)
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._signals = signals
        self._on_notification = on_notification
        self._on_repopulate = on_repopulate

    def prompt(self, duration_sec: float) -> None:
        tl = self.session.timeline
        if tl.locked:
            return
        self._modal.prompt_form(
            FormSpec(
                title=_GENERATE_TITLE,
                fields=(
                    _choice_field(
                        "character",
                        "character",
                        TIMELINE_PRESET_KIND_OPTIONS,
                        tl.timeline_preset_kind,
                        timeline_preset_kind_display,
                        help=_CHARACTER_HELP,
                        option_help=CHARACTER_HELP,
                    ),
                    _choice_field(
                        "density",
                        "density",
                        TIMELINE_PRESET_DENSITY_OPTIONS,
                        tl.timeline_preset_density,
                        timeline_preset_density_display,
                        help=_DENSITY_HELP,
                    ),
                    _choice_field(
                        "cue_snap",
                        "cue snap",
                        TIMELINE_PRESET_CUE_SNAP_OPTIONS,
                        tl.timeline_preset_cue_snap,
                        timeline_preset_cue_snap_display,
                        help=_CUE_SNAP_HELP,
                        option_help=_CUE_SNAP_OPTION_HELP,
                    ),
                    _choice_field(
                        "song_marker_snap",
                        "song marker snap",
                        TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS,
                        tl.timeline_preset_song_marker_snap,
                        timeline_preset_song_marker_snap_display,
                        help=_SONG_MARKER_SNAP_HELP,
                    ),
                    _choice_field(
                        "timeline_cuts",
                        "timeline cuts",
                        TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS,
                        tl.timeline_preset_timeline_cuts,
                        timeline_preset_timeline_cuts_display,
                        help=_TIMELINE_CUTS_HELP,
                        option_help=_TIMELINE_CUTS_OPTION_HELP,
                    ),
                    _choice_field(
                        "repopulate",
                        "re-populate preset lists",
                        TIMELINE_PRESET_REPOPULATE_OPTIONS,
                        tl.timeline_preset_repopulate,
                        timeline_preset_repopulate_display,
                        help=_REPOPULATE_HELP,
                        option_help=_REPOPULATE_OPTION_HELP,
                    ),
                    _choice_field(
                        "conductor",
                        "conductor",
                        _CONDUCTOR_OPTIONS,
                        tl.timeline_preset_conductor,
                        timeline_preset_conductor_display,
                        help=_CONDUCTOR_HELP,
                        option_help=_CONDUCTOR_OPTION_HELP,
                    ),
                    _choice_field(
                        "mode",
                        "mode",
                        TIMELINE_PRESET_MODE_OPTIONS,
                        tl.timeline_preset_mode,
                        timeline_preset_mode_display,
                        help=_MODE_HELP,
                        option_help=_MODE_OPTION_HELP,
                    ),
                ),
                confirm_label="Generate",
                on_confirm=lambda values: self._confirm_generate(
                    values, duration_sec
                ),
                info=lambda _values: self._generate_info(),
                help=_GENERATE_HELP,
            )
        )

    def _generate_info(self) -> str | None:
        count = self._cue_count()
        if count == 0:
            return None
        return f"Replaces {_cues_label(count)} on the timeline."

    def _cue_count(self) -> int:
        return sum(len(lane.cues) for lane in self.session.timeline.lanes.values())

    def _confirm_generate(self, values: FormValues, duration_sec: float) -> None:
        tl = self.session.timeline
        tl.timeline_preset_kind = TIMELINE_PRESET_KIND_OPTIONS[values["character"]]
        tl.timeline_preset_density = TIMELINE_PRESET_DENSITY_OPTIONS[values["density"]]
        tl.timeline_preset_cue_snap = TIMELINE_PRESET_CUE_SNAP_OPTIONS[
            values["cue_snap"]
        ]
        tl.timeline_preset_song_marker_snap = TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS[
            values["song_marker_snap"]
        ]
        tl.timeline_preset_timeline_cuts = TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS[
            values["timeline_cuts"]
        ]
        tl.timeline_preset_repopulate = TIMELINE_PRESET_REPOPULATE_OPTIONS[
            values["repopulate"]
        ]
        tl.timeline_preset_conductor = _CONDUCTOR_OPTIONS[values["conductor"]]
        tl.timeline_preset_mode = TIMELINE_PRESET_MODE_OPTIONS[values["mode"]]
        with self._history.recording("Generate timeline"):
            self._apply(tl.timeline_preset_kind, duration_sec)

    def prompt_reset(self) -> None:
        if self.session.timeline.locked:
            return
        count = self._cue_count()
        self._modal.prompt_form(
            FormSpec(
                title=_RESET_TITLE,
                body=f"Removes {_cues_label(count)}.",
                fields=(
                    FormField(
                        "layers",
                        "layers after reset",
                        _RESET_LAYER_OPTIONS,
                        help=_RESET_LAYERS_HELP,
                        option_help=_RESET_LAYERS_OPTION_HELP,
                    ),
                ),
                confirm_label="Reset timeline",
                on_confirm=self._confirm_reset,
                destructive=True,
                help=_RESET_HELP,
            )
        )

    def _apply(
        self,
        kind: str,
        duration_sec: float,
    ) -> None:
        if not self._bar_times:
            self._notify("No bars available; re-run separate")
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        builder, message = _KIND_BUILDERS[kind]
        grid = shift_bars_by_beats(
            self._bar_times,
            self._beat_times,
            self.session.timeline.bar_phase_offset,
        )
        if not grid:
            self._notify("No bars available; re-run separate")
            return
        self._clear_timeline_state()
        tl = self.session.timeline
        tl.enabled = True
        slots = list(self.session.layer_z_order)
        markers = list(self.session.song_markers.markers)
        marker_times = [m.time for m in markers]
        rng = random.Random()
        builder_kwargs: dict = {
            "bar_times": grid,
            "song_marker_times": marker_times,
            "density_bias": density_bias_for(tl.timeline_preset_density),
        }
        conductor_skipped = False
        if tl.timeline_preset_conductor:
            if self._signals is None:
                conductor_skipped = True
            else:
                builder_kwargs["signals"] = self._signals
                builder_kwargs["slot_stems"] = {
                    slot: self.session.layers[slot].stem for slot in slots
                }
        if tl.timeline_preset_mode == "pattern_mask":
            self._enable_pattern_mask()
            built = compose_pattern_mask_timeline(
                slots,
                duration_sec,
                rng,
                song_markers=markers,
                beat_times=self._beat_times,
                transition_duration=self.session.pattern_mask.transition,
                **builder_kwargs,
            )
            message = "Applied pattern mask timeline"
        else:
            built = builder(
                slots,
                duration_sec,
                rng,
                **builder_kwargs,
            )
            after_crescendo = apply_crescendo(
                built,
                slots,
                duration_sec=duration_sec,
                bar_times=grid,
                song_markers=markers,
                rng=rng,
            )
            if after_crescendo is not built:
                built = after_crescendo
                message = f"{message} (crescendo)"
            if tl.timeline_preset_conductor and self._signals is not None:
                after_accent = apply_accent(
                    built,
                    slots,
                    duration_sec=duration_sec,
                    bar_times=grid,
                    song_markers=markers,
                    signals=self._signals,
                    slot_stems={
                        slot: self.session.layers[slot].stem for slot in slots
                    },
                    density_bias=density_bias_for(tl.timeline_preset_density),
                    rng=rng,
                )
                if after_accent is not built:
                    built = after_accent
                    message = f"{message} (accent)"
        built = {
            slot: copy_lane(built.get(slot, empty_lane())) for slot in slots
        }
        self._apply_cue_snap(built, grid)
        self._apply_song_marker_snap(built, marker_times, slots)
        self._apply_timeline_cuts(built, marker_times, tl.timeline_preset_timeline_cuts)
        for slot in slots:
            tl.lanes[slot] = built[slot]
        if (
            tl.timeline_preset_repopulate != "no"
            and self._on_repopulate is not None
        ):
            self._on_repopulate()
        if conductor_skipped:
            self._notify("No signals; conductor skipped")
        else:
            self._notify(message)

    def _enable_pattern_mask(self) -> None:
        pm = self.session.pattern_mask
        pm.enabled = True
        pm.type = "strips"
        pm.feather_pct = 0
        pm.transition = _PATTERN_MASK_TRANSITION_SEC

    def _apply_cue_snap(
        self,
        lanes: dict[str, TimelineLane],
        bar_grid: Sequence[float],
    ) -> None:
        cue_snap = self.session.timeline.timeline_preset_cue_snap
        if cue_snap == "beats":
            grid = self._beat_times
        elif cue_snap == "bars":
            grid = bar_grid
        else:
            return
        for slot in list(lanes):
            lanes[slot] = snap_lane_to_beats(lanes[slot], grid)

    def _apply_song_marker_snap(
        self,
        lanes: dict[str, TimelineLane],
        markers: Sequence[float],
        slots: Sequence[str],
    ) -> None:
        proximity = self.session.timeline.timeline_preset_song_marker_snap
        if proximity is None:
            return
        updated, _moved = snap_lanes_to_song_markers(
            lanes,
            markers,
            proximity=float(proximity),
            layer_z_order=slots,
            slots=slots,
            mode="each_layer",
        )
        for slot in slots:
            lanes[slot] = updated[slot]

    def _apply_timeline_cuts(
        self,
        lanes: dict[str, TimelineLane],
        markers: Sequence[float],
        cuts: TimelinePresetTimelineCuts,
    ) -> None:
        if cuts == "none":
            return
        if cuts == "by marker":
            apply_cut_to_lanes(
                lanes, "soft", song_marker_times=markers, scope="all"
            )
            apply_cut_to_lanes(
                lanes, "hard", song_marker_times=markers, scope="markers_only"
            )
            return
        if cuts == "all soft":
            apply_cut_to_lanes(
                lanes, "soft", song_marker_times=markers, scope="all"
            )
            return
        if cuts == "all hard":
            apply_cut_to_lanes(
                lanes, "hard", song_marker_times=markers, scope="all"
            )

    def _confirm_reset(self, values: FormValues) -> None:
        with self._history.recording("Reset timeline"):
            self._reset(all_on=values["layers"] == 1)

    def _reset(self, *, all_on: bool) -> None:
        self._clear_timeline_state()
        tl = self.session.timeline
        tl.enabled = True
        tl.lanes = {
            slot: TimelineLane(baseline=1.0 if all_on else 0.0, cues=[])
            for slot in self.session.layer_z_order
        }
        message = (
            "Reset timeline: all layers on"
            if all_on
            else "Reset timeline: all layers off"
        )
        self._notify(message)

    def _clear_timeline_state(self) -> None:
        tl = self.session.timeline
        tl.lanes = {
            slot: empty_lane() for slot in self.session.layer_z_order
        }
        tl.record_buffer = {}
        tl.recording = False
        tl.record_start_sec = None
        tl.record_baseline = {}
        tl.record_slot_start_sec = {}
        tl.record_high_water_mark = None
        tl.armed_slots.clear()
        tl.override_slots.clear()
        tl.override_visible.clear()
        tl.arm_flash_start_ms.clear()

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
