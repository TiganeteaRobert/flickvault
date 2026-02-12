from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CollectionCreate, MovieCreate
from app import crud
from app.ai_generate import generate_collection

router = APIRouter(prefix="/api/collections", tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str
    movie_count: int = 10


@router.post("/generate")
def generate(data: GenerateRequest, db: Session = Depends(get_db)):
    """Generate an AI-powered movie collection from a natural language prompt."""
    try:
        result = generate_collection(data.prompt, data.movie_count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create the collection
    collection = crud.create_collection(
        db, CollectionCreate(name=result["name"], description=result["description"])
    )

    # Add all movies
    movies_data = [MovieCreate(**m) for m in result["movies"]]
    crud.add_movies_batch(db, collection.id, movies_data)

    return {"id": collection.id, "name": collection.name}
