"""Tests for first-run model-weight download status and cache checks."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from urllib.error import URLError
from unittest.mock import MagicMock

import pytest

from cleave.model_weights import (
    WeightDownloadError,
    beat_this_weight_spec,
    demucs_weight_spec,
    download_done_message,
    download_failed_message,
    download_start_message,
    ensure_weight_files,
    hub_checkpoints_dir,
    missing_weight_files,
)


class _FakeTqdm:
    def __init__(self, *args: object, **kwargs: object) -> None:
        total = kwargs.get("total")
        self.total = int(total) if isinstance(total, (int, float)) else None
        self.n = 0
        self.disable = bool(kwargs.get("disable", False))

    def update(self, n: int = 1) -> None:
        self.n += n

    def close(self) -> None:
        pass

    def __enter__(self) -> _FakeTqdm:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _install_fake_torch(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Stub torch.hub without importing the real package (WSL ld.so abort)."""
    hub = types.ModuleType("torch.hub")
    hub.tqdm = _FakeTqdm
    hub.set_dir = MagicMock()
    hub.download_url_to_file = MagicMock()
    torch_mod = types.ModuleType("torch")
    torch_mod.hub = hub
    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    monkeypatch.setitem(sys.modules, "torch.hub", hub)
    return hub


def _write_cached(spec, cache: Path) -> None:
    dest = hub_checkpoints_dir(cache)
    dest.mkdir(parents=True, exist_ok=True)
    for item in spec.files:
        (dest / item.filename).write_bytes(b"ckpt")


def test_demucs_htdemucs_spec_matches_installed_repo() -> None:
    spec = demucs_weight_spec("htdemucs")
    assert spec.label == "Demucs htdemucs"
    assert spec.size_hint == "~80 MB"
    assert len(spec.files) == 1
    assert spec.files[0].filename == "955717e8-8726e21a.th"
    assert spec.files[0].url.endswith("hybrid_transformer/955717e8-8726e21a.th")


def test_demucs_htdemucs_ft_spec_is_four_file_bag() -> None:
    spec = demucs_weight_spec("htdemucs_ft")
    assert spec.label == "Demucs htdemucs_ft"
    assert spec.size_hint == "~320 MB"
    assert [item.filename for item in spec.files] == [
        "f7e0c4bc-ba3fe64a.th",
        "d12395a8-e57c48e6.th",
        "92cfc3b6-ef3bcb9c.th",
        "04573f0d-f3cf25b2.th",
    ]


def test_beat_this_final0_spec() -> None:
    spec = beat_this_weight_spec()
    assert spec.label == "Beat This final0"
    assert spec.size_hint == "~78 MB"
    assert spec.files[0].filename == "beat_this-final0.ckpt"
    assert spec.files[0].url.endswith("/final0.ckpt")


def test_download_messages_name_model_and_one_time_data_dir() -> None:
    spec = beat_this_weight_spec()
    start = download_start_message(spec)
    assert "Beat This final0" in start
    assert "one-time into the data dir" in start
    assert "~78 MB" in start
    assert download_done_message(spec) == "Downloaded Beat This final0."
    failed = download_failed_message(spec)
    assert "Beat This final0" in failed
    assert "network connection is required the first time" in failed


def test_missing_cache_reports_progress_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    spec = beat_this_weight_spec()
    cache = tmp_path / "models"
    hub = _install_fake_torch(monkeypatch)
    order: list[object] = []
    messages: list[tuple[str, float | None]] = []

    def fake_download(url: str, dst: str, **_kwargs: object) -> None:
        order.append("download")
        Path(dst).write_bytes(b"ckpt")

    hub.download_url_to_file = fake_download

    def on_progress(message: str, fraction: float | None) -> None:
        order.append("progress")
        messages.append((message, fraction))

    fetched = ensure_weight_files(spec, on_progress=on_progress, cache_dir=cache)

    assert fetched is True
    assert order[0] == "progress"
    assert "download" in order
    assert "Beat This final0" in messages[0][0]
    assert "one-time into the data dir" in messages[0][0]
    assert messages[0][1] is None
    assert messages[-1] == ("Downloaded Beat This final0.", None)
    dest = hub_checkpoints_dir(cache) / spec.files[0].filename
    assert dest.read_bytes() == b"ckpt"


def test_warm_cache_skips_download_chatter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    spec = demucs_weight_spec("htdemucs")
    cache = tmp_path / "models"
    _write_cached(spec, cache)
    hub = _install_fake_torch(monkeypatch)
    hub.download_url_to_file = MagicMock()
    messages: list[tuple[str, float | None]] = []

    def on_progress(message: str, fraction: float | None) -> None:
        messages.append((message, fraction))

    fetched = ensure_weight_files(spec, on_progress=on_progress, cache_dir=cache)

    assert fetched is False
    assert messages == []
    hub.download_url_to_file.assert_not_called()
    assert missing_weight_files(spec, cache) == ()


def test_urlerror_names_model_and_network_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    spec = demucs_weight_spec("htdemucs")
    cache = tmp_path / "models"
    hub = _install_fake_torch(monkeypatch)

    def fail(_url: str, _dst: str, **_kwargs: object) -> None:
        raise URLError("offline")

    hub.download_url_to_file = fail

    with pytest.raises(WeightDownloadError, match="Demucs htdemucs") as caught:
        ensure_weight_files(spec, cache_dir=cache)

    assert "network connection is required the first time" in str(caught.value)


def test_connection_error_becomes_weight_download_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    spec = beat_this_weight_spec()
    cache = tmp_path / "models"
    hub = _install_fake_torch(monkeypatch)

    def fail(_url: str, _dst: str, **_kwargs: object) -> None:
        raise ConnectionError("refused")

    hub.download_url_to_file = fail

    with pytest.raises(WeightDownloadError, match="Beat This final0"):
        ensure_weight_files(spec, cache_dir=cache)


def test_missing_cache_prints_stderr_when_no_progress_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    spec = demucs_weight_spec("htdemucs")
    cache = tmp_path / "models"
    hub = _install_fake_torch(monkeypatch)

    def fake_download(_url: str, dst: str, **_kwargs: object) -> None:
        Path(dst).write_bytes(b"ckpt")

    hub.download_url_to_file = fake_download
    ensure_weight_files(spec, cache_dir=cache)

    err = capsys.readouterr().err
    assert "Downloading Demucs htdemucs" in err
    assert "one-time into the data dir" in err
    assert "Downloaded Demucs htdemucs." in err


def test_warm_cache_prints_nothing_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    spec = beat_this_weight_spec()
    cache = tmp_path / "models"
    _write_cached(spec, cache)
    hub = _install_fake_torch(monkeypatch)
    hub.download_url_to_file = MagicMock()

    ensure_weight_files(spec, cache_dir=cache)

    hub.download_url_to_file.assert_not_called()
    assert capsys.readouterr().err == ""


def test_hub_tqdm_bytes_map_to_fraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    spec = beat_this_weight_spec()
    cache = tmp_path / "models"
    hub = _install_fake_torch(monkeypatch)
    fractions: list[float | None] = []

    def fake_download(_url: str, dst: str, **_kwargs: object) -> None:
        import torch.hub as hub_mod

        with hub_mod.tqdm(total=100, disable=False, unit="B") as pbar:
            pbar.update(40)
            pbar.update(60)
        Path(dst).write_bytes(b"ckpt")

    hub.download_url_to_file = fake_download

    def on_progress(_message: str, fraction: float | None) -> None:
        fractions.append(fraction)

    ensure_weight_files(spec, on_progress=on_progress, cache_dir=cache)

    assert fractions[0] is None
    numbered = [value for value in fractions if value is not None]
    assert numbered[0] == pytest.approx(0.0)
    assert 0.39 < numbered[1] < 0.41
    assert numbered[-1] == pytest.approx(1.0)
    assert fractions[-1] is None
