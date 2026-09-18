"""Tests for first-run Milkdrop starter pack download."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.error import URLError

import pytest

from cleave.starter_packs import (
    STARTER_PACKS,
    StarterPackError,
    _DownloadProgress,
    download_starter_packs,
    starter_packs_needed,
)


class _FakeResp:
    def __init__(self, data: bytes, *, content_length: bool = True) -> None:
        self._buf = io.BytesIO(data)
        self.headers: dict[str, str] = {}
        if content_length:
            self.headers["Content-Length"] = str(len(data))

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _zip_bytes(repo: str, *, branch: str = "main") -> bytes:
    buf = io.BytesIO()
    root = f"{repo}-{branch}"
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{root}/", "")
        zf.writestr(f"{root}/marker.txt", repo)
    return buf.getvalue()


def _install_fake_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    payloads: dict[str, bytes],
    *,
    content_length: bool = True,
) -> list[str]:
    requested: list[str] = []

    def fake_urlopen(url: object, timeout: object = None) -> _FakeResp:
        raw = url if isinstance(url, str) else url.full_url
        requested.append(raw)
        try:
            data = payloads[raw]
        except KeyError as exc:
            raise URLError(f"unexpected url: {raw}") from exc
        return _FakeResp(data, content_length=content_length)

    monkeypatch.setattr("cleave.starter_packs.urllib.request.urlopen", fake_urlopen)
    return requested


def test_starter_packs_needed_empty_presets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    (tmp_path / "presets").mkdir()
    assert starter_packs_needed() is True


def test_starter_packs_needed_with_milk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    nested = tmp_path / "presets" / "pack" / "nested"
    nested.mkdir(parents=True)
    (nested / "demo.milk").write_text("dummy\n")
    assert starter_packs_needed() is False


def test_starter_packs_needed_no_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    assert not (tmp_path / "presets").exists()
    assert starter_packs_needed() is True


def test_download_starter_packs_extracts_and_renames(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    payloads = {
        pack.url: _zip_bytes(pack.repo, branch="main" if pack is STARTER_PACKS[0] else "master")
        for pack in STARTER_PACKS
    }
    _install_fake_urlopen(monkeypatch, payloads)

    download_starter_packs()

    for pack in STARTER_PACKS:
        dest = tmp_path / pack.dest_parent_key / pack.dest_name
        assert dest.is_dir()
        assert (dest / "marker.txt").read_text() == pack.repo
        assert not (dest.parent / f"{pack.repo}-main").exists()
        assert not (dest.parent / f"{pack.repo}-master").exists()


def test_download_starter_packs_skips_existing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    existing = STARTER_PACKS[0]
    dest = tmp_path / existing.dest_parent_key / existing.dest_name
    dest.mkdir(parents=True)
    (dest / "keep.txt").write_text("keep")

    payloads = {pack.url: _zip_bytes(pack.repo) for pack in STARTER_PACKS}
    requested = _install_fake_urlopen(monkeypatch, payloads)

    download_starter_packs()

    assert existing.url not in requested
    assert (dest / "keep.txt").read_text() == "keep"
    assert not (dest / "marker.txt").exists()
    for pack in STARTER_PACKS[1:]:
        assert pack.url in requested
        assert (tmp_path / pack.dest_parent_key / pack.dest_name / "marker.txt").is_file()


def test_download_starter_packs_reports_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    payloads = {pack.url: _zip_bytes(pack.repo) for pack in STARTER_PACKS}
    _install_fake_urlopen(monkeypatch, payloads)
    calls: list[tuple[str, float | None]] = []

    download_starter_packs(lambda message, fraction: calls.append((message, fraction)))

    assert calls
    assert all(message.startswith("Downloading starter packs") for message, _ in calls)
    assert all(isinstance(fraction, float) for _, fraction in calls)
    fractions = [fraction for _, fraction in calls]
    assert all(0.0 <= fraction <= 1.0 for fraction in fractions)
    assert fractions[-1] == pytest.approx(1.0)


def test_download_starter_packs_progress_without_content_length(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    payloads = {pack.url: _zip_bytes(pack.repo) for pack in STARTER_PACKS}
    _install_fake_urlopen(monkeypatch, payloads, content_length=False)
    calls: list[tuple[str, float | None]] = []

    download_starter_packs(lambda message, fraction: calls.append((message, fraction)))

    assert calls
    assert all(isinstance(fraction, float) for _, fraction in calls)
    fractions = [fraction for _, fraction in calls]
    assert all(0.0 <= fraction <= 1.0 for fraction in fractions)
    assert fractions[0] == pytest.approx(0.0)
    assert fractions[-1] == pytest.approx(1.0)


def test_download_progress_never_none_without_content_length() -> None:
    calls: list[tuple[str, float | None]] = []
    aggregator = _DownloadProgress(
        3, lambda message, fraction: calls.append((message, fraction)), "Downloading"
    )
    aggregator.on_bytes(0, None)
    aggregator.on_bytes(4096, None)
    aggregator.pulse()
    aggregator.finish_file()
    aggregator.on_bytes(0, None)
    aggregator.pulse()
    aggregator.finish_file()
    aggregator.on_bytes(50, 100)
    aggregator.finish_file()

    assert calls
    assert all(isinstance(fraction, float) for _, fraction in calls)
    assert all(0.0 <= fraction <= 1.0 for _, fraction in calls)
    assert calls[-1][1] == pytest.approx(1.0)


def test_download_starter_packs_network_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))

    def boom(url: object, timeout: object = None) -> None:
        raise URLError("offline")

    monkeypatch.setattr("cleave.starter_packs.urllib.request.urlopen", boom)

    with pytest.raises(StarterPackError, match="network connection"):
        download_starter_packs()


def test_starter_pack_urls_pin_master_branch() -> None:
    for pack in STARTER_PACKS:
        assert pack.url.endswith("/refs/heads/master.zip")
        assert pack.dest_name == pack.repo
