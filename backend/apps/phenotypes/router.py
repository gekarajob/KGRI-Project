import csv
import io
from datetime import UTC
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.accounts.dependencies import current_user, require_roles
from apps.audit.service import record_audit
from apps.participants.service import active_participant, snapshot, utcnow
from apps.phenotypes.schemas import PhenotypeCreate, PhenotypePatch
from config.database import get_db
from config.models import Participant, PhenotypeRecord, Study, User

router = APIRouter(prefix="/phenotypes", tags=["phenotypes"])
studies_router = APIRouter(prefix="/studies", tags=["studies"])
Database = Annotated[Session, Depends(get_db)]
Reader = Annotated[User, Depends(require_roles("admin", "field_officer"))]
Admin = Annotated[User, Depends(require_roles("admin"))]


def phenotype_json(
    db: Session, record: PhenotypeRecord, participant: Participant, study: Study | None = None
) -> dict[str, Any]:
    study = study if study is not None else db.get(Study, record.study_id)
    result = snapshot(record)
    result.update(
        kgri_id=participant.kgri_id,
        participant_name=participant.full_name,
        recruitment_site=participant.recruitment_site,
        study_code=study.code if study is not None else None,
    )
    return result


def active_record(
    db: Session, phenotype_id: int, *, lock: bool = False
) -> tuple[PhenotypeRecord, Participant]:
    statement = (
        select(PhenotypeRecord, Participant)
        .join(Participant, PhenotypeRecord.participant_id == Participant.id)
        .where(
            PhenotypeRecord.id == phenotype_id,
            PhenotypeRecord.deleted_at.is_(None),
            Participant.deleted_at.is_(None),
        )
    )
    if lock:
        statement = statement.with_for_update(of=PhenotypeRecord)
    row = db.execute(statement).first()
    if row is None:
        raise HTTPException(
            404, detail={"code": "not_found", "message": "Phenotype record not found."}
        )
    return row[0], row[1]


def get_study(db: Session, study_id: int) -> Study:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Study not found."})
    return study


def check_blood_pressure(values: dict[str, Any]) -> None:
    systolic = Decimal(str(values["systolic_bp"]))
    diastolic = Decimal(str(values["diastolic_bp"]))
    if systolic <= diastolic:
        raise HTTPException(
            422,
            detail={
                "code": "validation_error",
                "message": "systolic_bp must be greater than diastolic_bp.",
                "field": "systolic_bp",
                "allowed": [f"> {values['diastolic_bp']}"],
            },
        )


@studies_router.get("")
def list_studies(
    db: Database, user: Annotated[User, Depends(current_user)]
) -> list[dict[str, Any]]:
    return [snapshot(study) for study in db.scalars(select(Study).order_by(Study.code)).all()]


@router.get("")
def list_phenotypes(
    db: Database,
    user: Reader,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    participant_id: int | None = Query(default=None, gt=0),
    study_id: int | None = Query(default=None, gt=0),
    site: str | None = Query(default=None, max_length=150),
) -> dict[str, Any]:
    statement = (
        select(PhenotypeRecord, Participant, Study)
        .join(Participant, PhenotypeRecord.participant_id == Participant.id)
        .join(Study, PhenotypeRecord.study_id == Study.id)
        .where(PhenotypeRecord.deleted_at.is_(None), Participant.deleted_at.is_(None))
    )
    if participant_id is not None:
        statement = statement.where(PhenotypeRecord.participant_id == participant_id)
    if study_id is not None:
        statement = statement.where(PhenotypeRecord.study_id == study_id)
    if site:
        statement = statement.where(Participant.recruitment_site == site)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(
        statement.order_by(PhenotypeRecord.captured_at.desc(), PhenotypeRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            phenotype_json(db, record, participant, study) for record, participant, study in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def safe_csv_cell(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    if isinstance(value, str) and value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


@router.get("/export")
def export_phenotypes(
    db: Database,
    user: Reader,
    study_id: int = Query(gt=0),
    site: str | None = Query(default=None, max_length=150),
) -> Response:
    get_study(db, study_id)
    statement = (
        select(PhenotypeRecord, Participant)
        .join(Participant, PhenotypeRecord.participant_id == Participant.id)
        .where(
            PhenotypeRecord.study_id == study_id,
            PhenotypeRecord.deleted_at.is_(None),
            Participant.deleted_at.is_(None),
        )
    )
    if site:
        statement = statement.where(Participant.recruitment_site == site)
    statement = statement.order_by(PhenotypeRecord.id)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "kgri_id",
            "participant_name",
            "study_id",
            "recruitment_site",
            "captured_at",
            "height_cm",
            "weight_kg",
            "systolic_bp",
            "diastolic_bp",
            "malaria_history",
            "livestock_contact",
            "notes",
            "captured_by_id",
        ]
    )
    for record, participant in db.execute(statement).yield_per(500):
        values = [
            record.id,
            participant.kgri_id,
            participant.full_name,
            record.study_id,
            participant.recruitment_site,
            record.captured_at.astimezone(UTC).isoformat(),
            record.height_cm,
            record.weight_kg,
            record.systolic_bp,
            record.diastolic_bp,
            record.malaria_history,
            record.livestock_contact,
            record.notes or "",
            record.captured_by_id,
        ]
        writer.writerow([safe_csv_cell(value) for value in values])
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="kgri-study-{study_id}-phenotypes.csv"'
        },
    )


@router.post("", status_code=201)
def create_phenotype(payload: PhenotypeCreate, db: Database, user: Reader) -> dict[str, Any]:
    participant = active_participant(db, payload.participant_id, lock=True)
    study = get_study(db, payload.study_id)
    values = payload.model_dump()
    check_blood_pressure(values)
    record = PhenotypeRecord(**values, captured_by_id=user.id)
    db.add(record)
    db.flush()
    record_audit(db, user.id, "CREATE", "phenotype", record.id, {}, snapshot(record))
    db.commit()
    db.refresh(record)
    return phenotype_json(db, record, participant, study)


@router.get("/{phenotype_id}")
def get_phenotype(phenotype_id: int, db: Database, user: Reader) -> dict[str, Any]:
    record, participant = active_record(db, phenotype_id)
    return phenotype_json(db, record, participant)


@router.patch("/{phenotype_id}")
def update_phenotype(
    phenotype_id: int, payload: PhenotypePatch, db: Database, user: Reader
) -> dict[str, Any]:
    record, participant = active_record(db, phenotype_id, lock=True)
    before = snapshot(record)
    changes = payload.model_dump(exclude_unset=True)
    if "participant_id" in changes:
        participant = active_participant(db, changes["participant_id"], lock=True)
    if "study_id" in changes:
        get_study(db, changes["study_id"])
    check_blood_pressure({**before, **changes})
    for field, value in changes.items():
        setattr(record, field, value)
    record.updated_at = utcnow()
    db.flush()
    record_audit(db, user.id, "UPDATE", "phenotype", record.id, before, snapshot(record))
    db.commit()
    return phenotype_json(db, record, participant)


@router.delete("/{phenotype_id}", status_code=204)
def delete_phenotype(phenotype_id: int, db: Database, user: Admin) -> Response:
    record, participant = active_record(db, phenotype_id, lock=True)
    before = snapshot(record)
    record.deleted_at = utcnow()
    record.updated_at = record.deleted_at
    db.flush()
    record_audit(db, user.id, "DELETE", "phenotype", record.id, before, snapshot(record))
    db.commit()
    return Response(status_code=204)
