"""Run Demucs stem separation and write stem wavs into a Cleave project."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cleave.analyse import run_analyse
from cleave.config import ensure_project_viz_config
from cleave.extract import stem_paths, stems_dir
from cleave.paths import project_dir, project_slug, resolve_project
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


def _validate_audio_path(audio_path: Path) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if not audio_path.is_file():
        raise ValueError(f"not a file: {audio_path}")


def _run_demucs(
    audio_path: Path,
    project_dir: Path,
    *,
    high_quality: bool,
    force: bool,
) -> None:
    """Separate *audio_path* with Demucs and copy stems into *project_dir*."""
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

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "demucs",
                    "-n",
                    model,
                    "-o",
                    str(tmp_dir),
                    str(audio_path),
                ],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"demucs failed (exit {exc.returncode}) for {audio_path}"
            ) from exc

        demucs_out = tmp_dir / model / slug
        if not demucs_out.is_dir():
            raise RuntimeError(f"demucs output directory missing: {demucs_out}")

        paths = stem_paths(project_dir)
        missing_src = [
            name
            for name in paths
            if not (demucs_out / f"{name}.wav").is_file()
        ]
        if missing_src:
            raise RuntimeError(
                f"demucs output missing stem files in {demucs_out}: "
                f"{', '.join(missing_src)}"
            )

        for name, dst in paths.items():
            shutil.copy2(demucs_out / f"{name}.wav", dst)


def run_separate(
    target: Path | str, *, high_quality: bool = False, force: bool = False
) -> Path:
    """Separate and/or analyse a Cleave project from an audio file or project slug."""
    project_dir, audio_path = resolve_separate_target(target)
    ensure_project_viz_config(project_dir)

    stems_complete = project_stems_complete(project_dir)
    signals_done = signals_complete(project_dir)

    if stems_complete and signals_done and not force:
        return project_dir

    run_demucs = force or not stems_complete
    if run_demucs:
        _run_demucs(audio_path, project_dir, high_quality=high_quality, force=force)

    if run_demucs or not signals_done:
        print("Extracting signals (may take a while on longer tracks)...", flush=True)
        run_analyse(project_dir, high_quality=high_quality)

    return project_dir
