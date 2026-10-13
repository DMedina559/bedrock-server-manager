"""Index sanitized diagnostic filters.

Revision ID: e4d63b721a90
Revises: d1a602f43b71
"""

import sqlalchemy as sa
from alembic import op

revision = "e4d63b721a90"
down_revision = "d1a602f43b71"
branch_labels = None
depends_on = None


def upgrade():
    fields = {"owner": 160, "code": 80, "outcome": 16, "operation_id": 160}
    for name, length in fields.items():
        op.add_column(
            "diagnostic_history", sa.Column(name, sa.String(length), nullable=True)
        )
        op.create_index(f"ix_diagnostic_history_{name}", "diagnostic_history", [name])
    records = sa.table(
        "diagnostic_history",
        sa.column("id", sa.String(32)),
        sa.column("record", sa.JSON),
        *(sa.column(name, sa.String(length)) for name, length in fields.items()),
    )
    connection = op.get_bind()
    for row in connection.execute(sa.select(records.c.id, records.c.record)).mappings():
        data = row["record"]
        connection.execute(
            records.update()
            .where(records.c.id == row["id"])
            .values(**{name: data.get(name) for name in fields})
        )
    op.create_index(
        "ix_diagnostic_history_instance_time",
        "diagnostic_history",
        ["instance_id", "timestamp", "id"],
    )


def downgrade():
    op.drop_index(
        "ix_diagnostic_history_instance_time", table_name="diagnostic_history"
    )
    with op.batch_alter_table("diagnostic_history") as batch:
        for name in ("owner", "code", "outcome", "operation_id"):
            batch.drop_index(f"ix_diagnostic_history_{name}")
            batch.drop_column(name)
