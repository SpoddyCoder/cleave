"""Curated concurrent layer chords and stack-cost scoring."""

from __future__ import annotations

from dataclasses import dataclass


def chord_cost(n_active: int) -> float:
    if n_active <= 0:
        return 0.0
    if n_active == 1:
        return 1.0
    if n_active == 2:
        return 2.2
    if n_active == 3:
        return 4.0
    return 7.0 + max(0, n_active - 4) * 1.5


def chord_cost_for_active(active: frozenset[str]) -> float:
    return chord_cost(len(active))


@dataclass(frozen=True)
class ChordVocab:
    slots: tuple[str, ...]
    chords: dict[str, frozenset[str]]
    singles: tuple[str, ...]
    duos: tuple[str, ...]
    trios: tuple[str, ...]
    groups: tuple[str, ...]
    tutti_id: str | None

    def active_for(self, chord_id: str) -> frozenset[str]:
        return self.chords[chord_id]

    def cost_for(self, chord_id: str) -> float:
        return chord_cost_for_active(self.chords[chord_id])


def build_vocab(slots: list[str]) -> ChordVocab:
    n = len(slots)
    chords: dict[str, frozenset[str]] = {}
    singles: list[str] = []
    duos: list[str] = []
    trios: list[str] = []
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

    if n >= 4 and n % 2 == 0:
        mid = n // 2
        g0 = frozenset(slots[:mid])
        g1 = frozenset(slots[mid:])
        chords["g0"] = g0
        chords["g1"] = g1
        groups.extend(("g0", "g1"))

    tutti_id: str | None = None
    if n >= 2:
        tutti_id = "tutti"
        chords[tutti_id] = frozenset(slots)

    return ChordVocab(
        slots=tuple(slots),
        chords=chords,
        singles=tuple(singles),
        duos=tuple(duos),
        trios=tuple(trios),
        groups=tuple(groups),
        tutti_id=tutti_id,
    )
