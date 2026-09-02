"""Tests for scripts/windows_stage_freeze.py (no Windows, no real download)."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "scripts" / "windows_stage_freeze.py"


def _load_stage_freeze():
    spec = importlib.util.spec_from_file_location("windows_stage_freeze", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stage_freeze = _load_stage_freeze()


def _make_packaging(repo: Path) -> None:
    windows = repo / "packaging" / "windows"
    windows.mkdir(parents=True)
    (windows / "projectM-4.dll").write_bytes(b"dll-core")
    (windows / "projectM-4-playlist.dll").write_bytes(b"dll-playlist")
    licenses = windows / "licenses" / "libprojectM"
    licenses.mkdir(parents=True)
    (licenses / "LICENSE.txt").write_text("lgpl", encoding="utf-8")
    (licenses / "NOTICE.txt").write_text("notice", encoding="utf-8")


def _make_onedir(dist: Path, *, with_exe: bool = True) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    if with_exe:
        (dist / "cleave.exe").write_bytes(b"exe")
    (dist / "_internal").mkdir(exist_ok=True)


def _fake_ffmpeg_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ffmpeg-fake/bin/ffmpeg.exe", b"fake-ffmpeg")
        zf.writestr("ffmpeg-fake/LICENSE", b"GPL")
    return buf.getvalue()


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> list[str]:
    calls: list[str] = []

    def fake_urlopen(request, timeout=None):
        url = request if isinstance(request, str) else request.full_url
        calls.append(url)
        return io.BytesIO(payload)

    monkeypatch.setattr(stage_freeze.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_copy_dlls_and_licenses_into_onedir_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    dist = tmp_path / "dist" / "cleave"
    _make_packaging(repo)
    _make_onedir(dist)

    stage_freeze.copy_windows_dlls(repo, dist)
    stage_freeze.copy_libprojectm_licenses(repo, dist)

    assert (dist / "projectM-4.dll").read_bytes() == b"dll-core"
    assert (dist / "projectM-4-playlist.dll").read_bytes() == b"dll-playlist"
    assert (dist / "licenses" / "libprojectM" / "LICENSE.txt").read_text(
        encoding="utf-8"
    ) == "lgpl"
    assert (dist / "licenses" / "libprojectM" / "NOTICE.txt").read_text(
        encoding="utf-8"
    ) == "notice"
    assert not (dist / "_internal" / "projectM-4.dll").exists()
    assert not (dist / "_internal" / "projectM-4-playlist.dll").exists()


def test_ffmpeg_download_mocked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    dist = tmp_path / "dist" / "cleave"
    _make_packaging(repo)
    _make_onedir(dist)
    payload = _fake_ffmpeg_zip()
    digest = hashlib.sha256(payload).hexdigest()
    calls = _patch_urlopen(monkeypatch, payload)

    stage_freeze.stage_freeze(
        repo,
        dist,
        cache_path=tmp_path / "cache" / "ffmpeg-windows.zip",
        ffmpeg_url="https://example.invalid/ffmpeg.zip",
        ffmpeg_sha256=digest,
    )

    assert calls == ["https://example.invalid/ffmpeg.zip"]
    assert (dist / "ffmpeg.exe").read_bytes() == b"fake-ffmpeg"
    assert (dist / "licenses" / "ffmpeg" / "LICENSE").read_bytes() == b"GPL"
    assert (dist / "projectM-4.dll").is_file()
    assert not (dist / "_internal" / "ffmpeg.exe").exists()
    assert not (dist / "_internal" / "projectM-4.dll").exists()
    assert not (dist / "_internal" / "projectM-4-playlist.dll").exists()


def test_ffmpeg_checksum_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dist = tmp_path / "dist" / "cleave"
    _make_onedir(dist)
    payload = _fake_ffmpeg_zip()
    _patch_urlopen(monkeypatch, payload)

    with pytest.raises(stage_freeze.StageFreezeError, match="SHA-256 mismatch"):
        stage_freeze.stage_ffmpeg(
            dist,
            tmp_path / "cache" / "ffmpeg-windows.zip",
            url="https://example.invalid/ffmpeg.zip",
            sha256="0" * 64,
        )
    assert not (tmp_path / "cache" / "ffmpeg-windows.zip").exists()
    assert not (dist / "ffmpeg.exe").exists()


def test_missing_sidecar_fails_layout(tmp_path: Path) -> None:
    dist = tmp_path / "dist" / "cleave"
    _make_onedir(dist)
    (dist / "projectM-4.dll").write_bytes(b"dll")
    (dist / "projectM-4-playlist.dll").write_bytes(b"dll")

    with pytest.raises(stage_freeze.StageFreezeError, match="ffmpeg.exe"):
        stage_freeze.assert_onedir_layout(dist)


def test_sidecar_under_internal_fails_layout(tmp_path: Path) -> None:
    dist = tmp_path / "dist" / "cleave"
    _make_onedir(dist)
    (dist / "ffmpeg.exe").write_bytes(b"ff")
    (dist / "projectM-4.dll").write_bytes(b"dll")
    (dist / "projectM-4-playlist.dll").write_bytes(b"dll")
    (dist / "_internal" / "ffmpeg.exe").write_bytes(b"leaked")

    with pytest.raises(stage_freeze.StageFreezeError, match="_internal"):
        stage_freeze.assert_onedir_layout(dist)


def test_no_exe_check_skips_cleave_exe(tmp_path: Path) -> None:
    dist = tmp_path / "dist" / "cleave"
    _make_onedir(dist, with_exe=False)
    (dist / "ffmpeg.exe").write_bytes(b"ff")
    (dist / "projectM-4.dll").write_bytes(b"dll")
    (dist / "projectM-4-playlist.dll").write_bytes(b"dll")

    stage_freeze.assert_onedir_layout(dist, check_exe=False)
    with pytest.raises(stage_freeze.StageFreezeError, match="cleave.exe"):
        stage_freeze.assert_onedir_layout(dist, check_exe=True)


def test_main_mocked_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    dist = tmp_path / "dist" / "cleave"
    _make_packaging(repo)
    _make_onedir(dist, with_exe=False)
    payload = _fake_ffmpeg_zip()
    digest = hashlib.sha256(payload).hexdigest()
    _patch_urlopen(monkeypatch, payload)
    monkeypatch.setattr(stage_freeze, "FFMPEG_URL", "https://example.invalid/ffmpeg.zip")
    monkeypatch.setattr(stage_freeze, "FFMPEG_SHA256", digest)

    code = stage_freeze.main(
        [
            "--repo-root",
            str(repo),
            "--dist",
            str(dist),
            "--cache",
            str(tmp_path / "ffmpeg-windows.zip"),
            "--no-exe-check",
        ]
    )
    assert code == 0
    assert (dist / "ffmpeg.exe").is_file()
    assert (dist / "projectM-4.dll").is_file()


def test_cached_zip_skips_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dist = tmp_path / "dist" / "cleave"
    _make_onedir(dist)
    payload = _fake_ffmpeg_zip()
    digest = hashlib.sha256(payload).hexdigest()
    cache = tmp_path / "ffmpeg-windows.zip"
    cache.write_bytes(payload)
    calls = _patch_urlopen(monkeypatch, payload)

    stage_freeze.stage_ffmpeg(
        dist,
        cache,
        url="https://example.invalid/ffmpeg.zip",
        sha256=digest,
    )

    assert calls == []
    assert (dist / "ffmpeg.exe").read_bytes() == b"fake-ffmpeg"
