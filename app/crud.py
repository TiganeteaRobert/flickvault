from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Collection, Movie, CollectionMovie
from app.schemas import CollectionCreate, CollectionUpdate, MovieCreate


# --- Collections ---

def create_collection(db: Session, data: CollectionCreate, user_id: int) -> Collection:
    collection = Collection(name=data.name, description=data.description, media_type=data.media_type, user_id=user_id)
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


def get_collections(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(Collection, func.count(CollectionMovie.id).label("movie_count"))
        .outerjoin(CollectionMovie)
        .filter(Collection.user_id == user_id)
        .group_by(Collection.id)
        .order_by(Collection.name)
        .all()
    )
    results = []
    for collection, count in rows:
        results.append({
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
            "media_type": collection.media_type,
            "created_at": collection.created_at,
            "updated_at": collection.updated_at,
            "movie_count": count,
            "poster_urls": [],
        })

    # Fetch up to 4 poster URLs per collection in a single query
    collection_ids = [r["id"] for r in results]
    if collection_ids:
        poster_rows = (
            db.query(CollectionMovie.collection_id, Movie.poster_url)
            .join(Movie)
            .filter(
                CollectionMovie.collection_id.in_(collection_ids),
                Movie.poster_url != "",
                Movie.poster_url.isnot(None),
            )
            .order_by(CollectionMovie.collection_id, CollectionMovie.sort_order)
            .all()
        )
        posters: dict[int, list[str]] = {}
        for cid, url in poster_rows:
            if cid not in posters:
                posters[cid] = []
            if len(posters[cid]) < 4:
                posters[cid].append(url)
        for r in results:
            r["poster_urls"] = posters.get(r["id"], [])

    return results


def get_collection(db: Session, collection_id: int, user_id: int) -> Collection | None:
    return db.query(Collection).filter(
        Collection.id == collection_id, Collection.user_id == user_id
    ).first()


def get_collection_with_movies(db: Session, collection_id: int, user_id: int) -> dict | None:
    collection = db.query(Collection).filter(
        Collection.id == collection_id, Collection.user_id == user_id
    ).first()
    if not collection:
        return None
    cms = (
        db.query(CollectionMovie)
        .options(joinedload(CollectionMovie.movie))
        .filter(CollectionMovie.collection_id == collection_id)
        .order_by(CollectionMovie.sort_order, CollectionMovie.added_at)
        .all()
    )
    movies = [cm.movie for cm in cms]
    return {
        "id": collection.id,
        "name": collection.name,
        "description": collection.description,
        "media_type": collection.media_type,
        "created_at": collection.created_at,
        "updated_at": collection.updated_at,
        "movie_count": len(movies),
        "movies": movies,
    }


def update_collection(db: Session, collection_id: int, data: CollectionUpdate, user_id: int) -> Collection | None:
    collection = get_collection(db, collection_id, user_id)
    if not collection:
        return None
    if data.name is not None:
        collection.name = data.name
    if data.description is not None:
        collection.description = data.description
    db.commit()
    db.refresh(collection)
    return collection


def delete_collection(db: Session, collection_id: int, user_id: int) -> bool:
    collection = get_collection(db, collection_id, user_id)
    if not collection:
        return False
    db.delete(collection)
    db.commit()
    return True


# --- Movies ---

def find_or_create_movie(db: Session, data: MovieCreate) -> Movie:
    """Find existing movie by trakt_id or imdb_id, or create a new one."""
    movie = None
    if data.trakt_id:
        movie = db.query(Movie).filter(Movie.trakt_id == data.trakt_id).first()
    if not movie and data.imdb_id:
        movie = db.query(Movie).filter(Movie.imdb_id == data.imdb_id).first()
    if movie:
        # Update fields if new data is provided
        if data.title:
            movie.title = data.title
        if data.year is not None:
            movie.year = data.year
        if data.overview:
            movie.overview = data.overview
        if data.poster_url:
            movie.poster_url = data.poster_url
        if data.rating is not None:
            movie.rating = data.rating
        if data.tmdb_id and not movie.tmdb_id:
            movie.tmdb_id = data.tmdb_id
        if data.imdb_id and not movie.imdb_id:
            movie.imdb_id = data.imdb_id
        if data.trakt_id and not movie.trakt_id:
            movie.trakt_id = data.trakt_id
        db.commit()
        db.refresh(movie)
        return movie
    movie = Movie(
        title=data.title,
        year=data.year,
        trakt_id=data.trakt_id,
        imdb_id=data.imdb_id,
        tmdb_id=data.tmdb_id,
        overview=data.overview,
        poster_url=data.poster_url,
        rating=data.rating,
        media_type=data.media_type,
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


def add_movie_to_collection(db: Session, collection_id: int, data: MovieCreate, user_id: int) -> dict:
    """Add a movie to a collection. Returns the movie and whether it was newly added."""
    collection = get_collection(db, collection_id, user_id)
    if not collection:
        return {"error": "Collection not found"}

    if data.media_type != collection.media_type:
        return {"error": f"Cannot add a {data.media_type} to a {collection.media_type} collection"}

    movie = find_or_create_movie(db, data)

    existing = (
        db.query(CollectionMovie)
        .filter(CollectionMovie.collection_id == collection_id, CollectionMovie.movie_id == movie.id)
        .first()
    )
    if existing:
        return {"movie": movie, "added": False}

    max_order = (
        db.query(func.max(CollectionMovie.sort_order))
        .filter(CollectionMovie.collection_id == collection_id)
        .scalar()
    ) or 0
    cm = CollectionMovie(
        collection_id=collection_id,
        movie_id=movie.id,
        sort_order=max_order + 1,
    )
    db.add(cm)
    db.commit()
    return {"movie": movie, "added": True}


def add_movies_batch(db: Session, collection_id: int, movies_data: list[MovieCreate], user_id: int) -> dict:
    """Add multiple movies to a collection. Returns counts of added/skipped."""
    collection = get_collection(db, collection_id, user_id)
    if not collection:
        return {"error": "Collection not found"}

    added = 0
    skipped = 0
    for data in movies_data:
        result = add_movie_to_collection(db, collection_id, data, user_id)
        if "error" in result:
            return result
        if result["added"]:
            added += 1
        else:
            skipped += 1

    return {"added": added, "skipped": skipped, "total": len(movies_data)}


def remove_movie_from_collection(db: Session, collection_id: int, movie_id: int, user_id: int) -> bool:
    collection = get_collection(db, collection_id, user_id)
    if not collection:
        return False
    cm = (
        db.query(CollectionMovie)
        .filter(CollectionMovie.collection_id == collection_id, CollectionMovie.movie_id == movie_id)
        .first()
    )
    if not cm:
        return False
    db.delete(cm)
    db.commit()
    return True


def search_movies(db: Session, query: str, user_id: int) -> list[dict]:
    """Search movies by title, returning which of the user's collections each belongs to."""
    movies = (
        db.query(Movie)
        .filter(Movie.title.ilike(f"%{query}%"))
        .order_by(Movie.title)
        .limit(50)
        .all()
    )
    results = []
    for movie in movies:
        collection_names = (
            db.query(Collection.name)
            .join(CollectionMovie)
            .filter(
                CollectionMovie.movie_id == movie.id,
                Collection.user_id == user_id,
            )
            .all()
        )
        results.append({
            "movie": movie,
            "collections": [name for (name,) in collection_names],
        })
    return results
