"""Sanity checks for packaging/windows/cleave.iss (no iscc on Linux)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ISS = REPO_ROOT / "packaging" / "windows" / "cleave.iss"


def test_inno_script_has_appid_autopf_and_injected_version() -> None:
    text = ISS.read_text(encoding="utf-8")
    app_id = re.search(
        r"AppId=\{\{([0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12})\}",
        text,
    )
    assert app_id is not None, "AppId GUID missing or malformed"
    assert app_id.group(1).replace("-", "").strip("0"), "AppId must not be all zeros"
    assert r"{autopf}\Cleave" in text
    assert "#ifndef AppVersion" in text
    assert "#error" in text
    assert "AppVersion={#AppVersion}" in text
    assert re.search(r"^AppVersion=\d", text, re.M) is None
