"""Engine and session management.

SQLite for development; the DATABASE_URL env var swaps in Azure
PostgreSQL for production with zero code changes (SQLModel rides on
SQLAlchemy URLs).
"""

from functools import lru_cache

from sqlmodel import Session, SQLModel, create_engine

from vorentice_agents.settings import get_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


def create_db_and_tables() -> None:
    # Import registers the table metadata before create_all.
    import vorentice_agents.persistence.tables  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def open_session() -> Session:
    return Session(get_engine())
