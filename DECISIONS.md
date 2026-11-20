# Architecture Decision Log

## Draft · Preserve account history while controlling active access

Admins can edit usernames and roles and deactivate or reactivate accounts through a partial-update endpoint. Deactivation retains foreign-key references and denies login and protected requests while the account is inactive. Password changes and permanent token revocation remain separate workflows; an earlier unexpired token may work again after reactivation if its role still matches.

## Draft · Serialize Admin account changes

Account creation and updates acquire the same PostgreSQL transaction advisory lock, then refresh and recheck the acting Admin. This prevents a request that waited for another Admin's change from proceeding with stale privileges. The service protects the last active Admin and rejects self-deactivation or self-demotion. The lock is transaction-scoped, so commit and rollback release it automatically.

## Draft · Run the review checks in CI

Use separate GitHub Actions jobs for the FastAPI/PostgreSQL suite and the React checks and production build. CI starts its own disposable database with synthetic credentials and read-only repository permissions. It does not need development secrets or perform deployments; it checks the same source that reviewers receive.

Keep pytest and the HTTP client in `requirements-test.txt`, included by the development requirements. The Docker test stage installs only those test dependencies; local development and CI also install Ruff and mypy. This reduces the test image's download and installation work without dropping checks.

## Draft · Normalize capture times before persistence

Require a timezone on phenotype capture timestamps and convert them to UTC in request validation. PostgreSQL already stores the instant consistently, but normalizing before assignment also makes PATCH responses and audit diffs agree with subsequent reads. Display formatting can still use a staff member's local timezone.

## 2026-11-15 Adopt the supplied seven-entity schema

The project owner selected User, Study, Participant, ParticipantConsent, Sample, PhenotypeRecord, and AuditEvent as the database design. This supersedes the earlier six-entity proposal by adding Study and preserving the supplied creator fields, timestamps, constraints, and soft-delete fields. The project owner confirmed supervisor sign-off on 16 November 2026 before implementation of the initial migration.

## 2026-11-15 Place Study in the phenotypes application

Study and PhenotypeRecord will share the phenotypes application because study membership directly scopes phenotype capture and export. A separate studies application adds an extra module boundary for a small model with no independent workflow in the pilot.

## Draft · Use FastAPI, SQLAlchemy, and Alembic

Use FastAPI with SQLAlchemy 2.x for the REST API and Alembic for versioned schema changes. The earlier Django proposal offered integrated auth and migrations, while this stack gives us explicit request validation and dependency-based permission checks and follows the selected Python track.

## Draft · Use PostgreSQL throughout development

Use PostgreSQL in local development and in the separate test database so tests can exercise the sequences and constraints used by the app. SQLite would be easier to launch locally, but would require different DDL or behavior for some of those features.

## Draft · Block participant deletion when active samples exist

Return `409 Conflict` when a participant has a sample whose `deleted_at` is empty. Cascading a participant deletion to active samples would hide items still being tracked by the lab.

## Draft · Check permissions in API dependencies

Each protected route declares allowed roles through a shared dependency. JWT verification also checks the live account's role and active state, so a previously issued token cannot retain privileges after an account change. Hiding frontend controls alone would leave direct API requests unprotected.

## Draft · Keep sample transitions in one map

The API accepts only the next state listed in `TRANSITIONS` and locks the sample during a change. A database CHECK limits stored values but cannot independently express allowed transitions from the previous value. Metadata patches cannot assign status.

## Draft · Commit audit events with domain changes

An audit diff is added to the same SQLAlchemy session as the participant, sample, phenotype or Admin account mutation, followed by one commit. A failed audit write rolls back the change. A PostgreSQL trigger rejects audit UPDATE and DELETE operations rather than relying solely on a read-only endpoint.

## Draft · Generate identifiers with a PostgreSQL sequence

The database allocates KGRI IDs using a sequence and minimum four-digit padding. This avoids races from counting existing records and continues beyond 9999. Rolled-back requests may leave gaps, which are preferable to identifier reuse.

## Draft · Record consent decisions without erasing history

Absent consent choices default false with null timestamps; explicit choices and later changes are timestamped. Withdrawal updates the current flag and preserves prior audit history, samples and phenotype records. The assessment export includes active study records; partner-specific export restrictions require an agreed research governance policy before real-data use.

## Draft · Normalize API errors

API errors share an error object with a stable code, readable message and optional field/allowed values. Validation responses omit submitted input values to avoid echoing passwords or clinical data. HTTP status codes preserve the distinction between authentication, authorization, validation, transition and conflict failures.

## Draft · Export spreadsheet-safe CSV

Exports use UTF-8 with BOM, proper CSV quoting and ISO timestamps. Formula-like text cells receive a leading apostrophe so a participant name or note is not executed as a spreadsheet formula. A plain comma-joined string would mishandle quotes, commas and line breaks.

## Draft · Keep seed data explicit and idempotent

The seed is an explicit local command rather than part of production startup. It creates clearly marked synthetic records and reads random local account passwords from ignored environment settings. Existing passwords and records are retained on rerun.
