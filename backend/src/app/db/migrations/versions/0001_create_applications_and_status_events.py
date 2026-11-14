"""Create applications and status_events tables

Revision ID: 0001
Revises:
Create Date: 2026-11-14 15:32:56.702326
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column(
            "source",
            sa.Enum("cold", "inbound", "referral", name="source", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "saved",
                "applied",
                "screen",
                "interview",
                "offer",
                "rejected",
                "ghosted",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("applied_date", sa.Date(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(company) BETWEEN 1 AND 100", name=op.f("ck_applications_company_length")),
        sa.CheckConstraint("length(role) BETWEEN 1 AND 100", name=op.f("ck_applications_role_length")),
        sa.CheckConstraint("link IS NULL OR length(link) <= 500", name=op.f("ck_applications_link_length")),
        sa.CheckConstraint(
            "notes IS NULL OR length(notes) <= 5000", name=op.f("ck_applications_notes_length")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
    )
    op.create_table(
        "status_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column(
            "from_status",
            sa.Enum(
                "saved",
                "applied",
                "screen",
                "interview",
                "offer",
                "rejected",
                "ghosted",
                name="from_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "saved",
                "applied",
                "screen",
                "interview",
                "offer",
                "rejected",
                "ghosted",
                name="to_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("note IS NULL OR length(note) <= 500", name=op.f("ck_status_events_note_length")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_status_events_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_status_events")),
    )
    with op.batch_alter_table("status_events", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_status_events_application_id_created_at"),
            ["application_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("status_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_status_events_application_id_created_at"))

    op.drop_table("status_events")
    op.drop_table("applications")
