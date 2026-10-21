"""Distribusi Pengaturan AI oleh admin (2026-10-21): kolom
dibagikan_mode pada ai_settings + tabel target whitelist/blacklist.

Revision ID: 0010_ai_bagikan
Revises: 0009_pedagogi_kurikulum
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_ai_bagikan"
down_revision: Union[str, None] = "0009_pedagogi_kurikulum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_settings",
        sa.Column("dibagikan_mode", sa.String(20), nullable=False, server_default="tidak"),
    )
    op.create_table(
        "ai_setting_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setting_id", sa.Integer(), sa.ForeignKey("ai_settings.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("setting_id", "user_id", name="uq_ai_setting_target"),
    )


def downgrade() -> None:
    op.drop_table("ai_setting_targets")
    op.drop_column("ai_settings", "dibagikan_mode")
