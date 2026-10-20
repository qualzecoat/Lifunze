"""Kolom tag_pilihan di parser_packs (pilihan parser per tag, Mode Lanjutan).

Revision ID: 0005_tag_pilihan
Revises: 0004_bank_asal_template
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_tag_pilihan"
down_revision: Union[str, None] = "0004_bank_asal_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parser_packs",
        sa.Column("tag_pilihan", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parser_packs", "tag_pilihan")
