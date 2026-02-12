"""AI-powered collection generation using Claude + TMDB enrichment."""

import json

import anthropic

from app.config import ANTHROPIC_API_KEY
from app.tmdb import search_movie

SYSTEM_PROMPT = """You are a movie expert. The user will describe a movie collection they want.
Return a JSON object with exactly this structure:
{
  "name": "Collection Name",
  "description": "A brief description of the collection",
  "movies": [
    {"title": "Movie Title", "year": 1999},
    ...
  ]
}

Rules:
- Return ONLY valid JSON, no markdown fences, no extra text
- The "movies" array must contain exactly the number of movies requested
- Each movie must have "title" (string) and "year" (integer)
- Only include real, well-known movies that match the user's request
- Order movies by relevance to the prompt"""


def generate_collection(prompt: str, movie_count: int = 10) -> dict:
    """Call Claude to generate a movie collection, then enrich with TMDB data.

    Returns:
        {"name": str, "description": str, "movies": [MovieCreate-compatible dicts]}

    Raises:
        ValueError: If API key is missing or Claude returns invalid data.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_message = f"{prompt}\n\nPlease return exactly {movie_count} movies."

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
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

    if "name" not in data or "movies" not in data:
        raise ValueError("Claude response missing required fields (name, movies)")

    # Enrich each movie with TMDB data
    enriched_movies = []
    for movie in data["movies"]:
        title = movie.get("title", "")
        year = movie.get("year")

        movie_data = {"title": title, "year": year, "overview": "", "poster_url": ""}

        tmdb_result = search_movie(title, year)
        if tmdb_result:
            movie_data["tmdb_id"] = tmdb_result["tmdb_id"]
            movie_data["imdb_id"] = tmdb_result["imdb_id"]
            movie_data["poster_url"] = tmdb_result["poster_url"]
            movie_data["overview"] = tmdb_result["overview"]
            movie_data["rating"] = tmdb_result["rating"]

        enriched_movies.append(movie_data)

    return {
        "name": data["name"],
        "description": data.get("description", ""),
        "movies": enriched_movies,
    }
