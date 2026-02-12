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


def get_movie_details(tmdb_id: str, api_key: str | None = None) -> dict | None:
    """Fetch enriched movie details (genres, runtime, cast, etc.) from TMDB.

    Returns None on failure.
    """
    key = api_key or TMDB_API_KEY
    if not key:
        return None

    try:
        resp = httpx.get(
            f"{TMDB_BASE_URL}/movie/{tmdb_id}",
            params={"api_key": key, "append_to_response": "credits"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        backdrop_url = ""
        if data.get("backdrop_path"):
            backdrop_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"

        genres = [g["name"] for g in data.get("genres", [])]

        director = None
        cast = []
        credits = data.get("credits", {})
        for crew_member in credits.get("crew", []):
            if crew_member.get("job") == "Director":
                director = crew_member["name"]
                break
        for actor in credits.get("cast", [])[:10]:
            profile_url = ""
            if actor.get("profile_path"):
                profile_url = f"{TMDB_IMAGE_BASE}{actor['profile_path']}"
            cast.append({
                "name": actor.get("name", ""),
                "character": actor.get("character", ""),
                "profile_url": profile_url,
            })

        return {
            "backdrop_url": backdrop_url,
            "genres": genres,
            "runtime": data.get("runtime"),
            "release_date": data.get("release_date", ""),
            "tagline": data.get("tagline", ""),
            "director": director,
            "cast": cast,
        }
    except httpx.HTTPError:
        return None


def search_show(title: str, year: int | None = None, api_key: str | None = None) -> dict | None:
    """Search TMDB for a TV show and return poster_url, overview, tmdb_id, imdb_id."""
    key = api_key or TMDB_API_KEY
    if not key:
        return None

    params = {"api_key": key, "query": title}
    if year:
        params["first_air_date_year"] = year

    try:
        resp = httpx.get(f"{TMDB_BASE_URL}/search/tv", params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        show = results[0]
        tmdb_id = str(show["id"])

        poster_url = ""
        if show.get("poster_path"):
            poster_url = f"{TMDB_IMAGE_BASE}{show['poster_path']}"

        overview = show.get("overview", "")
        rating = show.get("vote_average")

        imdb_id = _fetch_imdb_id_tv(tmdb_id, api_key=key)

        return {
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
            "poster_url": poster_url,
            "overview": overview,
            "rating": round(rating, 1) if rating else None,
        }
    except httpx.HTTPError:
        return None


def get_show_details(tmdb_id: str, api_key: str | None = None) -> dict | None:
    """Fetch enriched TV show details (genres, creator, cast, seasons, etc.) from TMDB."""
    key = api_key or TMDB_API_KEY
    if not key:
        return None

    try:
        resp = httpx.get(
            f"{TMDB_BASE_URL}/tv/{tmdb_id}",
            params={"api_key": key, "append_to_response": "credits"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        backdrop_url = ""
        if data.get("backdrop_path"):
            backdrop_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"

        genres = [g["name"] for g in data.get("genres", [])]

        creator = None
        created_by = data.get("created_by", [])
        if created_by:
            creator = created_by[0].get("name")

        cast = []
        credits = data.get("credits", {})
        for actor in credits.get("cast", [])[:10]:
            profile_url = ""
            if actor.get("profile_path"):
                profile_url = f"{TMDB_IMAGE_BASE}{actor['profile_path']}"
            cast.append({
                "name": actor.get("name", ""),
                "character": actor.get("character", ""),
                "profile_url": profile_url,
            })

        return {
            "backdrop_url": backdrop_url,
            "genres": genres,
            "runtime": data.get("episode_run_time", [None])[0] if data.get("episode_run_time") else None,
            "release_date": data.get("first_air_date", ""),
            "tagline": data.get("tagline", ""),
            "creator": creator,
            "number_of_seasons": data.get("number_of_seasons"),
            "number_of_episodes": data.get("number_of_episodes"),
            "cast": cast,
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


def _fetch_imdb_id_tv(tmdb_id: str, api_key: str | None = None) -> str | None:
    """Fetch the IMDb ID for a TV show from TMDB external IDs endpoint."""
    key = api_key or TMDB_API_KEY
    try:
        resp = httpx.get(
            f"{TMDB_BASE_URL}/tv/{tmdb_id}/external_ids",
            params={"api_key": key},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("imdb_id") or None
    except httpx.HTTPError:
        return None


def search_media(title: str, year: int | None = None, media_type: str = "movie", api_key: str | None = None) -> dict | None:
    """Dispatch to search_movie or search_show based on media_type."""
    if media_type == "show":
        return search_show(title, year, api_key=api_key)
    return search_movie(title, year, api_key=api_key)


def get_media_details(tmdb_id: str, media_type: str = "movie", api_key: str | None = None) -> dict | None:
    """Dispatch to get_movie_details or get_show_details based on media_type."""
    if media_type == "show":
        return get_show_details(tmdb_id, api_key=api_key)
    return get_movie_details(tmdb_id, api_key=api_key)
