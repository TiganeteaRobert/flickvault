from pathlib import Path

import anthropic
import httpx
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import init_db, get_db
from app.dependencies import APIKeys, get_api_keys
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


# --- Health & API key endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/keys/status")
def keys_status(keys: APIKeys = Depends(get_api_keys)):
    return {
        "anthropic": bool(keys.anthropic_key),
        "tmdb": bool(keys.tmdb_key),
    }


@app.post("/api/keys/validate")
def keys_validate(keys: APIKeys = Depends(get_api_keys)):
    results = {"anthropic": False, "tmdb": False}

    if keys.tmdb_key:
        try:
            resp = httpx.get(
                "https://api.themoviedb.org/3/configuration",
                params={"api_key": keys.tmdb_key},
                timeout=10,
            )
            results["tmdb"] = resp.status_code == 200
        except httpx.HTTPError:
            pass

    if keys.anthropic_key:
        try:
            client = anthropic.Anthropic(api_key=keys.anthropic_key)
            client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            results["anthropic"] = True
        except Exception:
            pass

    return results


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
