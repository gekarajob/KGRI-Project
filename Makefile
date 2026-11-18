.PHONY: setup dev down test seed check build

setup:
	python3 scripts/init_env.py

dev:
	docker compose up --build -d

down:
	docker compose down

test:
	docker compose --profile test run --build --rm test

seed:
	docker compose exec api python -m apps.seed

check:
	.venv/bin/ruff check backend
	.venv/bin/ruff format --check backend
	.venv/bin/mypy --config-file backend/pyproject.toml backend/config backend/apps
	npm --prefix frontend run check
	npm --prefix frontend run lint

build:
	docker compose build api frontend
