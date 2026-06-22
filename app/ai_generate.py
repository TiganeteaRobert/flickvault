"""AI-powered collection generation using OpenRouter + TMDB enrichment."""

import json
from collections.abc import Generator

import httpx

from app.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_APP_TITLE,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_SITE_URL,
)
from app.recommendation_preferences import RecommendationPreferences, build_generation_user_message
from app.tmdb import search_media


OPENROUTER_CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"


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
    {{"title": "{item_label.title()} Title", "year": 1999, "reason": "One concise sentence explaining why this fits"}},
    ...
  ]
}}

Rules:
- Return ONLY valid JSON, no markdown fences, no extra text
- The "{key}" array must contain exactly the number of {item_label}s requested
- Each {item_label} must have "title" (string), "year" (integer), and "reason" (string)
- Only include real {item_label}s that match the user's request
- Calibrate title familiarity to the requested obscurity level
- Order {item_label}s by relevance to the prompt{rating_rule}"""


def generate_collection_iter(
    prompt: str,
    movie_count: int = 10,
    openrouter_key: str | None = None,
    tmdb_key: str | None = None,
    media_type: str = "movie",
    min_rating: float | None = None,
    exclude_titles: list[str] | None = None,
    preferences: RecommendationPreferences | None = None,
) -> Generator[dict, None, None]:
    """Generator that yields progress events and a final result.

    Yields:
        {"type": "progress", "found": int, "needed": int} — after each round if more are needed
        {"type": "result", "name": str, "description": str, "movies": list} — final result
    """
    ok = openrouter_key or OPENROUTER_API_KEY
    if not ok:
        raise ValueError("OPENROUTER_API_KEY is not set")

    item_label = "TV shows" if media_type == "show" else "movies"
    items_key = "shows" if media_type == "show" else "movies"

    system = _system_prompt(media_type, min_rating)

    all_exclude = set(exclude_titles or [])
    accepted: list[dict] = []
    collection_name = ""
    collection_desc = ""
    max_rounds = 5 if min_rating is not None else 1

    for round_num in range(max_rounds):
        still_needed = movie_count - len(accepted)
        if still_needed <= 0:
            break

        # Ask for extra on each round to compensate for filtering
        request_count = still_needed + 5 if min_rating is not None else still_needed
        user_message = build_generation_user_message(
            prompt,
            request_count,
            media_type,
            preferences=preferences,
        )

        if all_exclude:
            titles_list = ", ".join(f'"{t}"' for t in all_exclude)
            user_message += f"\n\nIMPORTANT: Do NOT include any of these titles (they are already in related collections or previous results): {titles_list}"

        raw_text = _call_openrouter(system, user_message, ok).strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[: raw_text.rfind("```")]

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"OpenRouter returned invalid JSON: {e}")

        if "name" not in data or (items_key not in data and "movies" not in data):
            raise ValueError(f"OpenRouter response missing required fields (name, {items_key})")

        # Keep name/description from the first round
        if round_num == 0:
            collection_name = data["name"]
            collection_desc = data.get("description", "")

        items = data.get(items_key) or data.get("movies", [])

        for item in items:
            title = item.get("title", "")
            year = item.get("year")
            reason = item.get("reason") or item.get("match_reason") or ""

            movie_data = {
                "title": title,
                "year": year,
                "overview": "",
                "poster_url": "",
                "media_type": media_type,
                "match_reason": reason,
            }

            tmdb_result = search_media(title, year, media_type=media_type, api_key=tmdb_key)
            if tmdb_result:
                movie_data["tmdb_id"] = tmdb_result["tmdb_id"]
                movie_data["imdb_id"] = tmdb_result["imdb_id"]
                movie_data["poster_url"] = tmdb_result["poster_url"]
                movie_data["overview"] = tmdb_result["overview"]
                movie_data["rating"] = tmdb_result["rating"]

            # Always exclude this title from future rounds
            all_exclude.add(title)

            # Apply rating filter
            if min_rating is not None:
                if movie_data.get("rating") is None or movie_data["rating"] < min_rating:
                    continue

            accepted.append(movie_data)
            if len(accepted) >= movie_count:
                break

        # If we still need more and have rounds left, yield progress
        if len(accepted) < movie_count and round_num < max_rounds - 1:
            yield {"type": "progress", "found": len(accepted), "needed": movie_count}

    yield {
        "type": "result",
        "name": collection_name,
        "description": collection_desc,
        "movies": accepted[:movie_count],
    }


def generate_collection(
    prompt: str,
    movie_count: int = 10,
    openrouter_key: str | None = None,
    tmdb_key: str | None = None,
    media_type: str = "movie",
    min_rating: float | None = None,
    exclude_titles: list[str] | None = None,
    preferences: RecommendationPreferences | None = None,
) -> dict:
    """Non-streaming wrapper. Returns the final result dict."""
    for event in generate_collection_iter(
        prompt, movie_count, openrouter_key=openrouter_key, tmdb_key=tmdb_key,
        media_type=media_type, min_rating=min_rating, exclude_titles=exclude_titles,
        preferences=preferences,
    ):
        if event["type"] == "result":
            return {"name": event["name"], "description": event["description"], "movies": event["movies"]}
    raise ValueError("Generation produced no result")


def _call_openrouter(system: str, user_message: str, openrouter_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 2048,
    }

    try:
        response = httpx.post(
            OPENROUTER_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as e:
        raise ValueError(f"OpenRouter request failed: {e}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"OpenRouter returned invalid response JSON: {e}") from e

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError("OpenRouter response missing message content") from e

    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)
