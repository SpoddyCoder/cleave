from __future__ import annotations

import pytest

from imgui_bundle import imgui

from cleave.viz import tooltips


@pytest.fixture(autouse=True)
def _restore() -> None:
    yield
    tooltips.set_tooltips_enabled(True)


def test_show_tooltip_calls_imgui_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    shown: list[str] = []
    monkeypatch.setattr(imgui, "set_tooltip", shown.append)
    tooltips.show_tooltip("tip")
    tooltips.set_tooltips_enabled(False)
    tooltips.show_tooltip("hidden")
    assert shown == ["tip"]


def test_show_tooltip_skips_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    shown: list[str] = []
    monkeypatch.setattr(imgui, "set_tooltip", shown.append)
    tooltips.show_tooltip("")
    assert shown == []
