from app.ai_generate import _system_prompt
from app.recommendation_preferences import (
    RecommendationPreferences,
    build_generation_user_message,
    normalize_obscurity_level,
)


def test_seed_movie_prompt_builds_movie_based_request():
    prefs = RecommendationPreferences(
        seed_title="Heat",
        seed_year=1995,
        obscurity_level=2,
        genres=["crime", "neo-noir"],
        tone="tense and melancholy",
    )

    message = build_generation_user_message(
        "more emotionally bruised than action-heavy",
        movie_count=8,
        media_type="movie",
        preferences=prefs,
    )

    assert 'Start from the movie "Heat" (1995)' in message
    assert "Return exactly 8 movies." in message
    assert "more emotionally bruised than action-heavy" in message
    assert "Obscurity level 2" in message
    assert "cult, international, older, or under-seen" in message
    assert "Genres: crime, neo-noir" in message
    assert "Tone: tense and melancholy" in message


def test_obscurity_level_is_clamped_from_hidden_gems_to_blockbusters():
    assert normalize_obscurity_level(0) == 1
    assert normalize_obscurity_level(3) == 3
    assert normalize_obscurity_level(99) == 5

    hidden = RecommendationPreferences(obscurity_level=1).obscurity_guidance
    mainstream = RecommendationPreferences(obscurity_level=5).obscurity_guidance

    assert "festival" in hidden
    assert "indie" in hidden
    assert "blockbuster" in mainstream
    assert "Avengers-scale" in mainstream


def test_advanced_constraints_are_rendered_in_the_generation_message():
    prefs = RecommendationPreferences(
        obscurity_level=4,
        genres=["science fiction", "mystery"],
        era="1990s",
        runtime="under_100",
        pace="slow_burn",
        ending_vibe="ambiguous",
        language_scope="non_english",
        watch_context="date_night",
        exclude_seen=True,
    )

    message = build_generation_user_message(
        "dreamlike puzzle films",
        movie_count=12,
        media_type="movie",
        preferences=prefs,
    )

    assert "Genres: science fiction, mystery" in message
    assert "Era: primarily from the 1990s" in message
    assert "Runtime: under 100 minutes" in message
    assert "Pace: slow burn" in message
    assert "Ending vibe: ambiguous or conversation-starting" in message
    assert "Language: prefer non-English-language picks" in message
    assert "Watch context: date night" in message
    assert "Avoid every title already saved in the user's vault" in message


def test_system_prompt_requires_per_title_reasons_and_real_titles():
    prompt = _system_prompt("movie", min_rating=7.0)

    assert '"reason": "One concise sentence explaining why this fits"' in prompt
    assert "Only include real movies" in prompt
    assert "well-known" not in prompt
    assert "rated 7.0+" in prompt
