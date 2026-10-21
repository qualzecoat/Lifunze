"""Jawaban Cek Pemahaman: tabel cek_answers untuk soal sisipan [CEK].

Revision ID: 0007_cek_pemahaman
Revises: 0006_dokumen_terpadu
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_cek_pemahaman"
down_revision: Union[str, None] = "0006_dokumen_terpadu"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cek_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("siswa_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cek_index", sa.Integer(), nullable=False),
        sa.Column("tipe", sa.String(20), nullable=False),
        sa.Column("jawaban", sa.Text(), nullable=False),
        sa.Column("benar", sa.Boolean(), nullable=True),
        sa.Column("skor", sa.Float(), nullable=True),
        sa.Column("diperbarui_pada", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("material_id", "siswa_id", "cek_index", name="uq_cek_jawaban"),
    )
    op.create_index("ix_cek_answers_material_id", "cek_answers", ["material_id"])
    op.create_index("ix_cek_answers_siswa_id", "cek_answers", ["siswa_id"])


def downgrade() -> None:
    op.drop_index("ix_cek_answers_siswa_id", table_name="cek_answers")
    op.drop_index("ix_cek_answers_material_id", table_name="cek_answers")
    op.drop_table("cek_answers")
