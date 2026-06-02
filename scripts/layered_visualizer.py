#!/usr/bin/env python3
"""Multi-stem layered visualizer synced to mixed audio and per-stem signals."""

from __future__ import annotations

import argparse
import colorsys
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cleave.signals import Signals, load_signals, resolve_signals_path  # noqa: E402
from cleave.viz_overlay import ControlsOverlay, layered_rows  # noqa: E402
from cleave.viz_playback import (  # noqa: E402
    SKIP_SEC,
    current_sec,
    elapsed_ms,
    init_playback,
    seek,
    toggle_pause,
)

WIDTH, HEIGHT = 1280, 720
FPS = 60
BG = (10, 8, 14)
CENTER = (WIDTH // 2, HEIGHT // 2)

DRUM_DECAY = 0.92
GAIN = 1.0
RIPPLE_DELTA = 0.08
RIPPLE_MS = 400
FLASH_DECAY = 0.82
FLASH_THRESHOLD = 0.65

OTHER_DECAY = 0.98
BASS_DECAY = 0.96
VOCALS_DECAY = 0.96

PITCH_MIN_HZ = 80.0
PITCH_MAX_HZ = 800.0
HUE_SMOOTH = 0.06


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


def sample_normalized(signals: Signals, stem: str, key: str, t_sec: float) -> float:
    values = signals.normalized(stem, key)
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
        if age < 0 or age >= RIPPLE_MS:
            continue
        alive.append(rip)
        prog = age / RIPPLE_MS
        radius = int(50 + prog * 320)
        if radius < 1:
            continue
        alpha = int(160 * (1.0 - prog) * rip.strength)
        if alpha < 4:
            continue
        size = radius * 2 + 4
        if size > WIDTH * 2:
            continue
        ring = pygame.Surface((size, size), pygame.SRCALPHA)
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


def hsv_to_rgb(hue: float, sat: float, val: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(hue / 360.0, sat, val)
    return int(r * 255), int(g * 255), int(b * 255)


def lerp_hue(current: float, target: float, factor: float) -> float:
    diff = (target - current + 180.0) % 360.0 - 180.0
    return (current + diff * factor) % 360.0


def pitch_to_hue(hz: float) -> float:
    t = (hz - PITCH_MIN_HZ) / (PITCH_MAX_HZ - PITCH_MIN_HZ)
    t = max(0.0, min(1.0, t))
    return t * 300.0


def draw_other_layer(surface: pygame.Surface, envelope: float) -> None:
    pivot = 0.25 + envelope * 0.55
    for y in range(0, HEIGHT, 2):
        fy = y / HEIGHT
        warmth = max(0.0, 1.0 - abs(fy - pivot) * 2.2) * (0.25 + envelope * 0.75)
        r = int(BG[0] + warmth * (55 + envelope * 45))
        g = int(BG[1] + warmth * (18 + envelope * 22))
        b = int(BG[2] + warmth * (-4))
        alpha = 50 + int(envelope * 35)
        pygame.draw.rect(surface, (r, g, b, alpha), (0, y, WIDTH, 2))


def draw_soft_ring(
    surface: pygame.Surface,
    radius: float,
    rgb: tuple[int, int, int],
    strength: float,
    alpha_peak: int,
) -> None:
    if radius < 6 or strength < 0.02:
        return
    r = int(radius)
    cx, cy = CENTER
    ring = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
    for step in range(r, max(r - 24, 0), -2):
        t = step / r
        alpha = int(alpha_peak * strength * (t**1.3))
        if alpha < 3:
            continue
        pygame.draw.circle(ring, (*rgb, alpha), (r + 4, r + 4), step, 3)
    surface.blit(ring, (cx - r - 4, cy - r - 4))


def draw_bass_layer(surface: pygame.Surface, sub_env: float, mid_env: float) -> None:
    draw_soft_ring(surface, 90 + sub_env * 240, (210, 45, 28), sub_env, 75)
    draw_soft_ring(surface, 55 + mid_env * 170, (255, 155, 55), mid_env, 65)


def draw_vocals_layer(surface: pygame.Surface, rms_env: float, hue: float) -> None:
    if rms_env < 0.015:
        return
    cx, cy = CENTER
    max_r = int(220 + rms_env * 260)
    rgb = hsv_to_rgb(hue, 0.55, 0.82)
    glow = pygame.Surface((max_r * 2, max_r * 2), pygame.SRCALPHA)
    for step in range(max_r, 0, -4):
        t = step / max_r
        alpha = int(55 * rms_env * (t**1.15))
        if alpha < 3:
            continue
        pygame.draw.circle(glow, (*rgb, alpha), (max_r, max_r), step)
    surface.blit(glow, (cx - max_r, cy - max_r))


def run(signals: Signals, audio_path: Path) -> None:
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    trackname = signals.path.parent.name
    pygame.display.set_caption(f"Cleave layered — {trackname}")
    clock = pygame.time.Clock()

    pygame.mixer.music.load(str(audio_path))
    pygame.mixer.music.play()

    playback = init_playback()
    duration_sec = signals.duration_sec

    drum_env = 0.0
    prev_drum_env = 0.0
    flash = 0.0
    ripples: list[Ripple] = []
    other_env = 0.0
    sub_env = 0.0
    mid_env = 0.0
    vocal_rms_env = 0.0
    vocal_hue = 180.0
    last_valid_hue = 180.0

    show_drums = True
    show_bass = True
    show_vocals = True
    show_other = True

    other_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    bass_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    vocals_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    overlay = ControlsOverlay(
        layered_rows(
            show_drums=show_drums,
            show_bass=show_bass,
            show_vocals=show_vocals,
            show_other=show_other,
            paused=playback.paused,
        )
    )

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                overlay.notify_input()
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    toggle_pause(playback, duration_sec)
                elif event.key == pygame.K_LEFT:
                    seek(playback, -SKIP_SEC, duration_sec)
                    ripples.clear()
                    flash = 0.0
                elif event.key == pygame.K_RIGHT:
                    seek(playback, SKIP_SEC, duration_sec)
                    ripples.clear()
                    flash = 0.0
                elif event.key == pygame.K_d:
                    show_drums = not show_drums
                elif event.key == pygame.K_b:
                    show_bass = not show_bass
                elif event.key == pygame.K_v:
                    show_vocals = not show_vocals
                elif event.key == pygame.K_o:
                    show_other = not show_other
                overlay.replace_rows(
                    layered_rows(
                        show_drums=show_drums,
                        show_bass=show_bass,
                        show_vocals=show_vocals,
                        show_other=show_other,
                        paused=playback.paused,
                    )
                )

        elapsed = elapsed_ms(playback)
        t_sec = current_sec(playback, duration_sec)

        raw_onset = sample_onset(signals, t_sec)
        drum_env = max(drum_env * DRUM_DECAY, raw_onset * GAIN)

        delta = drum_env - prev_drum_env
        if delta > RIPPLE_DELTA:
            ripples.append(Ripple(born_ms=elapsed, strength=min(1.0, delta * 4.0)))

        if drum_env > FLASH_THRESHOLD:
            flash = max(flash, (drum_env - FLASH_THRESHOLD) * 1.8)
        flash *= FLASH_DECAY

        centroid = sample_normalized(signals, "other", "spectral_centroid", t_sec)
        other_env = max(other_env * OTHER_DECAY, centroid)

        sub_raw = sample_normalized(signals, "bass", "sub_bass", t_sec)
        mid_raw = sample_normalized(signals, "bass", "mid_bass", t_sec)
        sub_env = max(sub_env * BASS_DECAY, sub_raw)
        mid_env = max(mid_env * BASS_DECAY, mid_raw)

        vocal_rms = sample_normalized(signals, "vocals", "rms", t_sec)
        vocal_rms_env = max(vocal_rms_env * VOCALS_DECAY, vocal_rms)

        pitch_hz = signals.sample("vocals", "pitch_hz", t_sec)
        if not math.isnan(pitch_hz) and pitch_hz > 0.0:
            target_hue = pitch_to_hue(pitch_hz)
            last_valid_hue = target_hue
            vocal_hue = lerp_hue(vocal_hue, target_hue, HUE_SMOOTH)
        else:
            vocal_hue = lerp_hue(vocal_hue, last_valid_hue, HUE_SMOOTH * 0.5)

        screen.fill(BG)

        if show_other:
            other_surf.fill((0, 0, 0, 0))
            draw_other_layer(other_surf, other_env)
            screen.blit(other_surf, (0, 0))

        if show_bass:
            bass_surf.fill((0, 0, 0, 0))
            draw_bass_layer(bass_surf, sub_env, mid_env)
            screen.blit(bass_surf, (0, 0))

        if show_vocals:
            vocals_surf.fill((0, 0, 0, 0))
            draw_vocals_layer(vocals_surf, vocal_rms_env, vocal_hue)
            screen.blit(vocals_surf, (0, 0))

        if show_drums:
            base_r = 40 + drum_env * 120
            draw_orb(screen, base_r, min(1.0, drum_env * 1.1))
            ripples = draw_ripples(screen, ripples, elapsed)
            draw_flash(screen, flash)

        overlay.draw(screen)
        pygame.display.flip()
        overlay.update(clock.tick(FPS) / 1000.0)

        prev_drum_env = drum_env
        if not playback.paused and not pygame.mixer.music.get_busy():
            if t_sec >= duration_sec - 0.05:
                running = False

    pygame.mixer.music.stop()
    pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-stem layered visualizer synced to mixed audio",
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
