# KGRI database schema

This schema transcribes the diagram supplied by the project owner on 15 November 2026. Supervisor sign-off is pending confirmation.

[Original diagram](database-schema.png)

```mermaid
erDiagram
    PARTICIPANT ||--|| PARTICIPANT_CONSENT : has
    PARTICIPANT ||--o{ SAMPLE : provides
    PARTICIPANT ||--o{ PHENOTYPE_RECORD : has
    STUDY ||--o{ PHENOTYPE_RECORD : contains
    USER ||--o{ PHENOTYPE_RECORD : captures
    USER ||--o{ AUDIT_EVENT : performs
    USER ||--o{ PARTICIPANT : creates
    USER ||--o{ SAMPLE : creates
    USER {
        bigint id PK
        string username UK
        string password_hash "bcrypt or Argon2"
        string role "admin, lab_tech, field_officer"
        boolean is_active
        datetime created_at
    }
    STUDY {
        bigint id PK
        string code UK "e.g. KGRI_BASELINE"
        string name
        datetime created_at
    }
    PARTICIPANT {
        bigint id PK
        string kgri_id UK "KGRI-XXXX from a DB sequence"
        string full_name "Indexed for search"
        smallint age "CHECK 0 to 120"
        string sex
        string community "Self-reported ethnicity"
        string county "Indexed"
        string recruitment_site "Indexed"
        bigint created_by_id FK
        datetime created_at
        datetime updated_at
        datetime deleted_at "Nullable, soft delete"
    }
    PARTICIPANT_CONSENT {
        bigint participant_id PK,FK
        boolean broad_consent
        datetime broad_consent_recorded_at "Nullable"
        boolean recontact_consent
        datetime recontact_consent_recorded_at "Nullable"
        boolean data_sharing_consent
        datetime data_sharing_consent_recorded_at "Nullable"
        datetime updated_at
    }
    SAMPLE {
        bigint id PK
        bigint participant_id FK "Indexed"
        string sample_type "dna, blood, saliva"
        string status "State machine, indexed"
        string platform "Nullable, ultima_ug100, ont_promethion, pacbio, olink"
        string batch_id "Nullable"
        string sequencing_file_path "Nullable, CRAM or BAM path"
        decimal mean_coverage "Nullable, CHECK >= 0"
        bigint created_by_id FK
        datetime created_at
        datetime updated_at
        datetime deleted_at "Nullable, soft delete"
    }
    PHENOTYPE_RECORD {
        bigint id PK
        bigint participant_id FK "Indexed"
        bigint study_id FK "Indexed"
        bigint captured_by_id FK
        datetime captured_at
        decimal height_cm "CHECK 50 to 250"
        decimal weight_kg "CHECK 10 to 300"
        decimal systolic_bp "CHECK 60 to 250"
        decimal diastolic_bp "CHECK 30 to 150"
        boolean malaria_history
        boolean livestock_contact
        string notes "Nullable, max 500 chars"
        datetime created_at
        datetime updated_at
        datetime deleted_at "Nullable, soft delete"
    }
    AUDIT_EVENT {
        bigint id PK
        bigint user_id FK "Indexed"
        datetime occurred_at "Indexed"
        string action "CREATE, UPDATE, DELETE"
        string entity_type "participant, sample, phenotype; indexed"
        bigint entity_id
        json changed_fields "JSON diff of old and new"
    }
```

## Implementation notes

- The two creator relationships make explicit the existing created_by_id foreign keys in the supplied diagram.
- Study belongs in the phenotypes application. Seed KGRI_BASELINE for the pilot.
- AuditEvent uses user_id as supplied. Its entity_id is a polymorphic identifier paired with entity_type. Consent changes are participant UPDATE events.
- Create a participant and its consent row in one transaction. The shared primary key enforces at most one consent row per participant.
- Use PostgreSQL and framework migrations after supervisor sign-off. The existing database/schema.sql describes a different SQLite model and is outside this design.
- Sample transitions follow collected > shipped > received_at_lab > dna_extracted > library_prepped > sequenced > qc_passed. Validate each transition against stored state.
- Write mutation audit events in the same transaction as their record changes.
- Preserve the supplied nullable consent timestamps. Confirm boolean defaults and the meaning of an unrecorded timestamp before implementation.
- Confirm string lengths, decimal precision, allowed sex values, age semantics, identifier behavior above 9999, and deletion behavior for linked records before migrations.
- Django may expose the password hash through its standard password attribute while mapping the database column to password_hash. Final auth model mapping remains an implementation decision.
