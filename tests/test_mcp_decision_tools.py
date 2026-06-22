import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud
from app.models import Base, User
from app.schemas import CollectionCreate, MovieCreate
from mcp_server import server


def test_decide_next_watch_mcp_tool_returns_ranked_picks(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(username="owner", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)
        collection = crud.create_collection(db, CollectionCreate(name="Queue", media_type="movie"), user.id)
        crud.add_movie_to_collection(
            db,
            collection.id,
            MovieCreate(title="Puzzle Box", year=2012, rating=7.6, media_type="movie", overview="A strange mystery."),
            user.id,
        )
        crud.add_movie_to_collection(
            db,
            collection.id,
            MovieCreate(title="Straight Drama", year=2020, rating=7.9, media_type="movie", overview="A plain drama."),
            user.id,
        )
        monkeypatch.setattr(server, "SessionLocal", lambda: db)

        payload = json.loads(server.decide_next_watch(user.id, collection.id, mode="mind_bender", limit=1))

        assert payload["collection_id"] == collection.id
        assert payload["mode"] == "mind_bender"
        assert payload["picks"][0]["title"] == "Puzzle Box"
        assert payload["stats"]["movie_count"] == 2
    finally:
        if db.is_active:
            db.close()
        Base.metadata.drop_all(bind=engine)
