# KGRI Participant Portal

Research operations overview

Audience and timing: 9 minute presentation

Date: 17 November 2026

## Slide 1 KGRI Participant Portal

Research operations overview

### Speaker notes

Audience: research leadership, operations and assessment stakeholders. Allow nine minutes. The portal is a local assessment implementation using synthetic data. Explain the operational workflow and the remaining decisions before introducing real research data. Sources: README.md; asbuild.md; docs/implementation.md.

## Slide 2 Research operations in one workspace

**Participant registry** Find enrolled people and maintain their demographic records

**Consent tracking** Record current choices with their decision timestamps

**Sample tracking** See each specimen and its permitted next processing step

**Study measurements** Capture validated observations and export a study dataset

### Speaker notes

These capabilities connect participant identity to specimens and measurements. Avoid promising measured time savings or productivity gains, since no user study or operational benchmark has been run. The system supports a pilot demonstration of the workflow. Source: README.md; frontend/src/Participants.tsx; Samples.tsx; Phenotypes.tsx.

## Slide 3 Staff responsibilities

| Role | Primary work | Restricted access |
| --- | --- | --- |
| Field Officer | Registration, consent, measurements and exports | No account or audit administration |
| Lab Tech | Samples and sequencing progress | No phenotype access |
| Admin | Account management and all domain workflows | Self-access safeguards apply |

### Speaker notes

All three roles can read the participant registry and sample summaries. Admin can create staff, edit usernames and roles, deactivate and reactivate accounts, and review domain audit history. Account access follows current role and active state. The API enforces permissions independently of hidden buttons. Source: README.md; backend/apps/accounts/; frontend/src/App.tsx.

## Slide 4 Participant and specimen workflow

**Registration** Create the participant identifier and initial consent record together

**Collection and processing** Link samples and progress through the approved processing sequence

**Study capture** Link observations to the participant, study and capturing staff member

**Review and export** Inspect history and download records for the selected study and site

### Speaker notes

Use a single fictional participant to explain the full workflow. A sample cannot skip stages. Clinical input rules reject out-of-range values. Authorized staff can correct records. Current exports include active records regardless of consent flags, so research governance must settle partner access and withdrawal-driven rules before real-data use. Sources: backend/apps/participants/; samples/; phenotypes/.

## Slide 5 Admin control of staff access

### Account actions

- Add an account with its required role
- Edit username or role
- Deactivate access when duties end
- Reactivate access when approved

### Continuity of access

- Keep at least one active administrator
- Prevent self-deactivation and role loss
- Deny protected calls while inactive
- Keep historical record references intact

### Speaker notes

Deactivation does not delete the user or remove links to their previous domain work. The service serializes concurrent admin changes and checks the acting admin again after waiting. On reactivation an account may sign in again. Unexpired prior tokens can work again if their role still matches, so this is state-based access control rather than permanent token revocation. Password reset and account-audit expansion remain possible later work. Sources: backend/apps/accounts/service.py; router.py; frontend/src/Admin.tsx.

## Slide 6 Data quality and accountability

### Data quality controls

- Required participant and study linkage
- Measurement ranges and blood-pressure order
- Permitted sample transitions
- Timezone-aware capture timestamps

### Accountability controls

- Current consent choices and decision times
- Actor-linked domain changes
- Audit history preserved by database rules
- Role-specific access to clinical information

### Speaker notes

Explain controls as implemented mechanisms rather than a certification. Domain events cover participants, samples and phenotypes. They do not currently cover all account changes, login attempts or export reads. Consent choices are captured accurately, but downstream restrictions need a research governance policy. Source: backend/config/models.py; backend/apps/audit/; README.md.

## Slide 7 Demonstration dataset

| Synthetic item | Seed quantity | Demonstration purpose |
| --- | --- | --- |
| Participants | 50 | Registry search across three recruitment sites |
| Samples | 35 | Processing stages and count summaries |
| Phenotype records | 24 | Validation, study filtering and CSV export |
| Staff roles | 3 | Role permissions and account administration |

Demo sites include Moyale, Nairobi and Meru. These counts describe seed data, not a live research cohort.

### Speaker notes

The explicit seed command is idempotent and preserves existing records and passwords. The three demo usernames are admin, lab_tech and field_officer. Read their passwords privately from .env. Avoid showing credentials during the presentation. Source: backend/apps/seed.py; README.md.

## Slide 8 Verification approach

| Check | What it demonstrates |
| --- | --- |
| PostgreSQL integration cases | Permissions, validation, transactions and account races |
| Frontend source checks and build | Type consistency, lint and production compilation |
| Docker and HTTP checks | Service readiness and request routing |
| Manual demonstration | Screen interaction and the complete staff workflow |

### Speaker notes

The 17 November 2026 account-management build passed all 65 integration cases, including cross-deactivation and cross-demotion races. Refer to the presenter walkthrough for the executed checks and demonstration steps. Browser-dependent checks should only be claimed when actually exercised. Automated checks do not establish clinical effectiveness, cohort-scale performance or regulatory approval. Sources: backend/tests/; .github/workflows/ci.yml; docs/implementation.md.

## Slide 9 Rollout decisions

### Research owners

- Approve consent and withdrawal rules
- Define partner export permissions
- Confirm staff roles and data visibility
- Set data retention responsibilities

### Technical owners

- Select supported hosting and HTTPS
- Agree on identity recovery and MFA
- Test backup and restoration
- Approve monitoring and access review

### Speaker notes

These are rollout decisions rather than delivered production capabilities. The current local installation runs via Docker Compose. Moving it requires configuration and a database backup if records must be retained. The application does not currently implement partner-specific consent, export approvals, a file-transfer pipeline or a managed backup service. Source: README.md; asbuild.md; docs/implementation.md.

## Slide 10 Pilot review

**Workflow review** Observe registration, sample progression and measurement export

**Access review** Confirm each role and exercise account deactivation

**Technical review** Inspect test evidence, transaction behavior and deployment requirements

**Next decision** Agree on the policy and operating requirements for a controlled pilot

### Speaker notes

Close with the review sequence and invite questions. Keep the decision framed as readiness for an agreed controlled pilot, not a claim that real-data deployment has already been authorized. The presenter walkthrough provides a nine-minute speaking route and a longer technical route. Sources: docs/presentations/walkthrough.md; README.md; DECISIONS.md.
