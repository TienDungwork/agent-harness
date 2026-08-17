"""Initial schema — mirrors storage.models (create_all compatible)."""

from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = '0001_initial'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Prefer metadata create for first boot; this revision documents the baseline.
    # Fresh environments can also rely on init_db(create_all). Alembic stamp after.
    bind = op.get_bind()
    from storage.models import Base

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from storage.models import Base

    Base.metadata.drop_all(bind=bind)
