"""Run Demucs stem separation and write stem wavs into a Cleave project."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from cleave.config import ensure_project_viz_config
from cleave.open_target import AUDIO_SUFFIXES, UNSUPPORTED_AUDIO_FORMAT
from cleave.stems import STEM_SOURCES, StemSource, stem_paths, stems_dir
from cleave.paths import (
    is_frozen,
    model_cache_dir,
    project_dir,
    project_slug,
    resolve_project,
)
from cleave.model_weights import demucs_weight_spec, ensure_weight_files
from cleave.project import load_manifest, manifest_path, mix_path, write_manifest
from cleave.signals import SIGNALS_VERSION


def project_stems_complete(project_dir: Path) -> bool:
    """Return True when every stem wav from :func:`stem_paths` exists."""
    paths = stem_paths(project_dir)
    return all(path.is_file() for path in paths.values())


def signals_complete(project_dir: Path) -> bool:
    """Return True when ``signals.json`` exists at the current schema version."""
    path = project_dir / "signals.json"
    if not path.is_file():
        return False
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    return data.get("version") == SIGNALS_VERSION


def signals_beat_detection_stem(project_dir: Path) -> StemSource | None:
    """Return stored ``beat_detection_stem`` from ``signals.json``, or None."""
    path = project_dir / "signals.json"
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("beat_detection_stem")
    if isinstance(raw, str) and raw in STEM_SOURCES:
        return cast(StemSource, raw)
    return None


def beat_detection_stem_mismatch(
    project_dir: Path, requested: StemSource | None
) -> bool:
    """True when an explicit stem differs from stored (missing reads as ``full_mix``)."""
    if requested is None or not signals_complete(project_dir):
        return False
    stored = signals_beat_detection_stem(project_dir)
    effective = stored if stored is not None else "full_mix"
    return requested != effective


def resolve_beat_detection_stem(
    project_dir: Path, requested: StemSource | None
) -> StemSource:
    """Explicit CLI value, else stored, else ``full_mix``."""
    if requested is not None:
        return requested
    stored = signals_beat_detection_stem(project_dir)
    return stored if stored is not None else "full_mix"


def resolve_separate_target(path_or_slug: Path | str) -> tuple[Path, Path]:
    """Resolve *path_or_slug* to ``(project_dir, audio_path)``.

    * Audio file: slug from filename stem, project under ``projects/<slug>/``.
    * Project slug or path: existing project directory and its mix copy.
    """
    raw = Path(path_or_slug)
    if raw.is_file():
        audio_path = raw.resolve()
        _require_supported_audio(audio_path)
        slug = project_slug(audio_path)
        return project_dir(slug).resolve(), audio_path
    project = resolve_project(path_or_slug)
    return project, mix_path(project)


STEM_SPLIT_MISSING_FROZEN = (
    "Stem split is not in this Windows build. "
    "Copy a project from Linux and play that instead."
)
STEM_SPLIT_MISSING_CHECKOUT = (
    "Stem split requires PyTorch and Demucs, which are not installed."
)
TORCHCODEC_AUDIO_IO_ERROR = (
    "Could not finish stem split: audio I/O tried to load TorchCodec, "
    "which this Windows build does not ship."
)


def stem_split_available() -> bool:
    """Return True when PyTorch can be imported (Demucs/analyse extra)."""
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def stem_split_missing_message() -> str:
    """Short error when stem split is required but the extra is missing."""
    if is_frozen():
        return STEM_SPLIT_MISSING_FROZEN
    return STEM_SPLIT_MISSING_CHECKOUT


def require_stem_split() -> None:
    """Raise :class:`RuntimeError` when Demucs/analyse extras are missing."""
    if not stem_split_available():
        raise RuntimeError(stem_split_missing_message())


def _validate_audio_path(audio_path: Path) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if not audio_path.is_file():
        raise ValueError(f"not a file: {audio_path}")


def _require_supported_audio(audio_path: Path) -> None:
    """Reject suffixes outside :data:`cleave.open_target.AUDIO_SUFFIXES`."""
    if audio_path.suffix.lower() not in AUDIO_SUFFIXES:
        raise ValueError(f"{UNSUPPORTED_AUDIO_FORMAT}: {audio_path.name}")


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _stored_mix_path(project: Path) -> Path | None:
    if not manifest_path(project).is_file():
        return None
    try:
        return mix_path(project)
    except (OSError, ValueError):
        return None


def _is_stored_project_mix(audio_path: Path, project: Path) -> bool:
    """True when *audio_path* is the mix already recorded for *project*."""
    stored = _stored_mix_path(project)
    return stored is not None and _same_file(audio_path, stored)


def _mix_slug(audio_path: Path, project: Path) -> str:
    if manifest_path(project).is_file():
        return load_manifest(project).slug
    return project_slug(audio_path)


def _normalized_mix_path(project: Path, slug: str) -> Path:
    return project / f"{slug}.wav"


def _needs_audio_prepare(audio_path: Path, project: Path) -> bool:
    """True when *audio_path* must be copied or decoded into the project mix."""
    if _is_stored_project_mix(audio_path, project):
        return False
    dest = _normalized_mix_path(project, _mix_slug(audio_path, project))
    return not _same_file(audio_path, dest)


def _partial_mix_path(dest: Path) -> Path:
    return dest.parent / f".{dest.stem}.ingest.wav"


def _cleanup_partial(tmp: Path) -> None:
    try:
        if tmp.is_file():
            tmp.unlink()
    except OSError:
        pass


def _replace_partial(tmp: Path, dest: Path) -> None:
    try:
        if not tmp.is_file():
            raise RuntimeError(f"audio prepare did not write {dest.name}")
        os.replace(tmp, dest)
    except Exception:
        _cleanup_partial(tmp)
        raise


def _copy_wav_atomic(source: Path, dest: Path) -> None:
    """Copy a WAV into *dest* without re-encoding. Leave *dest* untouched on failure."""
    if _same_file(source, dest):
        return
    tmp = _partial_mix_path(dest)
    try:
        shutil.copy2(source, tmp)
        _replace_partial(tmp, dest)
    except Exception:
        _cleanup_partial(tmp)
        raise


def _ffmpeg_to_wav(source: Path, dest: Path) -> None:
    """Decode *source* to 16-bit PCM WAV at *dest*. Native sample rate, no video."""
    from cleave.ffmpeg import ffmpeg_executable

    ffmpeg = ffmpeg_executable()
    tmp = _partial_mix_path(dest)
    cmd = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-acodec",
        "pcm_s16le",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        _cleanup_partial(tmp)
        err = (exc.stderr or b"").decode("utf-8", "replace").strip()
        detail = f": {err}" if err else ""
        raise RuntimeError(
            f"ffmpeg failed to convert {source} with {ffmpeg}{detail}"
        ) from exc
    except Exception:
        _cleanup_partial(tmp)
        raise
    try:
        _replace_partial(tmp, dest)
    except RuntimeError as exc:
        raise RuntimeError(
            f"ffmpeg failed to convert {source} with {ffmpeg}"
        ) from exc


_PREPARE_MESSAGE = "Preparing audio..."


def _prepare_project_mix(
    audio_path: Path,
    project: Path,
    *,
    on_progress: Callable[[str, float | None], None] | None = None,
) -> tuple[Path, Path]:
    """Return ``(mix_for_demucs, original_path)``.

    A mix already stored in the project is used in place, including an older
    non-wav filename. A new WAV is copied to ``<project>/<slug>.wav``. Any
    other accepted format is decoded to that WAV. ``original_path`` stays the
    user's source file, or the path already recorded when the mix is reused.
    """
    if _is_stored_project_mix(audio_path, project):
        return audio_path, Path(load_manifest(project).original_path)

    _require_supported_audio(audio_path)
    dest = _normalized_mix_path(project, _mix_slug(audio_path, project))
    if _same_file(audio_path, dest):
        return dest, audio_path

    if on_progress is not None:
        on_progress(_PREPARE_MESSAGE, None)
    project.mkdir(parents=True, exist_ok=True)
    if audio_path.suffix.lower() == ".wav":
        _copy_wav_atomic(audio_path, dest)
    else:
        _ffmpeg_to_wav(audio_path, dest)
    return dest, audio_path


def _load_demucs_track(audio_path: Path, audio_channels: int, samplerate: int):
    """Load mix audio as a ``(channels, samples)`` float tensor for Demucs.

    Frozen: decode with the sidecar from :func:`cleave.ffmpeg.ffmpeg_executable`
    (Demucs 4.0.1 ``load_track`` also shells out to ``ffprobe``, which we do
    not ship). Checkout: ``demucs.separate.load_track``.
    """
    if is_frozen():
        return _load_track_with_sidecar_ffmpeg(
            audio_path, audio_channels, samplerate
        )
    from demucs.separate import load_track

    return load_track(audio_path, audio_channels, samplerate)


def _load_track_with_sidecar_ffmpeg(
    audio_path: Path, audio_channels: int, samplerate: int
):
    """Decode *audio_path* with sidecar ffmpeg into a Demucs input tensor."""
    import numpy as np
    import torch

    from cleave.ffmpeg import ffmpeg_executable

    ffmpeg = ffmpeg_executable()
    cmd = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "f32le",
        "-ac",
        str(audio_channels),
        "-ar",
        str(samplerate),
        "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", "replace").strip()
        detail = f": {err}" if err else ""
        raise RuntimeError(
            f"demucs failed to load {audio_path} with {ffmpeg}{detail}"
        ) from exc
    pcm = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    if pcm.size == 0 or pcm.size % audio_channels != 0:
        raise RuntimeError(f"demucs failed to load {audio_path} with {ffmpeg}")
    return torch.from_numpy(pcm).view(-1, audio_channels).t().contiguous()


def _looks_like_torchcodec_error(exc: BaseException) -> bool:
    """True when *exc* (or a chained cause) names TorchCodec."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = f"{type(current).__name__}: {current}".lower()
        if "torchcodec" in text or "libtorchcodec" in text:
            return True
        current = current.__cause__ or current.__context__
    return False


def _reraise_torchcodec(exc: BaseException) -> None:
    """Re-raise TorchCodec failures with :data:`TORCHCODEC_AUDIO_IO_ERROR`."""
    if _looks_like_torchcodec_error(exc):
        raise RuntimeError(TORCHCODEC_AUDIO_IO_ERROR) from exc


_SEP_MESSAGE = "Separating stems..."
_SEP_FRAC_MODEL = 0.05
_SEP_FRAC_TRACK = 0.10
_SEP_FRAC_APPLY_END = 0.90


def _report_separation(
    on_progress: Callable[[str, float | None], None] | None,
    fraction: float,
) -> None:
    if on_progress is not None:
        on_progress(_SEP_MESSAGE, fraction)


@contextmanager
def _intercept_demucs_tqdm(
    on_progress: Callable[[str, float | None], None] | None,
    message: str,
    frac_start: float,
    frac_end: float,
) -> Iterator[None]:
    """Redirect Demucs ``apply_model`` tqdm into the loading bar."""
    if on_progress is None:
        yield
        return

    import tqdm as tqdm_mod

    original = tqdm_mod.tqdm
    frac_range = frac_end - frac_start
    last_frac = [frac_start]

    class _ProgressTqdm:
        """Drop-in for ``tqdm.tqdm`` that forwards progress to the loading bar."""

        def __init__(self, iterable=None, *args: object, **kwargs: object) -> None:
            self._iterable = iterable
            self.total = kwargs.get("total")
            if self.total is None and iterable is not None:
                try:
                    self.total = len(iterable)
                except TypeError:
                    pass
            self.n = 0

        def __iter__(self):  # type: ignore[override]
            if self._iterable is None:
                return
            for item in self._iterable:
                self.n += 1
                if self.total and self.total > 0:
                    frac = frac_start + min(1.0, self.n / self.total) * frac_range
                    if frac - last_frac[0] >= 0.01 or self.n >= self.total:
                        last_frac[0] = frac
                        on_progress(message, min(frac, frac_end))
                yield item

        def update(self, n: int = 1) -> None:
            self.n += n

        def close(self) -> None:
            pass

        def __enter__(self):  # type: ignore[override]
            return self

        def __exit__(self, *exc: object) -> None:
            pass

    tqdm_mod.tqdm = _ProgressTqdm  # type: ignore[assignment]
    try:
        yield
    finally:
        tqdm_mod.tqdm = original  # type: ignore[assignment]


def _save_stem_wav(wav, dest: Path, samplerate: int) -> None:
    """Write a Demucs source tensor as 16-bit PCM wav via soundfile.

    Avoids Demucs torchaudio wav export, which loads TorchCodec
    FFmpeg DLLs the freeze does not ship. Demucs layout is
    ``(channels, samples)``; soundfile wants ``(samples, channels)``.
    """
    import numpy as np
    import soundfile as sf

    array = np.asarray(wav.detach().cpu().numpy(), dtype=np.float32)
    if array.ndim == 2:
        array = array.T
    peak = float(np.abs(array).max()) if array.size else 0.0
    if peak > 0.0:
        array = array / max(1.01 * peak, 1.0)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), array, samplerate, subtype="PCM_16")


def _write_demucs_stems(
    audio_path: Path,
    dest_paths: Mapping[str, Path],
    *,
    model: str,
    on_progress: Callable[[str, float | None], None] | None = None,
) -> None:
    """Load *model* in-process and write stem wavs into *dest_paths*.

    Uses ``demucs.pretrained.get_model`` and ``demucs.apply.apply_model``.
    Imports stay lazy so play/render never load torch. Frozen: sidecar
    ffmpeg is on PATH for the Demucs call, and mix load uses that binary
    rather than Demucs ``load_track`` (which also needs ``ffprobe``).
    Stem wavs are written with soundfile, not Demucs torchaudio export
    (TorchCodec).
    """
    from cleave.ffmpeg import sidecar_ffmpeg_on_path

    with sidecar_ffmpeg_on_path():
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model

        torch.hub.set_dir(str(model_cache_dir()))
        ensure_weight_files(demucs_weight_spec(model), on_progress=on_progress)
        _report_separation(on_progress, 0.0)
        device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            model_obj = get_model(model)
            model_obj.cpu()
            model_obj.eval()
            _report_separation(on_progress, _SEP_FRAC_MODEL)
            wav = _load_demucs_track(
                audio_path, model_obj.audio_channels, model_obj.samplerate
            )
            _report_separation(on_progress, _SEP_FRAC_TRACK)
            ref = wav.mean(0)
            wav -= ref.mean()
            wav /= ref.std()
            with _intercept_demucs_tqdm(
                on_progress, _SEP_MESSAGE, _SEP_FRAC_TRACK, _SEP_FRAC_APPLY_END
            ):
                sources = apply_model(
                    model_obj,
                    wav[None],
                    device=device,
                    shifts=1,
                    split=True,
                    overlap=0.25,
                    progress=True,
                )[0]
            sources *= ref.std()
            sources += ref.mean()
        except FileNotFoundError:
            raise
        except SystemExit as exc:
            raise RuntimeError(f"demucs failed to load {audio_path}") from exc
        except Exception as exc:
            _reraise_torchcodec(exc)
            raise RuntimeError(f"demucs failed for {audio_path}") from exc

        _report_separation(on_progress, _SEP_FRAC_APPLY_END)
        try:
            for index, name in enumerate(model_obj.sources):
                dest = dest_paths.get(name)
                if dest is None:
                    continue
                _save_stem_wav(sources[index], dest, model_obj.samplerate)
        except Exception as exc:
            _reraise_torchcodec(exc)
            raise RuntimeError(f"demucs failed to write stems for {audio_path}") from exc

        _report_separation(on_progress, 1.0)
        missing_src = [name for name, dst in dest_paths.items() if not dst.is_file()]
        if missing_src:
            raise RuntimeError(
                f"demucs output missing stem files: {', '.join(missing_src)}"
            )


def _run_demucs(
    audio_path: Path,
    project_dir: Path,
    *,
    high_quality: bool,
    force: bool,
    on_progress: Callable[[str, float | None], None] | None = None,
) -> None:
    """Separate *audio_path* with Demucs and write stems into *project_dir*."""
    audio_path = Path(audio_path)
    _validate_audio_path(audio_path)

    if manifest_path(project_dir).is_file():
        slug = load_manifest(project_dir).slug
    else:
        slug = project_slug(audio_path)

    model = "htdemucs_ft" if high_quality else "htdemucs"

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "renders").mkdir(exist_ok=True)
    stems_dir(project_dir).mkdir(exist_ok=True)

    mix_for_demucs, original = _prepare_project_mix(
        audio_path,
        project_dir,
        on_progress=on_progress,
    )
    mix_filename = mix_for_demucs.name

    if force and manifest_path(project_dir).is_file():
        old_manifest = load_manifest(project_dir)
        if old_manifest.mix_filename != mix_filename:
            stale = project_dir / old_manifest.mix_filename
            if stale.is_file() and not _same_file(stale, mix_for_demucs):
                stale.unlink()

    write_manifest(
        project_dir,
        slug=slug,
        mix_filename=mix_filename,
        original_path=original,
        demucs_model=model,
    )

    _write_demucs_stems(
        mix_for_demucs,
        stem_paths(project_dir),
        model=model,
        on_progress=on_progress,
    )


def run_separate(
    target: Path | str,
    *,
    high_quality: bool = False,
    force: bool = False,
    beat_detection_stem: StemSource | None = None,
    on_progress: Callable[[str, float | None], None] | None = None,
) -> Path:
    """Separate and/or analyse a Cleave project from an audio file or project slug.

    *beat_detection_stem* is ``None`` when the CLI flag was omitted.
    *on_progress* receives ``(message, fraction)``; ``fraction`` is ``None`` for
    named waits. When omitted, existing stdout messages are unchanged.
    """
    project_dir, audio_path = resolve_separate_target(target)
    ensure_project_viz_config(project_dir)

    stems_complete = project_stems_complete(project_dir)
    signals_done = signals_complete(project_dir)
    stem_mismatch = beat_detection_stem_mismatch(project_dir, beat_detection_stem)

    if stems_complete and signals_done and not force and not stem_mismatch:
        return project_dir

    run_demucs = force or not stems_complete
    need_analyse = run_demucs or not signals_done or stem_mismatch
    if need_analyse:
        require_stem_split()

    if run_demucs:
        if on_progress is not None:
            if _needs_audio_prepare(audio_path, project_dir):
                on_progress(_PREPARE_MESSAGE, None)
            else:
                on_progress("Separating stems...", None)
        _run_demucs(
            audio_path,
            project_dir,
            high_quality=high_quality,
            force=force,
            on_progress=on_progress,
        )

    if need_analyse:
        from cleave.analyse import run_analyse

        source = resolve_beat_detection_stem(project_dir, beat_detection_stem)
        if on_progress is not None:
            on_progress("Extracting signals...", None)
        else:
            print(
                "Extracting signals (may take a while on longer tracks)...",
                flush=True,
            )
        run_analyse(
            project_dir,
            high_quality=high_quality,
            beat_detection_stem=source,
            on_progress=on_progress,
        )

    return project_dir
