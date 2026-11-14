"""Drain projectM preset load failures and log messages for live stem layers."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cleave.projectm import drain_log_messages
from cleave.viz.layer import StemLayer
from cleave.viz.preset_switching import (
    EMPTY_PRESET_LIST_NOTIFICATION,
    layer_notification,
)

PRESET_SKIP_NOTIFICATION_INTERVAL_SEC = 10.0
PROJECTM_LOG_NOTIFICATION_PREFIX = "projectM: "


@dataclass
class PresetSkipNotifyTracker:
    last_notify: dict[str, float] = field(default_factory=dict)


@dataclass
class ProjectMLogNotifyTracker:
    """Messages already toasted, keyed by layer slot (``None`` when unattributed)."""

    seen_messages: set[tuple[str | None, str]] = field(default_factory=set)


def drain_projectm_log_notifications(
    layers: Sequence[StemLayer] = (),
    *,
    layer_z_order: Sequence[str] = (),
    on_notification: Callable[[str], None] | None = None,
    log_notify_tracker: ProjectMLogNotifyTracker | None = None,
) -> None:
    """Drain queued Warning+ libprojectM logs; toast once per layer and message per session.

    Lines emitted inside a layer's libprojectM call carry that layer's panel number.
    """
    tracker = (
        log_notify_tracker
        if log_notify_tracker is not None
        else ProjectMLogNotifyTracker()
    )
    pending: list[tuple[str | None, str]] = [
        (None, message) for message in drain_log_messages()
    ]
    for layer in layers:
        pending.extend((layer.slot, message) for message in layer.pm.drain_log_messages())
    for slot, message in pending:
        key = (slot, message)
        if key in tracker.seen_messages:
            continue
        tracker.seen_messages.add(key)
        formatted = f"{PROJECTM_LOG_NOTIFICATION_PREFIX}{message}"
        if slot is not None and slot in layer_z_order:
            formatted = layer_notification(layer_z_order, slot, formatted)
        if on_notification is not None:
            on_notification(formatted)
        else:
            print(formatted, file=sys.stderr, flush=True)


def drain_stem_layers_preset_failures(
    layers: list[StemLayer],
    *,
    layer_z_order: Sequence[str],
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
                    on_notification(
                        layer_notification(
                            layer_z_order,
                            layer.slot,
                            EMPTY_PRESET_LIST_NOTIFICATION,
                        )
                    )
                continue
            if on_notification is None:
                continue
            last = tracker.last_notify.get(layer.slot, 0.0)
            if now - last < PRESET_SKIP_NOTIFICATION_INTERVAL_SEC:
                continue
            basename = Path(failure.filename).name if failure.filename else "preset"
            on_notification(
                layer_notification(
                    layer_z_order,
                    layer.slot,
                    f"Skipped preset: {basename}",
                )
            )
            tracker.last_notify[layer.slot] = now
