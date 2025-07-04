"""change_created_at_to_bigint

Revision ID: ec1089897471
Revises: bb3bc99617a7
Create Date: 2025-07-02 17:45:23.296131

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec1089897471'
down_revision: Union[str, Sequence[str], None] = 'bb3bc99617a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Change created_at column from timestamp to bigint
    op.execute("ALTER TABLE destinations ALTER COLUMN created_at TYPE BIGINT USING EXTRACT(EPOCH FROM created_at) * 1000;")


def downgrade() -> None:
    """Downgrade schema."""
    # Change created_at column back from bigint to timestamp
    op.execute("ALTER TABLE destinations ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE USING to_timestamp(created_at / 1000);")
