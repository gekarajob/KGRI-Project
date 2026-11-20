# Database connection recovery

## Incident: 18 November 2026

The persistent Compose services (`db`, `api`, and `frontend`) were stopped with exit code `255`. All three recorded a finish time of `2026-11-18T16:43:41Z` (19:43:41 EAT), an empty container `State.Error`, and restart policy `no`. With PostgreSQL stopped, the API could not serve database-backed requests.

The shared stop time suggests a common interruption, but container evidence does not establish the underlying host or Docker cause. The evidence does establish that no restart policy was configured to recover the services after an unexpected exit.

## Fix and recovery

`docker-compose.yml` now sets `restart: unless-stopped` on `db`, `api`, and `frontend`. This allows recovery after unexpected exits and Docker restarts, while respecting an explicit stop. The disposable test services retain their existing lifecycle.

Apply the configuration and wait for startup:

```sh
docker compose up --no-build --wait --wait-timeout 120
docker compose ps --all
```

This uses the existing images and retains the `postgres_data` volume. PostgreSQL must become healthy before API startup; the API applies Alembic migrations before launching, and the frontend waits for API readiness. Do not delete the database volume to resolve a connection failure.

## Verify the connection

Check the API process and its database connection separately:

```sh
curl --fail --silent --show-error http://localhost:8000/health
curl --fail --silent --show-error http://localhost:8000/health/ready
```

Both should return `{"status":"ok"}`. `/health` checks the process; `/health/ready` opens a database connection and executes `SELECT 1`, returning `503` if that fails. PostgreSQL's `pg_isready` health check alone does not verify the API's credentials.

Verify an authenticated connection using the API's actual SQLAlchemy configuration, without printing credentials or participant data:

```sh
docker compose exec -T api python - <<'PY'
from sqlalchemy import text
from config.database import engine

with engine.connect() as connection:
    row = connection.execute(text(
        "SELECT 1 AS connected, current_database() AS database, "
        "current_setting('TimeZone') AS timezone"
    )).mappings().one()
    print(dict(row))
PY
docker compose exec -T api alembic current
docker compose exec -T api alembic heads
```

Expect `connected: 1`, the configured database name, and timezone `UTC`. The current migration should match the migration head (`0001` at the time of this incident). If startup reports a migration failure, inspect its error before retrying; the normal API startup already runs `alembic upgrade head`.

Verified on 18 November 2026 after applying the fix:

- `docker compose up --no-build --wait --wait-timeout 120` completed successfully. All three persistent services were healthy, and container inspection confirmed `unless-stopped` on each.
- Both API health endpoints returned HTTP `200`; the host-published frontend at `http://localhost:5173/` also returned `200`.
- The API's authenticated SQL connection returned `1`, database `kgri` and timezone `UTC`. Alembic reported `0001 (head)`.
- Admin sign-in and a participant read through the frontend's Nginx proxy returned `200`, with the existing 50 synthetic participants retained. Verification printed no tokens, passwords or participant records.
- `docker compose --profile test run --build --rm test` passed all 65 integration cases against the separate temporary PostgreSQL database. The test database service was stopped afterward.

The original host/Docker interruption remains unidentified. The verified fix restores connectivity and adds recovery for unexpected container exits; it does not establish the cause of that interruption. Automatic recovery after a future daemon restart was not simulated during this check.

## Configuration checks

- Inside Compose, the API connects to PostgreSQL at `db:5432`. `localhost` inside the API container refers to that container itself.
- PostgreSQL has no published host port. A host-run Uvicorn, Alembic, or `psql` process needs a separately reachable PostgreSQL endpoint; the API's published port `8000` is not a database port.
- Compose reads the root `.env` when resolving its configuration. Host Python processes do not automatically load that file. Supply their environment explicitly, including `JWT_SECRET` and either `DATABASE_URL` or the individual `POSTGRES_*` settings. `DATABASE_URL` takes precedence. Separate credential fields use SQLAlchemy's URL builder to preserve password punctuation.
- PostgreSQL initializes its database user and password only when its data directory is empty. Changing `.env` later does not update the stored role password. If logs report authentication failure, reconcile the configured credentials with the existing database through an authorized administrative connection, then recreate the API container. Retain the data volume.

## If it happens again

Capture status and recent logs before recreating containers:

```sh
docker compose ps --all
docker compose logs --since 30m --tail 200 db api frontend
docker compose ps --all --quiet | xargs -r docker inspect --format \
  '{{.Name}} status={{.State.Status}} exit={{.State.ExitCode}} finished={{.State.FinishedAt}} oom={{.State.OOMKilled}} error={{json .State.Error}} restart={{.HostConfig.RestartPolicy.Name}}'
```

Use the first failing layer to direct recovery: a stopped `db` requires database/container investigation; a healthy database with API authentication errors requires credential reconciliation; a failed migration requires its specific schema error to be resolved. If readiness passes but a screen fails, inspect the API/frontend path and the response before changing database settings.

For simultaneous container exits, inspect Docker daemon and host logs around their recorded UTC finish times. On a systemd host, `journalctl -u docker --utc` and `journalctl -k --utc` can help identify daemon restarts or out-of-memory events; also check available disk space. Restart policy improves recovery but does not identify or repair the original host interruption.
