"""PyOpenGL error checking is off only in the frozen build, unless asked for."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cleave.gl_error_checking import ENV_VAR, gl_error_checking_wanted


@pytest.mark.parametrize(
    ("frozen", "env", "wanted"),
    [
        (False, None, True),
        (True, None, False),
        (True, "1", True),
        (True, "0", False),
        (False, "0", True),
    ],
)
def test_gl_error_checking_wanted(
    monkeypatch: pytest.MonkeyPatch, frozen: bool, env: str | None, wanted: bool
) -> None:
    if env is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, env)
    with patch("cleave.gl_error_checking.is_frozen", return_value=frozen):
        assert gl_error_checking_wanted() is wanted
