"""CUDA overlay download, verify, unpack, and import finder, with fake wheels."""

from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from pathlib import Path

import pytest

import cleave.cuda_extra as cuda_extra
from cleave.cuda_extra import CudaExtraError, CudaWheel
from cleave.first_run import FirstRunCancelled


def _wheel_bytes(*names: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(f"{name}/__init__.py", f"NAME = {name!r}\n")
    return buf.getvalue()


@pytest.fixture
def fake_wheels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, bytes]:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path / "data"))
    payloads = {
        "torch.whl": _wheel_bytes("torch", "functorch"),
        "torchaudio.whl": _wheel_bytes("torchaudio"),
        "torchcodec.whl": _wheel_bytes("torchcodec"),
    }
    wheels = tuple(
        CudaWheel(name, f"https://example.invalid/{name}", hashlib.sha256(data).hexdigest(), len(data))
        for name, data in payloads.items()
    )
    monkeypatch.setattr(cuda_extra, "CUDA_WHEELS", wheels)

    def urlopen(request, timeout):
        return io.BytesIO(payloads[request.full_url.rsplit("/", 1)[1]])

    monkeypatch.setattr(cuda_extra.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(cuda_extra, "activate_cuda_extra", lambda: True)
    return payloads


def test_root_is_local_app_data_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLEAVE_DATA", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cuda_extra.cuda_extra_root() == (tmp_path / "Cleave" / "cuda").resolve()


def test_download_unpacks_all_wheels_and_marks_complete(
    fake_wheels: dict[str, bytes],
) -> None:
    fractions: list[float | None] = []
    stale = cuda_extra.cuda_extra_root() / "cu999-old"
    stale.mkdir(parents=True)

    note = cuda_extra.download_cuda_extra(lambda _m, f: fractions.append(f))

    assert note is None
    final = cuda_extra.cuda_extra_dir()
    for name in ("torch", "functorch", "torchaudio", "torchcodec"):
        assert (final / name / "__init__.py").is_file()
    assert cuda_extra.cuda_extra_installed()
    assert not stale.exists()
    assert sorted(p.name for p in cuda_extra.cuda_extra_root().iterdir()) == [
        cuda_extra.CUDA_EXTRA_KEY
    ]
    assert fractions[-1] == 1.0
    assert all(f is not None and 0.0 <= f <= 1.0 for f in fractions)


def test_restart_note_when_torch_is_already_loaded(
    fake_wheels: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cuda_extra, "activate_cuda_extra", lambda: False)
    assert cuda_extra.download_cuda_extra() == cuda_extra.RESTART_NOTE


def test_hash_mismatch_leaves_nothing_installed(
    fake_wheels: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = cuda_extra.CUDA_WHEELS[1]
    monkeypatch.setattr(
        cuda_extra,
        "CUDA_WHEELS",
        (cuda_extra.CUDA_WHEELS[0], CudaWheel(bad.filename, bad.url, "0" * 64, bad.size), cuda_extra.CUDA_WHEELS[2]),
    )
    with pytest.raises(CudaExtraError, match="SHA-256"):
        cuda_extra.download_cuda_extra()
    assert not cuda_extra.cuda_extra_installed()
    assert list(cuda_extra.cuda_extra_root().iterdir()) == []


def test_network_error_is_a_cuda_error(
    fake_wheels: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(request, timeout):
        raise cuda_extra.urllib.error.URLError("offline")

    monkeypatch.setattr(cuda_extra.urllib.request, "urlopen", refuse)
    with pytest.raises(CudaExtraError):
        cuda_extra.download_cuda_extra()
    assert not cuda_extra.cuda_extra_installed()


def test_cancel_cleans_staging(fake_wheels: dict[str, bytes]) -> None:
    def cancel(_message: str, _fraction: float | None) -> None:
        raise FirstRunCancelled()

    with pytest.raises(FirstRunCancelled):
        cuda_extra.download_cuda_extra(cancel)
    assert list(cuda_extra.cuda_extra_root().iterdir()) == []


def test_missing_package_in_wheels_fails(
    fake_wheels: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_wheels["torchcodec.whl"] = _wheel_bytes("other")
    first, second, third = cuda_extra.CUDA_WHEELS
    data = fake_wheels["torchcodec.whl"]
    monkeypatch.setattr(
        cuda_extra,
        "CUDA_WHEELS",
        (first, second, CudaWheel(third.filename, third.url, hashlib.sha256(data).hexdigest(), len(data))),
    )
    with pytest.raises(CudaExtraError, match="torchcodec"):
        cuda_extra.download_cuda_extra()
    assert not cuda_extra.cuda_extra_installed()


def test_overlay_finder_resolves_only_torch_packages(tmp_path: Path) -> None:
    pkg = tmp_path / "torchcodec"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "sub" / "__init__.py").write_text("")
    finder = cuda_extra._OverlayFinder(tmp_path)

    spec = finder.find_spec("torchcodec", None)
    assert spec is not None and spec.origin == str(pkg / "__init__.py")
    sub = finder.find_spec("torchcodec.sub", [str(pkg)])
    assert sub is not None and sub.origin == str(pkg / "sub" / "__init__.py")
    assert finder.find_spec("numpy", None) is None


def test_activate_is_a_no_op_outside_the_frozen_windows_build() -> None:
    assert cuda_extra.activate_cuda_extra() is False


def test_unsupported_outside_the_frozen_windows_build() -> None:
    assert cuda_extra.cuda_extra_supported() is False


def test_pins_match_requirements_file() -> None:
    from cleave.paths import repo_root

    text = (repo_root() / "requirements-torch-cu130.txt").read_text(encoding="utf-8")
    for wheel in cuda_extra.CUDA_WHEELS:
        name, version = wheel.filename.split("-")[:2]
        assert f"{name}=={version.split('+')[0]}" in text
