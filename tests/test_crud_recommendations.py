import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud
from app.models import Base, Collection, User
from app.schemas import CollectionCreate, MovieCreate


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def create_user(db, username="user"):
    user = User(username=username, password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_get_user_media_titles_is_scoped_to_user_and_media_type(db):
    user = create_user(db, "owner")
    other = create_user(db, "other")
    movies = crud.create_collection(db, CollectionCreate(name="Movies", media_type="movie"), user.id)
    shows = crud.create_collection(db, CollectionCreate(name="Shows", media_type="show"), user.id)
    other_movies = crud.create_collection(db, CollectionCreate(name="Other", media_type="movie"), other.id)

    crud.add_movie_to_collection(db, movies.id, MovieCreate(title="Heat", media_type="movie"), user.id)
    crud.add_movie_to_collection(db, shows.id, MovieCreate(title="The Bear", media_type="show"), user.id)
    crud.add_movie_to_collection(db, other_movies.id, MovieCreate(title="Alien", media_type="movie"), other.id)

    assert crud.get_user_media_titles(db, user.id, "movie") == ["Heat"]
    assert crud.get_user_media_titles(db, user.id, "show") == ["The Bear"]


def test_generated_match_reason_is_stored_on_collection_movie(db):
    user = create_user(db)
    collection = crud.create_collection(db, CollectionCreate(name="Night", media_type="movie"), user.id)

    crud.add_movie_to_collection(
        db,
        collection.id,
        MovieCreate(
            title="In the Mood for Love",
            year=2000,
            media_type="movie",
            match_reason="Melancholy romantic restraint for a quiet late-night watch.",
        ),
        user.id,
    )

    data = crud.get_collection_with_movies(db, collection.id, user.id)

    assert data is not None
    assert data["movies"][0]["title"] == "In the Mood for Love"
    assert data["movies"][0]["match_reason"] == "Melancholy romantic restraint for a quiet late-night watch."


def test_get_collections_includes_parent_lineage_hint(db):
    user = create_user(db)
    root = crud.create_collection(db, CollectionCreate(name="Like Heat", media_type="movie"), user.id)
    child = crud.create_collection(
        db,
        CollectionCreate(name="Deeper Heat", media_type="movie"),
        user.id,
        parent_id=root.id,
    )

    collections = crud.get_collections(db, user.id)
    child_row = next(c for c in collections if c["id"] == child.id)

    assert child_row["parent_id"] == root.id
    assert child_row["parent_name"] == "Like Heat"
