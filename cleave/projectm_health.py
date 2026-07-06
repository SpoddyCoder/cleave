"""Drain projectM preset load failures for live stem layers."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from cleave.viz.layer import StemLayer
from cleave.viz.preset_switching import EMPTY_ROTATION_NOTIFICATION

PRESET_SKIP_NOTIFICATION_INTERVAL_SEC = 10.0


@dataclass
class PresetSkipNotifyTracker:
    last_notify: dict[str, float] = field(default_factory=dict)


def drain_stem_layers_preset_failures(
    layers: list[StemLayer],
    *,
    on_notification: Callable[[str], None] | None = None,
    skip_notify_tracker: PresetSkipNotifyTracker | None = None,
) -> None:
    """Drain queued preset failures; optionally show rate-limited panel messages."""
    tracker = (
        skip_notify_tracker
        if skip_notify_tracker is not None
        else PresetSkipNotifyTracker()
    )
    now = time.monotonic()
    for layer in layers:
        failures = layer.pm.drain_preset_failures()
        for failure in failures:
            if failure.exhausted:
                if on_notification is not None:
                    on_notification(EMPTY_ROTATION_NOTIFICATION)
                continue
            if on_notification is None:
                continue
            last = tracker.last_notify.get(layer.slot, 0.0)
            if now - last < PRESET_SKIP_NOTIFICATION_INTERVAL_SEC:
                continue
            basename = Path(failure.filename).name if failure.filename else "preset"
            on_notification(f"Skipped preset: {basename}")
            tracker.last_notify[layer.slot] = now
