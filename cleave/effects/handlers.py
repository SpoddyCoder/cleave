"""Registry of per-effect update and apply handlers for EffectRuntime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cleave.effects.registry import EffectDef
from cleave.signals import Signals


@dataclass(frozen=True)
class EffectHandler:
    effect_id: str
    state_factory: Callable[[], object]
    update: Callable[[object, Signals, EffectDef, float], None]
    apply: Callable[[object, int, object], object]


def _build_handlers() -> dict[str, EffectHandler]:
    from cleave.effects.flash import FLASH_HANDLER
    from cleave.effects.flare import FLARE_HANDLER
    from cleave.effects.grit import GRIT_HANDLER
    from cleave.effects.hue import HUE_HANDLER
    from cleave.effects.pulse import PULSE_HANDLER

    handlers = (
        PULSE_HANDLER,
        FLARE_HANDLER,
        FLASH_HANDLER,
        HUE_HANDLER,
        GRIT_HANDLER,
    )
    return {handler.effect_id: handler for handler in handlers}


EFFECT_HANDLERS: dict[str, EffectHandler] = _build_handlers()


def handler_for(effect_id: str) -> EffectHandler:
    try:
        return EFFECT_HANDLERS[effect_id]
    except KeyError as exc:
        raise KeyError(f"no handler registered for effect {effect_id!r}") from exc
