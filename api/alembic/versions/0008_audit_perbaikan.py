"""Perbaikan audit 2026-10-21 (Batch B–D): pengaturan kuis tersimpan di bank
(#9), indeks unik attempt yang sedang berjalan (#29), penanda top-up modul
cek pada paket preset (#35). Semua aditif.

Revision ID: 0008_audit_perbaikan
Revises: 0007_cek_pemahaman
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_audit_perbaikan"
down_revision: Union[str, None] = "0007_cek_pemahaman"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # #9 — pengaturan kuis ikut tersimpan di bank (jendela tidak termasuk).
    op.add_column("saved_quizzes", sa.Column("durasi_menit", sa.Integer(), nullable=True))
    op.add_column("saved_quizzes", sa.Column("acak_soal", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("saved_quizzes", sa.Column("acak_opsi", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("saved_quizzes", sa.Column("tampilkan_kunci", sa.Boolean(), nullable=False, server_default=sa.true()))
    # #35 — penanda top-up modul cek-pemahaman sudah diterapkan.
    op.add_column("parser_packs", sa.Column("topup_cek_v1", sa.Boolean(), nullable=False, server_default=sa.false()))
    # #29 — satu attempt in_progress per (kuis, siswa), ditegakkan DB.
    op.create_index(
        "uq_attempt_sedang_berjalan",
        "quiz_attempts",
        ["quiz_id", "siswa_id"],
        unique=True,
        sqlite_where=sa.text("status = 'in_progress'"),
        postgresql_where=sa.text("status = 'in_progress'"),
    )


def downgrade() -> None:
    op.drop_index("uq_attempt_sedang_berjalan", table_name="quiz_attempts")
    op.drop_column("parser_packs", "topup_cek_v1")
    op.drop_column("saved_quizzes", "tampilkan_kunci")
    op.drop_column("saved_quizzes", "acak_opsi")
    op.drop_column("saved_quizzes", "acak_soal")
    op.drop_column("saved_quizzes", "durasi_menit")
