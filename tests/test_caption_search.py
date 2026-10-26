"""Regression tests for A06: caption search keeps object type and number bounds.

``caption_search_terms`` must not turn a ``Table 1`` request into a ``Fig. 1``
search, and ``find_caption_start`` must reject matches that continue into
another digit or a panel letter (``Fig. 1`` vs ``Fig. 10`` / ``Fig. 1A``).
"""

from __future__ import annotations

import extract_figure_region as region
import pytest
from label_utils import caption_prefix_matches, caption_search_terms


class FakeSearcher:
    def __init__(self, starts, length):
        self._starts = starts
        self._length = length
        self._index = 0

    def get_next(self):
        if self._index >= len(self._starts):
            return None
        start = self._starts[self._index]
        self._index += 1
        return start, self._length


class FakeTextPage:
    def __init__(self, text):
        self.text = text

    def search(self, term, match_case=False, match_whole_word=False):
        haystack = self.text if match_case else self.text.lower()
        needle = term if match_case else term.lower()
        starts = []
        index = haystack.find(needle)
        while index != -1:
            starts.append(index)
            index = haystack.find(needle, index + 1)
        return FakeSearcher(starts, len(term))

    def get_text_range(self, start, count):
        if start < 0 or start >= len(self.text):
            return ""
        return self.text[start : start + count]


class FakeTextPageWithoutLayer:
    def count_chars(self):
        return 0


class FakeTextPageRaising:
    def count_chars(self):
        raise RuntimeError("pdfium text-layer failure")


class FakePage:
    def __init__(self, text_page):
        self._text_page = text_page

    def get_textpage(self):
        return self._text_page


class TestCaptionSearchTerms:
    def test_main_figure_terms(self):
        terms = caption_search_terms("Fig.1")
        assert terms == ["Figure 1", "Fig. 1", "Fig.1"]

    def test_supplementary_figure_terms(self):
        terms = caption_search_terms("Fig.S1")
        assert "Supplementary Figure 1" in terms
        assert "Figure S1" in terms
        assert all("S1" in term or "Supplementary" in term for term in terms)

    def test_table_terms_never_include_figure_words(self):
        terms = caption_search_terms("Table1")
        assert terms == ["Table 1", "Table1"]
        assert not any("fig" in term.lower() for term in terms)

    def test_supplementary_table_terms(self):
        terms = caption_search_terms("Table S2")
        assert "Table S2" in terms
        assert any("Supplementary Table" in term for term in terms)

    def test_supplementary_figure_number_three(self):
        assert "Supplementary Figure 3" in caption_search_terms("Supplementary Figure 3")

    def test_unparseable_label_falls_back_to_its_text(self):
        assert caption_search_terms("自定义图") == ["自定义图"]


class TestCaptionPrefixMatches:
    def test_table_caption_matches_table_label(self):
        assert caption_prefix_matches("Table 1: clinical data", "Table1") is True

    def test_table_label_rejects_figure_caption(self):
        assert caption_prefix_matches("Fig. 1 | synthesis", "Table1") is False

    def test_figure_caption_matches_figure_label(self):
        assert caption_prefix_matches("Figure 3. results", "Fig.3") is True

    def test_figure_label_rejects_table_caption(self):
        assert caption_prefix_matches("Table 2 | results", "Fig.3") is False

    @pytest.mark.parametrize(
        ("caption", "label", "expected"),
        [
            ("Fig. 10. wrong number", "Fig.1", False),
            ("Fig. 1. caption", "Fig.1", True),
            ("Table 1. rows", "Table1", True),
            ("Table 2. rows", "Table1", False),
        ],
    )
    def test_prefix_matches_checks_the_object_number(self, caption, label, expected):
        assert caption_prefix_matches(caption, label) is expected

    @pytest.mark.parametrize(
        ("caption", "label", "expected"),
        [
            ("Fig. S1. supplementary caption", "Fig.S1", True),
            ("Figure S1. supplementary caption", "Fig.S1", True),
            ("Fig. 1. caption", "Fig.S1", False),
            ("Fig. S1. caption", "Fig.1", False),
        ],
    )
    def test_prefix_matches_distinguishes_supplementary_numbers(
        self, caption, label, expected
    ):
        assert caption_prefix_matches(caption, label) is expected

    @pytest.mark.parametrize(
        ("caption", "label", "expected"),
        [
            ("Table 1. rows", "Fig. 1", False),
            ("Fig. 1. caption", "Table1", False),
        ],
    )
    def test_prefix_matches_checks_the_object_type(self, caption, label, expected):
        assert caption_prefix_matches(caption, label) is expected

    def test_unparseable_label_is_accepted(self):
        assert caption_prefix_matches("anything", "自定义图") is True


class TestFindCaptionStart:
    def test_fig1_does_not_match_fig10(self):
        text = "Fig. 10 overview\nFig. 1 | caption"
        page = FakeTextPage(text)
        start, term = region.find_caption_start(page, "Fig.1")
        assert start == text.index("Fig. 1 |")
        assert term in caption_search_terms("Fig.1")

    def test_fig1_does_not_match_fig1a(self):
        text = "Fig. 1A | panel demo\nFig. 1 | caption"
        page = FakeTextPage(text)
        start, _term = region.find_caption_start(page, "Fig.1")
        assert start == text.index("Fig. 1 |")

    def test_table_request_does_not_select_a_figure(self):
        text = "Fig. 1 | synthesis\nTable 1: clinical data"
        page = FakeTextPage(text)
        start, term = region.find_caption_start(page, "Table1")
        assert start == text.index("Table 1:")
        assert "table" in term.lower()

    def test_supplementary_figure_uses_supplementary_terms(self):
        text = "Supplementary Figure 1 | synthetic scheme"
        page = FakeTextPage(text)
        start, term = region.find_caption_start(page, "Fig.S1")
        assert start == 0
        assert term == "Supplementary Figure 1"

    def test_in_text_reference_is_not_preferred_over_the_caption_line(self):
        text = "as shown in Fig. 1 and later\nFig. 1 | caption"
        page = FakeTextPage(text)
        start, _term = region.find_caption_start(page, "Fig.1")
        assert start == text.index("Fig. 1 |")

    def test_only_in_text_reference_raises_caption_uncertain(self):
        page = FakeTextPage("as shown in Fig. 1 for details.")
        with pytest.raises(ValueError, match="caption_uncertain"):
            region.find_caption_start(page, "Fig.1")

    def test_missing_caption_raises_caption_not_found(self):
        page = FakeTextPage("no figure labels here")
        with pytest.raises(ValueError, match="caption_not_found"):
            region.find_caption_start(page, "Fig.1")

    def test_period_after_the_number_is_a_caption(self):
        text = "Fig. 1. caption starts here"
        start, term = region.find_caption_start(FakeTextPage(text), "Fig.1")
        assert start == 0
        assert term == "Fig. 1"

    def test_period_after_a_supplementary_number_is_a_caption(self):
        text = "Fig. S1. supplementary caption"
        start, term = region.find_caption_start(FakeTextPage(text), "Fig.S1")
        assert start == 0
        assert term == "Fig. S1"

    @pytest.mark.parametrize(
        "text",
        ["Fig. 1.2 continuation", "Fig. 1.A continuation"],
    )
    def test_dotted_continuation_is_not_accepted_as_a_caption(self, text):
        with pytest.raises(ValueError, match="caption_not_found"):
            region.find_caption_start(FakeTextPage(text), "Fig.1")

    def test_dotted_continuation_does_not_shadow_a_real_caption(self):
        text = "Fig. 1.2 continuing panel\nFig. 1. caption"
        start, _term = region.find_caption_start(FakeTextPage(text), "Fig.1")
        assert start == text.index("Fig. 1. caption")


class TestUnsupportedTextLayer:
    def test_page_without_text_layer_reports_unsupported(self):
        page = FakePage(FakeTextPageWithoutLayer())
        with pytest.raises(ValueError, match="unsupported_text_layer"):
            region.caption_for_page(page, 800.0, "Fig.1")

    def test_text_layer_failure_is_wrapped_as_unsupported(self):
        page = FakePage(FakeTextPageRaising())
        with pytest.raises(ValueError, match="unsupported_text_layer"):
            region.caption_for_page(page, 800.0, "Fig.1")
