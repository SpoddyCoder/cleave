from __future__ import annotations

import faulthandler
from dataclasses import replace
from pathlib import Path

import pytest

from cleave.crash_log import (
    crash_log_active,
    crash_log_path,
    start_crash_log,
    stop_crash_log,
)
from cleave.user_config import default_editor_settings, write_user_config


@pytest.fixture(autouse=True)
def _restore_faulthandler():
    was_enabled = faulthandler.is_enabled()
    yield
    stop_crash_log()
    if was_enabled:
        faulthandler.enable()


def test_crash_log_path_sits_beside_user_config(tmp_path: Path) -> None:
    assert crash_log_path(tmp_path / "config.yaml") == tmp_path / "crash.log"


def test_start_crash_log_stays_off_by_default(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_user_config(default_editor_settings(), config_path)
    assert start_crash_log(config_path) is None
    assert crash_log_active() is False
    assert not (tmp_path / "crash.log").exists()


def test_start_crash_log_stays_off_for_unreadable_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("editor: [", encoding="utf-8")
    assert start_crash_log(config_path) is None
    assert crash_log_active() is False


def test_start_crash_log_enables_faulthandler_into_log(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_user_config(replace(default_editor_settings(), crash_log=True), config_path)
    path = start_crash_log(config_path)
    assert path == tmp_path / "crash.log"
    assert crash_log_active() is True
    assert faulthandler.is_enabled()
    assert path.read_text(encoding="utf-8").startswith("=== Cleave ")
    # A second call in the same process keeps the one log.
    assert start_crash_log(config_path) == path
    assert path.read_text(encoding="utf-8").count("=== Cleave ") == 1


def test_trim_crash_log_keeps_newest_part_from_a_start_header(tmp_path: Path) -> None:
    from cleave.crash_log import CRASH_LOG_KEEP_BYTES, CRASH_LOG_MAX_BYTES, trim_crash_log

    path = tmp_path / "crash.log"
    entry = "=== Cleave 0.0.0 started 2026-01-01T00:00:00 pid 1\n" + "x" * 200 + "\n"
    count = CRASH_LOG_MAX_BYTES // len(entry) + 10
    path.write_text(entry * (count - 1) + entry.replace("pid 1", "pid 2"), encoding="utf-8")
    trim_crash_log(path)
    text = path.read_text(encoding="utf-8")
    assert len(text) <= CRASH_LOG_KEEP_BYTES
    assert text.startswith("=== Cleave ")
    assert text.rstrip("x\n").endswith("pid 2")


def test_trim_crash_log_leaves_a_small_log(tmp_path: Path) -> None:
    from cleave.crash_log import trim_crash_log

    path = tmp_path / "crash.log"
    path.write_text("=== Cleave 0.0.0 started\n", encoding="utf-8")
    trim_crash_log(path)
    assert path.read_text(encoding="utf-8") == "=== Cleave 0.0.0 started\n"


def test_open_crash_log_folder_creates_and_opens_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cleave.file_manager
    from cleave.crash_log import open_crash_log_folder

    opened: list[Path] = []
    monkeypatch.setattr(cleave.file_manager, "open_folder", opened.append)
    folder = tmp_path / "cleave"
    assert open_crash_log_folder(folder / "config.yaml") == folder
    assert folder.is_dir()
    assert opened == [folder]
