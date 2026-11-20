from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from config.models import AuditEvent


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {
            key: json_value(item)
            for key, item in value.items()
            if key not in {"password", "password_hash", "access_token"}
        }
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def record_audit(
    db: Session,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> AuditEvent:
    old_values = json_value(before or {})
    new_values = json_value(after or {})
    fields = sorted(old_values.keys() | new_values.keys())
    changed_fields = {
        field: {"old": old_values.get(field), "new": new_values.get(field)}
        for field in fields
        if old_values.get(field) != new_values.get(field)
    }
    event = AuditEvent(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changed_fields=changed_fields,
    )
    db.add(event)
    return event
