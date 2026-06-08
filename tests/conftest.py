"""Shared pytest fixtures for Cleave tests."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

import cleave.viz.controls  # noqa: F401 - preload before effects.runtime imports
from cleave.extract import STEM_NAMES, stems_dir
from cleave.signals import Signals
from tests.support.config import write_minimal_config
from tests.support.signals import make_onset_signals, make_signals

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _pygame_session() -> None:
    """Initialize pygame (including mixer) once for tests that toggle playback."""
    if not pygame.get_init():
        pygame.init()
    if not pygame.mixer.get_init():
        pygame.mixer.init()


@pytest.fixture
def signals_onset() -> Signals:
    return make_onset_signals([0.0, 1.0, 0.0])


@pytest.fixture
def minimal_signals() -> Signals:
    return make_signals("drums", "onset_strength", [0.0, 0.5, 1.0])


@pytest.fixture
def minimal_signals_json_path() -> Path:
    return _FIXTURES_DIR / "minimal_signals.json"


@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    write_minimal_config(project_dir, preset_root)
    stem_root = stems_dir(project_dir)
    stem_root.mkdir(parents=True, exist_ok=True)
    for stem in STEM_NAMES:
        (stem_root / f"{stem}.wav").write_bytes(b"wav")
    return project_dir
