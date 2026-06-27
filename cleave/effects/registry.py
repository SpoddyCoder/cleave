"""Per-stem effect roster: fixed effect and driver rows for the live tuning UI."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.extract import STEM_SOURCES, StemSource

EFFECT_IDS = frozenset({"pulse", "flare", "flash", "hue", "grit"})

DRIVER_SLUGS = frozenset(
    {"onset", "sub_bass", "mid_bass", "rms", "pitch", "centroid"}
)

_DRIVER_SIGNAL_KEYS: dict[str, tuple[str, str]] = {
    "onset": ("drums", "onset_strength"),
    "sub_bass": ("bass", "sub_bass"),
    "mid_bass": ("bass", "mid_bass"),
    "rms": ("vocals", "rms"),
    "pitch": ("vocals", "pitch_hz"),
    "centroid": ("other", "spectral_centroid"),
}


@dataclass(frozen=True)
class EffectDef:
    effect_id: str
    driver_slug: str
    signal_stem: str
    signal_key: str

    @property
    def row_label_prefix(self) -> str:
        return f"{self.effect_id} ({self.driver_slug}): "


def _def(effect_id: str, driver_slug: str) -> EffectDef:
    signal_stem, signal_key = _DRIVER_SIGNAL_KEYS[driver_slug]
    return EffectDef(
        effect_id=effect_id,
        driver_slug=driver_slug,
        signal_stem=signal_stem,
        signal_key=signal_key,
    )


_EFFECT_ROSTER: dict[StemSource, tuple[EffectDef, ...]] = {
    "drums": (
        _def("pulse", "onset"),
        _def("flare", "onset"),
        _def("flash", "onset"),
        _def("grit", "onset"),
    ),
    "bass": (
        _def("pulse", "sub_bass"),
        _def("pulse", "mid_bass"),
        _def("flash", "sub_bass"),
        _def("grit", "sub_bass"),
    ),
    "vocals": (
        _def("pulse", "rms"),
        _def("hue", "pitch"),
        _def("flash", "rms"),
        _def("grit", "rms"),
    ),
    "other": (
        _def("pulse", "centroid"),
        _def("flash", "centroid"),
        _def("grit", "centroid"),
    ),
    "full_mix": (
        EffectDef("pulse", "onset", "full_mix", "onset_strength"),
        EffectDef("flare", "onset", "full_mix", "onset_strength"),
        EffectDef("flash", "onset", "full_mix", "onset_strength"),
        EffectDef("grit", "onset", "full_mix", "onset_strength"),
    ),
}


def effect_roster(stem: StemSource) -> tuple[EffectDef, ...]:
    return _EFFECT_ROSTER[stem]


_EFFECT_HELP_TITLES: dict[str, str] = {
    "pulse": "Pulse",
    "flare": "Flare",
    "flash": "Flash",
    "hue": "Hue",
    "grit": "Grit",
}

_EFFECT_HELP_DESCRIPTIONS: dict[str, tuple[str, ...]] = {
    "pulse": (
        "Opacity follows the audio driver signal.",
        "Peaks on transients or sustained energy depending on driver.",
    ),
    "flare": (
        "Bloom burst on drum onsets.",
        "Drums stem only.",
    ),
    "flash": (
        "Brief white flash when the driver crosses its threshold.",
    ),
    "hue": (
        "Tints the layer from vocal pitch.",
        "Vocals stem, pitch driver only.",
    ),
    "grit": (
        "Film grain and chromatic aberration driven by the audio envelope.",
    ),
}


def effect_help_title(effect_id: str) -> str:
    return _EFFECT_HELP_TITLES.get(effect_id, effect_id)


def effect_help_description(effect_id: str) -> tuple[str, ...] | None:
    return _EFFECT_HELP_DESCRIPTIONS.get(effect_id)


def effect_row_count(stem: StemSource) -> int:
    return len(_EFFECT_ROSTER[stem])


def validate_effect_entry(
    slot: str,
    stem: StemSource,
    effect_id: str,
    driver_slug: str,
) -> None:
    if effect_id not in EFFECT_IDS:
        allowed = ", ".join(sorted(EFFECT_IDS))
        raise ValueError(
            f"layers.{slot}.effects.{effect_id}: unknown effect (expected one of: {allowed})"
        )
    if driver_slug not in DRIVER_SLUGS:
        allowed = ", ".join(sorted(DRIVER_SLUGS))
        raise ValueError(
            f"layers.{slot}.effects.{effect_id}.{driver_slug}: unknown driver "
            f"(expected one of: {allowed})"
        )
    valid = {
        (row.effect_id, row.driver_slug)
        for row in _EFFECT_ROSTER[stem]
    }
    if (effect_id, driver_slug) not in valid:
        raise ValueError(
            f"layers.{slot}.effects.{effect_id}.{driver_slug}: not in roster for {stem}"
        )


def all_stem_sources() -> tuple[StemSource, ...]:
    return STEM_SOURCES
