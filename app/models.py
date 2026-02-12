from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    collections = relationship("Collection", back_populates="user", cascade="all, delete-orphan")


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_collection_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    media_type = Column(String(10), nullable=False, default="movie")
    parent_id = Column(Integer, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="collections")
    collection_movies = relationship(
        "CollectionMovie", back_populates="collection", cascade="all, delete-orphan"
    )


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    year = Column(Integer)
    trakt_id = Column(String(50), unique=True, index=True)
    imdb_id = Column(String(20), unique=True, index=True)
    tmdb_id = Column(String(50))
    overview = Column(Text, default="")
    poster_url = Column(String(500), default="")
    rating = Column(Float, nullable=True)
    media_type = Column(String(10), nullable=False, default="movie")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    collection_movies = relationship("CollectionMovie", back_populates="movie")


class CollectionMovie(Base):
    __tablename__ = "collection_movies"
    __table_args__ = (
        UniqueConstraint("collection_id", "movie_id", name="uq_collection_movie"),
    )

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sort_order = Column(Integer, default=0)

    collection = relationship("Collection", back_populates="collection_movies")
    movie = relationship("Movie", back_populates="collection_movies")
