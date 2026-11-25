"""Generate and Reset timeline dialogs and their clear+apply orchestration."""

from __future__ import annotations

import random
import traceback
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
from cleave.config_schema.layers import preset_switching_mode_for_trigger
from cleave.timeline_presets.lanes import compose_layers_timeline
from cleave.timeline_presets.layer_setup import (
    FULL_OPACITY_PCT,
    change_presets_display,
    layer_opacity_display,
)
from cleave.timeline_presets.pattern_mask_arrange import compose_pattern_mask_timeline
from cleave.timeline_presets.conductor import timeline_preset_conductor_display
from cleave.timeline_presets.mode import (
    TIMELINE_PRESET_MODE_OPTIONS,
    timeline_preset_mode_display,
)
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
    DEFAULT_TIMELINE_PRESET_REPOPULATE,
    TIMELINE_PRESET_REPOPULATE_OPTIONS,
    TimelinePresetRepopulate,
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
from cleave.viz.timeline_clip_edits import row_clips
from cleave.viz.timeline_cut_controls import apply_cut_to_lanes
from cleave.viz.clip_presets import (
    is_each_clip,
    layers_label,
    locked_each_clip_reason,
)
from cleave.viz.edit_history import EditHistory

_GENERATE_TITLE = "Generate timeline"
_RESET_TITLE = "Reset timeline?"
_CONDUCTOR_OPTIONS = (False, True)
_RESET_LAYER_OPTIONS = ("off", "on")
_PATTERN_MASK_TRANSITION_SEC = 1.0
# Generate dialog sections: what the arrangement is, then how its cues are
# tidied, then what happens to the layers' preset lists.
_ARRANGEMENT_SECTION = "Arrangement"
_CUES_SECTION = "Clip timing and cuts"
_PRESETS_SECTION = "Presets"

_GENERATE_HELP = (
    "Builds a new timeline from these settings, replacing the current clips. Arrangement decides which layers play when, clip timing and cuts then tidy every generated clip, and each layer whose presets change on each clip gets a preset for every new clip. That replaces the layer's whole preset list, spares included.",
    "Each section is arranged to suit its song marker's type and intensity: how many layers play, which one leads, how bright each is, and how often presets change. Back-to-back markers of one type make one longer section, such as a build that rises across all of them. Settings are kept for the rest of the session.",
)
_DENSITY_HELP = (
    "How many layers tend to play at once: sparse favours solos, dense keeps more of the stack in.",
)
_CUE_SNAP_HELP = ("Moves the edges of every generated clip onto the beat or bar grid.",)
_CUE_SNAP_OPTION_HELP = {
    "none": "keep the generated clip times.",
    "beats": "move each clip edge to the nearest beat.",
    "bars": "move each clip edge to the nearest bar.",
}
_SONG_MARKER_SNAP_HELP = (
    "Pulls the nearest clip edge on each layer onto each song marker, if it is within this distance. none leaves the clips where they are.",
)
_TIMELINE_CUTS_HELP = (
    "The cut type each generated clip edge gets. Fade lengths for each type come from Timeline > Clip Fades.",
)
_TIMELINE_CUTS_OPTION_HELP = {
    "by marker": "hard cuts on song markers, soft cuts elsewhere.",
    "all soft": "every clip edge is a soft cut.",
    "all hard": "every clip edge is a hard cut.",
    "none": "keep the cut each clip edge was made with.",
}
_REPOPULATE_HELP = (
    "How each new clip gets its preset, on every layer whose presets change on each clip.",
)
_REPOPULATE_OPTION_HELP = {
    "cue roles": "a preset picked for each clip's role.",
    "directory random": "presets from the layer's preset directory, shuffled.",
    "directory sequential": "presets from the layer's preset directory, in order.",
}
_CONDUCTOR_HELP = (
    "Uses the stems' audio to decide which layer leads each phrase and to give layers roles, which set their blend modes. In layers mode a chorus or drop opens with an accent on one layer. It needs the song's audio analysis and is skipped without it.",
)
_CONDUCTOR_OPTION_HELP = {
    False: "layers take turns leading, and keep their own blend modes.",
    True: "the busiest stem leads, and layers get roles.",
}
_MODE_HELP = ("How the arrangement brings layers in and out.",)
_MODE_OPTION_HELP = {
    "layers": "clips bring whole layers in and out, at the opacity each section calls for.",
    "pattern_mask": (
        "short sections swap layers through the pattern mask; "
        "turns the mask on with strips."
    ),
}
_ON_OFF = (False, True)
_LAYER_OPACITY_HELP = (
    "Each layer's own opacity multiplies the opacity of its clips, so the brightness Generate plans shows as planned only on layers at 100%.",
)
_LAYER_OPACITY_OPTION_HELP = {
    False: "keep each layer's opacity; layers below 100% look dimmer than planned.",
    True: "set every unlocked layer to 100%.",
}
_CHANGE_PRESETS_HELP = (
    "Generate plans a new preset at song markers and every few bars, on layers that stay on. Those changes play only on layers whose presets change on each clip.",
)
_CHANGE_PRESETS_OPTION_HELP = {
    False: "keep how each layer changes presets.",
    True: "every unlocked layer changes presets on each clip, and every clip gets a preset as clip presets says.",
}
_RESET_HELP = ("Removes every clip on the timeline.",)
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
    section: str | None = None,
    visible: Callable[[FormValues], bool] | None = None,
    vertical: bool = False,
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
        section=section,
        visible=visible,
        vertical=vertical,
    )


def _clips_label(count: int) -> str:
    return "1 clip" if count == 1 else f"{count} clips"


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
        has_role_presets: Callable[[], bool] | None = None,
        history: EditHistory | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._history = history if history is not None else EditHistory(session)
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._signals = signals
        self._on_notification = on_notification
        self._on_repopulate = on_repopulate
        self._has_role_presets = has_role_presets
        # Reset's last "layers after reset" choice, for this session.
        self._last_reset_layers = 0

    def _repopulate_options(self) -> tuple[TimelinePresetRepopulate, ...]:
        """Refill choices; clip roles only when the library tags any preset with a role."""
        if self._has_role_presets is not None and self._has_role_presets():
            return TIMELINE_PRESET_REPOPULATE_OPTIONS
        return tuple(
            option
            for option in TIMELINE_PRESET_REPOPULATE_OPTIONS
            if option != "cue roles"
        )

    def prompt(self, duration_sec: float) -> None:
        tl = self.session.timeline
        if tl.locked or self._refuse_locked_layers():
            return
        repopulate_options = self._repopulate_options()
        repopulate_current = (
            tl.timeline_preset_repopulate
            if tl.timeline_preset_repopulate in repopulate_options
            else DEFAULT_TIMELINE_PRESET_REPOPULATE
        )
        self._modal.prompt_form(
            FormSpec(
                title=_GENERATE_TITLE,
                fields=(
                    _choice_field(
                        "mode",
                        "mode",
                        TIMELINE_PRESET_MODE_OPTIONS,
                        tl.timeline_preset_mode,
                        timeline_preset_mode_display,
                        help=_MODE_HELP,
                        option_help=_MODE_OPTION_HELP,
                        section=_ARRANGEMENT_SECTION,
                    ),
                    _choice_field(
                        "density",
                        "density",
                        TIMELINE_PRESET_DENSITY_OPTIONS,
                        tl.timeline_preset_density,
                        timeline_preset_density_display,
                        help=_DENSITY_HELP,
                        section=_ARRANGEMENT_SECTION,
                    ),
                    _choice_field(
                        "conductor",
                        "conductor",
                        _CONDUCTOR_OPTIONS,
                        tl.timeline_preset_conductor,
                        timeline_preset_conductor_display,
                        help=_CONDUCTOR_HELP,
                        option_help=_CONDUCTOR_OPTION_HELP,
                        section=_ARRANGEMENT_SECTION,
                    ),
                    _choice_field(
                        "layer_opacity",
                        "layer opacity",
                        _ON_OFF,
                        tl.timeline_preset_full_opacity,
                        layer_opacity_display,
                        help=_LAYER_OPACITY_HELP,
                        option_help=_LAYER_OPACITY_OPTION_HELP,
                        section=_ARRANGEMENT_SECTION,
                    ),
                    _choice_field(
                        "cue_snap",
                        "snap to grid",
                        TIMELINE_PRESET_CUE_SNAP_OPTIONS,
                        tl.timeline_preset_cue_snap,
                        timeline_preset_cue_snap_display,
                        help=_CUE_SNAP_HELP,
                        option_help=_CUE_SNAP_OPTION_HELP,
                        section=_CUES_SECTION,
                    ),
                    _choice_field(
                        "song_marker_snap",
                        "snap to song markers",
                        TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS,
                        tl.timeline_preset_song_marker_snap,
                        timeline_preset_song_marker_snap_display,
                        help=_SONG_MARKER_SNAP_HELP,
                        section=_CUES_SECTION,
                    ),
                    _choice_field(
                        "timeline_cuts",
                        "cut type",
                        TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS,
                        tl.timeline_preset_timeline_cuts,
                        timeline_preset_timeline_cuts_display,
                        help=_TIMELINE_CUTS_HELP,
                        option_help=_TIMELINE_CUTS_OPTION_HELP,
                        section=_CUES_SECTION,
                    ),
                    _choice_field(
                        "change_presets",
                        "change presets",
                        _ON_OFF,
                        tl.timeline_preset_each_clip,
                        change_presets_display,
                        help=_CHANGE_PRESETS_HELP,
                        option_help=_CHANGE_PRESETS_OPTION_HELP,
                        section=_PRESETS_SECTION,
                    ),
                    _choice_field(
                        "repopulate",
                        "clip presets",
                        repopulate_options,
                        repopulate_current,
                        timeline_preset_repopulate_display,
                        help=_REPOPULATE_HELP,
                        option_help=_REPOPULATE_OPTION_HELP,
                        section=_PRESETS_SECTION,
                        vertical=True,
                    ),
                ),
                confirm_label="Generate",
                on_confirm=lambda values: self._confirm_generate(
                    values, duration_sec, repopulate_options
                ),
                info=lambda values: self._generate_info(
                    duration_sec,
                    each_clip=_ON_OFF[values["change_presets"]],
                    full_opacity=_ON_OFF[values["layer_opacity"]],
                ),
                help=_GENERATE_HELP,
            )
        )

    def _refuse_locked_layers(self) -> bool:
        """Name the locked layers whose clips hold presets. True when there are any."""
        reason = locked_each_clip_reason(self.session)
        if reason is None:
            return False
        self._notify(reason)
        return True

    def _generate_info(
        self,
        duration_sec: float,
        *,
        each_clip: bool = False,
        full_opacity: bool = False,
    ) -> str | None:
        session = self.session
        parts: list[str] = []
        count = self._clip_count(duration_sec)
        if count:
            parts.append(f"{_clips_label(count)} on the timeline")
        converting = self._layers_to_convert() if each_clip else []
        slots = [
            slot
            for slot in session.layer_z_order
            if (is_each_clip(session, slot) and session.layers[slot].preset_list)
            or slot in converting
        ]
        if slots:
            noun = "preset list" if len(slots) == 1 else "preset lists"
            parts.append(f"the {noun} of {layers_label(session, slots)}")
        notes = [f"replaces {' and '.join(parts)}"] if parts else []
        # What stays as it is after the layer options: locked layers always do.
        others = [
            slot
            for slot in session.layer_z_order
            if not is_each_clip(session, slot) and slot not in converting
        ]
        if others:
            notes.append(f"no preset changes on {layers_label(session, others)}")
        dim = [
            slot
            for slot in session.layer_z_order
            if session.layers[slot].opacity_pct < FULL_OPACITY_PCT
            and not (full_opacity and not session.layers[slot].locked)
        ]
        if dim:
            notes.append(f"{layers_label(session, dim)} below 100%")
        return f"({'; '.join(notes)})" if notes else None

    def _layers_to_convert(self) -> list[str]:
        """Unlocked layers whose presets do not yet change on each clip."""
        session = self.session
        return [
            slot
            for slot in session.layer_z_order
            if not session.layers[slot].locked and not is_each_clip(session, slot)
        ]

    def _set_up_layers(self) -> None:
        """Apply the dialog's layer opacity and change presets choices."""
        tl = self.session.timeline
        for slot in self.session.layer_z_order:
            layer = self.session.layers[slot]
            if layer.locked:
                continue
            if tl.timeline_preset_full_opacity:
                layer.opacity_pct = FULL_OPACITY_PCT
        if not tl.timeline_preset_each_clip:
            return
        for slot in self._layers_to_convert():
            layer = self.session.layers[slot]
            if layer.preset_switching_trigger == "off":
                # The preset chosen with switching off stays the layer's own.
                layer.layer_preset = layer.playlist.anchor
            layer.preset_switching_trigger = "timeline"
            layer.preset_switching = preset_switching_mode_for_trigger("timeline")

    def _clip_count(self, duration_sec: float) -> int:
        return sum(
            len(row_clips(self.session, slot, duration_sec))
            for slot in self.session.timeline.lanes
            if slot in self.session.layers
        )

    def _confirm_generate(
        self,
        values: FormValues,
        duration_sec: float,
        repopulate_options: Sequence[TimelinePresetRepopulate],
    ) -> None:
        if self._refuse_locked_layers():
            return
        tl = self.session.timeline
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
        tl.timeline_preset_repopulate = repopulate_options[values["repopulate"]]
        tl.timeline_preset_conductor = _CONDUCTOR_OPTIONS[values["conductor"]]
        tl.timeline_preset_mode = TIMELINE_PRESET_MODE_OPTIONS[values["mode"]]
        tl.timeline_preset_full_opacity = _ON_OFF[values["layer_opacity"]]
        tl.timeline_preset_each_clip = _ON_OFF[values["change_presets"]]
        before = self._history.begin("Generate timeline")
        try:
            self._apply(duration_sec)
            self._history.commit()
        except Exception as exc:
            # A failed generate must not end the session and lose unsaved work.
            traceback.print_exc()
            self._history.rollback(before)
            reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            self._notify(f"Generate timeline failed, timeline unchanged: {reason}")

    def prompt_reset(self, duration_sec: float) -> None:
        if self.session.timeline.locked or self._refuse_locked_layers():
            return
        count = self._clip_count(duration_sec)
        self._modal.prompt_form(
            FormSpec(
                title=_RESET_TITLE,
                info=lambda _values: f"(removes {_clips_label(count)})",
                fields=(
                    FormField(
                        "layers",
                        "layers after reset",
                        _RESET_LAYER_OPTIONS,
                        self._last_reset_layers,
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

    def _apply(self, duration_sec: float) -> None:
        if not self._bar_times:
            self._notify("No bars available; re-run separate")
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        grid = shift_bars_by_beats(
            self._bar_times,
            self._beat_times,
            self.session.timeline.bar_phase_offset,
        )
        if not grid:
            self._notify("No bars available; re-run separate")
            return
        tl = self.session.timeline
        slots = list(self.session.layer_z_order)
        markers = list(self.session.song_markers.markers)
        marker_times = [m.time for m in markers]
        rng = random.Random()
        builder_kwargs: dict = {
            "bar_times": grid,
            "song_markers": markers,
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
                beat_times=self._beat_times,
                transition_duration=self.session.pattern_mask.transition,
                **builder_kwargs,
            )
            message = "Generated pattern mask timeline"
        else:
            built = compose_layers_timeline(slots, duration_sec, rng, **builder_kwargs)
            message = "Generated timeline"
        built = {
            slot: copy_lane(built.get(slot, empty_lane())) for slot in slots
        }
        self._apply_cue_snap(built, grid)
        self._apply_song_marker_snap(built, marker_times, slots)
        self._apply_timeline_cuts(built, marker_times, tl.timeline_preset_timeline_cuts)
        self._clear_timeline_state()
        tl.enabled = True
        for slot in slots:
            tl.lanes[slot] = built[slot]
        self._set_up_layers()
        if self._on_repopulate is not None:
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

    def _cue_snap_grid(self, bar_grid: Sequence[float]) -> Sequence[float]:
        """The grid clip edges snap to; empty when snap to grid is off."""
        cue_snap = self.session.timeline.timeline_preset_cue_snap
        if cue_snap == "beats":
            return self._beat_times
        return bar_grid if cue_snap == "bars" else ()

    def _apply_cue_snap(
        self,
        lanes: dict[str, TimelineLane],
        bar_grid: Sequence[float],
    ) -> None:
        grid = self._cue_snap_grid(bar_grid)
        if not grid:
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
        if self._refuse_locked_layers():
            return
        self._last_reset_layers = values["layers"]
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
