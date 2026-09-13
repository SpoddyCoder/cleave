"""Subprocess driver for in-editor project render (no pygame)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cleave.config import CleaveConfig
from cleave.config_snapshot import write_session_snapshot
from cleave.config_schema.project_render import ProjectRenderQuality
from cleave.paths import is_frozen
from cleave.render_progress import RENDER_PROGRESS_ENV, parse_render_progress_line
from cleave.viz.session import TuningSession


@dataclass(frozen=True)
class ProjectRenderSpec:
    project_dir: Path
    config_path: Path
    output_path: Path
    quality: ProjectRenderQuality
    start_sec: int
    end_sec: int
    width: int
    height: int
    fps: int


@dataclass(frozen=True)
class RenderJobStatus:
    done: bool
    ok: bool
    fraction: float
    error: str | None = None


class RenderJob(Protocol):
    def poll(self) -> RenderJobStatus: ...

    def abort(self) -> None: ...


class FailedRenderJob:
    """Job that is already finished in an error state."""

    def __init__(self, error: str) -> None:
        self._error = error

    def poll(self) -> RenderJobStatus:
        return RenderJobStatus(done=True, ok=False, fraction=0.0, error=self._error)

    def abort(self) -> None:
        return


class SubprocessRenderJob:
    """Poll a ``cleave render`` child and parse progress lines from stderr."""

    def __init__(self, proc: subprocess.Popen[str]) -> None:
        self._proc = proc
        self._lock = threading.Lock()
        self._fraction = 0.0
        self._stderr_tail: list[str] = []
        self._thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._thread.start()

    def _read_stderr(self) -> None:
        stream = self._proc.stderr
        if stream is None:
            return
        for raw in stream:
            frac = parse_render_progress_line(raw)
            with self._lock:
                if frac is not None:
                    self._fraction = frac
                else:
                    text = raw.rstrip()
                    if text:
                        self._stderr_tail.append(text)
                        if len(self._stderr_tail) > 24:
                            del self._stderr_tail[: len(self._stderr_tail) - 24]

    def poll(self) -> RenderJobStatus:
        rc = self._proc.poll()
        with self._lock:
            fraction = self._fraction
            stderr_tail = tuple(self._stderr_tail)
        if rc is None:
            return RenderJobStatus(done=False, ok=False, fraction=fraction)
        if rc == 0:
            return RenderJobStatus(done=True, ok=True, fraction=1.0)
        error = "\n".join(stderr_tail).strip() or f"render exited {rc}"
        return RenderJobStatus(done=True, ok=False, fraction=fraction, error=error)

    def abort(self) -> None:
        if self._proc.poll() is not None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()


def write_render_snapshot(cfg: CleaveConfig, session: TuningSession) -> Path:
    """Write live session YAML for the child ``cleave render`` to load."""
    project_dir = cfg.config_path.parent
    fd, name = tempfile.mkstemp(
        prefix="cleave-render-", suffix=".yaml", dir=str(project_dir)
    )
    os.close(fd)
    path = Path(name)
    try:
        write_session_snapshot(path, cfg=cfg, session=session)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def render_job_argv(
    spec: ProjectRenderSpec,
    *,
    frozen: bool | None = None,
    executable: str | None = None,
) -> list[str]:
    exe = sys.executable if executable is None else executable
    use_frozen = is_frozen() if frozen is None else frozen
    if use_frozen:
        cmd = [exe, "render", str(spec.project_dir)]
    else:
        cmd = [exe, "-m", "cleave", "render", str(spec.project_dir)]
    cmd.extend(
        [
            "--config",
            str(spec.config_path),
            "-o",
            str(spec.output_path),
            "--start",
            str(spec.start_sec),
            "--end",
            str(spec.end_sec),
            "--width",
            str(spec.width),
            "--height",
            str(spec.height),
            "--fps",
            str(spec.fps),
        ]
    )
    if spec.quality == "high":
        cmd.append("--hq")
    elif spec.quality == "viz":
        cmd.append("--viz-quality")
    return cmd


def _popen_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "bufsize": 1,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    return kwargs


def start_subprocess_render_job(spec: ProjectRenderSpec) -> RenderJob:
    argv = render_job_argv(spec)
    env = os.environ.copy()
    env[RENDER_PROGRESS_ENV] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        proc = subprocess.Popen(argv, env=env, **_popen_kwargs())  # type: ignore[call-arg]
    except OSError as exc:
        return FailedRenderJob(str(exc))
    return SubprocessRenderJob(proc)
