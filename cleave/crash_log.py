"""Opt-in crash log: Python tracebacks of every thread on a hard crash.

A segfault or abort in native code (projectM, SDL, the GL driver) kills the
process with no Python traceback. With ``editor.crash_log`` on, the editor
points ``faulthandler`` at ``crash.log`` beside the user config when it
starts, so the next crash records where each thread was. The setting is read
once per process; changing it takes effect on the next start.
"""

from __future__ import annotations

import faulthandler
import os
from datetime import datetime
from pathlib import Path
from typing import TextIO

import yaml

CRASH_LOG_FILENAME = "crash.log"
# At start, a log over the limit keeps only its newest part, from the first
# start header in that part.
CRASH_LOG_MAX_BYTES = 1024 * 1024
CRASH_LOG_KEEP_BYTES = 256 * 1024
_START_HEADER = b"=== Cleave "

# Open for the life of the process: faulthandler writes to its file
# descriptor from the signal handler.
_log_file: TextIO | None = None


def crash_log_path(user_config: Path | None = None) -> Path:
    """``crash.log`` in the folder that holds the user config."""
    from cleave.user_config import user_config_path

    return (user_config or user_config_path()).parent / CRASH_LOG_FILENAME


def trim_crash_log(path: Path) -> None:
    """Cut *path* down to its newest ``CRASH_LOG_KEEP_BYTES`` once it passes the limit."""
    try:
        if path.stat().st_size <= CRASH_LOG_MAX_BYTES:
            return
        with path.open("rb") as fh:
            fh.seek(-CRASH_LOG_KEEP_BYTES, os.SEEK_END)
            tail = fh.read()
    except OSError:
        return
    start = tail.find(b"\n" + _START_HEADER)
    if start < 0:
        start = tail.find(b"\n")
    tail = tail[start + 1 :] if start >= 0 else tail
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_bytes(tail)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)


def open_crash_log_folder(user_config: Path | None = None) -> Path:
    """Show the crash log folder in the file manager. Raises OSError on failure."""
    from cleave.file_manager import open_folder

    folder = crash_log_path(user_config).parent
    folder.mkdir(parents=True, exist_ok=True)
    open_folder(folder)
    return folder


def crash_log_active() -> bool:
    """True when this process is writing crashes to the crash log."""
    return _log_file is not None


def start_crash_log(user_config: Path | None = None) -> Path | None:
    """Enable ``faulthandler`` into the crash log when the user turned it on.

    Returns the log path when enabled. An unreadable user config or log file
    leaves it off; the full config load reports a bad config in the window.
    """
    global _log_file
    if _log_file is not None:
        return crash_log_path(user_config)
    from cleave import __version__
    from cleave.user_config import load_user_config

    try:
        cfg = load_user_config(user_config)
    except (OSError, ValueError, yaml.YAMLError):
        return None
    if not cfg.editor.crash_log:
        return None
    path = crash_log_path(cfg.path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        trim_crash_log(path)
        log = path.open("a", encoding="utf-8")
    except OSError:
        return None
    stamp = datetime.now().isoformat(timespec="seconds")
    log.write(f"=== Cleave {__version__} started {stamp} pid {os.getpid()}\n")
    log.flush()
    faulthandler.enable(file=log, all_threads=True)
    _log_file = log
    return path


def stop_crash_log() -> None:
    """Disable ``faulthandler`` and close the log. For tests."""
    global _log_file
    if _log_file is None:
        return
    faulthandler.disable()
    _log_file.close()
    _log_file = None
