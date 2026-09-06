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


def _job_ids(text: str) -> list[str]:
    jobs: list[str] = []
    seen_jobs = False
    for line in text.splitlines():
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
            jobs.append(line.strip()[:-1].strip())
    return jobs


def test_freeze_job_is_cpu_separate_product() -> None:
    text = _FREEZE_WORKFLOW.read_text(encoding="utf-8")
    assert _job_ids(text) == ["freeze"]
    freeze = _job_body(text, "freeze")
    assert "timeout-minutes: 180" in freeze
    assert "pyinstaller packaging/cleave.spec" in freeze
    assert "packaging/cleave-separate.spec" not in text
    assert "requirements-torch-cpu.txt" in freeze
    assert "requirements-freeze.txt" in freeze
    assert "STEM_SPLIT_MISSING_FROZEN" not in freeze
    assert "smoke-separate.wav" in freeze
    assert "assert_separate_project.py" in freeze
    assert "timeout-minutes: 90" in freeze
    assert freeze.count("run: gh release upload") == 2
    assert "name: cleave-windows-x64" in freeze
    assert "name: cleave-windows-x64-setup" in freeze
    assert "cleave-windows-x64-separate" not in freeze
    assert 'f"cleave-{cleave.__version__}-windows-x64.zip"' in freeze
    assert 'f"cleave-{version}-windows-x64-setup.exe"' in freeze
    assert "innosetup" in freeze.lower() or "Inno Setup" in freeze
    assert "pip install -r requirements.txt" not in freeze
    assert "runs-on: windows-latest" in freeze
    assert "windows-latest-8-cores" not in freeze
    assert "include_freeze" not in text
    assert "include_separate" not in text
    assert "require-job" not in text
    assert "freeze-separate" not in text


def test_workflow_call_has_release_tag_only() -> None:
    text = _FREEZE_WORKFLOW.read_text(encoding="utf-8")
    dispatch_idx = text.index("workflow_dispatch:")
    call_idx = text.index("workflow_call:")
    dispatch = text[dispatch_idx:call_idx]
    call = text[call_idx : text.index("permissions:")]
    assert "include_freeze" not in dispatch
    assert "include_separate" not in dispatch
    assert "release_tag:" in call
    assert "include_freeze" not in call
    assert "include_separate" not in call


def test_release_yml_does_not_mention_a_second_freeze_job() -> None:
    text = _RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "windows-freeze.yml" in text
    assert "include_separate:" not in text
    assert "include_freeze:" not in text
    assert "release_tag:" in text
    assert "freeze-separate" not in text
    assert "require-job" not in text
