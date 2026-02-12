"""CLI helper to import a JSON file into a collection.

Usage:
    uv --directory /Users/rtiganetea/movie-manager run python scripts/import_json.py <collection_name> <json_file>
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db
from app.schemas import CollectionCreate, MovieCreate
from app import crud


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <collection_name> <json_file>")
        sys.exit(1)

    collection_name = sys.argv[1]
    json_file = Path(sys.argv[2]).expanduser()

    if not json_file.exists():
        print(f"File not found: {json_file}")
        sys.exit(1)

    init_db()
    db = SessionLocal()

    try:
        # Find or create collection
        collections = crud.get_collections(db)
        collection = next((c for c in collections if c["name"] == collection_name), None)
        if not collection:
            col = crud.create_collection(db, CollectionCreate(name=collection_name))
            collection_id = col.id
            print(f"Created collection: {collection_name} (id={collection_id})")
        else:
            collection_id = collection["id"]
            print(f"Using existing collection: {collection_name} (id={collection_id})")

        with open(json_file) as f:
            data = json.load(f)

        movies = _extract_movies(data)
        print(f"Found {len(movies)} movies in {json_file.name}")

        movie_creates = [MovieCreate(**m) for m in movies]
        result = crud.add_movies_batch(db, collection_id, movie_creates)
        print(f"Added: {result['added']}, Skipped: {result['skipped']}, Total: {result['total']}")

    finally:
        db.close()


def _extract_movies(data) -> list[dict]:
    if isinstance(data, list):
        return _normalize(data)
    movies = []
    for key in ("already_added", "remaining", "movies"):
        if key in data and isinstance(data[key], list):
            movies.extend(data[key])
    if movies:
        return _normalize(movies)
    if isinstance(data, dict) and "title" in data:
        return _normalize([data])
    return []


def _normalize(items: list) -> list[dict]:
    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        movie = {"title": item.get("title", "Unknown")}
        if "year" in item:
            movie["year"] = item["year"]
        for field in ("trakt_id", "imdb_id", "tmdb_id", "overview", "poster_url"):
            if field in item:
                movie[field] = str(item[field])
        results.append(movie)
    return results


if __name__ == "__main__":
    main()
