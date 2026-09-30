"""Add investment risk to the profile (Phase 2: uncertainty).

Existing profiles get "medium", the default level.

Revision ID: 4a71bbf06f09
Revises: 1339a891fc0b
Create Date: 2026-09-30 15:45:33.291607

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a71bbf06f09"
down_revision: str | Sequence[str] | None = "1339a891fc0b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("financial_profiles", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "investment_risk",
                sa.Enum(
                    "low", "medium", "high", name="investmentrisk", native_enum=False, length=10
                ),
                server_default="medium",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            op.f("ck_financial_profiles_investment_risk_values"),
            "investment_risk IN ('low', 'medium', 'high')",
        )


def downgrade() -> None:
    with op.batch_alter_table("financial_profiles", schema=None) as batch_op:
        batch_op.drop_constraint(
            op.f("ck_financial_profiles_investment_risk_values"), type_="check"
        )
        batch_op.drop_column("investment_risk")
