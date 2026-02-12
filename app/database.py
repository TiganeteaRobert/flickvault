import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations():
    """Add columns that may be missing on existing databases."""
    with engine.connect() as conn:
        for table in ("collections", "movies"):
            cols = [
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            ]
            if "media_type" not in cols:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN media_type VARCHAR(10) NOT NULL DEFAULT 'movie'"
                ))
        conn.commit()


def init_db():
    from app.models import User, Collection, Movie, CollectionMovie  # noqa: F401
    if os.environ.get("RESET_DB", "").lower() == "true":
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _run_migrations()
