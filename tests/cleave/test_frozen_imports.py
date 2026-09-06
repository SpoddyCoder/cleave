"""Frozen play/render import graph: no librosa/torch on the complete-project path."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cleave.separate import STEM_SPLIT_MISSING_FROZEN, require_stem_split

REPO_ROOT = Path(__file__).resolve().parents[2]

_LEAN_SPEC = REPO_ROOT / "packaging" / "cleave.spec"
_SEPARATE_SPEC = REPO_ROOT / "packaging" / "cleave-separate.spec"
_ANALYSE_PACKAGES = ("torch", "demucs", "beat_this", "librosa", "matplotlib")

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


def _block_prelude(blocked: tuple[str, ...]) -> str:
    return f"""
import sys
sys.frozen = True
sys._MEIPASS = {str(REPO_ROOT)!r}

class _BlockHeavy:
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".", 1)[0]
        if root in {blocked!r}:
            raise ModuleNotFoundError(f"No module named {{root!r}}")
        return None

sys.meta_path.insert(0, _BlockHeavy())
"""


def _run_isolated(
    script: str,
    *,
    extra_env: dict[str, str] | None = None,
    blocked: tuple[str, ...] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
    }
    if extra_env:
        env.update(extra_env)
    prelude = _BLOCK_HEAVY if blocked is None else _block_prelude(blocked)
    return subprocess.run(
        [sys.executable, "-c", prelude + textwrap.dedent(script)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(REPO_ROOT),
    )


def _assigned_str_tuple(spec_text: str, name: str) -> tuple[str, ...]:
    tree = ast.parse(spec_text)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, ast.Tuple):
            raise AssertionError(f"{name} is not a tuple")
        return tuple(
            elt.value
            for elt in node.value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        )
    raise AssertionError(f"{name} not found")


def _analysis_excludes(spec_text: str) -> tuple[str, ...]:
    tree = ast.parse(spec_text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Name) or func.id != "Analysis":
            continue
        for kw in node.keywords:
            if kw.arg != "excludes":
                continue
            value = kw.value
            if isinstance(value, ast.List):
                return tuple(
                    elt.value
                    for elt in value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                )
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "list"
                and value.args
                and isinstance(value.args[0], ast.Name)
            ):
                return _assigned_str_tuple(spec_text, value.args[0].id)
    raise AssertionError("Analysis excludes not found")


def _collect_all_literal_names(spec_text: str) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(spec_text)
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "collect_all"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        names.add(node.args[0].value)
    return names


def _module_level_imported_roots(source: str) -> set[str]:
    roots: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_pyinstaller_spec_collects_soxr_and_excludes_analyse() -> None:
    spec = _LEAN_SPEC.read_text(encoding="utf-8")
    assert 'collect_all("soxr")' in spec
    for name in ("torch", "demucs", "beat_this", "librosa", "matplotlib"):
        assert f'"{name}"' in spec


def test_pyinstaller_specs_lean_excludes_analyse_separate_collects() -> None:
    lean = _LEAN_SPEC.read_text(encoding="utf-8")
    separate = _SEPARATE_SPEC.read_text(encoding="utf-8")

    lean_excludes = set(_analysis_excludes(lean))
    assert set(_ANALYSE_PACKAGES) <= lean_excludes
    assert {"pygame", "soxr"} <= _collect_all_literal_names(lean)

    collect = set(_assigned_str_tuple(separate, "COLLECT_PACKAGES"))
    assert {"pygame", "soxr", "torch", "demucs", "beat_this", "librosa"} <= collect
    assert "matplotlib" not in collect

    separate_excludes = set(_analysis_excludes(separate))
    assert "matplotlib" in separate_excludes
    for name in ("torch", "demucs", "beat_this", "librosa"):
        assert name not in separate_excludes

    cuda_markers = set(_assigned_str_tuple(separate, "CUDA_BINARY_MARKERS"))
    assert {"cudart", "cublas", "cudnn", "nccl", "nvrtc"} <= cuda_markers
    assert "torch" not in cuda_markers


def test_model_weights_import_does_not_load_torch() -> None:
    result = _run_isolated(
        """
        import sys
        import cleave.model_weights

        heavy = [
            name
            for name in ("librosa", "torch", "demucs", "beat_this")
            if name in sys.modules
        ]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")
        """
    )
    assert result.returncode == 0, result.stderr


def test_separate_module_import_does_not_load_torch() -> None:
    result = _run_isolated(
        """
        import ast
        import sys
        from pathlib import Path

        import cleave.separate

        heavy = [
            name
            for name in ("librosa", "torch", "demucs", "beat_this", "matplotlib")
            if name in sys.modules
        ]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")

        source = Path(cleave.separate.__file__).read_text(encoding="utf-8")
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                names = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            else:
                continue
            if any(name in ("torch", "demucs", "beat_this") for name in names):
                raise SystemExit(f"module-level import: {names}")
        """
    )
    assert result.returncode == 0, result.stderr


def test_demucs_api_imports_stay_inside_write_demucs_stems() -> None:
    source = (REPO_ROOT / "cleave" / "separate.py").read_text(encoding="utf-8")
    assert _module_level_imported_roots(source).isdisjoint({"torch", "demucs", "beat_this"})
    result = _run_isolated(
        """
        import sys
        import cleave.separate

        heavy = [name for name in ("torch", "demucs") if name in sys.modules]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")
        if "cleave.analyse" in sys.modules:
            raise SystemExit("unexpected analyse import")
        """
    )
    assert result.returncode == 0, result.stderr


def test_extract_module_import_does_not_load_torch() -> None:
    source = (REPO_ROOT / "cleave" / "extract.py").read_text(encoding="utf-8")
    assert _module_level_imported_roots(source).isdisjoint({"torch", "demucs", "beat_this"})
    result = _run_isolated(
        """
        import sys
        import cleave.extract

        heavy = [
            name
            for name in ("torch", "demucs", "beat_this", "matplotlib")
            if name in sys.modules
        ]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")
        """,
        blocked=("torch", "demucs", "beat_this", "matplotlib"),
    )
    assert result.returncode == 0, result.stderr


def test_play_path_modules_do_not_import_librosa_or_torch() -> None:
    result = _run_isolated(
        """
        import sys
        import cleave.config
        import cleave.pcm_io
        import cleave.stem_pcm
        import cleave.viz.app
        import cleave.viz.loading

        heavy = [
            name
            for name in (
                "librosa",
                "torch",
                "demucs",
                "beat_this",
                "matplotlib",
                "cleave.extract",
                "cleave.analyse",
            )
            if name in sys.modules
        ]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")
        """
    )
    assert result.returncode == 0, result.stderr


def test_cli_viz_config_imports_stay_torch_free() -> None:
    result = _run_isolated(
        """
        import sys
        import cleave.cli
        import cleave.config
        import cleave.viz

        heavy = [
            name
            for name in (
                "librosa",
                "torch",
                "demucs",
                "beat_this",
                "matplotlib",
                "cleave.extract",
                "cleave.analyse",
                "cleave.model_weights",
                "cleave.separate",
            )
            if name in sys.modules
        ]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")
        """,
        blocked=_ANALYSE_PACKAGES,
    )
    assert result.returncode == 0, result.stderr


def test_render_path_does_not_import_torch_or_librosa() -> None:
    result = _run_isolated(
        """
        import sys
        import cleave.viz.render

        heavy = [
            name
            for name in (
                "librosa",
                "torch",
                "demucs",
                "beat_this",
                "matplotlib",
                "cleave.extract",
                "cleave.analyse",
            )
            if name in sys.modules
        ]
        if heavy:
            raise SystemExit(f"unexpected imports: {heavy}")
        """,
        blocked=_ANALYSE_PACKAGES,
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
        from unittest.mock import MagicMock, patch
        from cleave.cli import build_parser, cmd_play

        window = MagicMock()
        window.quit_requested = False
        with (
            patch("cleave.viz.open_loading_window", return_value=window),
            patch("cleave.viz.continue_launch"),
        ):
            cmd_play(build_parser().parse_args(["play", {str(audio)!r}]))
        """,
        extra_env={"CLEAVE_DATA": str(tmp_path)},
    )
    assert result.returncode == 1, result.stderr
    assert "not in this Windows build" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "librosa" not in result.stderr
