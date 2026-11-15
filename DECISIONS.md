# Architecture Decision Log

## 2026-11-15 Adopt the supplied seven-entity schema

The project owner selected User, Study, Participant, ParticipantConsent, Sample, PhenotypeRecord, and AuditEvent as the database design. This supersedes the earlier six-entity proposal by adding Study and preserving the supplied creator fields, timestamps, constraints, and soft-delete fields. Supervisor sign-off remains pending confirmation before migrations.

## 2026-11-15 Place Study in the phenotypes application

Study and PhenotypeRecord will share the phenotypes application because study membership directly scopes phenotype capture and export. A separate studies application adds an extra module boundary for a small model with no independent workflow in the pilot.
