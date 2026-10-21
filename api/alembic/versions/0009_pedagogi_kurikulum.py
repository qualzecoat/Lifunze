"""Pedagogi & kurikulum (2026-10-21): tabel template alur mengajar,
kolom konteks kelas (semua opsional), rencana & ringkasan pertemuan.

Revision ID: 0009_pedagogi_kurikulum
Revises: 0008_audit_perbaikan
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_pedagogi_kurikulum"
down_revision: Union[str, None] = "0008_audit_perbaikan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pedagogy_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nama", sa.String(200), nullable=False),
        sa.Column("deskripsi", sa.Text(), nullable=True),
        sa.Column("dibuat_oleh", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("visibilitas", sa.String(20), nullable=False, server_default="private"),
        sa.Column("pack_id", sa.Integer(), sa.ForeignKey("parser_packs.id"), nullable=True),
        sa.Column("paket_dasar", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bagian", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Konteks kelas untuk AI — semua opsional, kelas lama tidak berubah.
    op.add_column("subjects", sa.Column("jenjang", sa.String(100), nullable=True))
    op.add_column("subjects", sa.Column("target_siswa", sa.Text(), nullable=True))
    op.add_column("subjects", sa.Column("tujuan_akhir", sa.Text(), nullable=True))
    op.add_column("subjects", sa.Column("kurikulum", sa.JSON(), nullable=True))
    # Kolom ber-FK lewat batch mode: ADD COLUMN + FK tidak didukung ALTER
    # biasa di SQLite (Postgres bisa) — batch aman di keduanya.
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.add_column(
            sa.Column("template_default_id", sa.Integer(), sa.ForeignKey("pedagogy_templates.id", name="fk_subjects_template_default"), nullable=True)
        )
        batch_op.add_column(
            sa.Column("pack_default_id", sa.Integer(), sa.ForeignKey("parser_packs.id", name="fk_subjects_pack_default"), nullable=True)
        )
    op.add_column("meetings", sa.Column("rencana", sa.JSON(), nullable=True))
    op.add_column("meetings", sa.Column("ringkasan", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("meetings", "ringkasan")
    op.drop_column("meetings", "rencana")
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.drop_column("pack_default_id")
        batch_op.drop_column("template_default_id")
    op.drop_column("subjects", "kurikulum")
    op.drop_column("subjects", "tujuan_akhir")
    op.drop_column("subjects", "target_siswa")
    op.drop_column("subjects", "jenjang")
    op.drop_table("pedagogy_templates")
