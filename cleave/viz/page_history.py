"""Back and Forward through recently shown inspector pages.

A page joins the history once it has stayed on screen for
``PAGE_VISIT_DWELL_SEC``, whatever selected it, so rows passed while
arrow-stepping are not kept. The history holds ``PAGE_HISTORY_LIMIT``
entries; a new visit drops the forward entries, like a browser.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

PAGE_HISTORY_LIMIT = 20
PAGE_VISIT_DWELL_SEC = 1.0

PageFilter = Callable[[str], bool]


class PageHistory:
    """Visited page ids and the position of the page on screen."""

    def __init__(
        self,
        *,
        limit: int = PAGE_HISTORY_LIMIT,
        dwell_sec: float = PAGE_VISIT_DWELL_SEC,
    ) -> None:
        self._limit = limit
        self._dwell_sec = dwell_sec
        self._entries: list[str] = []
        self._index = -1
        self._shown: str | None = None
        self._pending_sec = 0.0

    @property
    def entries(self) -> tuple[str, ...]:
        return tuple(self._entries)

    @property
    def index(self) -> int:
        return self._index

    def observe(self, page_id: str, dt_sec: float) -> None:
        """Note the page on screen this tick; commit it once it has dwelt."""
        if self._current() == page_id:
            self._shown = page_id
            return
        if not self._entries:
            self._shown = page_id
            self._commit(page_id)
            return
        if page_id != self._shown:
            # Time before this tick was spent on another page.
            self._shown = page_id
            self._pending_sec = 0.0
            return
        self._pending_sec += dt_sec
        if self._pending_sec >= self._dwell_sec:
            self._commit(page_id)

    def peek_back(self, can_show: PageFilter) -> str | None:
        """Page Back would show, without moving."""
        if self._shown is None:
            return None
        if self._uncommitted():
            candidates = self._entries[: self._index + 1]
        else:
            candidates = self._entries[: self._index]
        return _last_showable(reversed(candidates), self._shown, can_show)

    def peek_forward(self, can_show: PageFilter) -> str | None:
        """Page Forward would show, without moving."""
        if self._shown is None or self._uncommitted():
            return None
        candidates = self._entries[self._index + 1 :]
        return _last_showable(candidates, self._shown, can_show)

    def back(self, can_show: PageFilter) -> str | None:
        """Step back and return the page to show, or None at the oldest."""
        return self._step(-1, can_show)

    def forward(self, can_show: PageFilter) -> str | None:
        """Step forward and return the page to show, or None at the newest."""
        return self._step(1, can_show)

    def _step(self, delta: int, can_show: PageFilter) -> str | None:
        if self._shown is None:
            return None
        if self._uncommitted():
            self._commit(self._shown)
        self._prune(can_show)
        target = self._index + delta
        if not 0 <= target < len(self._entries):
            return None
        self._index = target
        self._shown = self._entries[target]
        self._pending_sec = 0.0
        return self._shown

    def _current(self) -> str | None:
        if self._index < 0:
            return None
        return self._entries[self._index]

    def _uncommitted(self) -> bool:
        return self._shown is not None and self._shown != self._current()

    def _commit(self, page_id: str) -> None:
        del self._entries[self._index + 1 :]
        self._entries.append(page_id)
        overflow = len(self._entries) - self._limit
        if overflow > 0:
            del self._entries[:overflow]
        self._index = len(self._entries) - 1
        self._pending_sec = 0.0

    def _prune(self, can_show: PageFilter) -> None:
        """Drop pages that can no longer be shown, then adjacent repeats."""
        kept: list[str] = []
        index = -1
        for position, page_id in enumerate(self._entries):
            keep = can_show(page_id) or page_id == self._shown
            if keep and not (kept and kept[-1] == page_id):
                kept.append(page_id)
            if position <= self._index and kept:
                index = len(kept) - 1
        self._entries = kept
        self._index = index if kept else -1


def _last_showable(
    candidates: Iterable[str], shown: str, can_show: PageFilter
) -> str | None:
    for page_id in candidates:
        if page_id != shown and can_show(page_id):
            return page_id
    return None
