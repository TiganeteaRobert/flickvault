from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CollectionCreate, CollectionUpdate, CollectionOut
from app import crud

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.get("", response_model=list[CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    return crud.get_collections(db)


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(data: CollectionCreate, db: Session = Depends(get_db)):
    try:
        collection = crud.create_collection(db, data)
    except Exception:
        raise HTTPException(status_code=400, detail="Collection name already exists")
    result = crud.get_collections(db)
    return next(c for c in result if c["id"] == collection.id)


@router.get("/{collection_id}")
def get_collection(collection_id: int, db: Session = Depends(get_db)):
    result = crud.get_collection_with_movies(db, collection_id)
    if not result:
        raise HTTPException(status_code=404, detail="Collection not found")
    return result


@router.put("/{collection_id}", response_model=CollectionOut)
def update_collection(collection_id: int, data: CollectionUpdate, db: Session = Depends(get_db)):
    collection = crud.update_collection(db, collection_id, data)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    result = crud.get_collections(db)
    return next(c for c in result if c["id"] == collection.id)


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    if not crud.delete_collection(db, collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")
