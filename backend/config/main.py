import os

from fastapi import FastAPI, Response, status
from sqlalchemy import URL, create_engine, select
from sqlalchemy.exc import SQLAlchemyError

database_url = URL.create(
    "postgresql+psycopg",
    username=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.environ["POSTGRES_HOST"],
    database=os.environ["POSTGRES_DB"],
)
engine = create_engine(database_url, connect_args={"connect_timeout": 3})
app = FastAPI(title="KGRI Participant Portal API")


@app.get("/health")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness(response: Response) -> dict[str, str | dict[str, str]]:
    try:
        with engine.connect() as connection:
            connection.execute(select(1))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "error": {
                "code": "database_unavailable",
                "message": "The database is unavailable.",
            }
        }
    return {"status": "ok"}
