# KGRI Participant Portal

An internship assessment project at CMB Genomics for participant registration and consent, sample tracking, and phenotype capture.

## Repository layout

```text
backend/
  config/          FastAPI entry point and health routes
  apps/            Accounts, participants, samples, phenotypes, and audit
frontend/src/      React feature directories, shared components, and API client
docs/              ER diagram and design notes
scripts/           Project commands as the modules are implemented
```

The React and domain module directories are reserved for later phases. Review the [seven-entity ER diagram](docs/er-diagram.md) before adding the first Alembic migration.

## Run Day 1 locally

1. Install Docker with the Compose plugin and verify `docker compose version`.
2. Run `cp .env.example .env` and set `POSTGRES_PASSWORD` to a local value. Docker uses these settings the first time it initializes the database volume.
3. Run `make dev`, or `docker compose up --build` if Make is unavailable.
4. In another terminal, check both endpoints.

```sh
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/health/ready
```

The first endpoint checks that the API responds. The second checks that the API can connect to PostgreSQL and execute a query. Compose waits for PostgreSQL to accept TCP connections before starting the API. The API is bound to localhost, and PostgreSQL is accessible to the API through the internal Compose network. See [Docker’s startup order documentation](https://docs.docker.com/compose/how-tos/startup-order/).

Use `docker compose ps` to check service health and `docker compose logs api db` to investigate startup errors. Run `docker compose down` to stop the services and retain the PostgreSQL volume.
