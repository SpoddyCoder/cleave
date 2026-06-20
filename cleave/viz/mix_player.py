"""SDL audio playback for preloaded mix PCM."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import numpy as np
from pygame._sdl2 import AUDIO_F32, AudioDevice, get_audio_device_names

from cleave.extract import StemSource

if TYPE_CHECKING:
    from collections.abc import Callable

FREQUENCY_HZ = 44100
NUM_CHANNELS = 2
DEFAULT_CHUNKSIZE = 4096


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
        self._solo_source: StemSource | None = None
        self._sample_rate = sample_rate
        self._chunksize = chunksize
        self._total_frames = len(self._pcm) // NUM_CHANNELS
        self._lock = threading.Lock()
        self._read_index = 0
        self._samples_played = 0
        self._device: AudioDevice | None = None
        self._callback: Callable[[AudioDevice, memoryview], None] | None = None

    def set_stem_pcm(self, stems: dict[str, np.ndarray]) -> None:
        self._stem_pcm = {
            name: np.ascontiguousarray(pcm, dtype=np.float32)
            for name, pcm in stems.items()
        }

    def set_solo_source(self, source: StemSource | None) -> None:
        with self._lock:
            self._solo_source = source

    def start(self) -> None:
        if self._device is not None:
            return

        def callback(_device: AudioDevice, memview: memoryview) -> None:
            n_samples = len(memview) // 4
            out = np.frombuffer(memview, dtype=np.float32, count=n_samples)
            with self._lock:
                read_index = self._read_index
                solo_source = self._solo_source
                stem_pcm = (
                    self._stem_pcm.get(solo_source) if solo_source else None
                )
            if stem_pcm is not None:
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
            with self._lock:
                self._read_index = new_index
                self._samples_played = new_index

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
        self._device.pause(0)

    def stop(self) -> None:
        if self._device is None:
            return
        self._device.close()
        self._device = None
        self._callback = None

    def pause(self, on: bool) -> None:
        if self._device is not None:
            self._device.pause(1 if on else 0)

    def seek(self, position_sec: float) -> None:
        frame = int(max(0.0, position_sec) * self._sample_rate)
        frame = min(frame, self._total_frames)
        with self._lock:
            self._read_index = frame
            self._samples_played = frame

    def current_sec(self) -> float:
        with self._lock:
            return self._samples_played / self._sample_rate

    def finished(self) -> bool:
        with self._lock:
            return self._samples_played >= self._total_frames
