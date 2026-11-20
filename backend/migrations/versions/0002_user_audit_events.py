"""Include user account changes in the audit trail.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_audit_events_entity_type"), "audit_events", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_events_entity_type"),
        "audit_events",
        "entity_type IN ('participant', 'sample', 'phenotype', 'user')",
    )


def downgrade() -> None:
    # Existing user events intentionally prevent downgrade; never delete audit history.
    op.drop_constraint(op.f("ck_audit_events_entity_type"), "audit_events", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_events_entity_type"),
        "audit_events",
        "entity_type IN ('participant', 'sample', 'phenotype')",
    )
