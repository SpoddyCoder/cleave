"""Inspector page history: dwell, Back/Forward, the cap, and pruning."""

from __future__ import annotations

from cleave.viz.page_history import (
    PAGE_HISTORY_LIMIT,
    PAGE_VISIT_DWELL_SEC,
    PageHistory,
)


def _any(_page_id: str) -> bool:
    return True


def _visit(history: PageHistory, *page_ids: str) -> None:
    for page_id in page_ids:
        history.observe(page_id, 0.0)
        history.observe(page_id, PAGE_VISIT_DWELL_SEC)


def test_first_page_commits_at_once_and_later_pages_after_the_dwell() -> None:
    history = PageHistory()
    history.observe("layers", 0.0)
    assert history.entries == ("layers",)
    history.observe("overlay", PAGE_VISIT_DWELL_SEC * 0.5)
    history.observe("post_fx", PAGE_VISIT_DWELL_SEC * 0.5)
    assert history.entries == ("layers",)
    history.observe("post_fx", PAGE_VISIT_DWELL_SEC * 0.6)
    assert history.entries == ("layers",)
    history.observe("post_fx", PAGE_VISIT_DWELL_SEC * 0.5)
    assert history.entries == ("layers", "post_fx")


def test_back_and_forward_step_and_return_none_at_the_ends() -> None:
    history = PageHistory()
    _visit(history, "a", "b", "c")
    assert history.peek_forward(_any) is None
    assert history.peek_back(_any) == "b"
    assert history.back(_any) == "b"
    history.observe("b", 5.0)
    assert history.back(_any) == "a"
    assert history.peek_back(_any) is None
    assert history.back(_any) is None
    assert history.forward(_any) == "b"
    assert history.forward(_any) == "c"
    assert history.forward(_any) is None
    assert history.entries == ("a", "b", "c")


def test_back_from_a_page_not_yet_dwelt_on_records_it_first() -> None:
    history = PageHistory()
    _visit(history, "a", "b")
    history.observe("c", 0.1)
    assert history.peek_back(_any) == "b"
    assert history.peek_forward(_any) is None
    assert history.back(_any) == "b"
    assert history.entries == ("a", "b", "c")
    assert history.forward(_any) == "c"


def test_a_new_visit_drops_the_forward_pages() -> None:
    history = PageHistory()
    _visit(history, "a", "b", "c")
    history.back(_any)
    history.back(_any)
    _visit(history, "d")
    assert history.entries == ("a", "d")
    assert history.peek_forward(_any) is None


def test_history_keeps_the_newest_twenty_pages() -> None:
    history = PageHistory()
    pages = [f"p{index}" for index in range(PAGE_HISTORY_LIMIT + 5)]
    _visit(history, *pages)
    assert history.entries == tuple(pages[-PAGE_HISTORY_LIMIT:])
    for _ in range(PAGE_HISTORY_LIMIT - 1):
        assert history.back(_any) is not None
    assert history.back(_any) is None
    assert history.peek_back(_any) is None


def test_pages_that_cannot_show_are_skipped_and_dropped() -> None:
    history = PageHistory()
    _visit(history, "a", "gone", "b")
    can_show = lambda page_id: page_id != "gone"  # noqa: E731
    assert history.peek_back(can_show) == "a"
    assert history.back(can_show) == "a"
    assert history.entries == ("a", "b")
    assert history.forward(can_show) == "b"


def test_dropping_a_page_merges_the_repeats_around_it() -> None:
    history = PageHistory()
    _visit(history, "a", "gone", "a")
    can_show = lambda page_id: page_id != "gone"  # noqa: E731
    assert history.peek_back(can_show) is None
    assert history.back(can_show) is None
    assert history.entries == ("a",)


def test_a_step_does_not_record_the_page_it_lands_on() -> None:
    history = PageHistory()
    _visit(history, "a", "b")
    history.back(_any)
    history.observe("a", PAGE_VISIT_DWELL_SEC * 2)
    assert history.entries == ("a", "b")
    assert history.index == 0
