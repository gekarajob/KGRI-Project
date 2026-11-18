# KGRI Participant Portal

Technical walkthrough

Audience and timing: 35 minute presentation

Date: 17 November 2026

## Slide 1 KGRI Participant Portal

Technical walkthrough

### Speaker notes

Audience: developers and the assessment supervisor. Allow 35 minutes including a live demonstration. Explain one request from browser to commit, then show the server rejecting an invalid operation. All demonstration people and measurements are synthetic. Sources: asbuild.md; README.md; docs/implementation.md.

## Slide 2 Application scope

### Research operations

- Participant registration and consent
- Sample lifecycle and sequencing metadata
- Study measurements and CSV exports

### Supporting services

- Staff authentication and role permissions
- Admin account creation, editing and status
- Transactional history for domain changes

### Speaker notes

The portal implements three domain modules. Accounts and audit support those modules. Account editing includes username and role changes and deactivation/reactivation. Password entry remains creation-only. Sequencing paths are metadata strings, with no file upload or sequencing execution service. Sources: backend/apps/; frontend/src/; README.md.

## Slide 3 Runtime architecture

| Layer | Runtime responsibility | Connection |
| --- | --- | --- |
| Browser | React forms and session token | localhost:5173 |
| Nginx | Static bundle and API reverse proxy | /api to api:8000 |
| FastAPI | Validation, permissions and transactions | db:5432 |
| PostgreSQL 16 | Seven domain tables and migrations | Internal network |

Compose starts the API after database health, then starts the frontend after API readiness.

### Speaker notes

The current deployment runs three containers. Nginx serves the production React bundle and proxies /api paths. The API and frontend ports bind to host loopback. PostgreSQL has no published host port. The API can also be reached locally on port 8000. Source: docker-compose.yml; frontend/nginx.conf; backend/Dockerfile.

## Slide 4 Seven domain tables

| Entity | Key relationship |
| --- | --- |
| User | Creator, capturing user and audit actor |
| Participant | One person with a unique KGRI identifier |
| ParticipantConsent | Shared participant primary and foreign key |
| Sample | Many samples belong to one participant |
| Study | One study scopes many phenotype records |
| PhenotypeRecord | Participant, study and capturing user |
| AuditEvent | Actor plus affected entity type and ID |

### Speaker notes

The consent key permits at most one current row. Registration supplies that row in the same transaction as the participant. Audit entity_id is an application-managed reference across entity types, not a polymorphic SQL foreign key. Alembic also adds its own version tracking table. Sources: backend/config/models.py; backend/migrations/versions/0001_portal_schema.py; docs/er-diagram.md.

## Slide 5 Schema and identifiers

**Alembic revision 0001** Versioned tables, foreign keys, checks, indexes and audit trigger

**PostgreSQL sequence** kgri_next_id generates KGRI-0001 and continues beyond four digits

**Soft deletion** deleted_at preserves domain records and removes them from active views

**Database constraints** Stored ranges and references complement request validation

### Speaker notes

The migration is authoritative. database/schema.sql points readers to it. Sequence gaps are expected after rolled-back requests. API path IDs are internal numeric primary keys, while kgri_id is the searchable display identifier. PostgreSQL check constraints permit stored states, while route logic enforces transitions between states. Sources: backend/migrations/versions/0001_portal_schema.py; database/schema.sql.

## Slide 6 Request transaction

| Stage | Responsibility |
| --- | --- |
| get_db | Supply a request session and roll back failures |
| Permission dependency | Verify token, account state and allowed role |
| Pydantic schema | Validate input and partial-update fields |
| Domain route | Apply the mutation and take snapshots |
| record_audit | Add before and after changes to the same session |
| Commit | Persist domain mutation and audit event together |

### Speaker notes

current_user itself depends on get_db, so the session exists during account lookup. Routes commit after adding their audit event. record_audit never commits separately. The test suite injects a failing audit writer and checks that the participant mutation rolls back. Sources: backend/config/database.py; backend/apps/audit/service.py; backend/apps/participants/router.py; backend/tests/test_portal.py.

## Slide 7 Authentication and live account checks

### Token issue

- Argon2 password verification
- HS256 JWT with user ID and role
- Issuer, audience and expiry claims
- Default lifetime of 60 minutes

### Every protected request

- Verify signature and required claims
- Load the current account
- Require an active account
- Match the signed role to the stored role

### Speaker notes

Login returns the same generic failure for an unknown username and an incorrect password. A dummy hash makes both paths perform password verification. JWT_SECRET must contain at least 32 characters. Tokens live in browser sessionStorage. Disabling an account blocks login and authenticated calls while inactive. A role change rejects tokens with the former role. Reactivation can allow an unexpired older token if its role matches, since there is no permanent token revocation store. Sources: backend/apps/accounts/security.py; dependencies.py; router.py; frontend/src/api.ts.

## Slide 8 Role permissions

| Operation | Admin | Lab Tech | Field Officer |
| --- | --- | --- | --- |
| Read participants and samples | Yes | Yes | Yes |
| Edit participants and consent | Yes | No | Yes |
| Maintain samples and status | Yes | Yes | No |
| Capture phenotypes and export | Yes | No | Yes |
| Manage accounts and audit access | Yes | No | No |
| Archive participants or phenotypes | Yes | No | No |

### Speaker notes

Sample archive permission belongs to Admin and Lab Tech. Participant and phenotype archiving are Admin-only. Lab Tech participant detail omits clinical records. UI navigation reflects these permissions, while route dependencies enforce them for direct API requests. Sources: backend/apps/*/router.py; frontend/src/App.tsx.

## Slide 9 Admin account management

### Supported operations

- Create accounts with an initial password
- Edit username and role
- Deactivate or reactivate another account
- Preserve accounts referenced by history

### Access safeguards

- Admin-only PATCH /api/auth/users/{id}
- Prevent self-deactivation and self-demotion
- Keep at least one active Admin
- Serialize writes and recheck the acting Admin

### Speaker notes

Registration and account PATCH share a PostgreSQL transaction advisory lock. Once a request acquires it, the service refreshes and rechecks the actor, closing a race where another admin removed the actor's access during the wait. The service then checks last-admin and self-access rules before committing. Concurrent cross-deactivation and cross-demotion tests verify those races. Username collisions return 409. Null or unknown input fields return 422. Password resets and account changes in domain audit events remain outside current scope. Sources: backend/apps/accounts/service.py; router.py; backend/tests/test_accounts.py; frontend/src/Admin.tsx.

## Slide 10 Participant registration and consent

**Registration** Create participant and consent together, assign creator and generated KGRI ID

**Registry search** Find names, IDs, counties or sites with escaped wildcard input

**Consent changes** Timestamp explicit decisions and retain historical changes in audit diffs

**Archiving** Lock the participant and block deletion while non-deleted samples exist

### Speaker notes

Age represents age at enrolment and must be 0 to 120. Lists default to 20 rows and allow up to 100. Sample creation locks the same participant row that deletion locks. This coordinates concurrent operations. Existing phenotype rows remain stored but disappear from active views when their participant is archived. Sources: backend/apps/participants/schemas.py; service.py; router.py.

## Slide 11 Consent decision semantics

| Input or event | Current value | Decision timestamp |
| --- | --- | --- |
| Choice omitted at registration | False | Null |
| Explicit first refusal | False | Recorded |
| Choice changes | New choice | Updated |
| Same recorded choice repeated | Unchanged | Preserved |

Withdrawal preserves records. The current CSV policy includes active study records regardless of consent flags.

### Speaker notes

An unanswered choice and a recorded refusal both have a false Boolean, but the timestamp distinguishes their meaning. The decision time records the latest actual decision. The audit diff preserves history. Partner permissions and withdrawal-driven export rules need governance approval before real research data use. Sources: backend/apps/participants/service.py; router.py; backend/apps/phenotypes/router.py; DECISIONS.md.

## Slide 12 Sample lifecycle

| Stored state | Allowed next state |
| --- | --- |
| collected | shipped |
| shipped | received_at_lab |
| received_at_lab | dna_extracted |
| dna_extracted | library_prepped |
| library_prepped | sequenced |
| sequenced | qc_passed |
| qc_passed | No next state |

### Speaker notes

New samples begin collected. The API locks a sample before changing status and consults TRANSITIONS. Metadata updates cannot set status. A collected-to-sequenced jump returns 400 with current and allowed states. The UI displays allowed_next_states supplied by the API. Source: backend/apps/samples/router.py; schemas.py; frontend/src/Samples.tsx.

## Slide 13 Sequencing metadata rules

| Condition | Required or prohibited values |
| --- | --- |
| Sequenced or QC-passed | Platform and batch ID required |
| Non-Olink at those states | BAM or CRAM path and mean coverage required |
| Olink platform | Sequencing path and coverage remain null |
| Any supplied sequencing path | Must end in .bam or .cram |

The portal stores path metadata. File transfer and sequencing execution need separate services.

### Speaker notes

Platform choices are Ultima UG100, ONT PromethION, PacBio and Olink. Sample types are DNA, blood and saliva. The validator evaluates the complete candidate record after applying metadata patches. Counts group active samples by status, platform and participant recruitment site. Sources: backend/apps/samples/schemas.py; router.py.

## Slide 14 Phenotype validation

| Measurement | Permitted range |
| --- | --- |
| Height | 50 to 250 cm |
| Weight | 10 to 300 kg |
| Systolic blood pressure | 60 to 250 mmHg |
| Diastolic blood pressure | 30 to 150 mmHg |

Systolic must exceed diastolic. Captures require a timezone and normalize to UTC.

### Speaker notes

Measurements allow up to two decimal places. The input model rejects non-finite values. Partial updates validate merged old and new blood pressures. Notes allow at most 500 characters. CaptureTime normalizes aware timestamps before persistence, immediate responses and auditing, including 12:00+03:00 becoming 09:00Z. Sources: backend/apps/phenotypes/schemas.py; router.py; tests/test_portal.py.

## Slide 15 CSV export and domain history

### Study CSV

- Filter active records by study and site
- Use proper quoting and UTF-8 BOM
- Prefix formula-like text with an apostrophe
- Buffer the response in memory

### Domain audit history

- Capture actor, entity and changed fields
- Commit with the domain mutation
- Reject database UPDATE and DELETE
- Offer Admin-only filters and diffs

### Speaker notes

Export is available to Admin and Field Officer. Current exports do not derive partner permissions from consent flags. The audit API filters by user, entity type and inclusive UTC dates. The frontend now submits YYYY-MM-DD dates to that API. Account creation/editing, login and export reads are outside current domain-audit coverage. Sources: backend/apps/phenotypes/router.py; backend/apps/audit/; frontend/src/Admin.tsx.

## Slide 16 Frontend request behavior

**Shared API client** Attach the bearer token and convert server errors into field messages

**Session handling** Restore the current account and return to sign-in after an authenticated 401

**Accessible forms** Link labels and validation messages to controls and preserve dialog focus

**List updates** Discard obsolete requests and correct pagination after archiving

### Speaker notes

App uses role-aware hash navigation. api.ts performs JSON requests and creates browser object URLs for CSV downloads. useLoad discards obsolete responses when inputs change. Modal traps focus within the top dialog, handles Escape and maintains nested scroll locks. Account editing refreshes the list, and an own-username edit immediately updates the sidebar. Sources: frontend/src/api.ts; ui.tsx; App.tsx; Admin.tsx.

## Slide 17 Docker startup and persistence

| Service or step | Behavior |
| --- | --- |
| PostgreSQL | Persistent named volume and readiness probe |
| API startup | Apply Alembic, then start Uvicorn as UID 10001 |
| Frontend startup | Wait for API readiness and serve the built bundle |
| Configuration | Generate an ignored .env with local random credentials |
| Migration to another machine | Move source or images, configuration and a database backup |

### Speaker notes

make setup, make dev and make seed are the principal local commands. The seed is explicit and idempotent. make down retains the named data volume. docker image save packages images but excludes volume data. A move needs database backup/restore when preserving current records and images appropriate for the destination architecture. Sources: docker-compose.yml; backend/Dockerfile; frontend/Dockerfile; scripts/init_env.py; README.md.

## Slide 18 Verification and continuous integration

### Local verification

- Ruff formatting and lint, mypy
- TypeScript, ESLint and production build
- Real PostgreSQL migrations and API cases
- Account permission and concurrency cases

### GitHub Actions

- Python 3.12 and PostgreSQL 16 job
- Node 22 build and frontend checks
- Disposable database and synthetic credentials
- Runs on push, pull request or manual dispatch

### Speaker notes

Use make check and make test. Test fixtures wrap each case in an outer rollback transaction, with savepoints for route commits. Setup fixtures commit their savepoints so a rejected request cannot erase them. Concurrency cases create unique temporary committed accounts across independent sessions and clean them up. CI is configured but a hosted run requires a push. Latest run evidence belongs in the presenter walkthrough, avoiding a stale fixed count in these slides. Sources: backend/tests/conftest.py; tests/test_accounts.py; .github/workflows/ci.yml.

## Slide 19 Technical demonstration

**Access management** Create a demo account, edit its role, deactivate it and verify denied access

**Participant and sample** Register a participant, record consent and advance a sample through valid steps

**Validation and export** Reject invalid blood pressure, correct it and export the study CSV

**Permissions and history** Show a role denial, then inspect audit changes from a successful domain mutation

### Speaker notes

Allow approximately six minutes. Keep actual passwords out of the projected screen and logs. Use only synthetic records. For the token demonstration capture a token in a private test client, disable the account, then call /auth/me and expect 401. Reactivate and sign in again. Show an invalid sample jump on a separate collected sample. Denied requests and account edits do not create domain audit events. Detailed setup and expected outcomes are in walkthrough.md.

## Slide 20 Deployment and governance limits

### Research policy

- Agree on withdrawal effects
- Define partner-specific export authority
- Review who may see clinical records
- Set retention and review responsibilities

### Operational readiness

- Configure HTTPS and supported hosting
- Test backups and restoration
- Agree on identity recovery and MFA
- Add account audit and token revocation if required

### Speaker notes

The delivered scope is a local assessment implementation with synthetic records. No production certification, real clinical validation, cohort-scale performance test or managed backup is claimed. Account state changes block access while inactive, but there is no permanent JWT revocation store. A single-container package would need additional process supervision and persistence design. Source: README.md; docs/implementation.md; asbuild.md.

## Slide 21 Code walkthrough questions

**Transaction boundary** Why do the domain change and audit event commit together?

**Permissions** Why does the API reload the account instead of trusting only the JWT role?

**Lifecycle** Why can a valid sample state still be an invalid next state?

**Concurrency** Why does account management recheck the actor after acquiring its lock?

### Speaker notes

Use these questions for the supervisor checkpoint. Follow with a small change exercise on an isolated branch: add a new measurement validation boundary across the request schema, database migration, form and integration test. Ask the presenter to trace one route without relying on the slide text. Source route: config/main.py, accounts/dependencies.py, accounts/service.py, participants/router.py, audit/service.py, tests/test_accounts.py.

## Slide 22 Source map for review

| Concern | Starting point |
| --- | --- |
| API and database | backend/config/main.py and database.py |
| Schema history | backend/migrations/versions/0001_portal_schema.py |
| Account safeguards | backend/apps/accounts/service.py |
| Domain workflows | backend/apps/participants, samples and phenotypes |
| Interface | frontend/src/App.tsx, Admin.tsx and ui.tsx |
| Runbook and checks | walkthrough.md, asbuild.md and backend/tests |

### Speaker notes

The source map is a navigation aid for discussion. Full explanations are in the presenter walkthrough and asbuild.md. The two decks serve distinct audiences. The high-level deck focuses on research operations, responsibilities, evidence and rollout decisions. All links are repository-relative paths. Date: 17 November 2026.
