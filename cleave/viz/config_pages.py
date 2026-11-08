"""Settings and Project pages opened from the menu bar.

They are inspector pages without a navigator row. The ids match the
inspector section map and the header hotkey map.
"""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.editor_mode_controls import is_preset_curation_mode


@dataclass(frozen=True)
class ConfigPage:
    id: str
    menu: str
    label: str


CONFIG_PAGES: tuple[ConfigPage, ...] = (
    ConfigPage("settings.preview", "Settings", "Preview"),
    ConfigPage("settings.ui", "Settings", "UI"),
    ConfigPage("project.resolution", "Project", "Resolution"),
    ConfigPage("project.render", "Project", "Render"),
    ConfigPage("project.compositor", "Project", "Compositor"),
    ConfigPage("project.projectm", "Project", "ProjectM"),
)

_BY_ID: dict[str, ConfigPage] = {page.id: page for page in CONFIG_PAGES}


def config_page(page_id: str) -> ConfigPage | None:
    return _BY_ID.get(page_id)


def is_config_page(node_id: str) -> bool:
    return node_id in _BY_ID


def config_page_title(page_id: str) -> str:
    """Breadcrumb such as ``Project > Resolution``. Unknown ids return as given."""
    page = _BY_ID.get(page_id)
    if page is None:
        return page_id
    return f"{page.menu} > {page.label}"


def available_config_page_ids(editor_mode: str) -> tuple[str, ...]:
    """Pages the menu can open. Preset curation has no Project pages."""
    curation = is_preset_curation_mode(editor_mode)
    return tuple(
        page.id for page in CONFIG_PAGES if not (curation and page.menu == "Project")
    )
