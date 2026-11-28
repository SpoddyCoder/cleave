"""Tests for the pattern mask transition, counted in beats, bars, or time."""

from __future__ import annotations

from pathlib import Path

from cleave.pattern_mask_transition import transition_seconds
from cleave.signals import Signals
from cleave.song_tempo import SongTempo, song_tempo_from_signals
from cleave.viz.pattern_mask_controls import PatternMaskControls
from cleave.viz.row_specs.pattern_mask import transition_display
from cleave.viz.session import TuningSession

_TEMPO = SongTempo(beat_sec=0.5, bar_sec=2.0)


def _controls() -> PatternMaskControls:
    session = TuningSession(layer_z_order=[])
    session.song_tempo = _TEMPO
    return PatternMaskControls(session)


def test_default_transition_is_one_beat() -> None:
    pm = TuningSession(layer_z_order=[]).pattern_mask
    assert (pm.transition_unit, pm.transition) == ("beats", 1.0)


def test_transition_seconds_follow_the_tempo() -> None:
    assert transition_seconds(0.25, "beats", _TEMPO) == 0.125
    assert transition_seconds(2.0, "bars", _TEMPO) == 4.0
    assert transition_seconds(1.5, "seconds", _TEMPO) == 1.5


def test_beats_step_through_quarter_and_half_beats() -> None:
    controls = _controls()
    pm = controls.session.pattern_mask
    seen = []
    for _ in range(4):
        controls.step_transition(forward=False, large=False)
        seen.append(pm.transition)
    assert seen == [0.5, 0.25, 0.0, 0.0]
    controls.step_transition(forward=True, large=True)
    assert pm.transition == 0.25


def test_seconds_step_by_tenths_and_whole_seconds() -> None:
    controls = _controls()
    pm = controls.session.pattern_mask
    controls.set_transition_unit("seconds")
    assert pm.transition == 0.5
    controls.step_transition(forward=True, large=False)
    assert pm.transition == 0.6
    controls.step_transition(forward=True, large=True)
    assert pm.transition == 1.6


def test_switching_unit_keeps_the_length() -> None:
    controls = _controls()
    pm = controls.session.pattern_mask
    pm.transition = 4.0
    controls.set_transition_unit("bars")
    assert (pm.transition_unit, pm.transition) == ("bars", 1.0)
    controls.set_transition_unit("seconds")
    assert pm.transition == 2.0
    controls.step_transition_unit(delta=-2)
    assert (pm.transition_unit, pm.transition) == ("beats", 4.0)


def test_transition_display() -> None:
    assert transition_display(0.25, "beats") == "1/4 beat"
    assert transition_display(0.5, "bars") == "1/2 bar"
    assert transition_display(1.0, "beats") == "1 beat"
    assert transition_display(2.0, "bars") == "2 bars"
    assert transition_display(0.0, "beats") == "0 (instant)"
    assert transition_display(1.5, "seconds") == "1.5s"


def test_song_tempo_from_signals() -> None:
    signals = Signals(
        sample_rate_hz=44100.0,
        duration_sec=8.0,
        path=Path("signals.json"),
        stems={},
        beat_times=tuple(i * 0.4 for i in range(20)),
        downbeat_times=tuple(i * 1.6 for i in range(5)),
    )
    tempo = song_tempo_from_signals(signals)
    assert abs(tempo.beat_sec - 0.4) < 1e-9
    assert abs(tempo.bar_sec - 1.6) < 1e-9
    assert song_tempo_from_signals(None) == SongTempo()
