"""Preset scan probe profiles, classification, and JSON report types."""

from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pygame
from OpenGL.GL import (
    GL_COLOR_ATTACHMENT0,
    GL_DEPTH_ATTACHMENT,
    GL_DEPTH_COMPONENT24,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_COMPLETE,
    GL_RENDERBUFFER,
    GL_RGBA,
    GL_RGBA8,
    GL_TEXTURE_2D,
    GL_UNSIGNED_BYTE,
    glBindFramebuffer,
    glBindRenderbuffer,
    glBindTexture,
    glCheckFramebufferStatus,
    glDeleteFramebuffers,
    glDeleteRenderbuffers,
    glDeleteTextures,
    glFramebufferRenderbuffer,
    glFramebufferTexture2D,
    glGenFramebuffers,
    glGenRenderbuffers,
    glGenTextures,
    glReadPixels,
    glRenderbufferStorage,
    glTexImage2D,
)

from cleave.pcm_io import SAMPLE_RATE_HZ
from cleave.preset_scan_targets import PresetTarget, ScanTargets
from cleave.projectm import PresetLoadFailure, ProjectM
from cleave.stem_pcm import samples_per_frame

ProbeMode = Literal["quick", "slow"]
ScanMode = Literal["project", "bulk"]
PresetResultCategory = Literal["load_failed", "black", "dim", "ok"]

QUICK_PROBE_FRAMES = 15
QUICK_PROBE_WARMUP_SEC = 0.5
SLOW_PROBE_FRAMES = 60
SLOW_PROBE_WARMUP_SEC = 3.0
PROBE_FPS = 30
PROBE_FBO_WIDTH = 480
PROBE_FBO_HEIGHT = 270
LUMA_PATCH_SIZE = 32

BLACK_MAX_LUMA_THRESHOLD = 1.0
DIM_MEAN_LUMA_THRESHOLD = 8.0

SCAN_THRESHOLDS: dict[str, float] = {
    "black_max_luma": BLACK_MAX_LUMA_THRESHOLD,
    "dim_mean_luma": DIM_MEAN_LUMA_THRESHOLD,
}


@dataclass(frozen=True)
class ProbeProfile:
    frames: int
    warmup_sec: float
    mode: ProbeMode


@dataclass(frozen=True)
class PresetScanTimings:
    load_sec: float | None = None
    render_sec: float | None = None


@dataclass(frozen=True)
class PresetScanResult:
    path: Path
    result: PresetResultCategory
    layers: tuple[str, ...]
    error: str | None = None
    timings: PresetScanTimings | None = None


@dataclass(frozen=True)
class ScanReport:
    scan_mode: ScanMode
    probe_mode: ProbeMode
    project_dir: Path | None
    config_path: Path | None
    presets_dir: Path | None
    preset_root: Path | None
    texture_paths: tuple[Path, ...]
    layers: dict[str, list[str]]
    thresholds: dict[str, float]
    probe_frames: int
    probe_fps: int
    fbo_size: tuple[int, int]
    presets: tuple[PresetScanResult, ...]


def probe_profile(*, slow: bool = False) -> ProbeProfile:
    if slow:
        return ProbeProfile(
            frames=SLOW_PROBE_FRAMES,
            warmup_sec=SLOW_PROBE_WARMUP_SEC,
            mode="slow",
        )
    return ProbeProfile(
        frames=QUICK_PROBE_FRAMES,
        warmup_sec=QUICK_PROBE_WARMUP_SEC,
        mode="quick",
    )


def classify_preset_result(
    failures: list[PresetLoadFailure],
    max_luma: float,
    mean_luma: float,
) -> tuple[PresetResultCategory, str | None]:
    if failures:
        return "load_failed", failures[0].message
    if max_luma < BLACK_MAX_LUMA_THRESHOLD:
        return "black", None
    if mean_luma < DIM_MEAN_LUMA_THRESHOLD:
        return "dim", None
    return "ok", None


def build_scan_report(
    *,
    scan_mode: ScanMode,
    profile: ProbeProfile,
    targets: ScanTargets,
    results: list[PresetScanResult] | tuple[PresetScanResult, ...],
    project_dir: Path | None = None,
    config_path: Path | None = None,
) -> ScanReport:
    layers = {
        slot: [str(path) for path in paths]
        for slot, paths in sorted(targets.layer_sources.items())
    }
    return ScanReport(
        scan_mode=scan_mode,
        probe_mode=profile.mode,
        project_dir=project_dir.resolve() if project_dir is not None else None,
        config_path=config_path.resolve() if config_path is not None else None,
        presets_dir=(
            targets.presets_dir.resolve() if targets.presets_dir is not None else None
        ),
        preset_root=(
            targets.preset_root.resolve() if targets.preset_root is not None else None
        ),
        texture_paths=tuple(p.resolve() for p in targets.texture_paths),
        layers=layers,
        thresholds=dict(SCAN_THRESHOLDS),
        probe_frames=profile.frames,
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
        presets=tuple(results),
    )


def scan_report_summary(report: ScanReport) -> dict[str, int]:
    counts: dict[str, int] = {
        "total": len(report.presets),
        "load_failed": 0,
        "black": 0,
        "dim": 0,
        "ok": 0,
    }
    for preset in report.presets:
        counts[preset.result] += 1
    return counts


def scan_report_to_dict(report: ScanReport) -> dict[str, Any]:
    return {
        "scan_mode": report.scan_mode,
        "probe_mode": report.probe_mode,
        "project_dir": _path_to_str(report.project_dir),
        "config_path": _path_to_str(report.config_path),
        "presets_dir": _path_to_str(report.presets_dir),
        "preset_root": _path_to_str(report.preset_root),
        "texture_paths": [str(path) for path in report.texture_paths],
        "layers": report.layers,
        "thresholds": report.thresholds,
        "probe_frames": report.probe_frames,
        "probe_fps": report.probe_fps,
        "fbo_size": list(report.fbo_size),
        "presets": [_preset_result_to_dict(preset) for preset in report.presets],
        "summary": scan_report_summary(report),
    }


def write_scan_report(path: Path, report: ScanReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(scan_report_to_dict(report), fh, indent=2)
        fh.write("\n")


def run_scan(
    targets: ScanTargets,
    *,
    slow: bool = False,
    texture_paths: tuple[Path, ...] | None = None,
) -> list[PresetScanResult]:
    """Probe each preset in *targets* with a hidden GL context and one ProjectM."""
    profile = probe_profile(slow=slow)
    paths = texture_paths if texture_paths is not None else targets.texture_paths
    texture_strs = [str(path) for path in paths]

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.init()
    try:
        pygame.display.set_mode(
            (PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
            pygame.OPENGL | pygame.HIDDEN,
        )
    except pygame.error as exc:
        pygame.quit()
        raise RuntimeError(f"failed to open OpenGL context: {exc}") from exc

    pm: ProjectM | None = None
    fbo: _ProbeFbo | None = None
    results: list[PresetScanResult] = []
    total = len(targets.presets)
    try:
        pm = ProjectM()
        pm.set_window_size(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        pm.set_fps(PROBE_FPS)
        pm.set_hard_cut_enabled(False)
        pm.set_texture_paths(texture_strs)

        fbo = _ProbeFbo(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        n_pcm = samples_per_frame(PROBE_FPS)
        warmup_frames = max(1, math.ceil(profile.warmup_sec * PROBE_FPS))
        frame_dt = 1.0 / PROBE_FPS

        for index, target in enumerate(targets.presets, start=1):
            _progress(f"Scanning {index}/{total} {target.path}...")
            result = _probe_preset(
                pm,
                fbo,
                target,
                profile=profile,
                n_pcm=n_pcm,
                warmup_frames=warmup_frames,
                frame_dt=frame_dt,
            )
            results.append(result)
    finally:
        if fbo is not None:
            fbo.destroy()
        if pm is not None:
            pm.destroy()
        pygame.quit()

    return results


def _progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _probe_preset(
    pm: ProjectM,
    fbo: _ProbeFbo,
    target: PresetTarget,
    *,
    profile: ProbeProfile,
    n_pcm: int,
    warmup_frames: int,
    frame_dt: float,
) -> PresetScanResult:
    pm.drain_preset_failures()

    load_started = time.perf_counter()
    pm.load_preset(target.path, smooth=False)
    pm.lock_preset(True)
    load_sec = time.perf_counter() - load_started

    render_started = time.perf_counter()
    frame_idx = 0
    max_luma = 0.0
    mean_luma = 0.0

    for _ in range(warmup_frames + profile.frames):
        t_sec = frame_idx * frame_dt
        pm.set_frame_time(t_sec)
        pm.feed_pcm(_synthetic_pcm_burst(frame_idx, n_pcm))
        fbo.bind()
        pm.render_to_fbo(fbo.fbo_id)
        if frame_idx >= warmup_frames:
            max_luma, mean_luma = _sample_center_luma(
                PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT
            )
        frame_idx += 1

    render_sec = time.perf_counter() - render_started
    failures = pm.drain_preset_failures()
    category, error = classify_preset_result(failures, max_luma, mean_luma)

    return PresetScanResult(
        path=target.path,
        result=category,
        layers=target.layers,
        error=error,
        timings=PresetScanTimings(load_sec=load_sec, render_sec=render_sec),
    )


def _synthetic_pcm_burst(frame_idx: int, n_samples: int) -> np.ndarray:
    """Mono PCM with energy every frame (sine plus light noise, never silence)."""
    if n_samples <= 0:
        return np.zeros(1, dtype=np.float32)

    t = np.arange(n_samples, dtype=np.float32) / SAMPLE_RATE_HZ
    freq = 440.0 + float(frame_idx % 7) * 55.0
    phase = float(frame_idx) * 0.41
    sine = (0.65 * np.sin(2.0 * math.pi * freq * t + phase)).astype(np.float32)
    rng = np.random.default_rng(frame_idx)
    noise = 0.12 * rng.standard_normal(n_samples).astype(np.float32)
    return np.clip(sine + noise, -1.0, 1.0).astype(np.float32)


def _sample_center_luma(width: int, height: int) -> tuple[float, float]:
    patch = min(LUMA_PATCH_SIZE, width, height)
    x = (width - patch) // 2
    y = (height - patch) // 2
    raw = glReadPixels(x, y, patch, patch, GL_RGBA, GL_UNSIGNED_BYTE)
    rgba = np.frombuffer(raw, dtype=np.uint8).reshape(patch, patch, 4)
    r = rgba[..., 0].astype(np.float32)
    g = rgba[..., 1].astype(np.float32)
    b = rgba[..., 2].astype(np.float32)
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return float(luma.max()), float(luma.mean())


def _gl_name(gen_fn, count: int = 1) -> int:
    names = gen_fn(count)
    try:
        return int(names[0])
    except (TypeError, IndexError):
        return int(names)


class _ProbeFbo:
    """Minimal RGBA FBO for raw projectM probe output."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._texture_id = _gl_name(glGenTextures)
        self._depth_rbo_id = _gl_name(glGenRenderbuffers)
        self.fbo_id = _gl_name(glGenFramebuffers)

        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA8,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )
        glBindRenderbuffer(GL_RENDERBUFFER, self._depth_rbo_id)
        glRenderbufferStorage(
            GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height
        )

        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo_id)
        glFramebufferTexture2D(
            GL_FRAMEBUFFER,
            GL_COLOR_ATTACHMENT0,
            GL_TEXTURE_2D,
            self._texture_id,
            0,
        )
        glFramebufferRenderbuffer(
            GL_FRAMEBUFFER,
            GL_DEPTH_ATTACHMENT,
            GL_RENDERBUFFER,
            self._depth_rbo_id,
        )
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glBindRenderbuffer(GL_RENDERBUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        if status != GL_FRAMEBUFFER_COMPLETE:
            self.destroy()
            raise RuntimeError(
                f"probe FBO incomplete ({width}x{height}): status 0x{status:x}"
            )

    def bind(self) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo_id)

    def destroy(self) -> None:
        if self._texture_id:
            glDeleteTextures(1, [self._texture_id])
            self._texture_id = 0
        if self._depth_rbo_id:
            glDeleteRenderbuffers(1, [self._depth_rbo_id])
            self._depth_rbo_id = 0
        if self.fbo_id:
            glDeleteFramebuffers(1, [self.fbo_id])
            self.fbo_id = 0


def _path_to_str(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path)


def _preset_result_to_dict(preset: PresetScanResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(preset.path),
        "result": preset.result,
        "layers": list(preset.layers),
    }
    if preset.error is not None:
        payload["error"] = preset.error
    if preset.timings is not None:
        timings: dict[str, float] = {}
        if preset.timings.load_sec is not None:
            timings["load_sec"] = preset.timings.load_sec
        if preset.timings.render_sec is not None:
            timings["render_sec"] = preset.timings.render_sec
        if timings:
            payload["timings"] = timings
    return payload
