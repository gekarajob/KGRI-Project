import csv
import io
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from apps.accounts.security import JWT_AUDIENCE, JWT_ISSUER, jwt_secret
from config.models import AuditEvent, Participant, PhenotypeRecord, Sample, User
from tests.conftest import PASSWORD


def participant_body(**changes):
    return {
        "full_name": "Demo New Participant",
        "age": 29,
        "sex": "female",
        "community": "Meru",
        "county": "Meru",
        "recruitment_site": "Meru",
        "consent": {"broad_consent": True},
        **changes,
    }


def phenotype_body(participant, study, **changes):
    return {
        "participant_id": participant.id,
        "study_id": study.id,
        "height_cm": 170,
        "weight_kg": 64,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "malaria_history": False,
        "livestock_contact": True,
        "notes": "Test only",
        **changes,
    }


def add_sample(client, headers, participant):
    response = client.post(
        "/api/samples",
        headers=headers("lab_tech"),
        json={"participant_id": participant.id, "sample_type": "blood"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_login_and_current_user(client, users):
    response = client.post(
        "/api/auth/login", json={"username": users["admin"].username, "password": PASSWORD}
    )
    assert response.status_code == 200
    data = response.json()
    assert "password_hash" not in data["user"]
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
        ).json()["role"]
        == "admin"
    )


def test_login_failure_does_not_reveal_identity(client, users):
    wrong_password = client.post(
        "/api/auth/login", json={"username": users["admin"].username, "password": "wrong"}
    )
    missing_user = client.post("/api/auth/login", json={"username": "missing", "password": "wrong"})
    assert wrong_password.status_code == missing_user.status_code == 401
    assert wrong_password.json() == missing_user.json()


def test_expired_and_tampered_tokens_denied(client, users):
    expired = jwt.encode(
        {
            "sub": str(users["admin"].id),
            "role": "admin",
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "nbf": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        jwt_secret(),
        algorithm="HS256",
    )
    for token in (expired, expired + "tampered"):
        assert (
            client.get(
                "/api/participants", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 401
        )


def test_disabled_and_changed_role_tokens_denied(client, headers, users, db):
    old_headers = headers("field_officer")
    users["field_officer"].is_active = False
    db.flush()
    assert client.get("/api/participants", headers=old_headers).status_code == 401
    users["field_officer"].is_active = True
    users["field_officer"].role = "lab_tech"
    db.flush()
    assert client.post(
        "/api/participants", headers=old_headers, json=participant_body()
    ).status_code in (401, 403)


def test_admin_only_registration_and_role_assignment(client, headers):
    body = {"username": "new_field_user", "password": PASSWORD, "role": "field_officer"}
    assert (
        client.post("/api/auth/register", headers=headers("field_officer"), json=body).status_code
        == 403
    )
    assert client.post("/api/auth/register", headers=headers(), json=body).status_code == 201
    assert client.post("/api/auth/register", headers=headers(), json=body).status_code == 409


def test_participant_create_and_detail(client, headers):
    response = client.post(
        "/api/participants", headers=headers("field_officer"), json=participant_body()
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["kgri_id"].startswith("KGRI-")
    assert item["consent"]["broad_consent"] is True
    assert item["consent"]["broad_consent_recorded_at"] is not None
    detail = client.get(f"/api/participants/{item['id']}", headers=headers()).json()
    assert detail["samples"] == [] and detail["phenotypes"] == []


def test_participant_search_by_county_and_consent_filter(client, headers, participant):
    response = client.get(
        "/api/participants", headers=headers(), params={"search": "Marsabit", "broad_consent": True}
    )
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == participant.id
    assert (
        client.get("/api/participants", headers=headers(), params={"broad_consent": False}).json()[
            "total"
        ]
        == 0
    )


def test_first_explicit_refusal_gets_timestamp(client, headers):
    item = client.post(
        "/api/participants", headers=headers(), json=participant_body(consent=None)
    ).json()
    assert item["consent"]["recontact_consent_recorded_at"] is None
    response = client.patch(
        f"/api/participants/{item['id']}/consent",
        headers=headers(),
        json={"recontact_consent": False},
    )
    assert response.status_code == 200
    assert response.json()["consent"]["recontact_consent_recorded_at"] is not None


def test_identifiers_continue_beyond_four_digits(client, headers, db):
    db.scalar(select(func.setval("kgri_id_seq", 9999, True)))
    response = client.post("/api/participants", headers=headers(), json=participant_body())
    assert response.status_code == 201 and response.json()["kgri_id"] == "KGRI-10000"


def test_participant_edit_and_consent_withdrawal(client, headers, participant):
    path = f"/api/participants/{participant.id}"
    assert (
        client.patch(path, headers=headers("field_officer"), json={"age": 34}).json()["age"] == 34
    )
    changed = client.patch(
        path + "/consent", headers=headers("field_officer"), json={"broad_consent": False}
    )
    assert changed.status_code == 200
    assert changed.json()["consent"]["broad_consent"] is False
    timestamp = changed.json()["consent"]["broad_consent_recorded_at"]
    assert timestamp
    unchanged = client.patch(
        path + "/consent", headers=headers("field_officer"), json={"broad_consent": False}
    )
    assert unchanged.json()["consent"]["broad_consent_recorded_at"] == timestamp


def test_participant_soft_delete_and_lab_denial(client, headers, participant, db):
    path = f"/api/participants/{participant.id}"
    denied = client.delete(path, headers=headers("lab_tech"))
    assert denied.status_code == 403 and "admin" in denied.json()["error"]["message"].lower()
    assert client.delete(path, headers=headers()).status_code == 204
    assert client.get(path, headers=headers()).status_code == 404
    db.refresh(participant)
    assert participant.deleted_at is not None
    assert client.get("/api/participants", headers=headers()).json()["total"] == 0


def test_participant_delete_blocked_with_active_samples(client, headers, participant):
    sample = add_sample(client, headers, participant)
    path = f"/api/participants/{participant.id}"
    assert client.delete(path, headers=headers()).status_code == 409
    assert (
        client.delete(f"/api/samples/{sample['id']}", headers=headers("lab_tech")).status_code
        == 204
    )
    assert client.delete(path, headers=headers()).status_code == 204


def test_lab_cannot_edit_participant(client, headers, participant):
    assert (
        client.patch(
            f"/api/participants/{participant.id}", headers=headers("lab_tech"), json={"age": 30}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/participants", headers=headers("lab_tech"), json=participant_body()
        ).status_code
        == 403
    )


def test_validation_errors_hide_inputs(client, headers):
    response = client.post("/api/participants", headers=headers(), json=participant_body(age=500))
    assert response.status_code == 422
    assert response.json()["error"]["field"] == "age"
    assert "input" not in response.json()["error"]
    assert (
        client.post(
            "/api/participants", headers=headers(), json=participant_body(role="admin")
        ).status_code
        == 422
    )


def test_sample_create_and_valid_three_step_chain(client, headers, participant):
    sample = add_sample(client, headers, participant)
    assert sample["status"] == "collected" and sample["kgri_id"] == participant.kgri_id
    for status in ("shipped", "received_at_lab", "dna_extracted"):
        response = client.patch(
            f"/api/samples/{sample['id']}/status",
            headers=headers("lab_tech"),
            json={"status": status},
        )
        assert response.status_code == 200 and response.json()["status"] == status


def test_sample_invalid_jump_names_current_and_allowed(client, headers, participant):
    sample = add_sample(client, headers, participant)
    response = client.patch(
        f"/api/samples/{sample['id']}/status",
        headers=headers("lab_tech"),
        json={"status": "sequenced"},
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert "collected" in error["message"] and "shipped" in error["message"]
    assert error["allowed"] == ["shipped"]


def test_sample_metadata_cannot_bypass_state_machine(client, headers, participant):
    sample = add_sample(client, headers, participant)
    assert (
        client.patch(
            f"/api/samples/{sample['id']}", headers=headers(), json={"status": "qc_passed"}
        ).status_code
        == 422
    )


def test_sample_summary_and_field_officer_delete_denied(client, headers, participant):
    sample = add_sample(client, headers, participant)
    summary = client.get("/api/samples/summary", headers=headers("field_officer")).json()
    assert summary["total"] == 1
    assert {"status": "collected", "count": 1} in summary["by_status"]
    assert {"recruitment_site": "Moyale", "count": 1} in summary["by_site"]
    assert (
        client.delete(f"/api/samples/{sample['id']}", headers=headers("field_officer")).status_code
        == 403
    )


def test_sample_sequencing_requirements_and_olink(client, headers, participant):
    sample = add_sample(client, headers, participant)
    path = f"/api/samples/{sample['id']}"
    for status in ("shipped", "received_at_lab", "dna_extracted", "library_prepped"):
        assert (
            client.patch(path + "/status", headers=headers(), json={"status": status}).status_code
            == 200
        )
    assert (
        client.patch(path + "/status", headers=headers(), json={"status": "sequenced"}).status_code
        == 422
    )
    assert (
        client.patch(
            path, headers=headers(), json={"platform": "olink", "mean_coverage": 30}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            path, headers=headers(), json={"platform": "olink", "batch_id": "DEMO"}
        ).status_code
        == 200
    )
    assert (
        client.patch(path + "/status", headers=headers(), json={"status": "sequenced"}).status_code
        == 200
    )


def test_phenotype_create_and_participant_linkage(client, headers, participant, study):
    response = client.post(
        "/api/phenotypes", headers=headers("field_officer"), json=phenotype_body(participant, study)
    )
    assert response.status_code == 201, response.text
    assert response.json()["kgri_id"] == participant.kgri_id
    detail = client.get(
        f"/api/participants/{participant.id}", headers=headers("field_officer")
    ).json()
    assert detail["phenotypes"][0]["id"] == response.json()["id"]


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"systolic_bp": 500}, "systolic_bp"),
        ({"height_cm": 20}, "height_cm"),
        ({"weight_kg": 301}, "weight_kg"),
        ({"diastolic_bp": 151}, "diastolic_bp"),
    ],
)
def test_phenotype_range_errors_name_field(client, headers, participant, study, changes, field):
    response = client.post(
        "/api/phenotypes", headers=headers(), json=phenotype_body(participant, study, **changes)
    )
    assert response.status_code == 422 and response.json()["error"]["field"] == field


def test_phenotype_blood_pressure_relationship(client, headers, participant, study):
    assert (
        client.post(
            "/api/phenotypes",
            headers=headers(),
            json=phenotype_body(participant, study, systolic_bp=80, diastolic_bp=90),
        ).status_code
        == 422
    )


def test_phenotype_decimal_precision_and_partial_bp_update(client, headers, participant, study):
    response = client.post(
        "/api/phenotypes",
        headers=headers(),
        json=phenotype_body(participant, study, systolic_bp=120.004),
    )
    assert response.status_code == 422 and response.json()["error"]["field"] == "systolic_bp"
    item = client.post(
        "/api/phenotypes",
        headers=headers(),
        json=phenotype_body(participant, study, diastolic_bp=80.02),
    ).json()
    response = client.patch(
        f"/api/phenotypes/{item['id']}", headers=headers(), json={"systolic_bp": 80.02}
    )
    assert response.status_code == 422 and response.json()["error"]["field"] == "systolic_bp"


def test_phenotype_capture_time_is_utc_in_responses_and_audit(client, headers, participant, study):
    response = client.post(
        "/api/phenotypes",
        headers=headers(),
        json=phenotype_body(participant, study, captured_at="2026-11-15T12:00:00+03:00"),
    )
    assert response.status_code == 201
    item = response.json()
    captured_at = datetime.fromisoformat(item["captured_at"])
    assert captured_at == datetime(2026, 11, 15, 9, tzinfo=UTC)
    assert captured_at.utcoffset() == timedelta(0)

    response = client.patch(
        f"/api/phenotypes/{item['id']}",
        headers=headers(),
        json={"captured_at": "2026-11-15T12:30:00+03:00"},
    )
    assert response.status_code == 200
    captured_at = datetime.fromisoformat(response.json()["captured_at"])
    assert captured_at == datetime(2026, 11, 15, 9, 30, tzinfo=UTC)
    assert captured_at.utcoffset() == timedelta(0)
    events = client.get(
        "/api/audit",
        headers=headers(),
        params={"entity_type": "phenotype"},
    ).json()["items"]
    changed = next(event for event in events if event["action"] == "UPDATE")
    assert changed["changed_fields"]["captured_at"] == {
        "old": "2026-11-15T09:00:00+00:00",
        "new": "2026-11-15T09:30:00+00:00",
    }


def test_phenotype_capture_time_requires_timezone_on_create_and_edit(
    client, headers, participant, study
):
    response = client.post(
        "/api/phenotypes",
        headers=headers(),
        json=phenotype_body(participant, study, captured_at="2026-11-15T12:00:00"),
    )
    assert response.status_code == 422 and response.json()["error"]["field"] == "captured_at"
    item = client.post(
        "/api/phenotypes",
        headers=headers(),
        json=phenotype_body(participant, study),
    ).json()
    response = client.patch(
        f"/api/phenotypes/{item['id']}",
        headers=headers(),
        json={"captured_at": "2026-11-15T12:00:00"},
    )
    assert response.status_code == 422 and response.json()["error"]["field"] == "captured_at"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_measurements_rejected(client, headers, participant, study, value):
    response = client.post(
        "/api/phenotypes",
        headers=headers(),
        json=phenotype_body(participant, study, height_cm=value),
    )
    assert response.status_code == 422


def test_phenotype_lab_access_denied(client, headers, participant, study):
    assert (
        client.post(
            "/api/phenotypes", headers=headers("lab_tech"), json=phenotype_body(participant, study)
        ).status_code
        == 403
    )
    assert client.get("/api/phenotypes", headers=headers("lab_tech")).status_code == 403
    assert (
        client.get(
            "/api/phenotypes/export", headers=headers("lab_tech"), params={"study_id": study.id}
        ).status_code
        == 403
    )
    assert (
        client.get(f"/api/participants/{participant.id}", headers=headers("lab_tech")).json()[
            "phenotypes_restricted"
        ]
        is True
    )


def test_phenotype_csv_bom_headers_site_filter_and_formula_safety(
    client, headers, participant, study
):
    created = client.post(
        "/api/phenotypes", headers=headers(), json=phenotype_body(participant, study, notes="=1+1")
    )
    assert created.status_code == 201
    response = client.get(
        "/api/phenotypes/export",
        headers=headers("field_officer"),
        params={"study_id": study.id, "site": "Moyale"},
    )
    assert response.status_code == 200 and response.content.startswith(b"\xef\xbb\xbf")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["kgri_id"] == participant.kgri_id
    assert rows[0]["notes"].startswith("'=1+1")
    assert "T" in rows[0]["captured_at"]
    empty = client.get(
        "/api/phenotypes/export",
        headers=headers(),
        params={"study_id": study.id, "site": "Nairobi"},
    )
    assert len(list(csv.DictReader(io.StringIO(empty.content.decode("utf-8-sig"))))) == 0


def test_phenotype_update_soft_delete_and_admin_permission(client, headers, participant, study, db):
    item = client.post(
        "/api/phenotypes", headers=headers(), json=phenotype_body(participant, study)
    ).json()
    path = f"/api/phenotypes/{item['id']}"
    assert (
        client.patch(path, headers=headers("field_officer"), json={"weight_kg": 70}).json()[
            "weight_kg"
        ]
        == 70
    )
    assert client.delete(path, headers=headers("field_officer")).status_code == 403
    assert client.delete(path, headers=headers()).status_code == 204
    assert client.get(path, headers=headers()).status_code == 404
    assert db.get(PhenotypeRecord, item["id"]).deleted_at is not None


def test_audit_written_with_mutation_and_admin_only(client, headers, db):
    response = client.post("/api/participants", headers=headers(), json=participant_body())
    event = db.scalar(select(AuditEvent).where(AuditEvent.entity_id == response.json()["id"]))
    assert (
        event.action == "CREATE"
        and event.changed_fields["full_name"]["new"] == "Demo New Participant"
    )
    assert "password_hash" not in str(event.changed_fields)
    assert client.get("/api/audit", headers=headers("field_officer")).status_code == 403
    data = client.get("/api/audit", headers=headers(), params={"entity_type": "participant"}).json()
    assert data["total"] == 1


def test_failed_audit_rolls_back_domain_change(client, headers, db, monkeypatch):
    def fail_audit(*args, **kwargs):
        raise SQLAlchemyError("Simulated failed audit write")

    monkeypatch.setattr("apps.participants.router.record_audit", fail_audit)
    response = client.post("/api/participants", headers=headers(), json=participant_body())
    assert response.status_code == 503
    assert db.scalar(select(func.count()).select_from(Participant)) == 0


def test_audit_rows_are_append_only(client, headers, db):
    client.post("/api/participants", headers=headers(), json=participant_body())
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(update(AuditEvent).values(action="DELETE"))


@pytest.mark.parametrize(
    "path",
    [
        "/api/participants",
        "/api/samples",
        "/api/samples/summary",
        "/api/phenotypes",
        "/api/studies",
        "/api/audit",
        "/api/auth/users",
    ],
)
def test_routes_require_authentication(client, path):
    assert client.get(path).status_code == 401


def test_seed_idempotency_and_all_seven_entities(db, monkeypatch):
    from apps.seed import seed

    for variable in ("SEED_ADMIN_PASSWORD", "SEED_LAB_PASSWORD", "SEED_FIELD_PASSWORD"):
        monkeypatch.setenv(variable, PASSWORD)
    seed(db)

    def counts():
        return tuple(
            db.scalar(select(func.count()).select_from(model))
            for model in (User, Participant, Sample, PhenotypeRecord, AuditEvent)
        )

    first = counts()
    seed(db)
    assert counts() == first
    assert first[1:4] == (50, 35, 24)
