from datetime import datetime

from pydantic import BaseModel


# --- Auth ---

class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Collection ---

class CollectionCreate(BaseModel):
    name: str
    description: str = ""


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class CollectionOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    movie_count: int = 0

    model_config = {"from_attributes": True}


# --- Movie ---

class MovieCreate(BaseModel):
    title: str
    year: int | None = None
    trakt_id: str | None = None
    imdb_id: str | None = None
    tmdb_id: str | None = None
    overview: str = ""
    poster_url: str = ""
    rating: float | None = None


class MovieOut(BaseModel):
    id: int
    title: str
    year: int | None
    trakt_id: str | None
    imdb_id: str | None
    tmdb_id: str | None
    overview: str
    poster_url: str
    rating: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MovieBatchCreate(BaseModel):
    movies: list[MovieCreate]


class MovieSearchResult(BaseModel):
    movie: MovieOut
    collections: list[str]
