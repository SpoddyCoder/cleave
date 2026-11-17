"""Settings > UI theme files: open the themes folder, reload it, and show problems."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.config import CleaveConfig
from cleave.paths import themes_dir
from cleave.viz.modal import ModalHost
from cleave.viz.theme import (
    BUILTIN_PALETTES,
    all_palettes,
    palette_for_theme,
    set_palette,
)
from cleave.viz.user_themes import install_user_themes

PROBLEMS_TITLE = "Problems in theme files"
# The notice lists at most this many problems, then says how many more.
MAX_LISTED_PROBLEMS = 12


def reloaded_message(count: int) -> str:
    noun = "theme" if count == 1 else "themes"
    return f"Themes reloaded: {count} user {noun} found"


def problems_body(problems: Sequence[str]) -> str:
    """One problem per line, up to ``MAX_LISTED_PROBLEMS``."""
    lines = list(problems[:MAX_LISTED_PROBLEMS])
    hidden = len(problems) - len(lines)
    if hidden > 0:
        lines.append(f"and {hidden} more")
    return "\n".join(lines)


class ThemeFileControls:
    """Reload user theme files and report what is wrong with them."""

    def __init__(
        self,
        cfg: CleaveConfig,
        modal: ModalHost,
        *,
        on_notification: Callable[[str], None],
    ) -> None:
        self.cfg = cfg
        self._modal = modal
        self._on_notification = on_notification

    def reload(self) -> None:
        """Re-read the themes folder and redraw with the chosen theme's colours."""
        problems = install_user_themes(themes_dir())
        set_palette(palette_for_theme(self.cfg.editor.theme))
        if problems:
            self.show_problems(problems)
            return
        self._on_notification(
            reloaded_message(len(all_palettes()) - len(BUILTIN_PALETTES))
        )

    def show_problems(self, problems: Sequence[str]) -> None:
        """List *problems* in a notice; nothing happens when there are none."""
        if not problems:
            return
        self._modal.prompt_notice(PROBLEMS_TITLE, body=problems_body(problems))

    def open_folder(self) -> None:
        """Show the themes folder in the file manager, creating it if needed."""
        from cleave.file_manager import open_folder

        folder = themes_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            open_folder(folder)
        except OSError as exc:
            self._on_notification(f"Could not open the themes folder: {exc}")
