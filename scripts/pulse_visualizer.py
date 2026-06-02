#!/usr/bin/env python3
"""Drum-pulse visualizer synced to mixed audio and drum onset strength."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cleave.signals import Signals, load_signals, resolve_signals_path  # noqa: E402

WIDTH, HEIGHT = 1280, 720
FPS = 60
DECAY = 0.92
GAIN = 1.0
RIPPLE_DELTA = 0.08
RIPPLE_MS = 400
FLASH_DECAY = 0.82
FLASH_THRESHOLD = 0.65
BG = (10, 8, 14)
CENTER = (WIDTH // 2, HEIGHT // 2)


@dataclass
class Ripple:
    born_ms: int
    strength: float


def resolve_audio_path(signals: Signals, override: Path | None) -> Path:
    if override is not None:
        path = override.resolve()
    elif signals.source is None:
        print(
            "error: signals.json has no source; pass --source path/to/mix.wav",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        path = Path(signals.source)
        if not path.is_file():
            path = ROOT / signals.source
    if not path.is_file():
        print(f"error: audio not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path


def sample_onset(signals: Signals, t_sec: float) -> float:
    values = signals.onset_normalized
    if len(values) == 0:
        return 0.0

    sr = signals.sample_rate_hz
    t_max = (len(values) - 1) / sr
    t = min(max(t_sec, 0.0), t_max)
    pos = t * sr
    i = int(pos)
    if i >= len(values) - 1:
        return float(values[-1])
    frac = pos - i
    return float(values[i] * (1.0 - frac) + values[i + 1] * frac)


def draw_orb(surface: pygame.Surface, radius: float, intensity: float) -> None:
    if radius < 2 or intensity < 0.02:
        return
    r = int(radius)
    cx, cy = CENTER
    glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    for step in range(r, 0, -3):
        t = step / r
        alpha = int(200 * intensity * (t**1.4))
        if alpha < 3:
            continue
        color = (255, int(70 + 90 * intensity), int(35 + 40 * intensity), alpha)
        pygame.draw.circle(glow, color, (r, r), step)
    surface.blit(glow, (cx - r, cy - r), special_flags=pygame.BLEND_RGBA_ADD)


def draw_ripples(
    surface: pygame.Surface, ripples: list[Ripple], now_ms: int
) -> list[Ripple]:
    cx, cy = CENTER
    alive: list[Ripple] = []
    for rip in ripples:
        age = now_ms - rip.born_ms
        if age >= RIPPLE_MS:
            continue
        alive.append(rip)
        prog = age / RIPPLE_MS
        radius = int(50 + prog * 320)
        alpha = int(160 * (1.0 - prog) * rip.strength)
        if alpha < 4:
            continue
        ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(
            ring, (255, 110, 55, alpha), (radius + 2, radius + 2), radius, 2
        )
        surface.blit(ring, (cx - radius - 2, cy - radius - 2))
    return alive


def draw_flash(surface: pygame.Surface, alpha: float) -> None:
    if alpha < 0.01:
        return
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((240, 235, 230, int(min(255, alpha * 255))))
    surface.blit(overlay, (0, 0))


def playback_ms(start_ms: int, paused_ms: int, paused: bool, pause_at: int) -> int:
    now = pygame.time.get_ticks()
    if paused:
        return pause_at - start_ms - paused_ms
    return now - start_ms - paused_ms


def run(signals: Signals, audio_path: Path) -> None:
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(f"Cleave pulse — {signals.path.parent.name}")
    clock = pygame.time.Clock()

    pygame.mixer.music.load(str(audio_path))
    pygame.mixer.music.play()
    start_ms = pygame.time.get_ticks()

    envelope = 0.0
    prev_envelope = 0.0
    flash = 0.0
    ripples: list[Ripple] = []
    paused = False
    paused_ms = 0
    pause_at = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if paused:
                        paused_ms += pygame.time.get_ticks() - pause_at
                        pygame.mixer.music.unpause()
                        paused = False
                    else:
                        pause_at = pygame.time.get_ticks()
                        pygame.mixer.music.pause()
                        paused = True

        elapsed_ms = playback_ms(start_ms, paused_ms, paused, pause_at)
        t_sec = min(elapsed_ms / 1000.0, signals.duration_sec)
        raw = sample_onset(signals, t_sec)
        envelope = max(envelope * DECAY, raw * GAIN)

        delta = envelope - prev_envelope
        if delta > RIPPLE_DELTA:
            ripples.append(Ripple(born_ms=elapsed_ms, strength=min(1.0, delta * 4.0)))

        if envelope > FLASH_THRESHOLD:
            flash = max(flash, (envelope - FLASH_THRESHOLD) * 1.8)
        flash *= FLASH_DECAY

        screen.fill(BG)
        base_r = 40 + envelope * 120
        draw_orb(screen, base_r, min(1.0, envelope * 1.1))
        ripples = draw_ripples(screen, ripples, elapsed_ms)
        draw_flash(screen, flash)
        pygame.display.flip()
        clock.tick(FPS)

        prev_envelope = envelope
        if not paused and not pygame.mixer.music.get_busy():
            if t_sec >= signals.duration_sec - 0.05:
                running = False

    pygame.mixer.music.stop()
    pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drum-pulse visualizer synced to mixed audio",
    )
    parser.add_argument("path", type=Path, help="signals.json or stems folder")
    parser.add_argument(
        "--source",
        type=Path,
        help="Original mix wav (overrides signals.json source)",
    )
    args = parser.parse_args()

    signals_path = resolve_signals_path(args.path)
    try:
        signals = load_signals(signals_path)
    except FileNotFoundError:
        print(f"error: {signals_path} not found", file=sys.stderr)
        sys.exit(1)

    audio_path = resolve_audio_path(signals, args.source)
    run(signals, audio_path)


if __name__ == "__main__":
    main()
