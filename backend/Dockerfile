FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY config ./config
COPY apps ./apps

USER 10001:10001
CMD ["python", "-m", "uvicorn", "config.main:app", "--host", "0.0.0.0", "--port", "8000"]
