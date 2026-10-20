"""Dokumen terpadu: grup_dokumen + jenis di materials/quizzes/saved_*; tenggat di materials.

Revision ID: 0006_dokumen_terpadu
Revises: 0005_tag_pilihan
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_dokumen_terpadu"
down_revision: Union[str, None] = "0005_tag_pilihan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for tabel, jenis_default in (
        ("materials", "materi"),
        ("quizzes", "kuis"),
        ("saved_materials", "materi"),
        ("saved_quizzes", "kuis"),
    ):
        op.add_column(
            tabel,
            sa.Column("grup_dokumen", sa.String(36), nullable=True),
        )
        op.create_index(f"ix_{tabel}_grup_dokumen", tabel, ["grup_dokumen"])
        op.add_column(
            tabel,
            sa.Column(
                "jenis",
                sa.String(20),
                nullable=False,
                server_default=jenis_default,
            ),
        )
    op.add_column(
        "materials",
        sa.Column("tenggat", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("materials", "tenggat")
    for tabel in ("materials", "quizzes", "saved_materials", "saved_quizzes"):
        op.drop_column(tabel, "jenis")
        op.drop_index(f"ix_{tabel}_grup_dokumen", table_name=tabel)
        op.drop_column(tabel, "grup_dokumen")
