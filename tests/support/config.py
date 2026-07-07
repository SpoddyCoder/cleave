"""Shared config helpers for unit tests."""

from __future__ import annotations

from pathlib import Path

from cleave.config import ChromaBoostConfig, HighlightRolloffConfig, LayerConfig, RenderPostFxConfig, VIZ_CONFIG_FILENAME, dump_yaml
from cleave.user_config import EditorSettings
from cleave.config_schema import (
    DEFAULT_LAYER_SLOTS,
    DEFAULT_LAYER_Z_ORDER,
    default_chroma_boost_runtime_values,
    default_highlight_rolloff_runtime_values,
    template_layer_entry,
    template_visualizer_section,
)
from cleave.extract import STEM_NAMES, StemSource
from cleave.paths import repo_root
from cleave.preset_playlist import playlist_at_dir
from cleave.viz.session import ChromaBoostRuntime, HighlightRolloffRuntime, LayerRuntime, RenderPostFxRuntime

TEST_LAYER_STEMS: dict[str, StemSource] = {
    "layer_1": "drums",
    "layer_2": "bass",
    "layer_3": "vocals",
    "layer_4": "other",
}


def default_highlight_rolloff_config() -> HighlightRolloffConfig:
    return HighlightRolloffConfig(**default_highlight_rolloff_runtime_values())


def default_chroma_boost_config() -> ChromaBoostConfig:
    return ChromaBoostConfig(**default_chroma_boost_runtime_values())


def default_render_post_fx_config(**overrides: object) -> RenderPostFxConfig:
    values: dict[str, object] = {
        "enabled": True,
        "fade_in": 30.0,
        "fade_out": 4.0,
        "highlight_rolloff": default_highlight_rolloff_config(),
        "chroma_boost": default_chroma_boost_config(),
    }
    values.update(overrides)
    return RenderPostFxConfig(**values)  # type: ignore[arg-type]


def default_render_post_fx_runtime(**overrides: object) -> RenderPostFxRuntime:
    values: dict[str, object] = {
        "enabled": True,
        "expanded": False,
        "fade_in": 30.0,
        "fade_out": 4.0,
        "highlight_rolloff": HighlightRolloffRuntime(
            **default_highlight_rolloff_runtime_values()
        ),
        "highlight_rolloff_expanded": False,
        "chroma_boost": ChromaBoostRuntime(**default_chroma_boost_runtime_values()),
        "chroma_boost_expanded": False,
    }
    values.update(overrides)
    highlight_rolloff = values.pop("highlight_rolloff")
    chroma_boost = values.pop("chroma_boost")
    return RenderPostFxRuntime(
        highlight_rolloff=highlight_rolloff,
        chroma_boost=chroma_boost,
        **values,
    )  # type: ignore[arg-type]


def repo_root_template_path() -> Path:
    return repo_root() / VIZ_CONFIG_FILENAME


def slot_for_stem(stem: str) -> str:
    for slot, assigned in TEST_LAYER_STEMS.items():
        if assigned == stem:
            return slot
    raise KeyError(stem)


def make_preset_dirs(preset_root: Path) -> None:
    for stem in STEM_NAMES:
        stem_dir = preset_root / stem
        stem_dir.mkdir(parents=True, exist_ok=True)
        (stem_dir / "anchor.milk").write_text("milk", encoding="utf-8")


def layer_configs(preset_root: Path) -> dict[str, LayerConfig]:
    return {
        slot: LayerConfig(
            preset=preset_root / TEST_LAYER_STEMS[slot] / "anchor.milk",
            stem=TEST_LAYER_STEMS[slot],
        )
        for slot in DEFAULT_LAYER_SLOTS
    }


def layer_runtimes(
    preset_root: Path,
    **per_slot: dict,
) -> dict[str, LayerRuntime]:
    runtimes: dict[str, LayerRuntime] = {}
    for slot in DEFAULT_LAYER_SLOTS:
        stem = TEST_LAYER_STEMS[slot]
        stem_dir = preset_root / stem
        kwargs = per_slot.get(slot, {})
        runtimes[slot] = LayerRuntime(
            playlist=playlist_at_dir(stem_dir, index=0),
            browse_floor=stem_dir,
            **kwargs,
        )
    return runtimes


def write_minimal_config(project_dir: Path, preset_root: Path, **overrides) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    preset_root.mkdir(parents=True, exist_ok=True)

    for stem in STEM_NAMES:
        milk = preset_root / stem / f"{stem}.milk"
        milk.parent.mkdir(parents=True, exist_ok=True)
        milk.write_text(f"; minimal test preset for {stem}\n", encoding="utf-8")

    texture_root = preset_root / "textures"
    texture_root.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "visualizer": template_visualizer_section(name="cleave-test"),
        "paths": {
            "preset_root": str(preset_root),
            "texture_paths": [str(texture_root)],
        },
        "layer_z_order": list(DEFAULT_LAYER_Z_ORDER),
        "layers": {
            slot: {
                **template_layer_entry(slot, stem=TEST_LAYER_STEMS[slot]),
                "preset": (
                    f"{TEST_LAYER_STEMS[slot]}/{TEST_LAYER_STEMS[slot]}.milk"
                ),
            }
            for slot in DEFAULT_LAYER_SLOTS
        },
    }
    data.update(overrides)

    config_path = project_dir / VIZ_CONFIG_FILENAME
    with config_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    return config_path


def write_user_config_file(
    path: Path,
    *,
    preset_root: Path | None = None,
    texture_paths: tuple[Path, ...] | None = None,
    editor: EditorSettings | None = None,
) -> Path:
    """Write a minimal user config file for merge and path tests."""
    data: dict = {}
    if editor is not None:
        data["editor"] = {
            "preview_quality": editor.preview_quality,
            "ui_width_mode": editor.ui_width_mode,
            "ui_width": editor.ui_width,
            "ui_fade": editor.ui_fade,
        }
    if preset_root is not None or texture_paths is not None:
        paths: dict = {}
        if preset_root is not None:
            paths["preset_root"] = str(preset_root)
        if texture_paths is not None:
            paths["texture_paths"] = [str(entry) for entry in texture_paths]
        data["paths"] = paths
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)
    return path
