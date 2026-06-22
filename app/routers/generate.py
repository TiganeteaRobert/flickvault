import json

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import APIKeys, get_api_keys, get_current_user
from app.schemas import CollectionCreate, MovieCreate
from app.models import User
from app.recommendation_preferences import RecommendationPreferences
from app import crud
from app.ai_generate import generate_collection_iter

router = APIRouter(prefix="/api/collections", tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str = ""
    movie_count: int = 10
    collection_name: str | None = None
    media_type: str = "movie"
    min_rating: float | None = None
    source_collection_id: int | None = None
    obscurity_level: int = Field(default=3, ge=1, le=5)
    seed_title: str | None = None
    seed_year: int | None = None
    genres: list[str] = Field(default_factory=list)
    tone: str | None = None
    era: str | None = None
    runtime: str | None = None
    pace: str | None = None
    ending_vibe: str | None = None
    language_scope: str | None = None
    watch_context: str | None = None
    exclude_seen: bool = True


@router.post("/generate")
def generate(data: GenerateRequest, db: Session = Depends(get_db), keys: APIKeys = Depends(get_api_keys), user: User = Depends(get_current_user)):
    """Generate an AI-powered movie collection from a natural language prompt. Streams SSE progress events."""
    # Gather titles to exclude from ancestor collections (for "More like this" lineage)
    exclude_titles: list[str] = []
    parent_id: int | None = None
    min_rating = data.min_rating
    preferences = RecommendationPreferences(
        obscurity_level=data.obscurity_level,
        seed_title=data.seed_title,
        seed_year=data.seed_year,
        genres=data.genres,
        tone=data.tone,
        era=data.era,
        runtime=data.runtime,
        pace=data.pace,
        ending_vibe=data.ending_vibe,
        language_scope=data.language_scope,
        watch_context=data.watch_context,
        exclude_seen=data.exclude_seen,
    )
    if data.source_collection_id:
        exclude_titles = crud.get_ancestor_movie_titles(db, data.source_collection_id, user.id)
        parent_id = data.source_collection_id
        # Inherit min_rating from source collection if not explicitly set
        if min_rating is None:
            source = crud.get_collection(db, data.source_collection_id, user.id)
            if source and source.min_rating is not None:
                min_rating = source.min_rating
    if data.exclude_seen:
        exclude_titles.extend(crud.get_user_media_titles(db, user.id, data.media_type))
    exclude_titles = list(dict.fromkeys(exclude_titles))

    def event_stream():
        try:
            for event in generate_collection_iter(
                data.prompt,
                data.movie_count,
                openrouter_key=keys.openrouter_key,
                tmdb_key=keys.tmdb_key,
                media_type=data.media_type,
                min_rating=min_rating,
                exclude_titles=exclude_titles or None,
                preferences=preferences,
            ):
                if event["type"] == "progress":
                    yield f"event: progress\ndata: {json.dumps({'found': event['found'], 'needed': event['needed']})}\n\n"

                elif event["type"] == "result":
                    result = event
                    # Create the collection, handling duplicate names
                    name = data.collection_name.strip() if data.collection_name and data.collection_name.strip() else result["name"]
                    collection = None
                    for attempt in range(20):
                        try_name = name if attempt == 0 else f"{name} ({attempt + 1})"
                        try:
                            collection = crud.create_collection(
                                db, CollectionCreate(name=try_name, description=result["description"], media_type=data.media_type), user.id,
                                parent_id=parent_id,
                                min_rating=min_rating,
                            )
                            break
                        except IntegrityError:
                            db.rollback()

                    if collection is None:
                        yield f"event: error\ndata: {json.dumps({'detail': 'A collection with that name already exists. Try a different prompt.'})}\n\n"
                        return

                    movies_data = [MovieCreate(**m) for m in result["movies"]]
                    crud.add_movies_batch(db, collection.id, movies_data, user.id)

                    yield f"event: complete\ndata: {json.dumps({'id': collection.id, 'name': collection.name})}\n\n"

        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
