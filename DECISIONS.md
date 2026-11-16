# Architecture Decision Log

## 2026-11-15 Adopt the supplied seven-entity schema

The project owner selected User, Study, Participant, ParticipantConsent, Sample, PhenotypeRecord, and AuditEvent as the database design. This supersedes the earlier six-entity proposal by adding Study and preserving the supplied creator fields, timestamps, constraints, and soft-delete fields. Supervisor sign-off remains pending confirmation before migrations.

## 2026-11-15 Place Study in the phenotypes application

Study and PhenotypeRecord will share the phenotypes application because study membership directly scopes phenotype capture and export. A separate studies application adds an extra module boundary for a small model with no independent workflow in the pilot.

## Draft · Use FastAPI, SQLAlchemy, and Alembic

Use FastAPI with SQLAlchemy 2.x for the REST API and Alembic for versioned schema changes. The earlier Django proposal offered integrated auth and migrations, while this stack gives us explicit request validation and dependency-based permission checks and follows the selected Python track.

## Draft · Use PostgreSQL throughout development

Use PostgreSQL in local development and in the separate test database so tests can exercise the sequences and constraints used by the app. SQLite would be easier to launch locally, but would require different DDL or behavior for some of those features.

## Draft · Block participant deletion when active samples exist

Return `409 Conflict` when a participant has a sample whose `deleted_at` is empty. Cascading a participant deletion to active samples would hide items still being tracked by the lab.
