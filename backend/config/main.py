import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from apps.accounts.router import router as auth_router
from apps.accounts.security import jwt_secret
from apps.audit.router import router as audit_router
from apps.participants.router import router as participant_router
from apps.phenotypes.router import router as phenotype_router
from apps.phenotypes.router import studies_router
from apps.samples.router import router as sample_router
from config.database import engine

FIELD_RANGES = {
    "age": [0, 120],
    "height_cm": [50, 250],
    "weight_kg": [10, 300],
    "systolic_bp": [60, 250],
    "diastolic_bp": [30, 150],
}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    jwt_secret()
    if not 1 <= int(os.getenv("TOKEN_EXPIRE_MINUTES", "60")) <= 1440:
        raise RuntimeError("TOKEN_EXPIRE_MINUTES must be between 1 and 1440.")
    yield


app = FastAPI(
    title="KGRI Participant Portal API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail: Any = exc.detail
    if not isinstance(detail, dict):
        detail = {"code": f"http_{exc.status_code}", "message": str(detail)}
    return JSONResponse({"error": detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Omit input values: failed requests may contain passwords or clinical data.
    details = []
    for item in exc.errors():
        field = ".".join(str(part) for part in item["loc"] if part not in ("body", "query", "path"))
        message = item["msg"]
        if not field and message.startswith("Value error, "):
            field = message.removeprefix("Value error, ").split(" ")[0]
        if field in FIELD_RANGES:
            lower, upper = FIELD_RANGES[field]
            if item["type"] in ("greater_than_equal", "less_than_equal"):
                message = f"{field} must be between {lower} and {upper}."
        details.append({"field": field, "message": message})
    first = details[0] if details else {"field": "request", "message": "Invalid request."}
    error = {
        "code": "validation_error",
        "message": first["message"],
        "field": first["field"],
        "details": details,
    }
    if first["field"] in FIELD_RANGES:
        error["allowed"] = FIELD_RANGES[first["field"]]
    return JSONResponse(
        {"error": error},
        status_code=422,
    )


@app.exception_handler(IntegrityError)
async def integrity_error(_request: Request, _exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "conflict", "message": "The change conflicts with an existing record."}},
        status_code=409,
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "database_unavailable", "message": "The database is unavailable."}},
        status_code=503,
    )


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "internal_error", "message": "The request could not be completed."}},
        status_code=500,
    )


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
            "error": {"code": "database_unavailable", "message": "The database is unavailable."}
        }
    return {"status": "ok"}


for router in (
    auth_router,
    participant_router,
    sample_router,
    studies_router,
    phenotype_router,
    audit_router,
):
    app.include_router(router, prefix="/api")
