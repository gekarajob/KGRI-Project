from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.accounts.security import create_access_token
from config.database import engine
from config.main import app
from config.models import User
from tests.conftest import PASSWORD


def test_admin_edits_account_username_and_role(client, headers, users, db):
    target = users["field_officer"]
    old_token = headers("field_officer")
    response = client.patch(
        f"/api/auth/users/{target.id}",
        headers=headers(),
        json={"username": "Updated.Field", "role": "lab_tech"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": target.id,
        "username": "updated.field",
        "role": "lab_tech",
        "is_active": True,
    }
    db.refresh(target)
    assert target.username == "updated.field" and target.role == "lab_tech"
    assert client.get("/api/auth/me", headers=old_token).status_code == 401
    login = client.post(
        "/api/auth/login",
        json={"username": "UPDATED.FIELD", "password": PASSWORD},
    )
    assert login.status_code == 200 and login.json()["user"]["role"] == "lab_tech"
    new_token = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/samples", headers=new_token).status_code == 200
    assert client.get("/api/phenotypes", headers=new_token).status_code == 403


def test_admin_deactivates_and_reactivates_account(client, headers, users):
    target = users["field_officer"]
    path = f"/api/auth/users/{target.id}"
    existing_token = headers("field_officer")
    admin_token = headers()
    response = client.patch(path, headers=admin_token, json={"is_active": False})
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert client.get("/api/auth/me", headers=existing_token).status_code == 401
    login_body = {"username": target.username, "password": PASSWORD}
    assert client.post("/api/auth/login", json=login_body).status_code == 401
    response = client.patch(path, headers=admin_token, json={"is_active": True})
    assert response.status_code == 200 and response.json()["is_active"] is True
    assert client.post("/api/auth/login", json=login_body).status_code == 200


@pytest.mark.parametrize("role", ["lab_tech", "field_officer"])
def test_account_edit_requires_admin(client, headers, users, role):
    response = client.patch(
        f"/api/auth/users/{users['field_officer'].id}",
        headers=headers(role),
        json={"is_active": False},
    )
    assert response.status_code == 403
    assert response.json()["error"]["allowed"] == ["admin"]


def test_account_edit_requires_authentication(client, users):
    response = client.patch(
        f"/api/auth/users/{users['field_officer'].id}",
        json={"is_active": False},
    )
    assert response.status_code == 401


def test_account_edit_missing_account(client, headers):
    response = client.patch(
        "/api/auth/users/9223372036854775807",
        headers=headers(),
        json={"is_active": False},
    )
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {"username": None},
        {"role": None},
        {"is_active": None},
        {"role": "owner"},
        {"username": "invalid name"},
        {"password": PASSWORD},
    ],
)
def test_account_patch_rejects_invalid_fields(client, headers, users, payload):
    response = client.patch(
        f"/api/auth/users/{users['field_officer'].id}",
        headers=headers(),
        json=payload,
    )
    assert response.status_code == 422


def test_account_duplicate_username_normalized_and_changes_rolled_back(client, headers, users, db):
    target = users["field_officer"]
    original_username = target.username
    response = client.patch(
        f"/api/auth/users/{target.id}",
        headers=headers(),
        json={"username": users["admin"].username.upper(), "role": "admin"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "username_exists"
    assert response.json()["error"]["field"] == "username"
    db.refresh(target)
    assert target.username == original_username and target.role == "field_officer"
    response = client.post(
        "/api/auth/register",
        headers=headers(),
        json={"username": original_username.upper(), "password": PASSWORD, "role": "lab_tech"},
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"is_active": False}, "self_deactivation"),
        ({"role": "lab_tech"}, "self_demotion"),
    ],
)
def test_admin_cannot_remove_own_access_with_another_admin(client, headers, users, payload, code):
    assert (
        client.patch(
            f"/api/auth/users/{users['lab_tech'].id}",
            headers=headers(),
            json={"role": "admin"},
        ).status_code
        == 200
    )
    response = client.patch(
        f"/api/auth/users/{users['admin'].id}",
        headers=headers(),
        json=payload,
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == code
    assert client.get("/api/auth/me", headers=headers()).status_code == 200


@pytest.mark.parametrize("payload", [{"is_active": False}, {"role": "field_officer"}])
def test_last_active_admin_cannot_be_removed(client, headers, users, payload):
    response = client.patch(
        f"/api/auth/users/{users['admin'].id}",
        headers=headers(),
        json=payload,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_active_admin"
    assert client.get("/api/auth/me", headers=headers()).status_code == 200


def test_admin_can_correct_own_username(client, headers, users):
    token = headers()
    response = client.patch(
        f"/api/auth/users/{users['admin'].id}",
        headers=token,
        json={"username": "Corrected.Admin", "role": "admin", "is_active": True},
    )
    assert response.status_code == 200 and response.json()["username"] == "corrected.admin"
    assert client.get("/api/auth/me", headers=token).json()["username"] == "corrected.admin"


@pytest.mark.parametrize("change", [{"is_active": False}, {"role": "field_officer"}])
def test_concurrent_admin_access_changes_leave_one_active_admin(password_hash, monkeypatch, change):
    from apps.accounts.router import lock_account_mutations

    suffix = uuid4().hex
    # Independent request transactions need committed setup visible to both
    # connections. These unique test-only accounts are removed in finally.
    with Session(engine, expire_on_commit=False) as setup:
        admins = [
            User(
                username=f"race_admin_{index}_{suffix}",
                password_hash=password_hash,
                role="admin",
                is_active=True,
            )
            for index in range(2)
        ]
        setup.add_all(admins)
        setup.commit()
        ids = [user.id for user in admins]
        tokens = [{"Authorization": f"Bearer {create_access_token(user)}"} for user in admins]

    authorized = Barrier(2)

    def wait_before_lock(db, actor_id):
        # Both requests pass initial JWT/role checks before either mutates a user.
        authorized.wait(timeout=10)
        return lock_account_mutations(db, actor_id)

    monkeypatch.setattr("apps.accounts.router.lock_account_mutations", wait_before_lock)
    try:
        with TestClient(app, raise_server_exceptions=False) as concurrent_client:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        concurrent_client.patch,
                        f"/api/auth/users/{ids[1 - index]}",
                        headers=tokens[index],
                        json=change,
                    )
                    for index in range(2)
                ]
                responses = [future.result(timeout=20) for future in futures]
        assert sorted(response.status_code for response in responses) == [200, 401]
        with Session(engine) as check:
            assert (
                check.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(
                        User.id.in_(ids),
                        User.role == "admin",
                        User.is_active,
                    )
                )
                == 1
            )
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(User).where(User.id.in_(ids)))
            cleanup.commit()
