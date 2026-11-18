"""Idempotent, synthetic local demonstration data. Never run against participant data."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.accounts.security import hash_password
from apps.audit.service import record_audit
from config.database import SessionLocal
from config.models import (
    Participant,
    ParticipantConsent,
    PhenotypeRecord,
    Sample,
    Study,
    User,
)

STATES = (
    "collected",
    "shipped",
    "received_at_lab",
    "dna_extracted",
    "library_prepped",
    "sequenced",
    "qc_passed",
)


def seed(db: Session) -> None:
    users = {}
    for username, role, variable in (
        ("admin", "admin", "SEED_ADMIN_PASSWORD"),
        ("lab_tech", "lab_tech", "SEED_LAB_PASSWORD"),
        ("field_officer", "field_officer", "SEED_FIELD_PASSWORD"),
    ):
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            password = os.environ.get(variable, "")
            if len(password) < 12:
                raise ValueError(f"Set {variable} to at least 12 characters before seeding.")
            user = User(
                username=username, role=role, password_hash=hash_password(password), is_active=True
            )
            db.add(user)
            db.flush()
        elif user.role != role:
            raise ValueError(f"Existing {username} has a different role; no account was changed.")
        users[role] = user

    study = db.scalar(select(Study).where(Study.code == "KGRI_BASELINE"))
    if study is None:
        study = Study(code="KGRI_BASELINE", name="KGRI Baseline Study")
        db.add(study)
        db.flush()

    first_names = (
        "Amina",
        "David",
        "Grace",
        "Hassan",
        "Faith",
        "James",
        "Fatuma",
        "Daniel",
        "Mary",
        "Peter",
    )
    last_names = ("Mwangi", "Ali", "Otieno", "Wanjiku", "Abdi")
    locations = (("Moyale", "Marsabit"), ("Nairobi", "Nairobi"), ("Meru", "Meru"))
    communities = ("Borana", "Kikuyu", "Meru", "Luo", "Somali")
    now = datetime.now(UTC)
    for index in range(50):
        name = f"Demo {first_names[index % 10]} {last_names[index // 10]}"
        participant = db.scalar(select(Participant).where(Participant.full_name == name))
        site, county = locations[index % 3]
        recorded = now - timedelta(days=50 - index)
        if participant is None:
            participant = Participant(
                full_name=name,
                age=18 + index % 59,
                sex="female" if index % 2 == 0 else "male",
                community=communities[index % 5],
                county=county,
                recruitment_site=site,
                created_by_id=users["field_officer"].id,
                created_at=recorded,
                updated_at=recorded,
            )
            participant.consent = ParticipantConsent(
                broad_consent=index % 7 != 0,
                broad_consent_recorded_at=recorded,
                recontact_consent=index % 3 != 0,
                recontact_consent_recorded_at=recorded,
                data_sharing_consent=index % 4 != 0,
                data_sharing_consent_recorded_at=recorded,
            )
            db.add(participant)
            db.flush()
            record_audit(
                db,
                users["field_officer"].id,
                "CREATE",
                "participant",
                participant.id,
                {},
                {"kgri_id": participant.kgri_id, "full_name": name, "source": "synthetic_seed"},
            )

        if (
            index < 35
            and db.scalar(select(Sample.id).where(Sample.participant_id == participant.id)) is None
        ):
            status = STATES[index % 7]
            sequenced = status in ("sequenced", "qc_passed")
            platform = (
                ("ultima_ug100", "ont_promethion", "pacbio", "olink")[index % 4]
                if sequenced
                else None
            )
            sample = Sample(
                participant_id=participant.id,
                sample_type=("blood", "dna", "saliva")[index % 3],
                status=status,
                platform=platform,
                batch_id=f"DEMO-{index // 7 + 1:03d}" if sequenced else None,
                sequencing_file_path=f"/synthetic/{participant.kgri_id}.cram"
                if sequenced and platform != "olink"
                else None,
                mean_coverage=30.5 if sequenced and platform != "olink" else None,
                created_by_id=users["lab_tech"].id,
                created_at=recorded,
            )
            db.add(sample)
            db.flush()
            record_audit(
                db,
                users["lab_tech"].id,
                "CREATE",
                "sample",
                sample.id,
                {},
                {"participant_id": participant.id, "status": status, "source": "synthetic_seed"},
            )

        if (
            index < 24
            and db.scalar(
                select(PhenotypeRecord.id).where(
                    PhenotypeRecord.participant_id == participant.id,
                    PhenotypeRecord.study_id == study.id,
                )
            )
            is None
        ):
            phenotype = PhenotypeRecord(
                participant_id=participant.id,
                study_id=study.id,
                captured_by_id=users["field_officer"].id,
                captured_at=recorded,
                height_cm=155 + index % 30,
                weight_kg=54 + index % 38,
                systolic_bp=110 + index % 25,
                diastolic_bp=65 + index % 19,
                malaria_history=index % 3 == 0,
                livestock_contact=index % 2 == 0,
                notes="Synthetic demonstration record; no real participant data.",
            )
            db.add(phenotype)
            db.flush()
            record_audit(
                db,
                users["field_officer"].id,
                "CREATE",
                "phenotype",
                phenotype.id,
                {},
                {
                    "participant_id": participant.id,
                    "study_id": study.id,
                    "source": "synthetic_seed",
                },
            )


if __name__ == "__main__":
    with SessionLocal.begin() as session:
        seed(session)
    print(
        "Synthetic seed complete: admin, lab_tech, field_officer; KGRI_BASELINE; 50 participants."
    )
