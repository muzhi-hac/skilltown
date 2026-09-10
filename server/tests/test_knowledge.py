"""What the corpus must be able to answer, stated as tests.

If a question in the product asks about a number, the retriever has to reach the
passage that carries that number. These cases pin that down so a chunking change
cannot quietly break the grounding.
"""

from __future__ import annotations

import pytest

from server.core import knowledge


def test_the_corpus_loads_both_documents():
    chunks = knowledge.corpus()
    assert len(chunks) > 40
    sources = {chunk.source for chunk in chunks}
    assert any("Thresholds" in source for source in sources)
    assert any("Regulation Reference" in source for source in sources)


def test_every_chunk_has_an_id_a_path_and_substance():
    for chunk in knowledge.corpus():
        assert chunk.id and chunk.title and chunk.path
        assert len(chunk.text) >= 80
        assert chunk.id.startswith(("ANNEX-", "REF-"))


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        ("gift from a public official worth 40 euro Germany", "ANNEX-1.2"),
        ("business meal 120 euro per person private sector", "ANNEX-1.3"),
        ("personal data breach notify supervisory authority 72 hours", "ANNEX-2.1"),
        ("cash payment of 12000 euro prohibited commercial transaction", "ANNEX-4.1"),
        ("beneficial ownership 25 percent threshold", "ANNEX-4.2"),
        ("NIS2 early warning within 24 hours of awareness", "ANNEX-5.1"),
        ("maximum weekly working hours 48 averaged", "ANNEX-6.1"),
        ("whistleblower report acknowledged within 7 days", "ANNEX-6.3"),
        ("GDPR fine 20 million or 4 percent of turnover", "ANNEX-2.4"),
    ],
)
def test_a_number_question_reaches_the_passage_that_carries_it(query, expected_id):
    hits = knowledge.search(query, limit=3)
    assert expected_id in [chunk.id for chunk in hits], [chunk.id for chunk in hits]


def test_search_can_be_narrowed_to_a_section():
    hits = knowledge.search("thresholds", limit=5, within="Anti-Corruption")
    assert hits
    assert all("Anti-Corruption" in chunk.path for chunk in hits)


def test_lookup_by_id_and_excerpt_trimming():
    chunk = knowledge.get("ANNEX-1.2")
    assert chunk is not None
    assert "25" in chunk.text
    excerpt = chunk.excerpt()
    assert len(excerpt) <= knowledge.EXCERPT_CHARS + 2
    assert knowledge.get("does-not-exist") is None
    assert [c.id for c in knowledge.get_many(["ANNEX-1.2", "nope"])] == ["ANNEX-1.2"]


def test_an_empty_or_stopword_only_query_returns_nothing():
    assert knowledge.search("") == []
    assert knowledge.search("the and of to") == []
