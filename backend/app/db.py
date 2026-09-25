from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def init_engine(url: str | None = None) -> Engine:
    """(Re)bind the session factory to a database and create missing tables."""
    global engine
    from app import models  # noqa: F401  (registers tables on Base.metadata)

    url = url or settings.db_url
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(engine)
    return engine


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
