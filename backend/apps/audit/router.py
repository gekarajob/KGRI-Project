from datetime import UTC, date, datetime, time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from apps.accounts.dependencies import require_roles
from config.database import get_db
from config.models import AuditEvent, User

router = APIRouter(prefix="/audit", tags=["Audit log"])


@router.get("")
def list_audit_events(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin"))],
    user_id: Annotated[int | None, Query(gt=0)] = None,
    entity_type: Literal["participant", "sample", "phenotype", "user"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "date_from must be on or before date_to.",
                "field": "date_from",
            },
        )
    conditions = []
    if user_id is not None:
        conditions.append(AuditEvent.user_id == user_id)
    if entity_type is not None:
        conditions.append(AuditEvent.entity_type == entity_type)
    if date_from is not None:
        conditions.append(AuditEvent.occurred_at >= datetime.combine(date_from, time.min, UTC))
    if date_to is not None:
        conditions.append(AuditEvent.occurred_at <= datetime.combine(date_to, time.max, UTC))
    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    events = db.scalars(
        select(AuditEvent)
        .options(joinedload(AuditEvent.user))
        .where(*conditions)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [
            {
                "id": event.id,
                "user_id": event.user_id,
                "username": event.user.username,
                "occurred_at": event.occurred_at,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "changed_fields": event.changed_fields,
            }
            for event in events
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
