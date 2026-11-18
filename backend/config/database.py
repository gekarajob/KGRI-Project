import os
from collections.abc import Generator

from sqlalchemy import URL, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


database_url = os.environ.get("DATABASE_URL") or URL.create(
    "postgresql+psycopg",
    username=os.environ.get("POSTGRES_USER", "kgri"),
    password=os.environ.get("POSTGRES_PASSWORD", ""),
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=int(os.environ.get("POSTGRES_PORT", "5432")),
    database=os.environ.get("POSTGRES_DB", "kgri"),
)
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3, "options": "-c timezone=UTC"},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
