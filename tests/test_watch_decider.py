from app.watch_decider import rank_watch_picks, summarize_collection


def test_rank_watch_picks_prefers_high_confidence_movie_for_sure_thing():
    movies = [
        {
            "id": 1,
            "title": "Unknown Drift",
            "year": 2022,
            "rating": 6.3,
            "overview": "A sparse experiment.",
            "match_reason": "",
            "sort_order": 1,
        },
        {
            "id": 2,
            "title": "The Safe Bet",
            "year": 2019,
            "rating": 8.4,
            "overview": "A tense and elegant crowd-pleaser.",
            "match_reason": "Strong fit for the collection tone and a reliable Friday-night watch.",
            "sort_order": 2,
        },
        {
            "id": 3,
            "title": "Pretty Good",
            "year": 2001,
            "rating": 7.2,
            "overview": "A fine pick.",
            "match_reason": "Matches the mood.",
            "sort_order": 3,
        },
    ]

    picks = rank_watch_picks(movies, mode="sure_thing", limit=2)

    assert [pick["title"] for pick in picks] == ["The Safe Bet", "Pretty Good"]
    assert picks[0]["score"] > picks[1]["score"]
    assert "highest rated" in picks[0]["why"].lower()
    assert "match reason" in picks[0]["badges"]


def test_rank_watch_picks_supports_context_modes():
    movies = [
        {
            "id": 1,
            "title": "Old Masterpiece",
            "year": 1968,
            "rating": 8.1,
            "overview": "A patient classic drama.",
            "match_reason": "Canon-level craft.",
            "sort_order": 1,
        },
        {
            "id": 2,
            "title": "New Pulse",
            "year": 2024,
            "rating": 7.3,
            "overview": "A propulsive thriller with a fast tempo.",
            "match_reason": "High energy and very watchable.",
            "sort_order": 2,
        },
        {
            "id": 3,
            "title": "Puzzle Box",
            "year": 2012,
            "rating": 7.6,
            "overview": "A strange mystery with dream logic and ambiguous clues.",
            "match_reason": "A cerebral sci-fi mind-bender.",
            "sort_order": 3,
        },
    ]

    assert rank_watch_picks(movies, mode="classic", limit=1)[0]["title"] == "Old Masterpiece"
    assert rank_watch_picks(movies, mode="newer", limit=1)[0]["title"] == "New Pulse"
    assert rank_watch_picks(movies, mode="mind_bender", limit=1)[0]["title"] == "Puzzle Box"


def test_summarize_collection_reports_decision_context():
    collection = {
        "movies": [
            {"title": "A", "year": 1979, "rating": 8.2, "match_reason": "Great fit"},
            {"title": "B", "year": 1984, "rating": None, "match_reason": ""},
            {"title": "C", "year": 2021, "rating": 7.1, "match_reason": "Good fit"},
        ]
    }

    stats = summarize_collection(collection)

    assert stats["movie_count"] == 3
    assert stats["average_rating"] == 7.7
    assert stats["highest_rating"] == 8.2
    assert stats["year_span"] == "1979-2021"
    assert stats["unrated_count"] == 1
    assert stats["explained_count"] == 2
    assert stats["decades"] == {"1970s": 1, "1980s": 1, "2020s": 1}
