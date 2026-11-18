from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from apps.accounts.security import JWT_AUDIENCE, JWT_ISSUER, jwt_secret
from config.database import get_db
from config.models import User

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail={"code": "unauthenticated", "message": "Please sign in to continue."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials,
            jwt_secret(),
            algorithms=["HS256"],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["sub", "role", "exp", "iat", "nbf"]},
        )
        user_id = int(claims["sub"])
        if not 1 <= user_id <= 2**63 - 1:
            raise unauthorized
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized from None
    user = db.get(User, user_id)
    if user is None or not user.is_active or claims["role"] != user.role:
        raise unauthorized
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def permitted_user(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role != "admin" and user.role not in roles:
            allowed = sorted({"admin", *roles})
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "forbidden",
                    "message": f"This action requires one of these roles: {', '.join(allowed)}.",
                    "allowed": allowed,
                },
            )
        return user

    return permitted_user
