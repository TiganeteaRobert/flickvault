from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import init_db, get_db
from app.routers import collections, movies, generate
from app import crud

app = FastAPI(title="Flickvault")

APP_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

# generate router must come before collections (so /generate doesn't match /{collection_id})
app.include_router(generate.router)
app.include_router(collections.router)
app.include_router(movies.router)


@app.on_event("startup")
def startup():
    init_db()


# --- Web UI routes ---

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    collections_list = crud.get_collections(db)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "collections": collections_list,
    })


@app.get("/collections/{collection_id}")
def collection_detail(request: Request, collection_id: int, db: Session = Depends(get_db)):
    data = crud.get_collection_with_movies(db, collection_id)
    if not data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "collections": crud.get_collections(db),
            "error": "Collection not found",
        })
    return templates.TemplateResponse("collection.html", {
        "request": request,
        "collection": data,
    })


@app.get("/import")
def import_page(request: Request, db: Session = Depends(get_db)):
    collections_list = crud.get_collections(db)
    return templates.TemplateResponse("import.html", {
        "request": request,
        "collections": collections_list,
    })


def run():
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
