# KGRI Participant Portal Presenter Walkthrough

Prepared for the project developer and supervisor

17 November 2026

## 1 Presenter briefing and timed routes

This guide supports a technical walkthrough of the KGRI Participant Portal and a shorter presentation for a nontechnical audience. The central message is that participant registration, sample progress and study measurements share one controlled record system. Staff roles determine permitted actions, and domain changes are saved with an audit history.

By the end of the technical session, the audience should be able to trace one request from React through FastAPI to PostgreSQL, explain the account and data safeguards, and reproduce the local build and checks. Use the live application for behavior and the editor for the short source-reading stops. All demonstration people and measurements must remain synthetic.

### Technical route lasting 35 minutes

| Minutes | Presenter focus | Evidence to show |
| --- | --- | --- |
| 0 to 3 | Purpose and three research workflows | Overview and role-aware navigation |
| 3 to 8 | Architecture and seven-table data model | Source map and ER diagram |
| 8 to 14 | Authentication and account administration | Sign-in, edit, deactivate and reactivate |
| 14 to 19 | Participants and transactional audit | Registration, consent and audit diff |
| 19 to 25 | Samples and phenotypes | Valid progression, denied jump, validation and CSV |
| 25 to 30 | Docker, checks and deployment boundary | Service health, migration and current test output |
| 30 to 35 | Questions and a small change exercise | Trace or modify one selected rule |

Allow five additional minutes for questions when a 40-minute slot is available. For 30 minutes, shorten the source-reading stops and retain the denied-operation examples.

### High level route lasting 9 minutes

| Minutes | Presenter focus |
| --- | --- |
| 0 to 1 | The research operations problem and system purpose |
| 1 to 3 | One participant record connects consent, samples and measurements |
| 3 to 5 | Roles, account deactivation and visible accountability |
| 5 to 7 | Sample progress and useful study export |
| 7 to 9 | Evidence, current limits and decisions before real-data deployment |

Before presenting, sign in once, confirm the seed, open the source files listed on page 2 and run the checks on page 7. Keep passwords and full tokens out of screen recordings and terminal output. Use the account and domain demonstration scripts on pages 8 and 9.

<!-- pagebreak -->

## 2 Architecture and source reading route

**Say:** The browser presents the workflow, FastAPI decides whether a request is allowed and valid, and PostgreSQL stores the records and enforces database constraints. A hidden button is a convenience; permission enforcement lives in the API.

The Compose request path is browser on localhost port 5173, then Nginx, then FastAPI for `/api/` requests, then PostgreSQL through SQLAlchemy and Psycopg. Nginx also serves the compiled React files. The API is separately reachable on localhost port 8000. PostgreSQL remains on the Compose network without a published host port.

| Layer | Main source | What to explain |
| --- | --- | --- |
| Interface | `frontend/src/App.tsx` and the domain screens | Login, role-aware navigation and user actions |
| HTTP client | `frontend/src/api.ts` | JSON requests, bearer header, errors and CSV download |
| API composition | `backend/config/main.py` | Routers, startup checks, health and error envelopes |
| Access control | `backend/apps/accounts/` | Argon2, JWT validation and role dependencies |
| Storage | `backend/config/database.py` and `models.py` | Request sessions, mappings and relationships |
| Database history | `backend/migrations/versions/0001_portal_schema.py` | Tables, constraints, IDs and audit trigger |
| Runtime | `docker-compose.yml` and both Dockerfiles | Startup order, images, ports and persistence |

### Read the code in this order

1. Open `frontend/src/Participants.tsx` at `ParticipantForm`. Locate the request payload and save handler.
2. Open `frontend/src/api.ts`. Follow the `/api` prefix and authorization header.
3. Open `backend/apps/accounts/dependencies.py`. Explain `current_user()` and `require_roles()`.
4. Open `backend/apps/participants/router.py` at `create_participant()`. Follow validation, flush, audit and commit.
5. Open `backend/apps/participants/service.py` at `participant_snapshot()` and `apply_consent()`.
6. Open `backend/apps/audit/service.py` at `record_audit()`. Show the before-and-after comparison.
7. Finish in `backend/config/models.py` and the migration. Explain the stored records and database safeguards.

The request session is supplied by `get_db()` and reused by authentication and the route. A successful participant write commits the participant, consent and audit event together. An exception rolls the request back.

**Source stop:** Ask the reviewer to choose either a sample transition or a phenotype correction next. The same path repeats: interface, request, permission, validation, stored change, audit and response. This makes the application easier to explain than treating every page as a separate system.

<!-- pagebreak -->

## 3 Data model and record integrity

**Say:** The model has seven domain entities. A participant is the central research record; samples and phenotype captures refer to that participant rather than repeating their identity data.

| Model | Responsibility and relationship |
| --- | --- |
| User | Staff account, password hash, role and active state |
| Participant | Demographics, generated KGRI ID, creator and lifecycle timestamps |
| ParticipantConsent | One current set of three consent choices linked by the participant primary key |
| Sample | A specimen and its sequencing metadata linked to one participant |
| Study | A study code and name that scopes phenotype captures |
| PhenotypeRecord | Participant, study, capturing user, measurements and capture time |
| AuditEvent | Actor, action, affected entity and changed fields |

### Explain the important constraints

The consent row uses `participant_id` as both primary key and foreign key. This permits at most one consent row for a participant. The registration transaction creates the participant and consent together, supplying the required row.

KGRI identifiers come from a PostgreSQL sequence and `kgri_next_id()`. Minimum four-digit padding produces `KGRI-0001` and continues to `KGRI-10000`. Counting existing participants would create a race between simultaneous registrations. Sequence gaps after a rollback are expected.

Foreign keys require valid creators, participants, studies and capturing users. Database checks repeat important measurement and enumeration rules. The Alembic migration is the authoritative schema history. `database/schema.sql` points readers to that history; it is not the schema creation script.

### Explain consent and archiving

An unanswered consent choice begins false with no recorded decision time. An explicitly supplied refusal receives a timestamp. Changing a choice updates that decision time; repeating an already recorded choice preserves it. The audit history preserves prior changes.

Archiving sets `deleted_at` rather than erasing a row. Participant archiving is blocked while any linked sample is not archived, regardless of the sample's status. The participant lock used for deletion is also acquired during sample creation, preventing a concurrent insert from bypassing that check. Retained phenotype rows become hidden with an archived participant.

Audit `entity_type` and `entity_id` identify the affected domain record through application logic. `entity_id` is not one foreign key pointing to all three domain tables. The separate actor field is a foreign key to User.

**Show:** `docs/er-diagram.md`, `backend/config/models.py` and migration revision `0001`. Ask the audience to describe each relationship as one sentence.

<!-- pagebreak -->

## 4 Authentication roles and account lifecycle

**Say:** A signed token identifies the account, and each request also checks the live account. Protected requests from an existing token are rejected while the account is inactive.

Passwords are stored as Argon2 hashes. Successful login issues an HS256 JWT containing subject, role, issuer, audience and time claims. The default lifetime is 60 minutes. `current_user()` verifies the signature and claims, loads the account, and rejects inactive accounts or a role claim that no longer matches. `require_roles()` enforces the allowed operation, with Admin access included.

| Operation | Admin | Lab Tech | Field Officer |
| --- | --- | --- | --- |
| Read participant and sample records | Yes | Yes | Yes |
| Create or edit participants and consent | Yes | No | Yes |
| Create or advance samples | Yes | Yes | No |
| Read or capture phenotypes and export | Yes | No | Yes |
| Administer staff or read audit history | Yes | No | No |

The frontend keeps the token in session storage. It removes the token on logout and returns to sign-in after an authenticated `401`. Navigation reflects the role; direct API requests still pass through the same server checks.

### Account administration

Admin can create staff through `POST /api/auth/register`, list them through `GET /api/auth/users`, and edit a selected account through `PATCH /api/auth/users/{id}`. Partial updates accept `username`, `role` and `is_active`. Password replacement is outside this update contract.

```json
{"username":"presentation_field","role":"field_officer","is_active":true}
```

Deactivation retains the account and historical creator references. It rejects new sign-ins and protected requests while inactive. Reactivation permits sign-in again and can make an earlier unexpired token usable if its role still matches. A role change rejects tokens with the former role claim; demonstrate the updated role after signing in again. Restoring that former role can also make an earlier unexpired token valid again because the application has no token revocation store.

The server prevents an Admin from deactivating their own account or removing their own Admin role. It also guards the last active administrator. Account writes use a PostgreSQL transaction-scoped advisory lock; the actor's live Admin status is rechecked after waiting for that lock. This protects the check-and-update sequence across API workers.

**Expected responses:** unauthorized requests return `401`; a signed-in user with an insufficient role receives `403`; self-deactivation, self-demotion and last-active-admin conflicts use `409`. Duplicate usernames also return `409`; invalid fields return `422`. User responses omit password hashes.

<!-- pagebreak -->

## 5 Participant workflow and transactional audit

**Say:** A participant change and its audit event are one database operation. The application should not save the research record and then lose the evidence of who changed it.

Participant registration validates demographics, assigns the authenticated creator, creates consent, flushes for generated IDs, records the initial snapshot and commits once. Admin and Field Officer can create and edit; only Admin can archive. Search accepts name, KGRI ID, county or site, with separate consent filters and pagination.

### Trace one registration in the editor

1. The form sends demographics and explicit consent choices through `api.ts`.
2. FastAPI obtains the shared database session and checks the account and writer role.
3. `ParticipantCreate` validates the submitted fields.
4. `create_participant()` adds the participant and its consent row.
5. PostgreSQL assigns the KGRI ID during the flush.
6. `participant_snapshot()` supplies values to `record_audit()`.
7. One commit stores the domain rows and audit event.
8. The API returns `201`, and the interface refreshes the list.

`record_audit()` compares old and new snapshots and stores only changed fields, with JSON-compatible timestamps and numbers. Password, password-hash and token keys are excluded. The function adds an event to the current session; it never commits separately.

```json
{"consent.recontact_consent":{"old":false,"new":true}}
```

Participant consent changes appear within the participant's audit snapshot using consent-prefixed field names. The exact diff can also contain updated timestamps. Use the displayed event to explain the saved values rather than promising only one field will change.

### Show the independent database safeguard

Migration `0001` installs `prevent_audit_mutation()` and an audit-table trigger that rejects ordinary updates and deletes. Admin can read events but has no application route for changing them. Audit filters select actor, entity type and inclusive UTC date boundaries using plain `YYYY-MM-DD` values.

The present domain audit covers participant, sample and phenotype mutations. Staff account administration and CSV reads are outside that domain audit scope. Describe this boundary clearly when discussing accountability.

**Demonstrate:** register a synthetic participant, change recontact consent and open the resulting audit diff. Then explain the rollback regression: a simulated failed audit write prevents the participant mutation from being committed. A Field Officer's direct `GET /api/audit` returns `403`, even though their participant work is allowed.

<!-- pagebreak -->

## 6 Samples phenotypes and research export

**Say:** Samples have an ordered workflow, while phenotype captures have measurement rules. Both are checked by the server before a change is saved.

### Sample lifecycle

```text
collected -> shipped -> received_at_lab -> dna_extracted
          -> library_prepped -> sequenced -> qc_passed
```

`TRANSITIONS` defines the permitted next state. `change_status()` locks the stored sample, checks that map, validates metadata, then saves the state and audit event. Metadata PATCH requests cannot set `status`. An attempted `collected` to `sequenced` jump returns `400` and lists the allowed next state.

Sequenced and QC-passed records require platform and batch. Non-Olink records at those states also require mean coverage and a `.cram` or `.bam` path. Olink records keep the path and coverage null. The stored path is metadata; the portal does not upload or inspect sequencing files. Summary queries group active sample counts by state, platform and participant site.

### Phenotype capture and correction

| Measurement | Accepted range |
| --- | --- |
| Height | 50 to 250 cm |
| Weight | 10 to 300 kg |
| Systolic pressure | 60 to 250 mmHg |
| Diastolic pressure | 30 to 150 mmHg |

Systolic pressure must exceed diastolic pressure. Request schemas reject excess decimal precision and non-finite values; database constraints repeat range and BP-order checks. A partial update checks the complete candidate values after merging changes with the stored record. Notes are limited to 500 characters.

Capture timestamps require a timezone. `CaptureTime` normalizes them to UTC before persistence, response and audit: `12:00+03:00` is the same instant as `09:00Z`. This prevents an edit response and a subsequent read from presenting different timezone offsets.

### CSV behavior to explain before downloading

Admin and Field Officer may export active study records, optionally filtered by site. The exporter uses proper CSV quoting, UTF-8 with a byte-order mark and UTC ISO timestamps. Formula-like text cells receive an apostrophe prefix. The response is currently assembled in memory.

The current assessment export includes active records regardless of consent flags. Consent withdrawal preserves existing records. Partner-specific access and withdrawal-driven export restrictions require an agreed governance policy before real research use. A useful demonstration shows the output columns and site filter, then names that policy boundary explicitly.

<!-- pagebreak -->

## 7 Start inspect and verify the application

The normal local route requires Docker with Compose, Python 3 for environment setup and optionally Make. Run commands from the repository root. Base-image and dependency downloads can make the first build slower than later builds.

```sh
make setup
make dev
docker compose ps
make seed
```

`make setup` generates a private ignored `.env` and preserves an existing one. `make dev` builds the images and starts the services. The API applies Alembic migrations before Uvicorn starts. Compose waits for database health, then API readiness, then starts the frontend. `make seed` explicitly loads synthetic accounts and records.

Open `http://localhost:5173`. The API documentation is at `http://localhost:8000/api/docs`. Seed usernames are `admin`, `lab_tech` and `field_officer`; use their corresponding `SEED_*_PASSWORD` values in `.env`. The empty-database seed creates 50 participants, 35 samples and 24 phenotype captures across three sites.

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/health/ready
docker compose exec api alembic current
make test
```

Both health endpoints should return `{"status":"ok"}` when the database is available, and the migration head should be `0001`. `/health` remains a process check; `/health/ready` depends on a successful database query. `make test` uses an isolated temporary PostgreSQL database ending in `_test`, applies the real migration and runs the integration suite.

Host source checks require Python 3.12+ and Node 20.19+ with the project dependencies installed. Docker supplies its own Python 3.12 and Node 22 images.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt \
  -r backend/requirements-dev.txt
npm --prefix frontend ci
make check
npm --prefix frontend run build
```

`make check` runs Ruff, mypy, TypeScript and ESLint. GitHub Actions repeats backend/PostgreSQL and frontend checks in separate jobs on push and pull request; it has no deployment job. Show the current command summary when presenting.

At the 17 November 2026 checkpoint, `make test` passed all 65 integration cases through the Python 3.12 Docker image, `make check` passed, and the frontend production build passed through Compose. The rebuilt application services were healthy. Browser keyboard and interaction checks remain manual because browser access was unavailable during verification.

For diagnosis, run `docker compose logs --tail=100 api db frontend`. `make down` stops the application and retains the database volume. After tests, stop the optional database with `docker compose --profile test stop db_test`.

<!-- pagebreak -->

## 8 Live demonstration of staff administration

Use a synthetic demonstration account distinct from your own Admin account. Keep a second browser session or private window for that account, so the Admin session remains available. Choose a unique username for the rehearsal; use a local temporary password of at least 12 characters without displaying it publicly.

### Create and edit an account

1. Sign in as Admin and open Accounts. Explain that this navigation is restricted to administrators.
2. Create an account such as `presentation_field` with the Field Officer role. Expected result: the account appears active in the directory; the API returns `201` and omits password data.
3. Select **Edit**, change the username to a unique value such as `presentation_field_2`, and save. Expected result: the directory shows the new name. A conflicting existing name should produce a readable `409` conflict.
4. In the second session, sign in using the updated username. Show participant and phenotype access, and the absence of account and audit administration controls.

### Prove deactivation affects an existing session

5. Keep that second session signed in. In the Admin session, select **Deactivate** for the demonstration account and confirm its inactive status in the directory.
6. In the second session, request a protected page or refresh its data. Expected result: the API returns `401`; the application removes the token and returns to sign-in. An attempted new login also returns the generic invalid-credentials response.
7. Select **Reactivate** for the same account from Admin. Sign in again in the second session. Expected result: access is restored using the retained account and password.

Deactivation does not erase historical records. Reactivation also does not reset the password. The system checks live account state on each request. Present deactivation as an access-state change, not as permanent revocation of every issued token after later reactivation.

### Demonstrate role and administrator safeguards

8. With the demonstration user signed in as Field Officer, change its role to Lab Tech from Admin. Its existing token now has a stale role claim; the next protected request returns `401`. Sign in again and show sample access while phenotype access is denied with `403`.
9. Open your own Admin account. Explain that the interface and API prevent self-deactivation and self-demotion. A direct self-protection request returns `409`; keep your Admin session usable.
10. Explain the last-active-admin safeguard and show its regression coverage or implementation. Account mutations are serialized before the safeguard is evaluated, and the requesting Admin is checked again after the lock is acquired.

A non-Admin request to the account-update endpoint must return `403`. Use an existing Lab Tech or Field Officer session in the API documentation to demonstrate the denial. Remove bearer credentials from the screen before switching back to the audience view.

<!-- pagebreak -->

## 9 Live demonstration of the research workflows

### Participant and consent

1. As Admin or Field Officer, register a clearly synthetic participant with valid demographics. Record the generated KGRI ID.
2. Find the participant by county and then by KGRI ID. Open detail and change recontact consent. Expected result: the saved choice and decision timestamp appear. Repeating the same recorded choice preserves that decision timestamp.
3. As Admin, open Audit and filter to participant events and the relevant actor/date. Expand the event and explain old/new values. Date filters use inclusive UTC dates.

### Sample progression and denial

4. As Admin or Lab Tech, register a DNA sample for that participant. Advance it through `shipped` and `received_at_lab`. Expected result: only valid next actions are offered and the summary counts refresh when read again.
5. Create a separate sample that remains `collected`. In authenticated API documentation, send `PATCH /api/samples/{id}/status` with the payload below. Expected result: `400` with current state and allowed next states. The stored sample remains collected.

```json
{"status":"sequenced"}
```

6. Try to archive the participant while a non-archived sample exists. Expected result: `409`. Explain that this preserves tracked laboratory material. Avoid hiding the main demonstration record until the walkthrough ends.

### Measurements validation and export

7. As Field Officer or Admin, select the participant and KGRI Baseline study. Capture height 170, weight 65, systolic 120 and diastolic 80, with valid boolean answers. Expected result: the saved capture appears against the participant and study.
8. Demonstrate the invalid systolic value 500. The form may reject it before submission. To show server validation, send authenticated `PATCH /api/phenotypes/{id}` for the saved capture with `{"systolic_bp":500}`. Expect `422` naming the field and range. Correct the value and save. Also explain that 80 systolic with 90 diastolic fails the relationship check.
9. Export the selected study CSV with an optional site filter. Open it in a spreadsheet, show the headers and one matching record, and explain UTF-8/BOM, quoting and formula protection. Use a synthetic note such as `=1+1` only if you want to demonstrate the protected text cell.
10. As Lab Tech, request `GET /api/phenotypes` directly. Expected result: `403`. As Field Officer, request `GET /api/audit`. Expected result: `403`. These are API evidence even though navigation hides the restricted screens.

Conclude this demonstration by stating the current consent/export policy boundary and showing the exact current test summary. Do not describe a browser interaction as verified until it has been rehearsed successfully.

<!-- pagebreak -->

## 10 High level speaking route

Use this route when the audience needs the purpose, working behavior and delivery boundary without reading code. Keep the full source walkthrough available for follow-up questions.

### Minute 0 to 1 Introduce the operational problem

**Say:** Research staff need to know who is registered, what consent was recorded, where samples have reached and which study measurements were captured. The portal connects those tasks in one system with staff sign-in and a history of record changes.

Show Overview. Point to the participant count, sample progress and recent registrations. Describe these as the current database state rather than a live laboratory instrument feed.

### Minutes 1 to 3 Follow one participant

Open a synthetic participant. Show their identifier and consent choices, then the linked samples and measurements. Explain that the identifier is generated centrally and that staff correct records through controlled forms.

**Say:** Consent choices have their own decision times. Changing a choice preserves a history of the change. Existing records are retained when consent is withdrawn, and the final research-use rules still need an agreed governance policy.

### Minutes 3 to 5 Explain staff access and accountability

Show the account directory as Admin and the restricted navigation in a second staff session. Explain that Field Officers capture participant and phenotype information, Lab Tech users manage samples, and Admin manages staff and reads audit history.

Deactivate the synthetic staff account and request data from its already signed-in session. Show the sign-in prompt after access is rejected, then reactivate and sign in again. State that deactivation retains historical records.

Open a participant audit event. Explain the actor, time, action and changed values. Staff account administration and export reads are not included in the present domain audit history.

### Minutes 5 to 7 Show progress and a useful output

Open a sample and show the next available state. Explain that the API prevents steps from being skipped. Show a valid phenotype capture and its range validation, then export the study CSV. Discuss the expected operational benefit: staff can locate records, see progress and prepare a consistent study extract.

### Minutes 7 to 9 Close with evidence and decisions

Show service health and the latest successful check summary. Separate working application behavior, automated evidence and remaining manual rehearsal. Name the local assessment scope: synthetic data, local Docker startup and no completed production deployment.

The decisions before real-data use are the consent/export policy, partner access, supported hosting and HTTPS, identity and recovery arrangements, backups and restore ownership. Explain that these decisions determine how the pilot should progress into an operational research service.

<!-- pagebreak -->

## 11 Checkpoint questions limits and references

### Questions to rehearse without notes

**Why check the database after validating a JWT?** Account active state and role may change before token expiry. A valid signature alone cannot show whether the account still has access.

**Why commit an audit event with the research change?** One transaction keeps the stored record and its history consistent. The rollback test proves a failed audit write prevents the domain mutation from being committed.

**Why does a status CHECK constraint not enforce the sample workflow?** It limits the set of stored values. `TRANSITIONS` and the locked current row determine which next value is allowed.

**Why are tests run on PostgreSQL?** The implementation depends on PostgreSQL sequences, locks, triggers and constraints. The tests exercise those mechanisms using real migrations and an isolated database.

**Why can a participant number be skipped?** A sequence value can be consumed by a rolled-back transaction. Gaps preserve concurrency safety and do not mean a record was silently deleted.

### Small supervised modification exercises

1. Change a phenotype validation boundary on a scratch branch. Update request validation, a new migration, the form and a meaningful integration test; explain why the frontend change alone is insufficient.
2. Add a proposed sample state to the map on a scratch branch. Trace every schema, database and interface assumption that must agree before the new state is usable.
3. Trace a deactivated account's existing request from the bearer header to the live-account check. Explain self-protection and the account mutation lock.

### Delivery boundary to state clearly

The current implementation is a local assessment application with synthetic seed records. Production work includes approved consent/export and partner-access policy, supported deployment and HTTPS, credential and database ownership, backup/restore, account recovery and an agreed MFA or identity-provider approach. Sequencing paths are metadata without file transfer. CSV generation buffers the result in memory. Earlier unexpired tokens can become usable again after account reactivation or restoration of their role; a token revocation store is future work.

### Source references for questions

- `README.md` and `asbuild.md` for setup and construction sequence.
- `docs/er-diagram.md` and `DECISIONS.md` for relationships and trade-offs.
- `backend/apps/accounts/` for security, account updates and administrator safeguards.
- `backend/apps/participants/`, `samples/` and `phenotypes/` for domain rules.
- `backend/apps/audit/` and migration `0001` for atomic diffs and immutability.
- `backend/tests/`, `.github/workflows/ci.yml` and `Makefile` for reproducible checks.
- `frontend/src/` and `docker-compose.yml` for user flows and runtime wiring.

Finish by inviting the reviewer to choose one route, rule or test to explain. Use current source and observed results as the evidence for your answers.
