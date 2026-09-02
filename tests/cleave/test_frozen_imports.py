"""Frozen play/render import graph: no librosa/torch on the complete-project path."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cleave.separate import STEM_SPLIT_MISSING_FROZEN, require_stem_split

REPO_ROOT = Path(__file__).resolve().parents[2]

_BLOCK_HEAVY = f"""
import sys
sys.frozen = True
sys._MEIPASS = {str(REPO_ROOT)!r}

class _BlockHeavy:
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".", 1)[0]
        if root in ("librosa", "torch"):
            raise ModuleNotFoundError(f"No module named {{root!r}}")
        return None

sys.meta_path.insert(0, _BlockHeavy())
"""


def _run_isolated(script: str, *, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_HEAVY + textwrap.dedent(script)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(REPO_ROOT),
    )


def test_pyinstaller_spec_collects_soxr_and_excludes_analyse() -> None:
    spec = (REPO_ROOT / "packaging" / "cleave.spec").read_text(encoding="utf-8")
    assert 'collect_all("soxr")' in spec
    for name in ("torch", "demucs", "librosa", "matplotlib"):
        assert f'"{name}"' in spec


def test_play_path_modules_do_not_import_librosa_or_torch() -> None:
    result = _run_isolated(
        """
        import sys
        import cleave.config
        import cleave.pcm_io
        import cleave.stem_pcm
        import cleave.viz.app

        heavy = [name for name in ("librosa", "torch", "cleave.extract") if name in sys.modules]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")
        """
    )
    assert result.returncode == 0, result.stderr


def test_require_stem_split_frozen_message_when_torch_blocked() -> None:
    result = _run_isolated(
        """
        from cleave.separate import STEM_SPLIT_MISSING_FROZEN, require_stem_split

        try:
            require_stem_split()
        except RuntimeError as exc:
            if str(exc) != STEM_SPLIT_MISSING_FROZEN:
                raise SystemExit(f"wrong message: {exc}")
        except ModuleNotFoundError as exc:
            raise SystemExit(f"ModuleNotFoundError: {exc}")
        else:
            raise SystemExit("expected RuntimeError")
        """
    )
    assert result.returncode == 0, result.stderr


def test_require_stem_split_frozen_message_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cleave.separate.stem_split_available", lambda: False)
    monkeypatch.setattr("cleave.separate.is_frozen", lambda: True)
    with pytest.raises(RuntimeError, match="not in this Windows build") as exc:
        require_stem_split()
    assert exc.value.args == (STEM_SPLIT_MISSING_FROZEN,)


def test_frozen_separate_raw_audio_uses_short_message(tmp_path: Path) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    result = _run_isolated(
        f"""
        from pathlib import Path
        from cleave.separate import STEM_SPLIT_MISSING_FROZEN, run_separate

        try:
            run_separate(Path({str(audio)!r}))
        except RuntimeError as exc:
            if str(exc) != STEM_SPLIT_MISSING_FROZEN:
                raise SystemExit(f"wrong message: {{exc}}")
        except ModuleNotFoundError as exc:
            raise SystemExit(f"ModuleNotFoundError: {{exc}}")
        else:
            raise SystemExit("expected RuntimeError")
        """,
        extra_env={"CLEAVE_DATA": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr


def test_frozen_cmd_separate_raw_audio_uses_short_message(tmp_path: Path) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    result = _run_isolated(
        f"""
        from cleave.cli import build_parser, cmd_separate

        cmd_separate(build_parser().parse_args(["separate", {str(audio)!r}]))
        """,
        extra_env={"CLEAVE_DATA": str(tmp_path)},
    )
    assert result.returncode == 1, result.stderr
    assert "not in this Windows build" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "librosa" not in result.stderr


def test_frozen_cmd_play_raw_audio_uses_short_message(tmp_path: Path) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    result = _run_isolated(
        f"""
        from cleave.cli import build_parser, cmd_play

        cmd_play(build_parser().parse_args(["play", {str(audio)!r}]))
        """,
        extra_env={"CLEAVE_DATA": str(tmp_path)},
    )
    assert result.returncode == 1, result.stderr
    assert "not in this Windows build" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "librosa" not in result.stderr
