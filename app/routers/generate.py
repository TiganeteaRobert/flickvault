from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import APIKeys, get_api_keys, get_current_user
from app.schemas import CollectionCreate, MovieCreate
from app.models import User
from app import crud
from app.ai_generate import generate_collection

router = APIRouter(prefix="/api/collections", tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str
    movie_count: int = 10
    collection_name: str | None = None
    media_type: str = "movie"
    min_rating: float | None = None


@router.post("/generate")
def generate(data: GenerateRequest, db: Session = Depends(get_db), keys: APIKeys = Depends(get_api_keys), user: User = Depends(get_current_user)):
    """Generate an AI-powered movie collection from a natural language prompt."""
    try:
        result = generate_collection(
            data.prompt,
            data.movie_count,
            anthropic_key=keys.anthropic_key,
            tmdb_key=keys.tmdb_key,
            media_type=data.media_type,
            min_rating=data.min_rating,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create the collection, handling duplicate names by appending a number
    name = data.collection_name.strip() if data.collection_name and data.collection_name.strip() else result["name"]
    collection = None
    for attempt in range(20):
        try_name = name if attempt == 0 else f"{name} ({attempt + 1})"
        try:
            collection = crud.create_collection(
                db, CollectionCreate(name=try_name, description=result["description"], media_type=data.media_type), user.id
            )
            break
        except IntegrityError:
            db.rollback()

    if collection is None:
        raise HTTPException(status_code=409, detail="A collection with that name already exists. Try a different prompt.")

    # Add all movies
    movies_data = [MovieCreate(**m) for m in result["movies"]]
    crud.add_movies_batch(db, collection.id, movies_data, user.id)

    return {"id": collection.id, "name": collection.name}
