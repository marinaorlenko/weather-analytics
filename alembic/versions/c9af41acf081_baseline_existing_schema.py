"""baseline existing schema

Revision ID: c9af41acf081
Revises: 
Create Date: 2026-11-01 12:07:21.624113

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'c9af41acf081'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
