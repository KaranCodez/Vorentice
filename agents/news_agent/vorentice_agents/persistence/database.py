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

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _apply_light_migrations(engine)


# Columns added after the first release. `create_all` only creates
# missing TABLES, never missing columns — so pre-existing dev databases
# are patched here with additive ALTERs (safe to re-run, no data loss).
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "news_items": {
        "trade_impact": "TEXT NOT NULL DEFAULT ''",
        "escalation_potential": "BOOLEAN NOT NULL DEFAULT 0",
        "watchlist_reason": "TEXT NOT NULL DEFAULT ''",
        "escalation_triggers": "TEXT NOT NULL DEFAULT ''",
    },
}


def _apply_light_migrations(engine) -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    )


def open_session() -> Session:
    return Session(get_engine())
