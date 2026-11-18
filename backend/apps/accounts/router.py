from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.accounts.dependencies import current_user, require_roles
from apps.accounts.security import create_access_token, hash_password, verify_password
from apps.accounts.service import lock_account_mutations, protect_admin_access
from config.database import get_db
from config.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])
dummy_password_hash = hash_password("timing-equalization-account-does-not-exist")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "lab_tech", "field_officer"]

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class AccountPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(
        default=None, min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    role: Literal["admin", "lab_tech", "field_officer"] | None = None
    is_active: bool | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @model_validator(mode="after")
    def reject_null_fields(self) -> "AccountPatch":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    valid_password = verify_password(
        payload.password, user.password_hash if user is not None else dummy_password_hash
    )
    if user is None or not valid_password or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "Invalid username or password."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user), user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    payload: RegistrationRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[User, Depends(require_roles("admin"))],
) -> User:
    password_hash = hash_password(payload.password)
    lock_account_mutations(db, actor.id)
    user = User(
        username=payload.username,
        password_hash=password_hash,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "username_exists",
                "message": "This username is already registered.",
                "field": "username",
            },
        ) from None
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin"))],
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: Annotated[int, Path(gt=0, le=2**63 - 1)],
    payload: AccountPatch,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[User, Depends(require_roles("admin"))],
) -> User:
    actor = lock_account_mutations(db, actor.id)
    user = db.get(User, user_id, populate_existing=True)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Account not found."},
        )
    changes = payload.model_dump(exclude_unset=True)
    protect_admin_access(
        db, actor, user, changes.get("role", user.role), changes.get("is_active", user.is_active)
    )
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "username_exists",
                "message": "This username is already registered.",
                "field": "username",
            },
        ) from None
    db.refresh(user)
    return user
