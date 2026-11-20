FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY config ./config
COPY apps ./apps
COPY alembic.ini ./
COPY migrations ./migrations

USER 10001:10001
CMD ["sh", "-c", "alembic upgrade head && exec python -m uvicorn config.main:app --host 0.0.0.0 --port 8000 --no-access-log"]

FROM runtime AS test
USER root
COPY requirements-test.txt ./
RUN python -m pip install --no-cache-dir -r requirements-test.txt
COPY pyproject.toml ./
COPY tests ./tests
USER 10001:10001
CMD ["pytest", "-q", "-p", "no:cacheprovider"]
