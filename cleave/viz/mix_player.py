"""SDL audio playback for preloaded mix PCM."""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from pygame._sdl2 import AUDIO_F32, AudioDevice, get_audio_device_names

from cleave.stems import StemSource
from cleave.viz.transport_clock import TransportClock

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
else:
    from collections.abc import Sequence

FREQUENCY_HZ = 44100
NUM_CHANNELS = 2
DEFAULT_CHUNKSIZE = 4096
# Pick an output endpoint by exact or substring name match.
AUDIO_DEVICE_ENV = "CLEAVE_AUDIO_DEVICE"
# Print the device list, the chosen endpoint, and mix PCM levels to stderr.
AUDIO_DEBUG_ENV = "CLEAVE_AUDIO_DEBUG"
CLICK_DURATION_SEC = 0.05
CLICK_ACCENT_DURATION_SEC = 0.18
CLICK_AMPLITUDE = 0.5
CLICK_ACCENT_AMPLITUDE = 1.0
CLICK_QUIET_AMPLITUDE = 0.75
CLICK_QUIET_FREQ_HZ = 900.0
# Middle C (C4).
CLICK_ACCENT_FREQ_HZ = 261.63
CLICK_ENVELOPE_DECAY = 70.0
CLICK_ACCENT_ENVELOPE_DECAY = 18.0


def _make_click_sample(
    sample_rate: int,
    duration_sec: float = CLICK_DURATION_SEC,
    *,
    amplitude: float = CLICK_AMPLITUDE,
    frequency_hz: float = 1000.0,
    envelope_decay: float = CLICK_ENVELOPE_DECAY,
) -> np.ndarray:
    n = max(1, int(sample_rate * duration_sec))
    t = np.arange(n, dtype=np.float32) / sample_rate
    envelope = np.exp(-t * envelope_decay, dtype=np.float32)
    tone = np.sin(2.0 * np.pi * frequency_hz * t, dtype=np.float32)
    return (amplitude * tone * envelope).astype(np.float32)


def _make_quiet_click_sample(sample_rate: int) -> np.ndarray:
    return _make_click_sample(
        sample_rate,
        CLICK_DURATION_SEC,
        amplitude=CLICK_QUIET_AMPLITUDE,
        frequency_hz=CLICK_QUIET_FREQ_HZ,
        envelope_decay=CLICK_ENVELOPE_DECAY,
    )


def _make_accent_click_sample(sample_rate: int) -> np.ndarray:
    return _make_click_sample(
        sample_rate,
        CLICK_ACCENT_DURATION_SEC,
        amplitude=CLICK_ACCENT_AMPLITUDE,
        frequency_hz=CLICK_ACCENT_FREQ_HZ,
        envelope_decay=CLICK_ACCENT_ENVELOPE_DECAY,
    )


def _mix_click_into_stereo(
    out: np.ndarray,
    click: np.ndarray,
    *,
    offset_frames: int,
) -> np.ndarray | None:
    """Mix mono *click* into interleaved stereo *out* at *offset_frames*.

    Returns any unmixed tail when *click* extends past the end of *out*.
    """
    if len(click) == 0:
        return None
    if offset_frames < 0:
        return click
    sample_offset = offset_frames * 2
    if sample_offset >= len(out):
        return click
    click_samples = min(len(click), (len(out) - sample_offset) // 2)
    if click_samples <= 0:
        return click
    for i in range(click_samples):
        sample = float(click[i])
        idx = sample_offset + i * 2
        out[idx] = min(1.0, max(-1.0, out[idx] + sample))
        out[idx + 1] = min(1.0, max(-1.0, out[idx + 1] + sample))
    if click_samples < len(click):
        return click[click_samples:]
    return None


def _merge_click_tails(
    existing: np.ndarray | None,
    tail: np.ndarray | None,
) -> np.ndarray | None:
    if tail is None or len(tail) == 0:
        return existing
    if existing is None or len(existing) == 0:
        return np.asarray(tail, dtype=np.float32).copy()
    n = max(len(existing), len(tail))
    merged = np.zeros(n, dtype=np.float32)
    merged[: len(existing)] += existing
    merged[: len(tail)] += tail
    return merged


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


class _SdlAudioSpec(ctypes.Structure):
    _fields_ = [
        ("freq", ctypes.c_int),
        ("format", ctypes.c_uint16),
        ("channels", ctypes.c_uint8),
        ("silence", ctypes.c_uint8),
        ("samples", ctypes.c_uint16),
        ("padding", ctypes.c_uint16),
        ("size", ctypes.c_uint32),
        ("callback", ctypes.c_void_p),
        ("userdata", ctypes.c_void_p),
    ]


_SDL_LIBRARY_PATTERNS = (
    ("SDL2.dll",)
    if sys.platform == "win32"
    else ("libSDL2-2*.dylib",)
    if sys.platform == "darwin"
    else ("libSDL2-2*.so*",)
)
_SDL_LIBRARY_FALLBACKS = (
    ("SDL2.dll",)
    if sys.platform == "win32"
    else ("libSDL2-2.0.dylib",)
    if sys.platform == "darwin"
    else ("libSDL2-2.0.so.0", "libSDL2.so")
)


def _sdl_library_paths() -> list[str]:
    """Candidate paths for the SDL library pygame itself loaded.

    A second SDL copy has its own subsystem state and reports the audio
    subsystem as uninitialized, so prefer the shared object shipped beside
    pygame (wheels bundle a hash-suffixed name) over a bare library name.
    """
    import pygame

    package = Path(pygame.__file__).resolve().parent
    search = [
        package,
        package.parent,
        package.parent / "pygame.libs",
        package / ".libs",
    ]
    paths: list[str] = []
    for directory in search:
        for pattern in _SDL_LIBRARY_PATTERNS:
            paths.extend(sorted(str(p) for p in directory.glob(pattern)))
    paths.extend(_SDL_LIBRARY_FALLBACKS)
    return paths


def sdl_default_output_device() -> str:
    """Endpoint name SDL reports as the system default output, or ``""``.

    ``pygame._sdl2.AudioDevice`` requires a non-empty device name, so it cannot
    ask SDL for the default the way ``SDL_OpenAudioDevice(NULL, ...)`` does.
    Read the default straight from the already-loaded SDL library instead.
    Returns ``""`` whenever SDL cannot answer; callers fall back to the
    enumerated device list.
    """
    for path in _sdl_library_paths():
        try:
            lib = ctypes.CDLL(path)
            get_info = lib.SDL_GetDefaultAudioInfo
        except (OSError, AttributeError):
            continue
        get_info.restype = ctypes.c_int
        get_info.argtypes = [
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(_SdlAudioSpec),
            ctypes.c_int,
        ]
        name_ptr = ctypes.c_char_p()
        spec = _SdlAudioSpec()
        if get_info(ctypes.byref(name_ptr), ctypes.byref(spec), 0) != 0:
            continue
        if not name_ptr.value:
            continue
        default = name_ptr.value.decode("utf-8", "replace")
        try:
            sdl_free = lib.SDL_free
        except AttributeError:
            sdl_free = None
        if sdl_free is not None:
            sdl_free.argtypes = [ctypes.c_void_p]
            sdl_free.restype = None
            sdl_free(name_ptr)
        return default
    return ""


def select_output_device(
    names: Sequence[str],
    *,
    requested: str = "",
    sdl_default: str = "",
) -> str:
    """Choose an SDL output endpoint from *names*.

    An explicit *requested* name wins (exact, then case-insensitive substring).
    Otherwise prefer the system default; enumeration order is arbitrary on
    Windows WASAPI, so ``names[0]`` is a last resort, not the default endpoint.
    """
    if requested:
        for name in names:
            if name == requested:
                return name
        lowered = requested.lower()
        for name in names:
            if lowered in name.lower():
                return name
        return requested
    if sdl_default and sdl_default in names:
        return sdl_default
    return names[0] if names else ""


def pcm_level_summary(pcm: np.ndarray) -> tuple[float, float]:
    """Peak and RMS amplitude of *pcm* (``(0.0, 0.0)`` when empty)."""
    if pcm.size == 0:
        return 0.0, 0.0
    peak = float(np.max(np.abs(pcm)))
    rms = float(np.sqrt(np.mean(np.square(pcm, dtype=np.float64))))
    return peak, rms


def audio_debug_lines(
    *,
    names: Sequence[str],
    requested: str,
    sdl_default: str,
    chosen: str,
    sample_rate: int,
    chunksize: int,
    total_frames: int,
    peak: float,
    rms: float,
) -> list[str]:
    """Lines describing device selection and mix PCM levels."""
    lines = [
        f"audio: devices={len(names)}",
        *(f"audio:   [{i}] {name}" for i, name in enumerate(names)),
        f"audio: sdl default={sdl_default or '<unknown>'}",
        f"audio: {AUDIO_DEVICE_ENV}={requested or '<unset>'}",
        f"audio: chosen={chosen or '<sdl default>'}",
        f"audio: request rate={sample_rate} channels={NUM_CHANNELS} "
        f"chunksize={chunksize}",
        f"audio: mix frames={total_frames} "
        f"duration={total_frames / sample_rate:.1f}s "
        f"peak={peak:.6f} rms={rms:.6f}",
    ]
    return lines


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
        self._click_tail: np.ndarray | None = None

    def set_residual_latency_sec(self, sec: float) -> None:
        with self._lock:
            self._clock.set_residual_latency_sec(sec)

    def set_click_schedule(
        self,
        schedule: Sequence[tuple[float, bool]] | None,
    ) -> None:
        with self._lock:
            if schedule is None:
                self._click_schedule = None
                self._next_click_index = 0
                self._click_tail = None
                return
            self._click_schedule = tuple(
                (float(time_sec), bool(accented)) for time_sec, accented in schedule
            )
            self._next_click_index = 0
            self._click_tail = None

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
        if frames_written <= 0:
            return
        if self._click_tail is not None:
            self._click_tail = _mix_click_into_stereo(
                out,
                self._click_tail,
                offset_frames=0,
            )
        click_schedule = self._click_schedule
        if click_schedule is None:
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
                tail = _mix_click_into_stereo(
                    out,
                    click,
                    offset_frames=offset_frames,
                )
                self._click_tail = _merge_click_tails(self._click_tail, tail)
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
        names = get_audio_device_names(False)
        requested = os.environ.get(AUDIO_DEVICE_ENV, "").strip()
        sdl_default = sdl_default_output_device()
        devicename = select_output_device(
            names, requested=requested, sdl_default=sdl_default
        )
        if os.environ.get(AUDIO_DEBUG_ENV, "").strip():
            peak, rms = pcm_level_summary(self._pcm)
            for line in audio_debug_lines(
                names=names,
                requested=requested,
                sdl_default=sdl_default,
                chosen=devicename,
                sample_rate=self._sample_rate,
                chunksize=self._chunksize,
                total_frames=self._total_frames,
                peak=peak,
                rms=rms,
            ):
                print(line, file=sys.stderr, flush=True)
        self._device = AudioDevice(
            devicename=devicename,
            iscapture=False,
            frequency=self._sample_rate,
            audioformat=AUDIO_F32,
            numchannels=NUM_CHANNELS,
            chunksize=self._chunksize,
            allowed_changes=0,
            callback=callback,
        )
        obtained = getattr(self._device, "chunksize", None)
        if os.environ.get(AUDIO_DEBUG_ENV, "").strip():
            print(f"audio: opened chunksize={obtained}", file=sys.stderr, flush=True)
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
            self._click_tail = None

    def file_position_sec(self) -> float:
        with self._lock:
            return self._clock.file_position_sec()

    def audible_position_sec(self) -> float:
        with self._lock:
            return self._clock.audible_position_sec()

    def audible_position_zero_residual_latency_sec(self) -> float:
        with self._lock:
            return self._clock.audible_position_zero_residual_latency_sec()

    def finished(self) -> bool:
        with self._lock:
            return self._clock.file_position_frames() >= self._total_frames
