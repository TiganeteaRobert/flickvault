import json

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import APIKeys, get_api_keys, get_current_user
from app.schemas import CollectionCreate, MovieCreate
from app.models import User
from app import crud
from app.ai_generate import generate_collection_iter

router = APIRouter(prefix="/api/collections", tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str
    movie_count: int = 10
    collection_name: str | None = None
    media_type: str = "movie"
    min_rating: float | None = None
    source_collection_id: int | None = None


@router.post("/generate")
def generate(data: GenerateRequest, db: Session = Depends(get_db), keys: APIKeys = Depends(get_api_keys), user: User = Depends(get_current_user)):
    """Generate an AI-powered movie collection from a natural language prompt. Streams SSE progress events."""
    # Gather titles to exclude from ancestor collections (for "More like this" lineage)
    exclude_titles: list[str] = []
    parent_id: int | None = None
    min_rating = data.min_rating
    if data.source_collection_id:
        exclude_titles = crud.get_ancestor_movie_titles(db, data.source_collection_id, user.id)
        parent_id = data.source_collection_id
        # Inherit min_rating from source collection if not explicitly set
        if min_rating is None:
            source = crud.get_collection(db, data.source_collection_id, user.id)
            if source and source.min_rating is not None:
                min_rating = source.min_rating

    def event_stream():
        try:
            for event in generate_collection_iter(
                data.prompt,
                data.movie_count,
                anthropic_key=keys.anthropic_key,
                tmdb_key=keys.tmdb_key,
                media_type=data.media_type,
                min_rating=min_rating,
                exclude_titles=exclude_titles or None,
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
