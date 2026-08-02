"""Per-cue cut type labels for timeline fade-group selection."""

from __future__ import annotations

from typing import Literal

CutType = Literal["none", "hard", "soft"]

CUT_TYPES: tuple[CutType, ...] = ("none", "hard", "soft")
