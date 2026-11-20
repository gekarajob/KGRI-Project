from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from config.models import Participant, ParticipantConsent

CONSENT_FIELDS = ("broad_consent", "recontact_consent", "data_sharing_consent")


def utcnow() -> datetime:
    return datetime.now(UTC)


def snapshot(record: Any) -> dict[str, Any]:
    values = {
        column.key: getattr(record, column.key) for column in inspect(record).mapper.column_attrs
    }
    return {
        key: float(value) if isinstance(value, Decimal) else value for key, value in values.items()
    }


def active_participant(db: Session, participant_id: int, *, lock: bool = False) -> Participant:
    statement = select(Participant).where(
        Participant.id == participant_id, Participant.deleted_at.is_(None)
    )
    if lock:
        statement = statement.with_for_update()
    participant = db.scalar(statement)
    if participant is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Participant not found."})
    return participant


def participant_snapshot(participant: Participant) -> dict[str, Any]:
    data = snapshot(participant)
    if participant.consent is not None:
        data.update(
            {f"consent.{key}": value for key, value in snapshot(participant.consent).items()}
        )
    return data


def participant_json(participant: Participant) -> dict[str, Any]:
    data = snapshot(participant)
    data["consent"] = snapshot(participant.consent) if participant.consent is not None else None
    return data


def apply_consent(consent: ParticipantConsent, changes: dict[str, bool]) -> None:
    now = utcnow()
    for field, value in changes.items():
        # A first recorded refusal differs from an unanswered default false.
        if getattr(consent, field) != value or getattr(consent, f"{field}_recorded_at") is None:
            setattr(consent, field, value)
            setattr(consent, f"{field}_recorded_at", now)
    consent.updated_at = now
