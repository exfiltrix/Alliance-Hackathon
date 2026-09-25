from collections.abc import Iterator

import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

log = logging.getLogger(__name__)


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
    _add_missing_columns(engine)
    _ensure_seal_uid_index(engine)
    return engine


def _add_missing_columns(engine: Engine) -> None:
    """create_all() never alters existing tables: add columns introduced after a DB was created.
    Enough for a hackathon (new columns only, each with a default); no Alembic."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                    ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}"
                    if default is not None:
                        ddl += f" DEFAULT '{default}'" if isinstance(default, str) else f" DEFAULT {default}"
                    conn.execute(text(ddl))


def _ensure_seal_uid_index(engine: Engine) -> None:
    """Create the UID uniqueness guard without making legacy duplicate data unbootable."""
    with engine.begin() as conn:
        duplicate = conn.execute(
            text("SELECT uid FROM seals GROUP BY uid HAVING COUNT(*) > 1 LIMIT 1")
        ).first()
        if duplicate is not None:
            log.warning("Skipping unique seals.uid index: existing duplicate UID rows are present")
            return
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_seals_uid_unique ON seals (uid)"))


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
