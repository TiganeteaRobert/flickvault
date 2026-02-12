from pathlib import Path

import anthropic
import httpx
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import init_db, get_db
from app.dependencies import APIKeys, get_api_keys, get_current_user, get_optional_user
from app.routers import auth, collections, movies, generate
from app.models import User
from app import crud

app = FastAPI(title="Flickvault")

APP_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

# Auth router first
app.include_router(auth.router)
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
def keys_status(keys: APIKeys = Depends(get_api_keys), user: User = Depends(get_current_user)):
    return {
        "anthropic": bool(keys.anthropic_key),
        "tmdb": bool(keys.tmdb_key),
    }


@app.post("/api/keys/validate")
def keys_validate(keys: APIKeys = Depends(get_api_keys), user: User = Depends(get_current_user)):
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


# --- Auth pages (public) ---

@app.get("/login")
def login_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register")
def register_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request})


# --- Protected Web UI routes ---

@app.get("/")
def home(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    collections_list = crud.get_collections(db, user.id)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "collections": collections_list,
        "user": user,
    })


@app.get("/collections/{collection_id}")
def collection_detail(request: Request, collection_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    data = crud.get_collection_with_movies(db, collection_id, user.id)
    if not data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "collections": crud.get_collections(db, user.id),
            "user": user,
            "error": "Collection not found",
        })
    return templates.TemplateResponse("collection.html", {
        "request": request,
        "collection": data,
        "user": user,
    })


@app.get("/import")
def import_page(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    collections_list = crud.get_collections(db, user.id)
    return templates.TemplateResponse("import.html", {
        "request": request,
        "collections": collections_list,
        "user": user,
    })


def run():
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
