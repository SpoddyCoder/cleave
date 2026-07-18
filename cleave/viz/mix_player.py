"""SDL audio playback for preloaded mix PCM."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import numpy as np
from pygame._sdl2 import AUDIO_F32, AudioDevice, get_audio_device_names

from cleave.extract import StemSource
from cleave.viz.transport_clock import TransportClock

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
else:
    from collections.abc import Sequence

FREQUENCY_HZ = 44100
NUM_CHANNELS = 2
DEFAULT_CHUNKSIZE = 4096
CLICK_DURATION_SEC = 0.005
CLICK_AMPLITUDE = 0.5
CLICK_ACCENT_AMPLITUDE = 0.85
CLICK_QUIET_AMPLITUDE = 0.28
CLICK_QUIET_FREQ_HZ = 900.0
CLICK_ACCENT_FREQ_HZ = 3200.0


def _make_click_sample(
    sample_rate: int,
    duration_sec: float = CLICK_DURATION_SEC,
    *,
    amplitude: float = CLICK_AMPLITUDE,
    frequency_hz: float = 1000.0,
) -> np.ndarray:
    n = max(1, int(sample_rate * duration_sec))
    t = np.arange(n, dtype=np.float32) / sample_rate
    envelope = np.exp(-t * 800.0, dtype=np.float32)
    tone = np.sin(2.0 * np.pi * frequency_hz * t, dtype=np.float32)
    return (amplitude * tone * envelope).astype(np.float32)


def _make_quiet_click_sample(sample_rate: int) -> np.ndarray:
    return _make_click_sample(
        sample_rate,
        amplitude=CLICK_QUIET_AMPLITUDE,
        frequency_hz=CLICK_QUIET_FREQ_HZ,
    )


def _make_accent_click_sample(sample_rate: int) -> np.ndarray:
    n = max(1, int(sample_rate * CLICK_DURATION_SEC))
    t = np.arange(n, dtype=np.float32) / sample_rate
    envelope = np.exp(-t * 1400.0, dtype=np.float32)
    ding = np.sin(2.0 * np.pi * CLICK_ACCENT_FREQ_HZ * t, dtype=np.float32)
    shimmer = np.sin(2.0 * np.pi * 73.0 * t, dtype=np.float32) * np.sin(
        2.0 * np.pi * 211.0 * t, dtype=np.float32
    )
    tone = ding + 0.45 * shimmer
    return (CLICK_ACCENT_AMPLITUDE * tone * envelope).astype(np.float32)


def _mix_click_into_stereo(
    out: np.ndarray,
    click: np.ndarray,
    *,
    offset_frames: int,
) -> None:
    if offset_frames < 0:
        return
    sample_offset = offset_frames * 2
    if sample_offset >= len(out):
        return
    click_samples = min(len(click), (len(out) - sample_offset) // 2)
    if click_samples <= 0:
        return
    for i in range(click_samples):
        sample = float(click[i])
        idx = sample_offset + i * 2
        out[idx] = min(1.0, max(-1.0, out[idx] + sample))
        out[idx + 1] = min(1.0, max(-1.0, out[idx + 1] + sample))


def estimate_output_latency_frames(
    obtained_chunksize: int | None,
    requested_chunksize: int,
) -> int:
    if obtained_chunksize is not None and obtained_chunksize > 0:
        return int(obtained_chunksize)
    return max(0, int(requested_chunksize))


def copy_stereo_pcm_chunk(
    pcm: np.ndarray,
    read_index: int,
    out: np.ndarray,
    *,
    total_frames: int,
) -> tuple[int, int]:
    """Fill interleaved stereo *out* from frame *read_index* in *pcm*.

    Returns ``(frames_written, new_read_index)``.
    """
    frames_requested = len(out) // 2
    frames_available = total_frames - read_index
    frames_written = min(frames_requested, max(0, frames_available))

    if frames_written > 0:
        start = read_index * 2
        end = (read_index + frames_written) * 2
        out[: frames_written * 2] = pcm[start:end]

    if frames_written < frames_requested:
        out[frames_written * 2 :] = 0.0

    return frames_written, read_index + frames_written


def copy_mono_pcm_chunk_as_stereo(
    pcm_mono: np.ndarray,
    read_index: int,
    out: np.ndarray,
    *,
    total_frames: int,
) -> tuple[int, int]:
    """Fill interleaved stereo *out* from mono *pcm_mono* at frame *read_index*.

    Returns ``(frames_written, new_read_index)``.
    """
    frames_requested = len(out) // 2
    frames_available = total_frames - read_index
    frames_written = min(frames_requested, max(0, frames_available))

    if frames_written > 0:
        mono = pcm_mono[read_index : read_index + frames_written]
        out[: frames_written * 2 : 2] = mono
        out[1 : frames_written * 2 : 2] = mono

    if frames_written < frames_requested:
        out[frames_written * 2 :] = 0.0

    return frames_written, read_index + frames_written


def _default_output_device() -> str:
    names = get_audio_device_names(False)
    return names[0] if names else ""


class MixPlayer:
    def __init__(
        self,
        pcm: np.ndarray,
        sample_rate: int = FREQUENCY_HZ,
        *,
        chunksize: int = DEFAULT_CHUNKSIZE,
    ) -> None:
        self._pcm = np.ascontiguousarray(pcm, dtype=np.float32)
        self._stem_pcm: dict[str, np.ndarray] = {}
        self._stem_channels: dict[str, int] = {}
        self._solo_source: StemSource | None = None
        self._sample_rate = sample_rate
        self._chunksize = chunksize
        self._total_frames = len(self._pcm) // NUM_CHANNELS
        self._lock = threading.Lock()
        self._read_index = 0
        self._clock = TransportClock(
            sample_rate=sample_rate,
            total_frames=self._total_frames,
            max_ahead_frames=chunksize,
            latency_frames=0,
        )
        self._clock.reanchor(0)
        self._device: AudioDevice | None = None
        self._callback: Callable[[AudioDevice, memoryview], None] | None = None
        self._click_schedule: tuple[tuple[float, bool], ...] | None = None
        self._click_only = False
        self._click_sample = _make_click_sample(sample_rate)
        self._click_accent_sample = _make_accent_click_sample(sample_rate)
        self._click_quiet_sample = _make_quiet_click_sample(sample_rate)
        self._next_click_index = 0

    def set_residual_delay_sec(self, sec: float) -> None:
        with self._lock:
            self._clock.set_residual_delay_sec(sec)

    def set_click_schedule(
        self,
        schedule: Sequence[tuple[float, bool]] | None,
    ) -> None:
        with self._lock:
            if schedule is None:
                self._click_schedule = None
                self._next_click_index = 0
                return
            self._click_schedule = tuple(
                (float(time_sec), bool(accented)) for time_sec, accented in schedule
            )
            self._next_click_index = 0

    def set_click_only(self, on: bool) -> None:
        with self._lock:
            self._click_only = on

    def _mix_click_schedule(
        self,
        out: np.ndarray,
        *,
        read_index: int,
        frames_written: int,
        click_only: bool,
    ) -> None:
        click_schedule = self._click_schedule
        if click_schedule is None or frames_written <= 0:
            return
        chunk_start_sec = read_index / self._sample_rate
        chunk_end_sec = (read_index + frames_written) / self._sample_rate
        while self._next_click_index < len(click_schedule):
            click_sec, accented = click_schedule[self._next_click_index]
            if click_sec >= chunk_end_sec:
                break
            if click_sec >= chunk_start_sec:
                if click_only:
                    click = (
                        self._click_accent_sample
                        if accented
                        else self._click_quiet_sample
                    )
                else:
                    click = self._click_sample
                offset_frames = int(
                    round((click_sec - chunk_start_sec) * self._sample_rate)
                )
                _mix_click_into_stereo(
                    out,
                    click,
                    offset_frames=offset_frames,
                )
            self._next_click_index += 1

    def _fill_output_buffer(self, out: np.ndarray) -> None:
        """Fill *out* from mix/stem PCM, mix beat clicks, and advance transport."""
        with self._lock:
            read_index = self._read_index
            click_only = self._click_only
            solo_source = None if click_only else self._solo_source
            stem_pcm = self._stem_pcm.get(solo_source) if solo_source else None
            stem_channels = (
                self._stem_channels.get(solo_source, 1) if solo_source else 1
            )
        if stem_pcm is not None:
            if stem_channels == 2:
                total_frames = len(stem_pcm) // 2
                frames_written, new_index = copy_stereo_pcm_chunk(
                    stem_pcm,
                    read_index,
                    out,
                    total_frames=total_frames,
                )
            else:
                total_frames = len(stem_pcm)
                frames_written, new_index = copy_mono_pcm_chunk_as_stereo(
                    stem_pcm,
                    read_index,
                    out,
                    total_frames=total_frames,
                )
        else:
            frames_written, new_index = copy_stereo_pcm_chunk(
                self._pcm,
                read_index,
                out,
                total_frames=self._total_frames,
            )
        if click_only:
            out.fill(0.0)
        with self._lock:
            self._mix_click_schedule(
                out,
                read_index=read_index,
                frames_written=frames_written,
                click_only=click_only,
            )
            self._read_index = new_index
            self._clock.reanchor(new_index)

    def set_stem_pcm(self, stems: dict[str, tuple[np.ndarray, int]]) -> None:
        self._stem_pcm = {
            name: np.ascontiguousarray(pcm, dtype=np.float32)
            for name, (pcm, _channels) in stems.items()
        }
        self._stem_channels = {name: channels for name, (_, channels) in stems.items()}

    def set_solo_source(self, source: StemSource | None) -> None:
        with self._lock:
            self._solo_source = source

    def start(self) -> None:
        if self._device is not None:
            return

        def callback(_device: AudioDevice, memview: memoryview) -> None:
            n_samples = len(memview) // 4
            out = np.frombuffer(memview, dtype=np.float32, count=n_samples)
            self._fill_output_buffer(out)

        self._callback = callback
        self._device = AudioDevice(
            devicename=_default_output_device(),
            iscapture=False,
            frequency=self._sample_rate,
            audioformat=AUDIO_F32,
            numchannels=NUM_CHANNELS,
            chunksize=self._chunksize,
            allowed_changes=0,
            callback=callback,
        )
        obtained = getattr(self._device, "chunksize", None)
        with self._lock:
            self._clock.set_latency_frames(
                estimate_output_latency_frames(obtained, self._chunksize)
            )
        self._device.pause(0)

    def stop(self) -> None:
        if self._device is None:
            return
        self._device.close()
        self._device = None
        self._callback = None

    def pause(self, on: bool) -> None:
        with self._lock:
            self._clock.set_paused(on)
        if self._device is not None:
            self._device.pause(1 if on else 0)

    def seek(self, position_sec: float) -> None:
        frame = int(max(0.0, position_sec) * self._sample_rate)
        frame = min(frame, self._total_frames)
        with self._lock:
            self._read_index = frame
            self._clock.reanchor(frame)

    def file_position_sec(self) -> float:
        with self._lock:
            return self._clock.file_position_sec()

    def audible_position_sec(self) -> float:
        with self._lock:
            return self._clock.audible_position_sec()

    def audible_position_zero_residual_sec(self) -> float:
        with self._lock:
            return self._clock.audible_position_zero_residual_sec()

    def finished(self) -> bool:
        with self._lock:
            return self._clock.file_position_frames() >= self._total_frames
