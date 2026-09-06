"""Run Demucs stem separation and write stem wavs into a Cleave project."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typing import Mapping, cast

from cleave.config import ensure_project_viz_config
from cleave.stems import STEM_SOURCES, StemSource, stem_paths, stems_dir
from cleave.paths import (
    is_frozen,
    model_cache_dir,
    project_dir,
    project_slug,
    resolve_project,
)
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


def _write_demucs_stems(
    audio_path: Path,
    dest_paths: Mapping[str, Path],
    *,
    model: str,
) -> None:
    """Load *model* in-process and write stem wavs into *dest_paths*.

    Uses ``demucs.pretrained.get_model`` and ``demucs.apply.apply_model``.
    Imports stay lazy so play/render never load torch.
    """
    import torch
    from demucs.apply import apply_model
    from demucs.audio import save_audio
    from demucs.pretrained import get_model
    from demucs.separate import load_track

    torch.hub.set_dir(str(model_cache_dir()))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        model_obj = get_model(model)
        model_obj.cpu()
        model_obj.eval()
        wav = load_track(audio_path, model_obj.audio_channels, model_obj.samplerate)
        ref = wav.mean(0)
        wav -= ref.mean()
        wav /= ref.std()
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
    except SystemExit as exc:
        raise RuntimeError(f"demucs failed to load {audio_path}") from exc
    except Exception as exc:
        raise RuntimeError(f"demucs failed for {audio_path}") from exc

    for index, name in enumerate(model_obj.sources):
        dest = dest_paths.get(name)
        if dest is None:
            continue
        save_audio(sources[index], str(dest), samplerate=model_obj.samplerate)

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
) -> None:
    """Separate *audio_path* with Demucs and write stems into *project_dir*."""
    audio_path = Path(audio_path)
    _validate_audio_path(audio_path)

    if manifest_path(project_dir).is_file():
        slug = load_manifest(project_dir).slug
    else:
        slug = project_slug(audio_path)

    model = "htdemucs_ft" if high_quality else "htdemucs"
    mix_filename = audio_path.name

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "renders").mkdir(exist_ok=True)
    stems_dir(project_dir).mkdir(exist_ok=True)

    if force and manifest_path(project_dir).is_file():
        old_manifest = load_manifest(project_dir)
        if old_manifest.mix_filename != mix_filename:
            stale = project_dir / old_manifest.mix_filename
            if stale.is_file():
                stale.unlink()

    mix_dst = project_dir / mix_filename
    if audio_path.resolve() != mix_dst.resolve():
        shutil.copy2(audio_path, mix_dst)
    write_manifest(
        project_dir,
        slug=slug,
        mix_filename=mix_filename,
        original_path=audio_path,
        demucs_model=model,
    )

    _write_demucs_stems(audio_path, stem_paths(project_dir), model=model)


def run_separate(
    target: Path | str,
    *,
    high_quality: bool = False,
    force: bool = False,
    beat_detection_stem: StemSource | None = None,
) -> Path:
    """Separate and/or analyse a Cleave project from an audio file or project slug.

    *beat_detection_stem* is ``None`` when the CLI flag was omitted.
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
        _run_demucs(audio_path, project_dir, high_quality=high_quality, force=force)

    if need_analyse:
        from cleave.analyse import run_analyse

        source = resolve_beat_detection_stem(project_dir, beat_detection_stem)
        print("Extracting signals (may take a while on longer tracks)...", flush=True)
        run_analyse(
            project_dir,
            high_quality=high_quality,
            beat_detection_stem=source,
        )

    return project_dir
