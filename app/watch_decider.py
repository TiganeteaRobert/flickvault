"""Decision helpers for choosing what to watch from a generated collection."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Mapping


WATCH_MODES = {
    "sure_thing": "Safe Bet",
    "hidden_gem": "Hidden Gem",
    "newer": "Newer",
    "classic": "Classic",
    "high_energy": "High Energy",
    "mind_bender": "Mind Bender",
    "date_night": "Date Night",
    "wild_card": "Wild Card",
}

MODE_KEYWORDS = {
    "high_energy": (
        "action", "thriller", "propulsive", "fast", "momentum", "tense", "chase",
        "kinetic", "heist", "crime",
    ),
    "mind_bender": (
        "mystery", "strange", "dream", "dreamlike", "ambiguous", "puzzle",
        "cerebral", "sci-fi", "science fiction", "surreal",
    ),
    "date_night": (
        "romantic", "romance", "warm", "funny", "comedy", "humane", "charm",
        "bittersweet", "intimate",
    ),
}


def rank_watch_picks(
    movies: list[Mapping[str, Any]],
    mode: str = "sure_thing",
    limit: int = 3,
    collection_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic, explained picks for a collection."""
    clean_mode = mode if mode in WATCH_MODES else "sure_thing"
    safe_limit = max(1, min(int(limit or 3), 10))
    scored = [
        _build_pick(movie, clean_mode, movies, collection_id=collection_id)
        for movie in movies
    ]
    scored.sort(key=lambda item: (-item["score"], item["sort_order"], item["title"].lower()))
    return scored[:safe_limit]


def summarize_collection(collection: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize a collection in terms useful for choosing a next watch."""
    movies = list(collection.get("movies") or [])
    ratings = [_as_float(movie.get("rating")) for movie in movies]
    ratings = [rating for rating in ratings if rating is not None]
    years = [_as_int(movie.get("year")) for movie in movies]
    years = [year for year in years if year is not None and year > 0]
    explained_count = sum(1 for movie in movies if _text(movie.get("match_reason")))

    decades: dict[str, int] = {}
    for year in years:
        decade = f"{year // 10 * 10}s"
        decades[decade] = decades.get(decade, 0) + 1

    year_span = ""
    if years:
        min_year = min(years)
        max_year = max(years)
        year_span = str(min_year) if min_year == max_year else f"{min_year}-{max_year}"

    return {
        "movie_count": len(movies),
        "average_rating": round_one_decimal(sum(ratings) / len(ratings)) if ratings else None,
        "highest_rating": max(ratings) if ratings else None,
        "year_span": year_span,
        "unrated_count": len(movies) - len(ratings),
        "explained_count": explained_count,
        "decades": decades,
    }


def _build_pick(
    movie: Mapping[str, Any],
    mode: str,
    all_movies: list[Mapping[str, Any]],
    collection_id: int | None = None,
) -> dict[str, Any]:
    rating = _as_float(movie.get("rating"))
    year = _as_int(movie.get("year"))
    reason = _text(movie.get("match_reason"))
    overview = _text(movie.get("overview"))
    sort_order = _as_int(movie.get("sort_order")) or 9999
    score = _base_score(rating, reason, sort_order)
    why_parts: list[str] = []

    if mode == "classic":
        score += _classic_bonus(year)
        why_parts.append("classic-era weight")
    elif mode == "newer":
        score += _newer_bonus(year)
        why_parts.append("newer-release weight")
    elif mode == "hidden_gem":
        score += _hidden_gem_bonus(rating, reason, sort_order)
        why_parts.append("left-field discovery weight")
    elif mode == "high_energy":
        score += _keyword_score(movie, MODE_KEYWORDS["high_energy"]) * 8
        why_parts.append("high-energy language")
    elif mode == "mind_bender":
        score += _keyword_score(movie, MODE_KEYWORDS["mind_bender"]) * 8
        why_parts.append("mystery or mind-bender language")
    elif mode == "date_night":
        score += _keyword_score(movie, MODE_KEYWORDS["date_night"]) * 8
        why_parts.append("warmer date-night language")
    elif mode == "wild_card":
        score = 35 + _stable_wildcard_score(movie, collection_id)
        why_parts.append("deterministic wild-card draw")
    else:
        why_parts.append("safe-bet weighting")

    if rating is not None and rating == _highest_rating(all_movies):
        why_parts.insert(0, "highest rated option")
    elif rating is not None and rating >= 7.5:
        why_parts.insert(0, "strong audience rating")

    if reason:
        why_parts.append("has a curator match reason")
    if overview and not reason:
        why_parts.append("has enough plot context to judge")

    badges = _badges(movie, reason)
    return {
        "id": movie.get("id"),
        "title": _text(movie.get("title")) or "Unknown",
        "year": year,
        "rating": rating,
        "poster_url": movie.get("poster_url") or "",
        "overview": overview,
        "match_reason": reason,
        "score": max(1, min(100, round(score))),
        "sort_order": sort_order,
        "mode": mode,
        "mode_label": WATCH_MODES[mode],
        "why": "; ".join(dict.fromkeys(why_parts)),
        "badges": badges,
    }


def _base_score(rating: float | None, reason: str, sort_order: int) -> float:
    rating_score = (rating or 6.0) * 8.0
    reason_bonus = 12.0 if reason else 0.0
    curator_order_bonus = max(0.0, 8.0 - min(sort_order, 8))
    return rating_score + reason_bonus + curator_order_bonus


def _classic_bonus(year: int | None) -> float:
    if not year:
        return 0.0
    return max(0.0, min(35.0, (2000 - year) * 0.75))


def _newer_bonus(year: int | None) -> float:
    if not year:
        return 0.0
    current_year = date.today().year
    return max(0.0, min(40.0, 40.0 - ((current_year - year) * 2.5)))


def _hidden_gem_bonus(rating: float | None, reason: str, sort_order: int) -> float:
    trusted = 12.0 if rating is None or rating >= 6.8 else 0.0
    explanation = 12.0 if len(reason) >= 40 else 0.0
    later_in_list = min(12.0, max(0.0, sort_order - 2) * 2.0)
    return trusted + explanation + later_in_list


def _keyword_score(movie: Mapping[str, Any], keywords: tuple[str, ...]) -> int:
    text = " ".join(
        _text(movie.get(field))
        for field in ("title", "overview", "match_reason")
    ).lower()
    return sum(1 for keyword in keywords if keyword in text)


def _stable_wildcard_score(movie: Mapping[str, Any], collection_id: int | None) -> int:
    seed = f"{collection_id or 0}:{movie.get('id') or ''}:{movie.get('title') or ''}:{movie.get('year') or ''}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 61


def _highest_rating(movies: list[Mapping[str, Any]]) -> float | None:
    ratings = [_as_float(movie.get("rating")) for movie in movies]
    ratings = [rating for rating in ratings if rating is not None]
    return max(ratings) if ratings else None


def _badges(movie: Mapping[str, Any], reason: str) -> list[str]:
    badges: list[str] = []
    rating = _as_float(movie.get("rating"))
    year = _as_int(movie.get("year"))
    if rating is not None:
        badges.append(f"{rating:.1f} rating")
    if year:
        badges.append(str(year))
    if reason:
        badges.append("match reason")
    return badges


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def round_one_decimal(value: float) -> float:
    return int((value * 10) + 0.5) / 10
