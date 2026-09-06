#!/usr/bin/env python3
"""Assert a Cleave project from ``cleave separate`` has stems and signals."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cleave.signals import SIGNALS_VERSION
from cleave.stems import STEM_NAMES, stem_paths


def missing_stem_wavs(project_dir: Path) -> list[str]:
    """Return stem names whose wav is missing under ``stems/``."""
    missing: list[str] = []
    for name in STEM_NAMES:
        path = stem_paths(project_dir)[name]
        if not path.is_file():
            missing.append(name)
    return missing


def read_signals_version(project_dir: Path) -> object:
    """Return the ``version`` field from ``signals.json``."""
    path = project_dir / "signals.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("signals.json is not an object")
    return data.get("version")


def assert_separate_project(project_dir: Path) -> None:
    """Raise ``SystemExit`` unless stem wavs exist and signals version matches."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise SystemExit(f"missing project dir {project_dir}")
    missing = missing_stem_wavs(project_dir)
    if missing:
        names = ", ".join(f"stems/{name}.wav" for name in missing)
        raise SystemExit(f"missing {names} under {project_dir}")
    try:
        version = read_signals_version(project_dir)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise SystemExit(f"signals.json unreadable: {exc}") from exc
    if version != SIGNALS_VERSION:
        raise SystemExit(
            f"signals.json version {version!r} != {SIGNALS_VERSION}"
        )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit("usage: assert_separate_project.py <project-dir>")
    assert_separate_project(Path(args[0]))
    print("separate project ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
