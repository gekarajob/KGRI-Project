from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from apps.accounts.dependencies import current_user, require_roles
from apps.audit.service import record_audit
from apps.participants.service import active_participant, snapshot, utcnow
from apps.samples.schemas import Platform, SampleCreate, SamplePatch, SampleStatus, StatusChange
from config.database import get_db
from config.models import Participant, Sample, User

router = APIRouter(prefix="/samples", tags=["samples"])
Database = Annotated[Session, Depends(get_db)]
Reader = Annotated[User, Depends(current_user)]
Writer = Annotated[User, Depends(require_roles("admin", "lab_tech"))]

TRANSITIONS: dict[str, list[str]] = {
    "collected": ["shipped"],
    "shipped": ["received_at_lab"],
    "received_at_lab": ["dna_extracted"],
    "dna_extracted": ["library_prepped"],
    "library_prepped": ["sequenced"],
    "sequenced": ["qc_passed"],
    "qc_passed": [],
}


def sample_json(sample: Sample, participant: Participant) -> dict[str, Any]:
    result = snapshot(sample)
    result.update(
        kgri_id=participant.kgri_id,
        participant_name=participant.full_name,
        recruitment_site=participant.recruitment_site,
        allowed_next_states=TRANSITIONS[sample.status],
    )
    return result


def active_sample(db: Session, sample_id: int, *, lock: bool = False) -> tuple[Sample, Participant]:
    statement = (
        select(Sample, Participant)
        .join(Participant, Sample.participant_id == Participant.id)
        .where(
            Sample.id == sample_id, Sample.deleted_at.is_(None), Participant.deleted_at.is_(None)
        )
    )
    if lock:
        statement = statement.with_for_update(of=Sample)
    row = db.execute(statement).first()
    if row is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Sample not found."})
    return row[0], row[1]


def validate_sequencing(values: dict[str, Any]) -> None:
    path = values.get("sequencing_file_path")
    coverage = values.get("mean_coverage")
    platform = values.get("platform")
    if platform == "olink" and (path is not None or coverage is not None):
        raise HTTPException(
            422,
            detail={
                "code": "validation_error",
                "message": "Olink records must leave sequencing_file_path and mean_coverage empty.",
                "field": "platform",
                "allowed": ["sequencing_file_path=null", "mean_coverage=null"],
            },
        )
    if path and not path.lower().endswith((".cram", ".bam")):
        raise HTTPException(
            422,
            detail={
                "code": "validation_error",
                "message": "sequencing_file_path must end in .cram or .bam.",
                "field": "sequencing_file_path",
                "allowed": [".cram", ".bam"],
            },
        )
    if values.get("status") in {"sequenced", "qc_passed"}:
        required = ["platform", "batch_id"]
        if platform != "olink":
            required.extend(["sequencing_file_path", "mean_coverage"])
        for field in required:
            if values.get(field) is None:
                raise HTTPException(
                    422,
                    detail={
                        "code": "validation_error",
                        "message": f"{field} is required when the sample is sequenced.",
                        "field": field,
                    },
                )


@router.get("")
def list_samples(
    db: Database,
    user: Reader,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: SampleStatus | None = None,
    platform: Platform | None = None,
    site: str | None = Query(default=None, max_length=150),
    participant_id: int | None = Query(default=None, gt=0),
) -> dict[str, Any]:
    statement = (
        select(Sample, Participant)
        .join(Participant, Sample.participant_id == Participant.id)
        .where(Sample.deleted_at.is_(None), Participant.deleted_at.is_(None))
    )
    if status:
        statement = statement.where(Sample.status == status)
    if platform:
        statement = statement.where(Sample.platform == platform)
    if site:
        statement = statement.where(Participant.recruitment_site == site)
    if participant_id is not None:
        statement = statement.where(Sample.participant_id == participant_id)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(
        statement.order_by(Sample.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [sample_json(sample, participant) for sample, participant in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/summary")
def sample_summary(
    db: Database, user: Reader, site: str | None = Query(default=None, max_length=150)
) -> dict[str, Any]:
    filters: list[ColumnElement[bool]] = [
        Sample.deleted_at.is_(None),
        Participant.deleted_at.is_(None),
    ]
    if site:
        filters.append(Participant.recruitment_site == site)
    base = (
        select(
            Sample.status.label("status"),
            Sample.platform.label("platform"),
            Participant.recruitment_site.label("recruitment_site"),
        )
        .join(Participant, Sample.participant_id == Participant.id)
        .where(*filters)
        .subquery()
    )
    status_counts: dict[str, int] = dict(
        db.execute(select(base.c.status, func.count()).group_by(base.c.status)).all()
    )
    platform_counts = db.execute(
        select(base.c.platform, func.count()).group_by(base.c.platform).order_by(base.c.platform)
    ).all()
    site_counts = db.execute(
        select(base.c.recruitment_site, func.count())
        .group_by(base.c.recruitment_site)
        .order_by(base.c.recruitment_site)
    ).all()
    return {
        "total": sum(status_counts.values()),
        "by_status": [
            {"status": status, "count": status_counts.get(status, 0)} for status in TRANSITIONS
        ],
        "by_platform": [
            {"platform": platform, "count": count} for platform, count in platform_counts
        ],
        "by_site": [
            {"recruitment_site": site_name, "count": count} for site_name, count in site_counts
        ],
    }


@router.post("", status_code=201)
def create_sample(payload: SampleCreate, db: Database, user: Writer) -> dict[str, Any]:
    participant = active_participant(db, payload.participant_id, lock=True)
    values = payload.model_dump()
    values["status"] = "collected"
    validate_sequencing(values)
    sample = Sample(**values, created_by_id=user.id)
    db.add(sample)
    db.flush()
    record_audit(db, user.id, "CREATE", "sample", sample.id, {}, snapshot(sample))
    db.commit()
    db.refresh(sample)
    return sample_json(sample, participant)


@router.get("/{sample_id}")
def get_sample(sample_id: int, db: Database, user: Reader) -> dict[str, Any]:
    sample, participant = active_sample(db, sample_id)
    return sample_json(sample, participant)


@router.patch("/{sample_id}")
def update_sample(
    sample_id: int, payload: SamplePatch, db: Database, user: Writer
) -> dict[str, Any]:
    sample, participant = active_sample(db, sample_id, lock=True)
    before = snapshot(sample)
    changes = payload.model_dump(exclude_unset=True)
    validate_sequencing({**before, **changes})
    for field, value in changes.items():
        setattr(sample, field, value)
    sample.updated_at = utcnow()
    db.flush()
    record_audit(db, user.id, "UPDATE", "sample", sample.id, before, snapshot(sample))
    db.commit()
    return sample_json(sample, participant)


@router.patch("/{sample_id}/status")
def change_status(
    sample_id: int, payload: StatusChange, db: Database, user: Writer
) -> dict[str, Any]:
    sample, participant = active_sample(db, sample_id, lock=True)
    allowed = TRANSITIONS[sample.status]
    if payload.status not in allowed:
        next_states = ", ".join(allowed) if allowed else "none (final state)"
        raise HTTPException(
            400,
            detail={
                "code": "invalid_transition",
                "message": (
                    f"Cannot move from {sample.status} to {payload.status}. "
                    f"Allowed next states: {next_states}."
                ),
                "field": "status",
                "allowed": allowed,
            },
        )
    before = snapshot(sample)
    validate_sequencing({**before, "status": payload.status})
    sample.status = payload.status
    sample.updated_at = utcnow()
    db.flush()
    record_audit(db, user.id, "UPDATE", "sample", sample.id, before, snapshot(sample))
    db.commit()
    return sample_json(sample, participant)


@router.delete("/{sample_id}", status_code=204)
def delete_sample(sample_id: int, db: Database, user: Writer) -> Response:
    sample, participant = active_sample(db, sample_id, lock=True)
    before = snapshot(sample)
    sample.deleted_at = utcnow()
    sample.updated_at = sample.deleted_at
    db.flush()
    record_audit(db, user.id, "DELETE", "sample", sample.id, before, snapshot(sample))
    db.commit()
    return Response(status_code=204)
