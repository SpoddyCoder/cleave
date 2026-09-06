"""Structural checks for the Windows freeze workflow (no GitHub runner)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_FREEZE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "windows-freeze.yml"
_RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


def _job_body(text: str, job_id: str) -> str:
    lines = text.splitlines(keepends=True)
    capturing = False
    seen_jobs = False
    chunks: list[str] = []
    for line in lines:
        if line.startswith("jobs:"):
            seen_jobs = True
            continue
        if not seen_jobs:
            continue
        if (
            line.startswith("  ")
            and not line.startswith("    ")
            and not line.lstrip().startswith("#")
            and line.rstrip().endswith(":")
        ):
            name = line.strip()[:-1].strip()
            if capturing:
                break
            capturing = name == job_id
            continue
        if capturing:
            chunks.append(line)
    body = "".join(chunks)
    assert body, f"job {job_id!r} not found"
    return body


def _input_defaults(section: str) -> dict[str, str]:
    defaults: dict[str, str] = {}
    current: str | None = None
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if (
            line.startswith("      ")
            and not line.startswith("        ")
            and stripped.endswith(":")
        ):
            current = stripped[:-1]
            continue
        if current is not None and stripped.startswith("default:"):
            defaults[current] = stripped.split(":", 1)[1].strip()
            current = None
    return defaults


def test_lean_freeze_job_unchanged_default_path() -> None:
    text = _FREEZE_WORKFLOW.read_text(encoding="utf-8")
    freeze = _job_body(text, "freeze")
    assert (
        "if: ${{ inputs.include_freeze == true || inputs.include_freeze == 'true' }}"
        in freeze
    )
    assert "pyinstaller packaging/cleave.spec" in freeze
    assert "packaging/cleave-separate.spec" not in freeze
    assert "requirements-torch-cpu.txt" not in freeze
    assert "STEM_SPLIT_MISSING_FROZEN" in freeze
    assert 'dummy.write_bytes(b"audio")' in freeze
    assert freeze.count("run: gh release upload") == 2
    assert "cleave-windows-x64" in freeze
    assert "innosetup" in freeze.lower() or "Inno Setup" in freeze
    assert "pip install -r requirements.txt" not in freeze
    assert "runs-on: windows-latest" in freeze
    assert "windows-latest-8-cores" not in freeze
    assert "larger" not in freeze.lower()


def test_separate_job_is_isolated_cpu_smoke() -> None:
    text = _FREEZE_WORKFLOW.read_text(encoding="utf-8")
    assert "include_separate:" in text
    separate = _job_body(text, "freeze-separate")
    assert (
        "if: ${{ inputs.include_separate == true || inputs.include_separate == 'true' }}"
        in separate
    )
    assert "runs-on: windows-latest" in separate
    assert "windows-latest-8-cores" not in separate
    assert "pyinstaller packaging/cleave-separate.spec" in separate
    assert "pyinstaller packaging/cleave.spec" not in separate
    assert "requirements-freeze.txt" in separate
    assert "requirements-torch-cpu.txt" in separate
    assert "pip install -r requirements.txt" not in separate
    assert "scripts/windows_stage_freeze.py" in separate
    assert "STEM_SPLIT_MISSING_FROZEN" not in separate
    assert "smoke-separate.wav" in separate
    assert "assert_separate_project.py" in separate
    assert "timeout-minutes: 90" in separate
    assert "cleave-windows-x64-separate" in separate
    assert "retention-days: 5" in separate
    assert "github.event_name == 'workflow_dispatch'" in separate
    assert "run: gh release upload" not in separate
    assert "innosetup" not in separate.lower()
    assert "iscc" not in separate.lower()


def test_include_defaults_dispatch_both_true_call_freeze_only() -> None:
    text = _FREEZE_WORKFLOW.read_text(encoding="utf-8")
    dispatch_idx = text.index("workflow_dispatch:")
    call_idx = text.index("workflow_call:")
    dispatch = text[dispatch_idx:call_idx]
    call = text[call_idx : text.index("permissions:")]
    dispatch_defaults = _input_defaults(dispatch)
    call_defaults = _input_defaults(call)
    assert dispatch_defaults["include_freeze"] == "true"
    assert dispatch_defaults["include_separate"] == "true"
    assert call_defaults["include_freeze"] == "true"
    assert call_defaults["include_separate"] == "false"
    assert "release_tag:" in call


def test_require_job_fails_when_both_off() -> None:
    text = _FREEZE_WORKFLOW.read_text(encoding="utf-8")
    guard = _job_body(text, "require-job")
    assert "include_freeze != true" in guard
    assert "include_separate != true" in guard
    assert "runs-on: ubuntu-latest" in guard
    assert "exit 1" in guard
    assert "windows-latest" not in guard


def test_release_yml_does_not_enable_separate_job() -> None:
    text = _RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "windows-freeze.yml" in text
    assert "include_separate:" not in text
    assert "include_freeze:" not in text
    assert "release_tag:" in text
