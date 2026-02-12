"""MCP server for Flickvault — tools for managing movie collections."""

import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Ensure the project root is on sys.path so we can import app.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, init_db
from app.schemas import CollectionCreate, CollectionUpdate, MovieCreate
from app import crud
from app.ai_generate import generate_collection as ai_generate_collection

mcp = FastMCP("flickvault")


def _get_db():
    return SessionLocal()


# --- Tool 1: create_collection ---

@mcp.tool()
def create_collection(user_id: int, name: str, description: str = "") -> str:
    """Create a new named movie collection.

    Args:
        user_id: ID of the authenticated user who owns this collection
        name: Unique name for the collection (unique per user)
        description: Optional description
    """
    db = _get_db()
    try:
        data = CollectionCreate(name=name, description=description)
        collection = crud.create_collection(db, data, user_id)
        return json.dumps({
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


# --- Tool 2: list_collections ---

@mcp.tool()
def list_collections(user_id: int) -> str:
    """List all movie collections with their movie counts for a user.

    Args:
        user_id: ID of the authenticated user whose collections to list
    """
    db = _get_db()
    try:
        collections = crud.get_collections(db, user_id)
        return json.dumps([
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "movie_count": c["movie_count"],
            }
            for c in collections
        ])
    finally:
        db.close()


# --- Tool 3: add_movie_to_collection ---

@mcp.tool()
def add_movie_to_collection(
    user_id: int,
    collection_id: int,
    title: str,
    year: int | None = None,
    trakt_id: str | None = None,
    imdb_id: str | None = None,
    tmdb_id: str | None = None,
    overview: str = "",
) -> str:
    """Add a single movie to a collection. Deduplicates by trakt_id or imdb_id.

    Args:
        user_id: ID of the authenticated user who owns the collection
        collection_id: ID of the collection to add to
        title: Movie title
        year: Release year
        trakt_id: Trakt ID for deduplication
        imdb_id: IMDb ID for deduplication
        tmdb_id: TMDb ID
        overview: Movie overview/description
    """
    db = _get_db()
    try:
        data = MovieCreate(
            title=title, year=year, trakt_id=trakt_id,
            imdb_id=imdb_id, tmdb_id=tmdb_id, overview=overview,
        )
        result = crud.add_movie_to_collection(db, collection_id, data, user_id)
        if "error" in result:
            return json.dumps(result)
        return json.dumps({
            "movie_id": result["movie"].id,
            "title": result["movie"].title,
            "added": result["added"],
        })
    finally:
        db.close()


# --- Tool 4: add_movies_batch ---

@mcp.tool()
def add_movies_batch(user_id: int, collection_id: int, movies_json: str) -> str:
    """Add multiple movies to a collection in one batch. Key for bulk operations.

    Args:
        user_id: ID of the authenticated user who owns the collection
        collection_id: ID of the collection to add to
        movies_json: JSON string — array of objects with fields: title, year, trakt_id, imdb_id, tmdb_id, overview
    """
    db = _get_db()
    try:
        movies_data = json.loads(movies_json)
        movie_creates = [MovieCreate(**m) for m in movies_data]
        result = crud.add_movies_batch(db, collection_id, movie_creates, user_id)
        return json.dumps(result)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON string"})
    finally:
        db.close()


# --- Tool 5: list_movies_in_collection ---

@mcp.tool()
def list_movies_in_collection(user_id: int, collection_id: int) -> str:
    """List all movies in a specific collection.

    Args:
        user_id: ID of the authenticated user who owns the collection
        collection_id: ID of the collection
    """
    db = _get_db()
    try:
        data = crud.get_collection_with_movies(db, collection_id, user_id)
        if not data:
            return json.dumps({"error": "Collection not found"})
        movies = [
            {
                "id": m.id,
                "title": m.title,
                "year": m.year,
                "trakt_id": m.trakt_id,
                "imdb_id": m.imdb_id,
            }
            for m in data["movies"]
        ]
        return json.dumps({
            "collection": data["name"],
            "movie_count": data["movie_count"],
            "movies": movies,
        })
    finally:
        db.close()


# --- Tool 6: remove_movie_from_collection ---

@mcp.tool()
def remove_movie_from_collection(user_id: int, collection_id: int, movie_id: int) -> str:
    """Remove a movie from a collection (does not delete the movie record).

    Args:
        user_id: ID of the authenticated user who owns the collection
        collection_id: ID of the collection
        movie_id: ID of the movie to remove
    """
    db = _get_db()
    try:
        success = crud.remove_movie_from_collection(db, collection_id, movie_id, user_id)
        return json.dumps({"success": success})
    finally:
        db.close()


# --- Tool 7: delete_collection ---

@mcp.tool()
def delete_collection(user_id: int, collection_id: int) -> str:
    """Delete an entire collection and its movie associations.

    Args:
        user_id: ID of the authenticated user who owns the collection
        collection_id: ID of the collection to delete
    """
    db = _get_db()
    try:
        success = crud.delete_collection(db, collection_id, user_id)
        return json.dumps({"success": success})
    finally:
        db.close()


# --- Tool 8: search_movies ---

@mcp.tool()
def search_movies(user_id: int, query: str) -> str:
    """Search movies by title across all collections. Collection names are scoped to the user.

    Args:
        user_id: ID of the authenticated user (collection names scoped to this user)
        query: Search term to match against movie titles
    """
    db = _get_db()
    try:
        results = crud.search_movies(db, query, user_id)
        return json.dumps([
            {
                "id": r["movie"].id,
                "title": r["movie"].title,
                "year": r["movie"].year,
                "trakt_id": r["movie"].trakt_id,
                "collections": r["collections"],
            }
            for r in results
        ])
    finally:
        db.close()


# --- Tool 9: import_from_json_file ---

@mcp.tool()
def import_from_json_file(user_id: int, collection_id: int, file_path: str) -> str:
    """Import movies from a JSON file on disk into a collection.
    Supports trakt-watchlist-pending.json format (reads both 'already_added' and 'remaining' arrays)
    and plain arrays of movie objects.

    Args:
        user_id: ID of the authenticated user who owns the collection
        collection_id: ID of the collection to import into
        file_path: Absolute path to the JSON file
    """
    db = _get_db()
    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        with open(path) as f:
            data = json.load(f)

        movies = _extract_movies(data)
        if not movies:
            return json.dumps({"error": "No movies found in file"})

        movie_creates = [MovieCreate(**m) for m in movies]
        result = crud.add_movies_batch(db, collection_id, movie_creates, user_id)
        return json.dumps(result)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON file"})
    finally:
        db.close()


# --- Tool 10: generate_collection ---

@mcp.tool()
def generate_collection(user_id: int, prompt: str, movie_count: int = 10) -> str:
    """Generate a movie collection using AI. Describe the collection you want in natural language
    and Claude will create it with matching movies, enriched with TMDB poster and plot data.

    Args:
        user_id: ID of the authenticated user who will own the new collection
        prompt: Natural language description of the collection (e.g. "Top 10 sci-fi movies from the 90s")
        movie_count: Number of movies to include (default 10)
    """
    db = _get_db()
    try:
        result = ai_generate_collection(prompt, movie_count)
        collection = crud.create_collection(
            db, CollectionCreate(name=result["name"], description=result["description"]), user_id
        )
        movie_creates = [MovieCreate(**m) for m in result["movies"]]
        batch_result = crud.add_movies_batch(db, collection.id, movie_creates, user_id)
        return json.dumps({
            "collection_id": collection.id,
            "collection_name": collection.name,
            "movies_added": batch_result.get("added", 0),
        })
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


def _extract_movies(data) -> list[dict]:
    """Extract movie entries from various JSON formats."""
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
            if field in item and item[field] is not None:
                movie[field] = str(item[field])
        if "rating" in item and item["rating"] is not None:
            movie["rating"] = float(item["rating"])
        results.append(movie)
    return results


def main():
    init_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
