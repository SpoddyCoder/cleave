"""Run Demucs stem separation and write stem wavs into a Cleave project."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cleave.extract import stem_paths
from cleave.paths import project_dir, project_slug


class ProjectStemsExist(Exception):
    """All expected stem wavs already exist in *project_dir*."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        super().__init__(
            f"stem wavs already exist in project: {project_dir}"
        )


def project_stems_complete(project_dir: Path) -> bool:
    """Return True when every stem wav from :func:`stem_paths` exists."""
    paths = stem_paths(project_dir)
    return all(path.is_file() for path in paths.values())


def _validate_audio_path(audio_path: Path) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if not audio_path.is_file():
        raise ValueError(f"not a file: {audio_path}")


def run_separate(
    audio_path: Path, *, slow: bool = False, force: bool = False
) -> Path:
    """Separate *audio_path* with Demucs and copy stems into the project directory.

    Raises :class:`ProjectStemsExist` when stems are complete and *force* is False.
    """
    audio_path = Path(audio_path)
    _validate_audio_path(audio_path)

    slug = project_slug(audio_path)
    out_dir = project_dir(slug)

    if project_stems_complete(out_dir) and not force:
        raise ProjectStemsExist(out_dir)

    model = "htdemucs_ft" if slow else "htdemucs"

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

        paths = stem_paths(out_dir)
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

        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "renders").mkdir(exist_ok=True)
        for name, dst in paths.items():
            shutil.copy2(demucs_out / f"{name}.wav", dst)

    return out_dir
