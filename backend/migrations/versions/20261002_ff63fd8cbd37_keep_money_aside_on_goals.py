"""Keep money aside on goals: savings and investments a goal doesn't use.

Existing goals get 0 for both, so they keep counting all cash and investments.

Revision ID: ff63fd8cbd37
Revises: 4a71bbf06f09
Create Date: 2026-10-02 10:34:19.185319

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ff63fd8cbd37"
down_revision: str | Sequence[str] | None = "4a71bbf06f09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("keep_savings", "keep_investments")


def upgrade() -> None:
    with op.batch_alter_table("goals", schema=None) as batch_op:
        for column in COLUMNS:
            batch_op.add_column(
                sa.Column(
                    column, sa.Numeric(precision=14, scale=2), server_default="0", nullable=False
                )
            )
            batch_op.create_check_constraint(op.f(f"ck_goals_{column}_gte_0"), f"{column} >= 0")


def downgrade() -> None:
    with op.batch_alter_table("goals", schema=None) as batch_op:
        for column in reversed(COLUMNS):
            batch_op.drop_constraint(op.f(f"ck_goals_{column}_gte_0"), type_="check")
            batch_op.drop_column(column)
