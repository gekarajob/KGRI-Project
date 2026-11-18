from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from apps.accounts.dependencies import current_user, require_roles
from apps.audit.service import record_audit
from apps.participants.schemas import ConsentPatch, ParticipantCreate, ParticipantPatch
from apps.participants.service import (
    CONSENT_FIELDS,
    active_participant,
    apply_consent,
    participant_json,
    participant_snapshot,
    utcnow,
)
from config.database import get_db
from config.models import Participant, ParticipantConsent, PhenotypeRecord, Sample, User

router = APIRouter(prefix="/participants", tags=["participants"])
Database = Annotated[Session, Depends(get_db)]
Reader = Annotated[User, Depends(current_user)]
Writer = Annotated[User, Depends(require_roles("admin", "field_officer"))]
Admin = Annotated[User, Depends(require_roles("admin"))]


@router.get("")
def list_participants(
    db: Database,
    user: Reader,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=150),
    county: str | None = Query(default=None, max_length=150),
    site: str | None = Query(default=None, max_length=150),
    broad_consent: bool | None = None,
    recontact_consent: bool | None = None,
    data_sharing_consent: bool | None = None,
) -> dict[str, Any]:
    statement = select(Participant).join(ParticipantConsent).where(Participant.deleted_at.is_(None))
    if search and search.strip():
        value = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{value}%"
        statement = statement.where(
            or_(
                *[
                    column.ilike(pattern, escape="\\")
                    for column in (
                        Participant.full_name,
                        Participant.kgri_id,
                        Participant.county,
                        Participant.recruitment_site,
                    )
                ]
            )
        )
    if county:
        statement = statement.where(Participant.county == county)
    if site:
        statement = statement.where(Participant.recruitment_site == site)
    choices = {
        "broad_consent": broad_consent,
        "recontact_consent": recontact_consent,
        "data_sharing_consent": data_sharing_consent,
    }
    for field, consent_value in choices.items():
        if consent_value is not None:
            statement = statement.where(getattr(ParticipantConsent, field) == consent_value)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    participants = db.scalars(
        statement.options(selectinload(Participant.consent))
        .order_by(Participant.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [participant_json(item) for item in participants],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=201)
def create_participant(payload: ParticipantCreate, db: Database, user: Writer) -> dict[str, Any]:
    values = payload.model_dump(exclude={"consent"})
    participant = Participant(**values, created_by_id=user.id)
    consent = ParticipantConsent(**{field: False for field in CONSENT_FIELDS})
    if payload.consent is not None:
        for field in payload.consent.model_fields_set:
            setattr(consent, field, getattr(payload.consent, field))
            setattr(consent, f"{field}_recorded_at", utcnow())
    participant.consent = consent
    db.add(participant)
    db.flush()
    record_audit(
        db, user.id, "CREATE", "participant", participant.id, {}, participant_snapshot(participant)
    )
    db.commit()
    db.refresh(participant)
    return participant_json(participant)


@router.get("/{participant_id}")
def get_participant(participant_id: int, db: Database, user: Reader) -> dict[str, Any]:
    from apps.phenotypes.router import phenotype_json
    from apps.samples.router import sample_json

    participant = active_participant(db, participant_id)
    result = participant_json(participant)
    samples = db.scalars(
        select(Sample)
        .where(Sample.participant_id == participant_id, Sample.deleted_at.is_(None))
        .order_by(Sample.id.desc())
    ).all()
    result["samples"] = [sample_json(sample, participant) for sample in samples]
    result["phenotypes_restricted"] = user.role == "lab_tech"
    if user.role == "lab_tech":
        result["phenotypes"] = []
    else:
        records = db.scalars(
            select(PhenotypeRecord)
            .where(
                PhenotypeRecord.participant_id == participant_id,
                PhenotypeRecord.deleted_at.is_(None),
            )
            .order_by(PhenotypeRecord.captured_at.desc())
        ).all()
        result["phenotypes"] = [phenotype_json(db, record, participant) for record in records]
    return result


@router.patch("/{participant_id}")
def update_participant(
    participant_id: int, payload: ParticipantPatch, db: Database, user: Writer
) -> dict[str, Any]:
    participant = active_participant(db, participant_id, lock=True)
    before = participant_snapshot(participant)
    changes = payload.model_dump(exclude_unset=True, exclude={"consent"})
    for field, value in changes.items():
        setattr(participant, field, value)
    if payload.consent is not None:
        apply_consent(participant.consent, payload.consent.model_dump(exclude_unset=True))
    participant.updated_at = utcnow()
    db.flush()
    record_audit(
        db,
        user.id,
        "UPDATE",
        "participant",
        participant.id,
        before,
        participant_snapshot(participant),
    )
    db.commit()
    return participant_json(participant)


@router.patch("/{participant_id}/consent")
def update_consent(
    participant_id: int, payload: ConsentPatch, db: Database, user: Writer
) -> dict[str, Any]:
    participant = active_participant(db, participant_id, lock=True)
    before = participant_snapshot(participant)
    apply_consent(participant.consent, payload.model_dump(exclude_unset=True))
    participant.updated_at = utcnow()
    db.flush()
    record_audit(
        db,
        user.id,
        "UPDATE",
        "participant",
        participant.id,
        before,
        participant_snapshot(participant),
    )
    db.commit()
    return participant_json(participant)


@router.delete("/{participant_id}", status_code=204)
def delete_participant(participant_id: int, db: Database, user: Admin) -> Response:
    from fastapi import HTTPException

    participant = active_participant(db, participant_id, lock=True)
    active_samples = (
        db.scalar(
            select(func.count())
            .select_from(Sample)
            .where(Sample.participant_id == participant_id, Sample.deleted_at.is_(None))
        )
        or 0
    )
    if active_samples:
        raise HTTPException(
            409,
            detail={
                "code": "active_samples",
                "message": "Participant cannot be deleted while active samples exist.",
            },
        )
    before = participant_snapshot(participant)
    participant.deleted_at = utcnow()
    participant.updated_at = participant.deleted_at
    db.flush()
    record_audit(
        db,
        user.id,
        "DELETE",
        "participant",
        participant.id,
        before,
        participant_snapshot(participant),
    )
    db.commit()
    return Response(status_code=204)
