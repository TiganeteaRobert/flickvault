"""TMDB API client for fetching movie posters and metadata."""

import httpx

from app.config import TMDB_API_KEY

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def search_movie(title: str, year: int | None = None, api_key: str | None = None) -> dict | None:
    """Search TMDB for a movie and return poster_url, overview, tmdb_id, imdb_id.

    Returns None if no match is found or API key is missing.
    """
    key = api_key or TMDB_API_KEY
    if not key:
        return None

    params = {"api_key": key, "query": title}
    if year:
        params["year"] = year

    try:
        resp = httpx.get(f"{TMDB_BASE_URL}/search/movie", params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        movie = results[0]
        tmdb_id = str(movie["id"])

        poster_url = ""
        if movie.get("poster_path"):
            poster_url = f"{TMDB_IMAGE_BASE}{movie['poster_path']}"

        overview = movie.get("overview", "")
        rating = movie.get("vote_average")

        # Fetch external IDs (imdb_id) from TMDB
        imdb_id = _fetch_imdb_id(tmdb_id, api_key=key)

        return {
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
            "poster_url": poster_url,
            "overview": overview,
            "rating": round(rating, 1) if rating else None,
        }
    except httpx.HTTPError:
        return None


def _fetch_imdb_id(tmdb_id: str, api_key: str | None = None) -> str | None:
    """Fetch the IMDb ID for a movie from TMDB external IDs endpoint."""
    key = api_key or TMDB_API_KEY
    try:
        resp = httpx.get(
            f"{TMDB_BASE_URL}/movie/{tmdb_id}/external_ids",
            params={"api_key": key},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("imdb_id") or None
    except httpx.HTTPError:
        return None
