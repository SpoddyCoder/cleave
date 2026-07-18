"""Curated concurrent layer chords and stack-cost scoring."""

from __future__ import annotations

from dataclasses import dataclass

# Hard ceiling on how many layers may be active in any generated chord.
MAX_CONCURRENT_LAYERS = 4

# Base stack costs (also the n_layers <= 2 baseline).
_BASE_COST = {
    1: 1.0,
    2: 2.2,
    3: 4.0,
    4: 7.0,
}

# Cost subtracted from base when density level is 1 (raised) or 2 (max).
# Quartet level-1 lands at 4.0 so stack_up/shed clear the Arc mid-build budget.
_DENSITY_COST_DELTA: dict[int, tuple[float, float]] = {
    2: (0.5, 0.9),
    3: (1.0, 1.8),
    4: (3.0, 4.0),
}

# Motif-pick score bonus for a chord peak at density level 1 / 2.
_DENSITY_SCORE_BONUS: tuple[float, float] = (1.25, 2.5)


def stack_density_level(n_layers: int, cardinality: int) -> int:
    """How aggressively to favor ``cardinality``-stacks for this layer count.

    Returns 0 (baseline), 1 (raised), or 2 (max). Layers <= 2 stay at baseline
    for every cardinality. Higher layer counts unlock denser stacks step by step:
    duos first, then trios, then capped-4 stacks.
    """
    if cardinality < 2 or cardinality > MAX_CONCURRENT_LAYERS:
        return 0
    if n_layers <= 2:
        return 0
    if cardinality == 2:
        return 1 if n_layers == 3 else 2
    if cardinality == 3:
        if n_layers <= 3:
            return 0
        return 1 if n_layers == 4 else 2
    # cardinality == 4
    if n_layers <= 4:
        return 0
    return 1 if n_layers == 5 else 2


def density_score_bonus(n_layers: int, cardinality: int) -> float:
    level = stack_density_level(n_layers, cardinality)
    if level <= 0:
        return 0.0
    return _DENSITY_SCORE_BONUS[level - 1]


def chord_cost(n_active: int, n_layers: int | None = None) -> float:
    if n_active <= 0:
        return 0.0
    capped = min(n_active, MAX_CONCURRENT_LAYERS)
    if n_active > MAX_CONCURRENT_LAYERS:
        # Over-cap stacks are not generated; keep a steep penalty for scoring.
        return _BASE_COST[MAX_CONCURRENT_LAYERS] + (n_active - MAX_CONCURRENT_LAYERS) * 1.5
    base = _BASE_COST[capped]
    if n_layers is None or capped <= 1:
        return base
    level = stack_density_level(n_layers, capped)
    if level <= 0:
        return base
    delta = _DENSITY_COST_DELTA[capped][level - 1]
    return max(_BASE_COST[1], base - delta)


def chord_cost_for_active(
    active: frozenset[str],
    n_layers: int | None = None,
) -> float:
    return chord_cost(len(active), n_layers)


@dataclass(frozen=True)
class ChordVocab:
    slots: tuple[str, ...]
    chords: dict[str, frozenset[str]]
    singles: tuple[str, ...]
    duos: tuple[str, ...]
    trios: tuple[str, ...]
    quartets: tuple[str, ...]
    groups: tuple[str, ...]
    tutti_id: str | None

    def active_for(self, chord_id: str) -> frozenset[str]:
        return self.chords[chord_id]

    def cost_for(self, chord_id: str) -> float:
        return chord_cost_for_active(self.chords[chord_id], len(self.slots))


def build_vocab(slots: list[str]) -> ChordVocab:
    n = len(slots)
    chords: dict[str, frozenset[str]] = {}
    singles: list[str] = []
    duos: list[str] = []
    trios: list[str] = []
    quartets: list[str] = []
    groups: list[str] = []

    for i, slot in enumerate(slots):
        chord_id = f"s{i}"
        chords[chord_id] = frozenset({slot})
        singles.append(chord_id)

    for i in range(n - 1):
        chord_id = f"d{i}{i + 1}"
        chords[chord_id] = frozenset({slots[i], slots[i + 1]})
        duos.append(chord_id)

    if n >= 4:
        for i in range(n // 2):
            j = n - 1 - i
            if i >= j:
                continue
            chord_id = f"do{i}{j}"
            pair = frozenset({slots[i], slots[j]})
            if pair not in chords.values():
                chords[chord_id] = pair
                duos.append(chord_id)

    if n >= 3:
        for i in range(n - 2):
            chord_id = f"t{i}"
            chords[chord_id] = frozenset({slots[i], slots[i + 1], slots[i + 2]})
            trios.append(chord_id)

    if n >= 4:
        for i in range(n - 3):
            chord_id = f"q{i}"
            quartet = frozenset(slots[i : i + 4])
            assert len(quartet) <= MAX_CONCURRENT_LAYERS
            chords[chord_id] = quartet
            quartets.append(chord_id)

    if n >= 4 and n % 2 == 0:
        mid = n // 2
        g0 = frozenset(slots[:mid][:MAX_CONCURRENT_LAYERS])
        g1 = frozenset(slots[mid:][:MAX_CONCURRENT_LAYERS])
        chords["g0"] = g0
        chords["g1"] = g1
        groups.extend(("g0", "g1"))

    tutti_id: str | None = None
    if n >= 2:
        tutti_id = "tutti"
        # Cap the full-stack flash at MAX_CONCURRENT_LAYERS (slots are
        # already shuffled by the arranger, so this is a random subset).
        chords[tutti_id] = frozenset(slots[: min(n, MAX_CONCURRENT_LAYERS)])

    return ChordVocab(
        slots=tuple(slots),
        chords=chords,
        singles=tuple(singles),
        duos=tuple(duos),
        trios=tuple(trios),
        quartets=tuple(quartets),
        groups=tuple(groups),
        tutti_id=tutti_id,
    )
