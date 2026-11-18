from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.models import User

# A fixed two-integer namespace serializes account writes across API workers.
# Transaction-scoped locks release automatically on either commit or rollback.
ACCOUNT_LOCK_NAMESPACE = 0x4B475249
ACCOUNT_LOCK_KEY = 1


def lock_account_mutations(db: Session, actor_id: int) -> User:
    db.execute(select(func.pg_advisory_xact_lock(ACCOUNT_LOCK_NAMESPACE, ACCOUNT_LOCK_KEY)))
    # Authentication ran before acquiring the lock. Another admin may have revoked
    # this actor while the request waited, and the identity map may hold old values.
    actor = db.get(User, actor_id, populate_existing=True)
    if actor is None or not actor.is_active or actor.role != "admin":
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthenticated", "message": "Please sign in to continue."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return actor


def protect_admin_access(
    db: Session, actor: User, target: User, new_role: str, new_is_active: bool
) -> None:
    if target.role == "admin" and target.is_active and (new_role != "admin" or not new_is_active):
        active_admins = db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.is_active)
        )
        if active_admins is None or active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "last_active_admin",
                    "message": "At least one active admin account must remain.",
                },
            )
    if target.id == actor.id and not new_is_active:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "self_deactivation",
                "message": "You cannot deactivate your own account. Ask another admin.",
                "field": "is_active",
            },
        )
    if target.id == actor.id and new_role != "admin":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "self_demotion",
                "message": "You cannot change your own admin role. Ask another admin.",
                "field": "role",
            },
        )
