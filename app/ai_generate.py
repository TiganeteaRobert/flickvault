"""AI-powered collection generation using Claude + TMDB enrichment."""

import json

import anthropic

from app.config import ANTHROPIC_API_KEY
from app.tmdb import search_media


def _system_prompt(media_type: str, min_rating: float | None = None) -> str:
    if media_type == "show":
        item_label = "TV show"
        key = "shows"
    else:
        item_label = "movie"
        key = "movies"

    rating_rule = ""
    if min_rating is not None:
        rating_rule = f"\n- Only include {item_label}s with a strong reputation — aim for titles generally rated {min_rating}+ on TMDB/IMDb"

    return f"""You are a {item_label} expert. The user will describe a {item_label} collection they want.
Return a JSON object with exactly this structure:
{{
  "name": "Collection Name",
  "description": "A brief description of the collection",
  "{key}": [
    {{"title": "{item_label.title()} Title", "year": 1999}},
    ...
  ]
}}

Rules:
- Return ONLY valid JSON, no markdown fences, no extra text
- The "{key}" array must contain exactly the number of {item_label}s requested
- Each {item_label} must have "title" (string) and "year" (integer)
- Only include real, well-known {item_label}s that match the user's request
- Order {item_label}s by relevance to the prompt{rating_rule}"""


def generate_collection(
    prompt: str,
    movie_count: int = 10,
    anthropic_key: str | None = None,
    tmdb_key: str | None = None,
    media_type: str = "movie",
    min_rating: float | None = None,
) -> dict:
    """Call Claude to generate a collection, then enrich with TMDB data.

    Returns:
        {"name": str, "description": str, "movies": [MovieCreate-compatible dicts]}

    Raises:
        ValueError: If API key is missing or Claude returns invalid data.
    """
    ak = anthropic_key or ANTHROPIC_API_KEY
    if not ak:
        raise ValueError("ANTHROPIC_API_KEY is not set")

    item_label = "TV shows" if media_type == "show" else "movies"
    items_key = "shows" if media_type == "show" else "movies"

    client = anthropic.Anthropic(api_key=ak)

    # Request extra items when filtering by rating so we're more likely to hit the target count
    request_count = movie_count + 5 if min_rating is not None else movie_count
    user_message = f"{prompt}\n\nPlease return exactly {request_count} {item_label}."

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=_system_prompt(media_type, min_rating),
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text[: raw_text.rfind("```")]

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}")

    if "name" not in data or (items_key not in data and "movies" not in data):
        raise ValueError(f"Claude response missing required fields (name, {items_key})")

    items = data.get(items_key) or data.get("movies", [])

    # Enrich each item with TMDB data
    enriched_movies = []
    for item in items:
        title = item.get("title", "")
        year = item.get("year")

        movie_data = {"title": title, "year": year, "overview": "", "poster_url": "", "media_type": media_type}

        tmdb_result = search_media(title, year, media_type=media_type, api_key=tmdb_key)
        if tmdb_result:
            movie_data["tmdb_id"] = tmdb_result["tmdb_id"]
            movie_data["imdb_id"] = tmdb_result["imdb_id"]
            movie_data["poster_url"] = tmdb_result["poster_url"]
            movie_data["overview"] = tmdb_result["overview"]
            movie_data["rating"] = tmdb_result["rating"]

        enriched_movies.append(movie_data)

    # Filter by minimum rating if requested
    if min_rating is not None:
        enriched_movies = [
            m for m in enriched_movies
            if m.get("rating") is not None and m["rating"] >= min_rating
        ]
        # Trim back to the originally requested count
        enriched_movies = enriched_movies[:movie_count]

    return {
        "name": data["name"],
        "description": data.get("description", ""),
        "movies": enriched_movies,
    }
