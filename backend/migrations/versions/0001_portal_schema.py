"""Create the approved seven-table portal schema.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE kgri_id_seq START WITH 1")
    op.execute(
        """
        CREATE FUNCTION kgri_next_id() RETURNS text
        LANGUAGE plpgsql VOLATILE AS $$
        DECLARE
            next_id text := nextval('kgri_id_seq')::text;
        BEGIN
            RETURN 'KGRI-' || lpad(next_id, greatest(4, length(next_id)), '0');
        END;
        $$
        """
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'lab_tech', 'field_officer')", name=op.f("ck_users_role")
        ),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "participants",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "kgri_id", sa.String(32), server_default=sa.text("kgri_next_id()"), nullable=False
        ),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("sex", sa.String(30), nullable=False),
        sa.Column("community", sa.String(120), nullable=False),
        sa.Column("county", sa.String(100), nullable=False),
        sa.Column("recruitment_site", sa.String(120), nullable=False),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("age BETWEEN 0 AND 120", name=op.f("ck_participants_age_range")),
        sa.CheckConstraint(
            "length(trim(full_name)) > 0", name=op.f("ck_participants_full_name_required")
        ),
        sa.UniqueConstraint("kgri_id", name=op.f("uq_participants_kgri_id")),
    )
    op.create_index("ix_participants_full_name", "participants", ["full_name"])
    op.create_index("ix_participants_county", "participants", ["county"])
    op.create_index("ix_participants_recruitment_site", "participants", ["recruitment_site"])
    op.create_table(
        "participant_consents",
        sa.Column(
            "participant_id",
            sa.BigInteger(),
            sa.ForeignKey("participants.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("broad_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("broad_consent_recorded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "recontact_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("recontact_consent_recorded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "data_sharing_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("data_sharing_consent_recorded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "samples",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "participant_id",
            sa.BigInteger(),
            sa.ForeignKey("participants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sample_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), server_default="collected", nullable=False),
        sa.Column("platform", sa.String(30)),
        sa.Column("batch_id", sa.String(120)),
        sa.Column("sequencing_file_path", sa.Text()),
        sa.Column("mean_coverage", sa.Numeric(10, 2, asdecimal=False)),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "sample_type IN ('dna', 'blood', 'saliva')", name=op.f("ck_samples_sample_type")
        ),
        sa.CheckConstraint(
            "status IN ('collected', 'shipped', 'received_at_lab', 'dna_extracted', "
            "'library_prepped', 'sequenced', 'qc_passed')",
            name=op.f("ck_samples_status"),
        ),
        sa.CheckConstraint(
            "platform IS NULL OR platform IN ('ultima_ug100', 'ont_promethion', 'pacbio', 'olink')",
            name=op.f("ck_samples_platform"),
        ),
        sa.CheckConstraint(
            "mean_coverage IS NULL OR mean_coverage >= 0", name=op.f("ck_samples_coverage")
        ),
        sa.CheckConstraint(
            "platform IS DISTINCT FROM 'olink' OR "
            "(sequencing_file_path IS NULL AND mean_coverage IS NULL)",
            name=op.f("ck_samples_olink_metadata"),
        ),
    )
    op.create_index("ix_samples_participant_id", "samples", ["participant_id"])
    op.create_index("ix_samples_status", "samples", ["status"])
    op.create_index("ix_samples_platform", "samples", ["platform"])
    op.create_table(
        "studies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("code", name=op.f("uq_studies_code")),
    )
    op.create_table(
        "phenotype_records",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "participant_id",
            sa.BigInteger(),
            sa.ForeignKey("participants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            sa.BigInteger(),
            sa.ForeignKey("studies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "captured_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("height_cm", sa.Numeric(6, 2, asdecimal=False), nullable=False),
        sa.Column("weight_kg", sa.Numeric(6, 2, asdecimal=False), nullable=False),
        sa.Column("systolic_bp", sa.Numeric(6, 2, asdecimal=False), nullable=False),
        sa.Column("diastolic_bp", sa.Numeric(6, 2, asdecimal=False), nullable=False),
        sa.Column("malaria_history", sa.Boolean(), nullable=False),
        sa.Column("livestock_contact", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "height_cm BETWEEN 50 AND 250", name=op.f("ck_phenotype_records_height_range")
        ),
        sa.CheckConstraint(
            "weight_kg BETWEEN 10 AND 300", name=op.f("ck_phenotype_records_weight_range")
        ),
        sa.CheckConstraint(
            "systolic_bp BETWEEN 60 AND 250", name=op.f("ck_phenotype_records_systolic_range")
        ),
        sa.CheckConstraint(
            "diastolic_bp BETWEEN 30 AND 150", name=op.f("ck_phenotype_records_diastolic_range")
        ),
        sa.CheckConstraint(
            "systolic_bp > diastolic_bp", name=op.f("ck_phenotype_records_blood_pressure_order")
        ),
    )
    op.create_index("ix_phenotype_records_participant_id", "phenotype_records", ["participant_id"])
    op.create_index("ix_phenotype_records_study_id", "phenotype_records", ["study_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "action IN ('CREATE', 'UPDATE', 'DELETE')", name=op.f("ck_audit_events_action")
        ),
        sa.CheckConstraint(
            "entity_type IN ('participant', 'sample', 'phenotype')",
            name=op.f("ck_audit_events_entity_type"),
        ),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.execute(
        """
        CREATE FUNCTION prevent_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Audit events are append-only.';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation()"
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION prevent_audit_mutation()")
    op.drop_table("phenotype_records")
    op.drop_table("studies")
    op.drop_table("samples")
    op.drop_table("participant_consents")
    op.drop_table("participants")
    op.drop_table("users")
    op.execute("DROP FUNCTION kgri_next_id()")
    op.execute("DROP SEQUENCE kgri_id_seq")
