# Implementation walkthrough

The application follows the approved seven-table ER model. Read one request from the frontend API client through the route, permission dependency, ORM operation, audit event, and commit. The supervisor sign-off was confirmed by the project owner on 16 November 2026 before the migration was written.

## Functions to understand

- `get_db()` lends one SQLAlchemy session to a request, rolls back on failure, and closes it afterward. Routes commit only after the mutation and its audit event have been added.
- `current_user()` verifies the JWT signature, expiry, issuer and audience, loads the current user, and checks active status and role. `require_roles()` turns a route's allowed roles into a FastAPI dependency; a valid token alone never grants access outside that set.
- `create_access_token()` signs the user ID and role with a short expiry. `hash_password()` uses Argon2, and login verifies against a dummy hash for unknown accounts so failure responses do not reveal which credential was wrong.
- `lock_account_mutations()` acquires a shared transaction advisory lock for Admin account API writes and reloads the actor after waiting. `protect_admin_access()` rejects removal of the last active Admin and self-deactivation or self-demotion. `PATCH /api/auth/users/{id}` applies only submitted username, role and active-status changes; deactivation retains historical references.
- `kgri_next_id()` is a PostgreSQL function using `nextval()`. Each concurrent request receives its own sequence value. Padding is a minimum width, so identifiers continue beyond 9999.
- `create_participant()` creates a participant and consent row together, flushes to obtain the ID, records the initial audit diff, and commits once. `apply_consent()` updates only explicitly supplied choices and timestamps only actual changes.
- `active_participant()` hides soft-deleted records and can lock a row for writes. Participant deletion takes that lock and checks active samples; sample creation takes the same participant lock, preventing a concurrent insert from escaping the deletion check.
- `change_status()` locks the sample, looks up the allowed next statuses in `TRANSITIONS`, validates sequencing metadata, and writes the status and audit event together. `sample_summary()` joins participant sites and groups counts in PostgreSQL.
- `check_blood_pressure()` validates the relationship between measurements after applying a partial update to the current values. Individual Pydantic fields validate ranges before the route runs, and PostgreSQL checks enforce them again at storage time.
- `CaptureTime` requires an aware timestamp and converts it to UTC before a create or edit reaches the route. An entry at `12:00+03:00` is returned and audited as `09:00Z`, so an edit and a later read agree.
- `export_phenotypes()` selects active records in a study, optionally filters the participant's site, escapes formula-like text, and encodes the CSV with a BOM. It exports current records; it does not silently reinterpret consent choices as a partner-specific authorization policy.
- `record_audit()` compares before/after snapshots, converts timestamps to JSON, excludes password hashes, and adds the event to the caller's session. It never commits independently. PostgreSQL rejects attempts to edit or delete events.
- `seed()` inserts missing demo accounts, study, participants and example records. Running it again leaves existing data and passwords in place. The enclosing transaction rolls back the whole seed if any required credential or insert fails.
- `Field` links each label and validation message to its input, including the participant selector. `Modal` keeps focus stable as forms rerender, handles Escape for the top dialog and restores scrolling after the final dialog closes. `Pagination` returns to the last available page if archiving removes its final record.

## Automated checks

Database connection recovery on 18 November 2026 is documented in the [troubleshooting guide](database-troubleshooting.md). The database, API and frontend had exited together with no restart policy. Compose now sets `restart: unless-stopped` for those services, and recovery retained the existing PostgreSQL volume. The guide records the observed evidence, verification results and steps for distinguishing service, credential and networking failures.

`make check` runs the configured Python and frontend checks. `make test` runs the API suite against the isolated PostgreSQL service, and `npm --prefix frontend run build` checks the production frontend bundle. The GitHub Actions workflow repeats these checks in separate backend and frontend jobs after a push or pull request.

Verified on 16 November 2026: `make check`, the production frontend build and all 45 API integration cases through Docker's Python 3.12 test image passed. The running Compose application passed HTTP checks for frontend assets, OpenAPI, documentation security policies, sign-in for all three roles and their access restrictions. The API applied migration `0001` and ran as UID 10001. Browser interaction checks could not run because browser access was unavailable; the keyboard checks below remain manual. GitHub-hosted CI awaits a reviewed push.

Verified on 17 November 2026 after account management changes: all 65 PostgreSQL integration cases passed through `make test`, including concurrent cross-deactivation and cross-demotion. `make check` and the production frontend Docker build passed. The audit date filters now submit plain `YYYY-MM-DD` values to match the API's inclusive UTC date contract. Browser interaction checks remain manual because browser access is unavailable.

The rebuilt application's live HTTP checks through Nginx also passed account creation, username and role changes, inactive-token and login denials, reactivation, non-Admin permission denial, self-access protection, duplicate username conflicts and inclusive date filtering. The temporary verification account was removed afterward.

The database fixtures commit their setup savepoints while retaining the outer test transaction. A rejected request can therefore roll back its own session without removing the test accounts or participant; the outer rollback still removes every test's data afterward. This matters for tests that send an invalid request followed by a corrected request.

For a manual keyboard check, open a participant form, click the Full name label and type several characters. Focus should stay in that input. Open an edit dialog from participant detail, press Escape once and confirm only the edit dialog closes. Close the detail and confirm the page scrolls again. Finally, archive the sole record on a final list page and confirm the list returns to an available page.

## Run the assessment demo

Start with `make setup`, `make dev`, and `make seed`. Passwords are the corresponding `SEED_*_PASSWORD` values in your private `.env`.

1. Sign in as Admin and register a participant with all demographic fields.
2. Search the registry by their county, then by the new KGRI ID.
3. Open their detail and change recontact consent to yes; confirm its recorded timestamp.
4. Register a DNA sample linked to that participant.
5. Open the sample and advance collected → shipped → received_at_lab.
6. Create a second collected sample. The UI exposes only valid next states; use authenticated `PATCH /api/samples/{id}/status` with `{"status":"sequenced"}` in the API docs to show the `400` naming `collected` and `shipped`.
7. Capture a valid phenotype. Try systolic 500 and confirm the range error; correct to 120 with diastolic 80 and save.
8. Export KGRI Baseline CSV, optionally filtered by site, and open it in Excel or Sheets.
9. Sign in as Field Officer. Audit navigation is hidden; an authenticated `GET /api/audit` shows the API's `403`.
10. Sign in as Admin, open Audit log and filter by entity type, user and date.
11. Open Overview and inspect the status, platform and site count summaries.
12. Open Team accounts. Create a synthetic account, edit its username or role, deactivate it and confirm its login is denied. Reactivate it and sign in again. The current Admin's status action and own-role change are protected. Existing tokens are denied while inactive; an unexpired earlier token can become usable again after reactivation if its role matches.
13. Close references and explain three files selected by the supervisor.

Steps 6 and 9 deliberately exercise denied API operations because the UI hides actions outside valid states or roles. The automated API suite covers these denials. Opening a CSV in a desktop spreadsheet and the final oral walkthrough are human assessment steps.

For a timed presentation, use the [presenter walkthrough](presentations/walkthrough.md), [technical deck](presentations/KGRI_Technical_Presentation.pptx) and [high-level deck](presentations/KGRI_High_Level_Presentation.pptx). The walkthrough also comes as a [Word document](presentations/KGRI_Presenter_Walkthrough.docx).

## Checkpoint practice

1. Why do role-aware buttons still need server-side permissions, and why does the API check the live account as well as the JWT claim?
2. What would happen if the audit event committed separately from the participant change? Where does the rollback test prove this cannot occur?
3. Why is a database constraint on allowed sample statuses insufficient to enforce the transition order?

Modify it on the spot: add a new measurement validation range in the Pydantic schema, PostgreSQL migration, form and integration test. Explain why editing only the frontend would be insufficient.

## Review before real-data deployment

This is an assessment implementation using synthetic records. The proposed consent defaults, withdrawal effects and export policy are explicit in README.md and need governance review for real research use. There is no partner-specific consent model, export approval airlock, MFA, password-reset flow, managed backup/restore, or production HTTPS deployment in this scope. CSV generation buffers the result in memory, which suits the pilot but should stream or run as a job for large cohorts. The API schema and UI roles are enforced, but deployment credentials and database ownership still need production configuration.

Do not manufacture historical commits or AI log entries to meet the assessment counts. Review the changes in coherent groups and write your own decisions and interaction log. Session raw material: the assistant implemented the approved schema, API, React screens, Docker workflow, synthetic seed and integration tests; you confirmed ER sign-off and should review the consent/export defaults, role matrix, ID generation and audit transaction behavior.
