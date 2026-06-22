from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User
from app import crud
from app.routers.collections import get_collection_picks
from app.schemas import CollectionCreate, MovieCreate


def test_get_collection_picks_returns_ranked_decision_payload():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(username="owner", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)
        collection = crud.create_collection(db, CollectionCreate(name="Tonight", media_type="movie"), user.id)
        crud.add_movie_to_collection(
            db,
            collection.id,
            MovieCreate(title="Risky", year=2024, rating=6.3, media_type="movie"),
            user.id,
        )
        crud.add_movie_to_collection(
            db,
            collection.id,
            MovieCreate(
                title="Reliable",
                year=2018,
                rating=8.5,
                media_type="movie",
                match_reason="A strong fit with enough momentum for a weeknight pick.",
            ),
            user.id,
        )

        payload = get_collection_picks(collection.id, mode="sure_thing", limit=1, db=db, user=user)

        assert payload["collection"]["id"] == collection.id
        assert payload["mode"] == "sure_thing"
        assert payload["stats"]["average_rating"] == 7.4
        assert payload["picks"][0]["title"] == "Reliable"
        assert payload["picks"][0]["score"] >= 80
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
