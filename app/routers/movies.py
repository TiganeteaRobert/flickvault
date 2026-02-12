import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MovieCreate, MovieOut, MovieBatchCreate, MovieSearchResult
from app.dependencies import get_current_user, get_api_keys, APIKeys
from app.models import User, Movie
from app import crud
from app.tmdb import get_media_details

router = APIRouter(tags=["movies"])


@router.post("/api/collections/{collection_id}/movies", response_model=MovieOut, status_code=201)
def add_movie(collection_id: int, data: MovieCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = crud.add_movie_to_collection(db, collection_id, data, user.id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result["movie"]


@router.post("/api/collections/{collection_id}/movies/batch")
def add_movies_batch(collection_id: int, data: MovieBatchCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = crud.add_movies_batch(db, collection_id, data.movies, user.id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/api/collections/{collection_id}/movies/{movie_id}", status_code=204)
def remove_movie(collection_id: int, movie_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not crud.remove_movie_from_collection(db, collection_id, movie_id, user.id):
        raise HTTPException(status_code=404, detail="Movie not found in collection")


@router.get("/api/movies/{movie_id}/details")
def movie_details(movie_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user), keys: APIKeys = Depends(get_api_keys)):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    result = {
        "id": movie.id,
        "title": movie.title,
        "year": movie.year,
        "rating": movie.rating,
        "overview": movie.overview,
        "poster_url": movie.poster_url,
        "imdb_id": movie.imdb_id,
        "tmdb_id": movie.tmdb_id,
        "media_type": movie.media_type,
    }

    if movie.tmdb_id:
        details = get_media_details(movie.tmdb_id, media_type=movie.media_type, api_key=keys.tmdb_key)
        if details:
            result.update(details)

    return result


@router.get("/api/movies/search", response_model=list[MovieSearchResult])
def search_movies(q: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.search_movies(db, q, user.id)


@router.post("/api/collections/{collection_id}/import")
async def import_json(collection_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    movies = _extract_movies_from_json(data)
    if not movies:
        raise HTTPException(status_code=400, detail="No movies found in JSON")

    movie_creates = [MovieCreate(**m) for m in movies]
    result = crud.add_movies_batch(db, collection_id, movie_creates, user.id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


def _extract_movies_from_json(data: dict | list) -> list[dict]:
    """Extract movie entries from various JSON formats (trakt watchlist, plain list, etc.)."""
    if isinstance(data, list):
        return _normalize_movie_list(data)

    movies = []
    # Support trakt-watchlist-pending.json format
    for key in ("already_added", "remaining", "movies"):
        if key in data and isinstance(data[key], list):
            movies.extend(data[key])
    if movies:
        return _normalize_movie_list(movies)

    # Single movie object
    if "title" in data:
        return _normalize_movie_list([data])

    return []


def _normalize_movie_list(items: list) -> list[dict]:
    """Normalize movie entries to MovieCreate-compatible dicts."""
    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        movie = {}
        movie["title"] = item.get("title", "Unknown")
        if "year" in item:
            movie["year"] = item["year"]
        for field in ("trakt_id", "imdb_id", "tmdb_id", "overview", "poster_url"):
            if field in item and item[field] is not None:
                movie[field] = str(item[field])
        if "rating" in item and item["rating"] is not None:
            movie["rating"] = float(item["rating"])
        results.append(movie)
    return results
