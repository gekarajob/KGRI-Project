from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'lab_tech', 'field_officer')", name="role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint("age BETWEEN 0 AND 120", name="age_range"),
        CheckConstraint("length(trim(full_name)) > 0", name="full_name_required"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kgri_id: Mapped[str] = mapped_column(
        String(32), unique=True, server_default=text("kgri_next_id()")
    )
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    age: Mapped[int] = mapped_column(SmallInteger)
    sex: Mapped[str] = mapped_column(String(30))
    community: Mapped[str] = mapped_column(String(120))
    county: Mapped[str] = mapped_column(String(100), index=True)
    recruitment_site: Mapped[str] = mapped_column(String(120), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent: Mapped["ParticipantConsent"] = relationship(
        back_populates="participant", uselist=False
    )
    samples: Mapped[list["Sample"]] = relationship(back_populates="participant")
    phenotype_records: Mapped[list["PhenotypeRecord"]] = relationship(back_populates="participant")


class ParticipantConsent(Base):
    __tablename__ = "participant_consents"

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="RESTRICT"), primary_key=True
    )
    broad_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    broad_consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recontact_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    recontact_consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_sharing_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    data_sharing_consent_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )
    participant: Mapped[Participant] = relationship(back_populates="consent")


class Sample(Base):
    __tablename__ = "samples"
    __table_args__ = (
        CheckConstraint("sample_type IN ('dna', 'blood', 'saliva')", name="sample_type"),
        CheckConstraint(
            "status IN ('collected', 'shipped', 'received_at_lab', 'dna_extracted', "
            "'library_prepped', 'sequenced', 'qc_passed')",
            name="status",
        ),
        CheckConstraint(
            "platform IS NULL OR platform IN ('ultima_ug100', 'ont_promethion', 'pacbio', 'olink')",
            name="platform",
        ),
        CheckConstraint("mean_coverage IS NULL OR mean_coverage >= 0", name="coverage"),
        CheckConstraint(
            "platform IS DISTINCT FROM 'olink' OR "
            "(sequencing_file_path IS NULL AND mean_coverage IS NULL)",
            name="olink_metadata",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="RESTRICT"), index=True
    )
    sample_type: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(
        String(30), default="collected", server_default="collected", index=True
    )
    platform: Mapped[str | None] = mapped_column(String(30), index=True)
    batch_id: Mapped[str | None] = mapped_column(String(120))
    sequencing_file_path: Mapped[str | None] = mapped_column(Text)
    mean_coverage: Mapped[float | None] = mapped_column(Numeric(10, 2, asdecimal=False))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participant: Mapped[Participant] = relationship(back_populates="samples")


class Study(Base):
    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class PhenotypeRecord(Base):
    __tablename__ = "phenotype_records"
    __table_args__ = (
        CheckConstraint("height_cm BETWEEN 50 AND 250", name="height_range"),
        CheckConstraint("weight_kg BETWEEN 10 AND 300", name="weight_range"),
        CheckConstraint("systolic_bp BETWEEN 60 AND 250", name="systolic_range"),
        CheckConstraint("diastolic_bp BETWEEN 30 AND 150", name="diastolic_range"),
        CheckConstraint("systolic_bp > diastolic_bp", name="blood_pressure_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="RESTRICT"), index=True
    )
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id", ondelete="RESTRICT"), index=True)
    captured_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    height_cm: Mapped[float] = mapped_column(Numeric(6, 2, asdecimal=False))
    weight_kg: Mapped[float] = mapped_column(Numeric(6, 2, asdecimal=False))
    systolic_bp: Mapped[float] = mapped_column(Numeric(6, 2, asdecimal=False))
    diastolic_bp: Mapped[float] = mapped_column(Numeric(6, 2, asdecimal=False))
    malaria_history: Mapped[bool] = mapped_column(Boolean)
    livestock_contact: Mapped[bool] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participant: Mapped[Participant] = relationship(back_populates="phenotype_records")
    study: Mapped[Study] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("action IN ('CREATE', 'UPDATE', 'DELETE')", name="action"),
        CheckConstraint(
            "entity_type IN ('participant', 'sample', 'phenotype', 'user')", name="entity_type"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True
    )
    action: Mapped[str] = mapped_column(String(10))
    entity_type: Mapped[str] = mapped_column(String(20), index=True)
    entity_id: Mapped[int] = mapped_column(BigInteger)
    changed_fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    user: Mapped[User] = relationship()
