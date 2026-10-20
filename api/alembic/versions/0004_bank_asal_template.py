"""Penanda asal bank + tabel template kelas (paket perbaikan 2026-10-20).

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("saved_materials", sa.Column("asal_id", sa.Integer(), nullable=True))
    op.add_column("saved_quizzes", sa.Column("asal_id", sa.Integer(), nullable=True))
    op.create_table(
        "class_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pemilik_id", sa.Integer(), nullable=False),
        sa.Column("nama", sa.String(length=200), nullable=False),
        sa.Column("deskripsi", sa.Text(), nullable=True),
        sa.Column("data", JSONB_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["pemilik_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("class_templates")
    op.drop_column("saved_quizzes", "asal_id")
    op.drop_column("saved_materials", "asal_id")
