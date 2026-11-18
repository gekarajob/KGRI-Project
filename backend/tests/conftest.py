import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# An explicitly named test database is mandatory. Never fall back to application data.
test_url = os.environ.get("TEST_DATABASE_URL", "")
if not test_url or not (make_url(test_url).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must point to a separate database ending in _test.")
os.environ["DATABASE_URL"] = test_url
os.environ.setdefault("JWT_SECRET", "isolated-test-signing-key-at-least-32-characters")

from apps.accounts.security import create_access_token, hash_password  # noqa: E402
from config.database import engine, get_db  # noqa: E402
from config.main import app  # noqa: E402
from config.models import Participant, ParticipantConsent, Study, User  # noqa: E402

PASSWORD = "Test-portal-password-2026"


@pytest.fixture(scope="session", autouse=True)
def migrate() -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def password_hash() -> str:
    return hash_password(PASSWORD)


@pytest.fixture
def db(migrate: None) -> Iterator[Session]:
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def users(db: Session, password_hash: str) -> dict[str, User]:
    result = {}
    for role in ("admin", "lab_tech", "field_officer"):
        user = User(username=f"test_{role}", password_hash=password_hash, role=role, is_active=True)
        db.add(user)
        db.flush()
        result[role] = user
    # Release the fixture savepoint so request rollbacks cannot remove setup data.
    # The outer connection transaction still rolls everything back after the test.
    db.commit()
    return result


@pytest.fixture
def headers(users: dict[str, User]):
    def for_role(role: str = "admin") -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(users[role])}"}

    return for_role


@pytest.fixture
def client(db: Session, users: dict[str, User]) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def participant(db: Session, users: dict[str, User]) -> Participant:
    item = Participant(
        full_name="Test Participant",
        age=33,
        sex="female",
        community="Borana",
        county="Marsabit",
        recruitment_site="Moyale",
        created_by_id=users["field_officer"].id,
    )
    item.consent = ParticipantConsent(
        broad_consent=True, recontact_consent=False, data_sharing_consent=True
    )
    db.add(item)
    db.commit()
    return item


@pytest.fixture
def study(db: Session) -> Study:
    item = Study(code="TEST_BASELINE", name="Isolated test study")
    db.add(item)
    db.commit()
    return item
