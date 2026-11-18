# KGRI Participant Portal

A full-stack assessment implementation for participant registration and consent, sample and sequencing tracking, phenotype capture, and study exports. The React interface uses a FastAPI REST API backed by PostgreSQL. All seeded people and measurements are synthetic.

## Start locally

Requirements: Docker with Compose, Python 3 for the one-time environment generator, and optionally Make.

```sh
make setup
make dev
make seed
```

Open **http://localhost:5173**. The API documentation is at **http://localhost:8000/api/docs** (also reachable through the frontend's API documentation link). `make setup` creates a private, ignored `.env` with random local credentials and never overwrites an existing file. If you already have `.env`, add the settings from `.env.example`, including a signing key of at least 32 characters and three seed passwords of at least 12 characters. Password punctuation is handled by SQLAlchemy's URL builder.

| Demo username | Password source in your local `.env` | Role |
| --- | --- | --- |
| `admin` | `SEED_ADMIN_PASSWORD` | Admin |
| `lab_tech` | `SEED_LAB_PASSWORD` | Lab technician |
| `field_officer` | `SEED_FIELD_PASSWORD` | Field officer |

The API applies Alembic migrations on startup. Compose waits for PostgreSQL and then API readiness before starting the frontend. `make seed` is explicit and idempotent: it creates the three accounts, KGRI Baseline study, 50 demo participants across Moyale, Nairobi, and Meru, 35 samples, and 24 phenotype records. It does not overwrite existing passwords or records. Read seed passwords from your own `.env`; they are never printed by setup or seed commands.

Without Make, run `python3 scripts/init_env.py`, `docker compose up --build -d`, then `docker compose exec api python -m apps.seed`. Stop with `make down`; the PostgreSQL volume is retained. Run `docker compose ps` and `docker compose logs api db frontend` for diagnostics. Keep `.env` out of version control.

The database, API and frontend use `restart: unless-stopped` to recover after unexpected exits or Docker restarts. For connection failures, follow the [database troubleshooting and recovery guide](docs/database-troubleshooting.md), which includes readiness checks, credential checks and recovery without deleting data.

## Architecture

```text
frontend/src/              React pages, shared forms, API client and role-aware navigation
backend/config/            Application, PostgreSQL sessions and seven ORM models
backend/apps/accounts/     Argon2 passwords, JWT issue/verify and permission dependencies
backend/apps/participants/ Registry, search, consent and soft deletion
backend/apps/samples/      Sequencing metadata, state machine and count summaries
backend/apps/phenotypes/   Study measurements, validation and safe CSV export
backend/apps/audit/        Transactional diffs and admin queries
backend/apps/seed.py       Explicit synthetic demo seed
backend/migrations/       Versioned Alembic PostgreSQL schema
backend/tests/             Isolated PostgreSQL integration tests
```

Nginx serves the production React build and proxies `/api` to FastAPI. Only the frontend and API bind to localhost; PostgreSQL stays on the Compose network. CORS allows the single configured `FRONTEND_ORIGIN`. JWTs expire after `TOKEN_EXPIRE_MINUTES` (60 by default), use a configured signing secret, and are held in browser session storage. Every authenticated request checks the current account's active status and role as well as the signed role claim.

The Nginx content security policy permits FastAPI's CDN assets and inline initialization only on `/api/docs` and `/api/redoc`. The portal screens and other API routes retain the stricter policy. The interactive documentation needs internet access to download those UI assets.

Participant, sample and phenotype mutations write their audit diff in the same database transaction. Database constraints validate ranges and foreign keys; a PostgreSQL trigger rejects audit updates and deletes. Search uses ORM parameters and escaped wildcard characters. Access logging is disabled so search query strings do not appear in routine server logs.

## Permissions

| Operation | Admin | Lab technician | Field officer |
| --- | --- | --- | --- |
| Read participants and consent | Yes | Yes | Yes |
| Create/edit participants and consent | Yes | No | Yes |
| Delete participants | Yes | No | No |
| Read samples and summaries | Yes | Yes | Yes |
| Create/edit/advance/delete samples | Yes | Yes | No |
| Read/create/edit phenotypes and export CSV | Yes | No | Yes |
| Delete phenotypes | Yes | No | No |
| Create/edit/deactivate/reactivate accounts and view audit log | Yes | No | No |

Registration is admin-only. The seed command bootstraps the first admin. A lab technician's participant detail omits clinical records, and direct phenotype API calls return `403`. Navigation and actions reflect the role, while the API independently enforces permissions.

Under **Team accounts**, Admins can create accounts, edit usernames and roles, and confirm deactivation or reactivation. Deactivation preserves the account and its historical references. Inactive accounts cannot sign in or use authenticated API routes. Admins cannot deactivate themselves or change their own Admin role, and at least one active Admin must remain. Account API writes acquire a PostgreSQL transaction advisory lock and recheck the acting Admin after waiting, protecting concurrent changes. Username conflicts return `409`.

Role changes require a new sign-in while an existing token carries the former role. Account activation is checked on every request; reactivation can make an unexpired earlier token usable again if its role still matches. This build has no permanent token-revocation store or password-reset workflow. Account administration is separate from the current participant/sample/phenotype audit scope.

## API summary

All domain routes below start with `/api`. Protected routes require `Authorization: Bearer <token>`. Lists return `{items,total,page,page_size}`, defaulting to 20 per page with a maximum of 100. Studies and account lists return arrays.

| Route | Methods | Purpose |
| --- | --- | --- |
| `/auth/login`, `/auth/me` | POST, GET respectively | JSON login and current account |
| `/auth/register`, `/auth/users` | POST, GET respectively | Admin account creation and directory |
| `/auth/users/{id}` | PATCH | Admin username/role edits and activation status |
| `/participants` | GET, POST | Registry and registration |
| `/participants/{id}` | GET, PATCH, DELETE | Detail with linked records, edit, soft-delete |
| `/participants/{id}/consent` | PATCH | Update individual consent choices |
| `/samples` | GET, POST | Sample list and registration |
| `/samples/{id}` | GET, PATCH, DELETE | Sample detail and metadata |
| `/samples/{id}/status` | PATCH | One valid next state only |
| `/samples/summary` | GET | Counts by status, platform and recruitment site |
| `/studies` | GET | Available studies |
| `/phenotypes` | GET, POST | Measurement list and capture |
| `/phenotypes/{id}` | GET, PATCH, DELETE | Measurement detail, correction and soft-delete |
| `/phenotypes/export?study_id=1&site=Moyale` | GET | UTF-8 CSV with BOM and formula protection |
| `/audit` | GET | Admin log, filtered by actor/entity/date |
| `/health`, `/health/ready` (no `/api` prefix) | GET | Process and database readiness |

Participant filters: `search`, `county`, `site`, and any of `broad_consent`, `recontact_consent`, `data_sharing_consent` as booleans. Sample filters: `participant_id`, `status`, `platform`, `site`. Phenotype filters: `participant_id`, `study_id`, `site`. Audit filters: `user_id`, `entity_type`, `date_from`, `date_to` with inclusive ISO dates.

Errors consistently return `{error:{code,message,field?,allowed?,details?}}`. The status codes distinguish unauthenticated `401`, forbidden `403`, missing `404`, invalid transition `400`, conflict `409`, and validation `422`. Validation errors omit submitted input values.

## Domain rules

- IDs use a PostgreSQL sequence and minimum four-digit padding: `KGRI-0001`, continuing to `KGRI-10000`. Gaps after rolled-back requests are expected.
- Consent starts false with null recorded timestamps when no choice is supplied. Explicit registration choices get a timestamp. Changing a choice records its latest decision time; submitting the same choice preserves that timestamp. History remains in audit diffs.
- Withdrawal preserves existing records and samples. The assessment export includes all active study records, regardless of consent flags. Research use, partner-specific permissions and withdrawal-driven export restrictions require a governance policy before real-data use; the application does not infer one.
- Participant deletion is soft and blocked with `409` while any linked sample has no `deleted_at`. Linked phenotype records are retained and hidden with the participant.
- Samples advance through `collected → shipped → received_at_lab → dna_extracted → library_prepped → sequenced → qc_passed`. Sequenced records require a platform and batch; DNA sequencing also requires a `.cram`/`.bam` path and coverage. Olink records have no sequencing path or coverage. Metadata updates cannot bypass status transitions.
- Phenotype ranges: height 50–250 cm, weight 10–300 kg, systolic 60–250 and diastolic 30–150 mmHg; systolic must exceed diastolic. Capture timestamps require a timezone and normalize to UTC for creation, edits, responses and audit diffs. Notes are at most 500 characters.
- CSV exports include headers, ISO capture timestamps and a UTF-8 BOM. Text that could be interpreted as a spreadsheet formula is prefixed with an apostrophe.

## Test and develop

```sh
make test
```

This builds the test image and starts a **separate, temporary `kgri_test` PostgreSQL database**. The suite applies the real migrations and wraps each test in a rollback transaction. It tests all three modules, JWTs, role denials, audit atomicity/immutability, CSV contents and seed idempotency. The test configuration refuses database names without an `_test` suffix. Stop the optional test services with `docker compose --profile test stop db_test`.

The test image installs `backend/requirements-test.txt` for pytest and the HTTP client. `backend/requirements-dev.txt` includes those packages plus Ruff and mypy for local checks and CI, keeping lint tooling out of the test image.

[GitHub Actions](.github/workflows/ci.yml) runs Python lint, formatting, type checks and PostgreSQL integration tests alongside frontend TypeScript, lint and production-build checks on each push and pull request. It uses a disposable test database and synthetic credentials; repository secrets are not required. The workflow can also be started manually from GitHub's Actions tab. It will begin running after these source changes are reviewed and pushed.

For host development, install Python 3.12+ and Node 20.19+:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
npm --prefix frontend ci
make check
npm --prefix frontend run build
```

Load your local database and signing environment before starting `uvicorn config.main:app --app-dir backend --no-access-log`; use `DATABASE_URL` to connect to a reachable local PostgreSQL instance. For the frontend, `npm --prefix frontend run dev` proxies API requests to `127.0.0.1:8000`; `API_PROXY_TARGET` changes that target. Host tests additionally require `TEST_DATABASE_URL` pointing at an isolated PostgreSQL database ending in `_test`.

See [the step-by-step build documentation](asbuild.md), [the implementation walkthrough and demo](docs/implementation.md), [the presenter walkthrough](docs/presentations/walkthrough.md), [the technical slides](docs/presentations/KGRI_Technical_Presentation.pptx), [the high-level slides](docs/presentations/KGRI_High_Level_Presentation.pptx), [the ER model](docs/er-diagram.md), and [draft architecture decisions](DECISIONS.md). The presenter walkthrough is also available as a [Word document](docs/presentations/KGRI_Presenter_Walkthrough.docx). `AI_LOG.md` remains for the project owner to write. Source is left for review; this build does not create assessment commits or publish to a server automatically.
