from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_collection_template_contains_decision_and_shortlist_controls():
    html = (ROOT / "app" / "templates" / "collection.html").read_text()

    assert "watch-mode-btn" in html
    assert "decision-panel" in html
    assert "decision-picks" in html
    assert "shortlist-btn" in html
    assert "compare-drawer" in html


def test_index_template_surfaces_collection_decision_stats():
    html = (ROOT / "app" / "templates" / "index.html").read_text()

    assert "average_rating" in html
    assert "year_span" in html
